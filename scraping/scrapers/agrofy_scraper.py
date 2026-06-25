"""
Agrofy scraper — uses Playwright (headless browser) because Agrofy is a React SPA.
The Playwright service runs in a dedicated Docker container (Dockerfile.playwright).
This scraper communicates with that container via HTTP to avoid bundling browsers
into the main worker image.

If the PLAYWRIGHT_SERVICE_URL environment variable is not set, it falls back to
a direct httpx request (best-effort, may fail on JS-rendered pages).
"""
from __future__ import annotations
import logging
import os
import re
import time
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup

from scraping.scrapers.base_scraper import BaseScraper, RawProduct
from scraping.utils.anti_blocking import async_random_delay, detect_block, random_delay, BlockedError
from scraping.utils.headers import get_browser_headers

logger = logging.getLogger(__name__)

# Public search URL for agroquímicos — filterable by category
_BASE_SEARCH = "https://www.agrofy.com.ar/agroquimicos"
_CATEGORIES = [
    "fungicidas",
    "insecticidas",
    "herbicidas",
    "fertilizantes",
]

_PLAYWRIGHT_SERVICE_URL = os.environ.get("PLAYWRIGHT_SERVICE_URL", "")


class AgrofyScraper(BaseScraper):
    source = "agrofy"

    def scrape(self) -> List[RawProduct]:
        products: List[RawProduct] = []
        for category in _CATEGORIES:
            try:
                raw_products = self._scrape_category(category)
                products.extend(raw_products)
                random_delay(2.0, 5.0)
            except Exception as exc:
                logger.warning("Agrofy category=%s failed: %s", category, exc)
        logger.info("Agrofy scrape complete: %d products collected", len(products))
        return products

    def _fetch_page(self, url: str) -> str:
        # CF Browser Rendering espera a que carguen las cards del producto
        return self._fetch_html(
            url,
            wait_selector=".product-item, .andes-card, .ui-search-result",
            referer="https://www.agrofy.com.ar/",
        )

    def _scrape_category(self, category: str) -> List[RawProduct]:
        url = f"{_BASE_SEARCH}/{category}"
        html = self._fetch_page(url)
        if detect_block(html):
            raise BlockedError(f"Agrofy returned block page for {url}")
        return self._parse_listing(html, category, url)

    def _parse_listing(self, html: str, category: str, listing_url: str) -> List[RawProduct]:
        soup = BeautifulSoup(html, "html.parser")
        products: List[RawProduct] = []

        # Agrofy product cards — selector targets common card patterns
        cards = (
            soup.select(".product-item")
            or soup.select(".andes-card")
            or soup.select("[data-testid='product-card']")
            or soup.select(".ui-search-result")
        )

        for card in cards[:50]:  # cap at 50 per category
            try:
                product = self._parse_card(card, category, listing_url)
                if product:
                    products.append(product)
            except Exception as exc:
                logger.debug("Agrofy card parse error: %s", exc)

        return products

    def _parse_card(self, card, category: str, listing_url: str) -> Optional[RawProduct]:
        name_el = (
            card.select_one(".product-item__title")
            or card.select_one(".andes-card__content h2")
            or card.select_one("[class*='title']")
            or card.select_one("h2")
            or card.select_one("h3")
        )
        if not name_el:
            return None
        name = name_el.get_text(strip=True)
        if not name:
            return None

        price_el = (
            card.select_one(".andes-money-amount__fraction")
            or card.select_one("[class*='price']")
            or card.select_one(".price")
        )
        price_raw = price_el.get_text(strip=True) if price_el else None

        link_el = card.select_one("a[href]")
        product_url = ""
        if link_el:
            href = link_el.get("href", "")
            if href.startswith("http"):
                product_url = href
            else:
                product_url = f"https://www.agrofy.com.ar{href}"

        manufacturer_el = card.select_one("[class*='brand']") or card.select_one("[class*='manufacturer']")
        manufacturer = manufacturer_el.get_text(strip=True) if manufacturer_el else None

        stock_el = card.select_one("[class*='stock']") or card.select_one("[class*='disponible']")
        stock_raw = stock_el.get_text(strip=True) if stock_el else None

        return RawProduct(
            source=self.source,
            source_url=product_url or listing_url,
            name=name,
            manufacturer=manufacturer,
            product_type_raw=category.rstrip("s"),  # fungicidas -> fungicida
            price_raw=price_raw,
            stock_raw=stock_raw,
            availability_regions=["AR"],
            html_snapshot=str(card),
        )

    def _parse_price(self, price_raw: Optional[str]) -> tuple[Optional[float], Optional[str]]:
        if not price_raw:
            return None, None
        digits = re.sub(r"[^\d,.]", "", price_raw)
        digits = digits.replace(",", "")
        try:
            return float(digits), "ARS"
        except ValueError:
            return None, None
