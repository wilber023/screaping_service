from __future__ import annotations
import logging
import os
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

import httpx

from scraping.utils.headers import get_browser_headers

logger = logging.getLogger(__name__)

# Proxy opcional: set PROXY_URL=http://user:pass@host:port en .env
_PROXY_URL = os.environ.get("PROXY_URL", "")


@dataclass
class RawProduct:
    """Datos crudos del producto antes de normalizar."""
    source: str
    source_url: str
    name: str
    manufacturer: Optional[str] = None
    active_ingredient: Optional[str] = None
    product_type_raw: Optional[str] = None
    target_crops_raw: List[str] = field(default_factory=list)
    target_diseases_raw: List[str] = field(default_factory=list)
    price_raw: Optional[str] = None
    price_amount: Optional[float] = None
    price_currency: Optional[str] = None
    stock_raw: Optional[str] = None
    availability_regions: List[str] = field(default_factory=list)
    image_url: Optional[str] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None
    presentacion: Optional[str] = None
    extra: dict = field(default_factory=dict)
    scraped_at: datetime = field(default_factory=datetime.utcnow)
    html_snapshot: Optional[str] = None


class BaseScraper(ABC):
    """Base abstracta para todos los scrapers."""

    source: str = ""

    def __init__(self) -> None:
        self.logger = logging.getLogger(f"scraper.{self.source}")

    @abstractmethod
    def scrape(self) -> List[RawProduct]:
        """Extraer y retornar productos crudos."""

    def _safe_scrape(self) -> List[RawProduct]:
        try:
            return self.scrape()
        except Exception as exc:
            self.logger.error("Scrape failed source=%s: %s", self.source, exc, exc_info=True)
            return []

    def _fetch_html(self, url: str, wait_selector: Optional[str] = None, referer: str = "") -> str:
        """
        Descarga HTML con estrategia en cascada:
          1. cloudscraper  — TLS fingerprint bypass, sin headless browser
          2. CF Browser Rendering — Chromium real en la nube (usa quota)
          3. httpx directo — último recurso
        """
        # 1. cloudscraper
        html = self._fetch_cloudscraper(url, referer=referer)
        if html and len(html) > 3000 and not self._is_challenge_page(html):
            self.logger.debug("cloudscraper OK: %s (%d bytes)", url, len(html))
            return html

        # 2. CF Browser Rendering
        from scraping.utils import cf_browser
        if cf_browser.is_available():
            self.logger.debug("CF Browser: %s", url)
            return cf_browser.render_page(url, wait_selector=wait_selector)

        # 3. httpx directo
        self.logger.debug("httpx directo: %s", url)
        proxies = {"http://": _PROXY_URL, "https://": _PROXY_URL} if _PROXY_URL else {}
        with httpx.Client(
            timeout=30,
            follow_redirects=True,
            headers=get_browser_headers(referer=referer or url),
            proxies=proxies or None,
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.text

    def _fetch_cloudscraper(self, url: str, referer: str = "") -> str:
        """Intenta con cloudscraper (maneja TLS fingerprinting de Cloudflare)."""
        try:
            import cloudscraper
            headers = get_browser_headers(referer=referer or url)
            proxies = {"http": _PROXY_URL, "https": _PROXY_URL} if _PROXY_URL else {}
            scraper = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "mobile": False}
            )
            scraper.headers.update(headers)
            kwargs = {"timeout": 30, "allow_redirects": True}
            if proxies:
                kwargs["proxies"] = proxies
            # Delay humano antes del request
            time.sleep(random.uniform(1.5, 3.5))
            resp = scraper.get(url, **kwargs)
            if resp.status_code == 200:
                return resp.text
            self.logger.debug("cloudscraper HTTP %s: %s", resp.status_code, url)
            return ""
        except ImportError:
            self.logger.debug("cloudscraper no instalado")
            return ""
        except Exception as exc:
            self.logger.debug("cloudscraper failed url=%s: %s", url, exc)
            return ""

    def _is_challenge_page(self, html: str) -> bool:
        lower = html.lower()
        return any(s in lower for s in [
            "just a moment", "challenge validation", "checking your browser",
            "suspicious-traffic", "prueba que eres humano",
            "captcha", "robot check",
        ])
