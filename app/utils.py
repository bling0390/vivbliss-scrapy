import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def compute_fingerprint(payload: Dict[str, Any], exclude: Iterable[str] | None = None) -> str:
    exclude = set(exclude or [])
    filtered = {k: v for k, v in payload.items() if k not in exclude}
    encoded = json.dumps(filtered, sort_keys=True, default=str, ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_dedupe_key(product_key: str, version: int, event_type: str) -> str:
    raw = f"{product_key}:{version}:{event_type}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
