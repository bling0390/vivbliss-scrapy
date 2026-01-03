import logging
import os
import subprocess
from pathlib import Path
from typing import List

from bson import ObjectId
from pymongo import ReturnDocument

from app.celery_app import celery_app
from app.config import settings
from app.mongo import (
    ensure_indexes,
    outbox_events,
    send_receipts,
)
from app.senders import send_with_strategy
from app.utils import now_utc

logger = logging.getLogger(__name__)


def _ensure_dirs() -> None:
    Path(settings.data_dir, "logs").mkdir(parents=True, exist_ok=True)
    Path(settings.data_dir, "state").mkdir(parents=True, exist_ok=True)


@celery_app.task(name="app.tasks.crawl_site")
def crawl_site(force_full: bool | None = None) -> None:
    """
    Trigger scrapy crawl via subprocess. First run is full, later runs incremental.
    """
    _ensure_dirs()
    state_file = Path(settings.data_dir, "state", "crawl_state.txt")
    mode = "incremental"
    if force_full or not state_file.exists():
        mode = "full"
    env = os.environ.copy()
    env["CRAWL_MODE"] = mode
    log_args: List[str] = []
    if settings.crawl_log:
        log_args = ["-s", f"LOG_FILE={settings.crawl_log}"]
    cmd = ["scrapy", "crawl", settings.crawl_spider, *log_args]
    logger.info("Starting crawl: mode=%s cmd=%s", mode, " ".join(cmd))
    subprocess.run(cmd, check=True, env=env, cwd=str(Path(__file__).resolve().parent.parent))
    state_file.write_text(now_utc().isoformat())


@celery_app.task(name="app.tasks.dispatch_outbox")
def dispatch_outbox(batch_size: int = 20) -> int:
    ensure_indexes()
    pending = list(
        outbox_events()
        .find({"status": "pending"})
        .sort("created_at")
        .limit(batch_size)
    )
    for event in pending:
        send_event.delay(str(event["_id"]))
    return len(pending)


@celery_app.task(name="app.tasks.send_event")
def send_event(event_id: str) -> str:
    ensure_indexes()
    event = outbox_events().find_one_and_update(
        {"_id": ObjectId(event_id), "status": "pending"},
        {
            "$set": {"status": "processing", "updated_at": now_utc()},
            "$inc": {"try_count": 1},
        },
        return_document=ReturnDocument.AFTER,
    )
    if not event:
        return "skipped"

    dedupe_key = event["dedupe_key"]
    receipt = send_receipts().find_one({"_id": dedupe_key})
    if receipt:
        outbox_events().update_one(
            {"_id": event["_id"]},
            {"$set": {"status": "sent", "updated_at": now_utc()}},
        )
        return "duplicate-suppressed"

    product = event.get("payload", {}).get("product") or {}
    change = event.get("payload", {}).get("change") or {}
    try:
        message_ids, strategy = send_with_strategy(
            settings.message_strategy, product=product, change=change
        )
        send_receipts().insert_one(
            {
                "_id": dedupe_key,
                "target_chat": settings.telegram_target_chat,
                "message_ids": list(message_ids),
                "sent_at": now_utc(),
            }
        )
        outbox_events().update_one(
            {"_id": event["_id"]},
            {
                "$set": {
                    "status": "sent",
                    "last_error": None,
                    "updated_at": now_utc(),
                    "strategy_used": strategy,
                }
            },
        )
        return "sent"
    except Exception as exc:  # pragma: no cover - skeletal error handling
        logger.exception("Failed to send event %s", event_id)
        outbox_events().update_one(
            {"_id": event["_id"]},
            {
                "$set": {
                    "status": "pending",
                    "last_error": str(exc),
                    "updated_at": now_utc(),
                }
            },
        )
        return "failed"
