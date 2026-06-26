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
    "just a moment",
    "cf-browser-verification",
    "challenge-form",
    "checking your browser",
    "suspicious-traffic",
    "enter the characters",
    "prueba que eres humano",
    "challenge validation",
]

_BLOCK_INDICATORS = [
    "403 forbidden",
    "503 service unavailable",
    "your ip has been blocked",
    "ip address blocked",
    "access to this resource",
]


def detect_block(html: str) -> bool:
    lower = html.lower()
    return any(s in lower for s in _CAPTCHA_INDICATORS + _BLOCK_INDICATORS)


def detect_captcha(html: str) -> bool:
    lower = html.lower()
    return any(s in lower for s in _CAPTCHA_INDICATORS)


def random_delay(min_seconds: float = 3.0, max_seconds: float = 7.0) -> None:
    """Delay con variación humana: pausa corta + larga para simular lectura."""
    base = random.uniform(min_seconds, max_seconds)
    # Ocasionalmente una pausa más larga (simula distracción)
    if random.random() < 0.15:
        base += random.uniform(3, 8)
    time.sleep(base)


async def async_random_delay(min_seconds: float = 3.0, max_seconds: float = 7.0) -> None:
    base = random.uniform(min_seconds, max_seconds)
    if random.random() < 0.15:
        base += random.uniform(3, 8)
    await asyncio.sleep(base)


def scraper_retry(func: Callable) -> Callable:
    """3 intentos con backoff exponencial, log antes de cada reintento."""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        retry=retry_if_exception_type((Exception,)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )(func)


def random_scroll_delay() -> None:
    """Simula tiempo de scroll y lectura de página."""
    time.sleep(random.uniform(1.5, 3.5))


class BlockedError(Exception):
    """Se lanza cuando el scraper detecta bloqueo o CAPTCHA."""
