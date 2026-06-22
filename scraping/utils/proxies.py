from __future__ import annotations
import random
import logging
from typing import Optional, Dict

from scraping.config import settings

logger = logging.getLogger(__name__)

_proxy_list: list[str] = []
_failed_proxies: set[str] = set()


def _load_proxies() -> list[str]:
    global _proxy_list
    if not _proxy_list:
        _proxy_list = settings.get_proxy_list()
    return _proxy_list


def get_random_proxy() -> Optional[Dict[str, str]]:
    proxies = _load_proxies()
    available = [p for p in proxies if p not in _failed_proxies]
    if not available:
        if _failed_proxies:
            _failed_proxies.clear()
            available = proxies
        if not available:
            return None
    chosen = random.choice(available)
    return {"http://": chosen, "https://": chosen}


def mark_proxy_failed(proxy_url: str) -> None:
    _failed_proxies.add(proxy_url)
    logger.warning("Proxy marked as failed: %s", proxy_url)


def get_httpx_proxy() -> Optional[str]:
    proxies = _load_proxies()
    available = [p for p in proxies if p not in _failed_proxies]
    if not available:
        return None
    return random.choice(available)
