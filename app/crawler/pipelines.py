import logging
from typing import Any, Dict, List

from pymongo.errors import DuplicateKeyError

from app.mongo import ensure_indexes, outbox_events, product_media, products
from app.utils import build_dedupe_key, compute_fingerprint, now_utc

logger = logging.getLogger(__name__)


class MongoPipeline:
    def open_spider(self, spider):
        ensure_indexes()
        logger.info("MongoPipeline initialized for spider=%s", spider.name)

    def process_item(self, item, spider):
        product_key = item["product_key"]
        now = now_utc()

        product_doc: Dict[str, Any] = {
            "_id": product_key,
            "product_key": product_key,
            "url": item.get("url"),
            "title": item.get("title"),
            "price": item.get("price"),
            "raw": item.get("raw"),
        }
        media_items: List[Dict[str, Any]] = item.get("media") or []
        fingerprint_payload = dict(product_doc)
        fingerprint_payload["media"] = [
            {
                "media_type": media.get("media_type"),
                "source_url": media.get("source_url"),
            }
            for media in media_items
        ]
        fingerprint = compute_fingerprint(fingerprint_payload, exclude=["raw"])

        existing = products().find_one({"_id": product_key})
        version = 1
        event_type = "product_created"
        change: Dict[str, Any] = {"changed_fields": [], "previous_version": None}

        if existing:
            if existing.get("fingerprint") == fingerprint:
                version = existing.get("version", 1)
                event_type = None
            else:
                version = existing.get("version", 1) + 1
                change["previous_version"] = existing.get("version")
                change["changed_fields"] = [
                    field
                    for field in ["title", "price", "url"]
                    if product_doc.get(field) != existing.get(field)
                ]
                event_type = "product_updated"

        product_doc.update(
            {
                "fingerprint": fingerprint,
                "version": version,
                "updated_at": now,
            }
        )
        if not existing:
            product_doc["created_at"] = now
        else:
            product_doc["created_at"] = existing.get("created_at", now)

        products().update_one(
            {"_id": product_key},
            {"$set": product_doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )

        if media_items:
            docs = []
            for media in media_items:
                docs.append(
                    {
                        "product_key": product_key,
                        "version": version,
                        "media_type": media.get("media_type"),
                        "source_url": media.get("source_url"),
                        "local_path": media.get("local_path"),
                        "created_at": now,
                    }
                )
            try:
                product_media().insert_many(docs, ordered=False)
            except DuplicateKeyError:
                logger.debug("Duplicate media ignored for product %s", product_key)

        if event_type:
            dedupe_key = build_dedupe_key(product_key, version, event_type)
            payload = {
                "product": {
                    "product_key": product_key,
                    "url": product_doc.get("url"),
                    "title": product_doc.get("title"),
                    "price": product_doc.get("price"),
                    "version": version,
                },
                "change": change,
            }
            try:
                outbox_events().insert_one(
                    {
                        "dedupe_key": dedupe_key,
                        "product_key": product_key,
                        "version": version,
                        "event_type": event_type,
                        "payload": payload,
                        "status": "pending",
                        "try_count": 0,
                        "last_error": None,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
            except DuplicateKeyError:
                logger.debug("Outbox duplicate suppressed for %s", dedupe_key)

        return item
