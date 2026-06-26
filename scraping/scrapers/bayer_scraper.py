"""
Bayer CropScience scraper — targets Bayer México's public product catalog.
Respects robots.txt: targets only the /productos/ public section.
"""
from __future__ import annotations
import logging
import re
from typing import List, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from scraping.scrapers.base_scraper import BaseScraper, RawProduct
from scraping.utils.anti_blocking import detect_block, random_delay, BlockedError
from scraping.utils.headers import get_browser_headers

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.cropscience.bayer.mx"
_CATALOG_URL = f"{_BASE_URL}/productos"

_CROP_KEYWORDS = ["calabaza", "frijol", "mora", "maíz", "maiz", "papa", "fresa", "tomate"]

_TYPE_KEYWORDS = {
    "fungicida": ["fungicida", "fungicide"],
    "insecticida": ["insecticida", "insecticide"],
    "herbicida": ["herbicida", "herbicide"],
    "fertilizante": ["fertilizante", "nutricion"],
}


class BayerScraper(BaseScraper):
    source = "bayer"

    def scrape(self) -> List[RawProduct]:
        products: List[RawProduct] = []
        product_urls = self._get_product_urls()
        logger.info("Bayer: found %d product URLs", len(product_urls))

        for url in product_urls[:80]:
            try:
                product = self._scrape_product_page(url)
                if product:
                    products.append(product)
                random_delay(2.0, 4.5)
            except Exception as exc:
                logger.warning("Bayer product page failed url=%s: %s", url, exc)

        logger.info("Bayer scrape complete: %d products", len(products))
        return products

    def _get_product_urls(self) -> List[str]:
        html = self._fetch_html(
            _CATALOG_URL,
            referer=_BASE_URL,
            wait_selector="main, article, .product-card, [class*='product'], .catalog",
        )
        if detect_block(html):
            raise BlockedError("Bayer catalog blocked")

        soup = BeautifulSoup(html, "html.parser")
        urls: List[str] = []
        for link in soup.select("a[href]"):
            href = link.get("href", "")
            if "/producto" in href.lower() or "/product" in href.lower():
                full = urljoin(_BASE_URL, href)
                if full not in urls and _BASE_URL in full:
                    urls.append(full)
        for card in soup.select(".product-card, .card-product, [class*='product-item']"):
            link = card.select_one("a[href]")
            if link:
                full = urljoin(_BASE_URL, link.get("href", ""))
                if full not in urls and _BASE_URL in full:
                    urls.append(full)
        return urls

    def _scrape_product_page(self, url: str) -> Optional[RawProduct]:
        html = self._fetch_html(url, referer=_CATALOG_URL)
        if detect_block(html):
            raise BlockedError(f"Bayer blocked: {url}")
        soup = BeautifulSoup(html, "html.parser")
        return self._parse_page(soup, url, html)

    def _parse_page(self, soup: BeautifulSoup, url: str, html: str) -> Optional[RawProduct]:
        name_el = (
            soup.select_one("h1.product-name")
            or soup.select_one("h1[class*='name']")
            or soup.select_one(".product-header h1")
            or soup.select_one("h1")
        )
        if not name_el:
            return None
        name = name_el.get_text(strip=True)
        if not name:
            return None

        full_text = soup.get_text(separator=" ")
        active_ingredient = self._extract_field(full_text, [
            "ingrediente activo", "active ingredient", "i.a.", "principio activo"
        ])
        product_type_raw = self._infer_type(full_text)
        target_crops = [c for c in _CROP_KEYWORDS if c in full_text.lower()]
        target_diseases = self._extract_diseases(soup)

        img_el = (
            soup.select_one("img.product-image")
            or soup.select_one("[class*='product-img'] img")
            or soup.select_one("img[itemprop='image']")
            or soup.select_one(".product-header img")
        )
        image_url = img_el.get("src") or img_el.get("data-src") if img_el else None

        return RawProduct(
            source=self.source,
            source_url=url,
            name=name,
            manufacturer="Bayer",
            active_ingredient=active_ingredient,
            product_type_raw=product_type_raw,
            target_crops_raw=target_crops,
            target_diseases_raw=target_diseases,
            image_url=image_url,
            availability_regions=["MX"],
            html_snapshot=html[:50000],
        )

    def _extract_field(self, text: str, labels: List[str]) -> Optional[str]:
        lower = text.lower()
        for label in labels:
            pattern = rf"{re.escape(label)}\s*[:：]\s*([^\n\r.;,]{{1,200}})"
            match = re.search(pattern, lower, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _infer_type(self, text: str) -> str:
        lower = text.lower()
        for ptype, kws in _TYPE_KEYWORDS.items():
            for kw in kws:
                if kw in lower:
                    return ptype
        return "otro"

    def _extract_diseases(self, soup: BeautifulSoup) -> List[str]:
        section = soup.select_one(
            "[class*='enfermedades'], [class*='disease'], [class*='control'], [class*='plagas']"
        )
        if not section:
            return []
        return list(set(
            el.get_text(strip=True)
            for el in section.select("li, td")
            if el.get_text(strip=True)
        ))[:20]
