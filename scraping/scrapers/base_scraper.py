from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

import httpx

from scraping.utils.headers import get_browser_headers

logger = logging.getLogger(__name__)


@dataclass
class RawProduct:
    """Raw product data as extracted from a source, before normalization."""
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
    extra: dict = field(default_factory=dict)
    scraped_at: datetime = field(default_factory=datetime.utcnow)
    html_snapshot: Optional[str] = None


class BaseScraper(ABC):
    """Abstract base for all product scrapers."""

    source: str = ""

    def __init__(self) -> None:
        self.logger = logging.getLogger(f"scraper.{self.source}")

    @abstractmethod
    def scrape(self) -> List[RawProduct]:
        """Fetch and return raw products."""

    def _safe_scrape(self) -> List[RawProduct]:
        try:
            return self.scrape()
        except Exception as exc:
            self.logger.error("Scrape failed for source=%s: %s", self.source, exc, exc_info=True)
            return []

    def _fetch_html(self, url: str, wait_selector: Optional[str] = None, referer: str = "") -> str:
        """
        Descarga HTML de una URL.
        - Si Cloudflare Browser Rendering está configurado → usa Chromium real (evita 403)
        - Si no → httpx directo con headers de navegador
        """
        from scraping.utils import cf_browser

        if cf_browser.is_available():
            self.logger.debug("CF Browser: %s", url)
            return cf_browser.render_page(url, wait_selector=wait_selector)

        self.logger.debug("httpx directo: %s", url)
        with httpx.Client(
            timeout=30,
            follow_redirects=True,
            headers=get_browser_headers(referer=referer or url),
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.text