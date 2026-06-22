from __future__ import annotations
import json
import logging
from typing import Any, Optional

import redis as redis_lib

from scraping.config import settings

logger = logging.getLogger(__name__)

redis_client = redis_lib.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry_on_timeout=True,
)


def get_redis() -> redis_lib.Redis:
    return redis_client


def cache_get(key: str) -> Optional[Any]:
    try:
        raw = redis_client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.warning("Redis cache_get failed for key=%s: %s", key, exc)
        return None


def cache_set(key: str, value: Any, ttl_seconds: int = 3600) -> bool:
    try:
        redis_client.setex(key, ttl_seconds, json.dumps(value, default=str))
        return True
    except Exception as exc:
        logger.warning("Redis cache_set failed for key=%s: %s", key, exc)
        return False


def cache_delete(key: str) -> None:
    try:
        redis_client.delete(key)
    except Exception as exc:
        logger.warning("Redis cache_delete failed for key=%s: %s", key, exc)


def cache_delete_pattern(pattern: str) -> None:
    try:
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)
    except Exception as exc:
        logger.warning("Redis cache_delete_pattern failed for pattern=%s: %s", pattern, exc)
