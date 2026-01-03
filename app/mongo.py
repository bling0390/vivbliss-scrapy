from functools import lru_cache

from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from app.config import settings


@lru_cache(maxsize=1)
def get_client() -> MongoClient:
    return MongoClient(settings.mongo_uri)


def get_db() -> Database:
    return get_client()[settings.mongo_db]


def products() -> Collection:
    return get_db()["products"]


def product_media() -> Collection:
    return get_db()["product_media"]


def outbox_events() -> Collection:
    return get_db()["outbox_events"]


def send_receipts() -> Collection:
    return get_db()["send_receipts"]


def ensure_indexes() -> None:
    product_media().create_index(
        [
            ("product_key", ASCENDING),
            ("version", ASCENDING),
            ("media_type", ASCENDING),
            ("source_url", ASCENDING),
        ],
        unique=True,
        name="uniq_media",
    )
    outbox_events().create_index(
        [("dedupe_key", ASCENDING)],
        unique=True,
        name="uniq_outbox",
    )
    outbox_events().create_index(
        [("status", ASCENDING), ("created_at", ASCENDING)],
        name="status_created_idx",
    )
    send_receipts().create_index(
        [("_id", ASCENDING)],
        unique=True,
        name="uniq_receipt",
    )

