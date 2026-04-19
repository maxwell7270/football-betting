from datetime import datetime, timedelta
from typing import Optional

_CACHE: dict[str, tuple[datetime, dict]] = {}


def build_cache_key(source: str, fixture_id: str, market: str) -> str:
    return f"{source}:{fixture_id}:{market}"


def get_cached(key: str, ttl_minutes: int) -> Optional[dict]:
    item = _CACHE.get(key)
    if not item:
        return None

    cached_at, payload = item
    if datetime.utcnow() - cached_at > timedelta(minutes=ttl_minutes):
        return None

    return payload


def set_cached(key: str, payload: dict) -> None:
    _CACHE[key] = (datetime.utcnow(), payload)