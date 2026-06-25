from __future__ import annotations
import asyncio
import logging
import random
import time
from typing import Callable, TypeVar

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

_CAPTCHA_INDICATORS = [
    "captcha",
    "robot",
    "human verification",
    "access denied",
    "please verify",
    "verificación",
    "bot detection",
    "rate limit",
    "too many requests",
    "just a moment",           # Cloudflare IUAM challenge title
    "cf-browser-verification", # Cloudflare challenge div id
    "challenge-form",          # Cloudflare challenge form
    "checking your browser",   # Cloudflare challenge text
]


def detect_block(html: str) -> bool:
    lower = html.lower()
    return any(indicator in lower for indicator in _CAPTCHA_INDICATORS)


def random_delay(min_seconds: float = 1.0, max_seconds: float = 4.0) -> None:
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)


async def async_random_delay(min_seconds: float = 1.0, max_seconds: float = 4.0) -> None:
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)


def scraper_retry(func: Callable) -> Callable:
    """Decorator: 3 attempts with exponential backoff, logs before each sleep."""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type((Exception,)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )(func)


class BlockedError(Exception):
    """Raised when the scraper detects a block or CAPTCHA page."""
