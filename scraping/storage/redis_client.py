from __future__ import annotations
import json
import logging
from typing import Any, Optional

import redis as redis_lib

from scraping.config import settings

logger = logging.getLogger(__name__)

# If REDIS_URL is empty, caching is disabled entirely (graceful no-op)
redis_client: Optional[redis_lib.Redis] = None
if settings.REDIS_URL:
    try:
        redis_client = redis_lib.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
            retry_on_timeout=False,
        )
    except Exception as exc:
        logger.warning("Redis init failed, caching disabled: %s", exc)


def get_redis() -> Optional[redis_lib.Redis]:
    return redis_client


def cache_get(key: str) -> Optional[Any]:
    if redis_client is None:
        return None
    try:
        raw = redis_client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.debug("Redis cache_get failed for key=%s: %s", key, exc)
        return None


def cache_set(key: str, value: Any, ttl_seconds: int = 3600) -> bool:
    if redis_client is None:
        return False
    try:
        redis_client.setex(key, ttl_seconds, json.dumps(value, default=str))
        return True
    except Exception as exc:
        logger.debug("Redis cache_set failed for key=%s: %s", key, exc)
        return False


def cache_delete(key: str) -> None:
    if redis_client is None:
        return
    try:
        redis_client.delete(key)
    except Exception as exc:
        logger.debug("Redis cache_delete failed for key=%s: %s", key, exc)


def cache_delete_pattern(pattern: str) -> None:
    if redis_client is None:
        return
    try:
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)
    except Exception as exc:
        logger.debug("Redis cache_delete_pattern failed for pattern=%s: %s", pattern, exc)