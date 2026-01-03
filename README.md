# Vivbliss Scrapy + Celery + Pyrogram Skeleton

This is a minimal crawl-and-send pipeline using Scrapy for collection, MongoDB for storage, Redis + Celery for scheduling, and Pyrogram for Telegram delivery.

## Features
- Daily 00:00 `crawl_site` (first run full, afterwards incremental by fingerprint/version).
- Incremental updates: `fingerprint` change bumps `version`; outbox dedupe key = `sha256(product_key:version:event_type)`.
- Outbox dispatch every minute; idempotent send guarded by `send_receipts`.
- Configurable message strategy (`S1` media group, `S2` text-only, `S3` diff + new media).
- Dockerized stack: redis, mongo, worker, beat, optional manual crawler; mounts `./data:/data` for logs/media/state.

## Quickstart
1) Copy env template and fill Telegram/Mongo/Redis settings:
   ```bash
   cp .env.example .env
   # edit .env to set TG_API_ID, TG_API_HASH, TG_BOT_TOKEN or TG_SESSION_STRING, TG_TARGET_CHAT, etc.
   ```
2) Build & start infrastructure + Celery services:
   ```bash
   docker compose up -d --build redis mongo worker beat
   ```
3) (Optional) Tail worker logs:
   ```bash
   docker compose logs -f worker
   ```

## Manual operations
- Trigger one crawl now (uses `CRAWL_MODE=full` on first run, otherwise incremental):
  ```bash
  docker compose run --rm crawler
  # or via Celery:
  docker compose run --rm worker celery -A app.tasks call app.tasks.crawl_site
  ```
- Manually dispatch pending outbox events:
  ```bash
  docker compose run --rm worker celery -A app.tasks call app.tasks.dispatch_outbox
  ```

## Collections
- `products`: `_id=product_key, fingerprint, version, url, title, price, created_at, updated_at, raw`
- `product_media`: `product_key, version, media_type, source_url, local_path, created_at`
- `outbox_events`: `dedupe_key UNIQUE, product_key, version, event_type, payload, status, try_count, last_error, timestamps`
- `send_receipts`: `_id=dedupe_key UNIQUE, target_chat, message_ids, sent_at`

## Status & debugging
- Inspect outbox events:
  ```bash
  docker compose exec mongo mongosh --eval 'db.outbox_events.find({}, {dedupe_key:1,status:1,product_key:1,version:1}).pretty()'
  ```
- Inspect send receipts:
  ```bash
  docker compose exec mongo mongosh --eval 'db.send_receipts.find({}, {message_ids:1,target_chat:1}).pretty()'
  ```
- Scrapy log file (inside mounted volume): `/data/logs/scrapy.log`

## Scrapy spider
- Edit `app/crawler/spiders/product_spider.py` to add real selectors and start URLs.
- Item fields: `product_key, url, title, price, media(list of {media_type, source_url, local_path}), raw`.

## Notes
- Pyrogram config is fully environment-driven (`TG_API_ID`, `TG_API_HASH`, `TG_SESSION_STRING` *or* `TG_BOT_TOKEN`, `TG_TARGET_CHAT`).
- Outbox events are claimed atomically (`status: pending -> processing`); send is skipped when a matching receipt exists, then event is marked `sent`.
