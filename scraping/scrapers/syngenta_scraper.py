"""
Syngenta scraper — targets Syngenta México's public product catalog.
Uses httpx + BeautifulSoup to parse static HTML product pages.
Respects robots.txt: targets only the public /productos/ catalog section.
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

_BASE_URL = "https://www.syngenta.com.mx"
_CATALOG_URL = f"{_BASE_URL}/productos"

_PRODUCT_TYPE_KEYWORDS = {
    "fungicida": ["fungicida", "fungicide"],
    "insecticida": ["insecticida", "insecticide"],
    "herbicida": ["herbicida", "herbicide"],
    "fertilizante": ["fertilizante", "nutricion", "fertilizer"],
}

_CROP_KEYWORDS = [
    "calabaza", "frijol", "manzana", "mora", "cereza", "maíz", "maiz",
    "durazno", "uva", "naranja", "pimienta", "papa", "frambuesa",
    "soja", "fresa", "tomate", "trigo", "arroz", "sorgo",
]


class SyngentaScraper(BaseScraper):
    source = "syngenta"

    def __init__(self) -> None:
        super().__init__()
        self._client = httpx.Client(
            timeout=30,
            follow_redirects=True,
            headers=get_browser_headers(referer=_BASE_URL),
        )

    def scrape(self) -> List[RawProduct]:
        products: List[RawProduct] = []
        try:
            product_urls = self._get_product_urls()
            logger.info("Syngenta: found %d product URLs", len(product_urls))

            for url in product_urls[:80]:  # respect rate limit
                try:
                    product = self._scrape_product_page(url)
                    if product:
                        products.append(product)
                    random_delay(2.0, 4.0)
                except Exception as exc:
                    logger.warning("Syngenta product page failed url=%s: %s", url, exc)
        finally:
            self._client.close()

        logger.info("Syngenta scrape complete: %d products", len(products))
        return products

    def _get_product_urls(self) -> List[str]:
        resp = self._client.get(_CATALOG_URL)
        resp.raise_for_status()
        html = resp.text

        if detect_block(html):
            raise BlockedError("Syngenta catalog page is blocked")

        soup = BeautifulSoup(html, "html.parser")
        urls: List[str] = []

        for link in soup.select("a[href]"):
            href = link.get("href", "")
            if "/producto" in href or "/product" in href:
                full_url = urljoin(_BASE_URL, href)
                if full_url not in urls:
                    urls.append(full_url)

        return urls

    def _scrape_product_page(self, url: str) -> Optional[RawProduct]:
        resp = self._client.get(url, headers=get_browser_headers(referer=_CATALOG_URL))
        resp.raise_for_status()
        html = resp.text

        if detect_block(html):
            raise BlockedError(f"Syngenta product page blocked: {url}")

        soup = BeautifulSoup(html, "html.parser")
        return self._parse_product_page(soup, url, html)

    def _parse_product_page(self, soup: BeautifulSoup, url: str, html: str) -> Optional[RawProduct]:
        # Product name
        name_el = (
            soup.select_one("h1.product-title")
            or soup.select_one("h1[class*='product']")
            or soup.select_one("h1[class*='titulo']")
            or soup.select_one(".product-name h1")
            or soup.select_one("h1")
        )
        if not name_el:
            return None
        name = name_el.get_text(strip=True)
        if not name:
            return None

        # Active ingredient
        active_ingredient = self._extract_field(soup, [
            "ingrediente activo", "active ingredient", "principio activo", "i.a."
        ])

        # Product type from page content
        product_type_raw = self._extract_type(soup)

        # Target crops
        target_crops = self._extract_crops(soup)

        # Target diseases
        target_diseases = self._extract_diseases(soup)

        return RawProduct(
            source=self.source,
            source_url=url,
            name=name,
            manufacturer="Syngenta",
            active_ingredient=active_ingredient,
            product_type_raw=product_type_raw,
            target_crops_raw=target_crops,
            target_diseases_raw=target_diseases,
            availability_regions=["MX"],
            html_snapshot=html[:50000],
        )

    def _extract_field(self, soup: BeautifulSoup, labels: List[str]) -> Optional[str]:
        text = soup.get_text(separator=" ").lower()
        for label in labels:
            pattern = rf"{re.escape(label)}\s*[:：]\s*([^\n\r.;,]+)"
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:200]
        return None

    def _extract_type(self, soup: BeautifulSoup) -> str:
        text = soup.get_text().lower()
        for ptype, keywords in _PRODUCT_TYPE_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    return ptype
        return "otro"

    def _extract_crops(self, soup: BeautifulSoup) -> List[str]:
        text = soup.get_text().lower()
        return [crop for crop in _CROP_KEYWORDS if crop in text]

    def _extract_diseases(self, soup: BeautifulSoup) -> List[str]:
        disease_section = soup.select_one("[class*='enfermedades'], [class*='disease'], [class*='plagas']")
        if not disease_section:
            return []
        items = disease_section.select("li, td, span")
        diseases = [el.get_text(strip=True) for el in items if el.get_text(strip=True)]
        return list(set(diseases))[:20]
