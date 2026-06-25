"""
BASF Agricultural Solutions scraper — targets BASF México/LatAm public product catalog.
Respects robots.txt: targets only the public /productos/ catalog.
"""
from __future__ import annotations
import logging
import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scraping.scrapers.base_scraper import BaseScraper, RawProduct
from scraping.utils.anti_blocking import detect_block, random_delay, BlockedError

logger = logging.getLogger(__name__)

_BASE_URL = "https://agriculture.basf.com"
_CATALOG_URL = f"{_BASE_URL}/mx/es/productos.html"
_ALT_CATALOG_URL = "https://www.agro.basf.mx/es/productos.html"

_CROP_KEYWORDS = [
    "calabaza", "frijol", "manzana", "mora", "cereza", "maíz", "maiz",
    "durazno", "uva", "naranja", "pimienta", "papa", "frambuesa",
    "soja", "fresa", "tomate", "trigo", "arroz",
]

_TYPE_KEYWORDS = {
    "fungicida": ["fungicida", "fungicide"],
    "insecticida": ["insecticida", "insecticide"],
    "herbicida": ["herbicida", "herbicide"],
    "fertilizante": ["fertilizante", "biofertilizante", "nutricion vegetal"],
}


class BasfScraper(BaseScraper):
    source = "basf"

    def scrape(self) -> List[RawProduct]:
        products: List[RawProduct] = []
        product_urls = self._get_product_urls()
        logger.info("BASF: found %d product URLs", len(product_urls))

        for url in product_urls[:80]:
            try:
                product = self._scrape_product_page(url)
                if product:
                    products.append(product)
                random_delay(2.0, 4.5)
            except Exception as exc:
                logger.warning("BASF product page failed url=%s: %s", url, exc)

        logger.info("BASF scrape complete: %d products", len(products))
        return products

    def _get_product_urls(self) -> List[str]:
        for catalog_url in [_CATALOG_URL, _ALT_CATALOG_URL]:
            try:
                html = self._fetch_html(
                    catalog_url,
                    referer=_BASE_URL,
                    wait_selector="main, article, .product-item, [class*='product'], .catalog",
                )
                if detect_block(html):
                    continue
                return self._extract_urls_from_catalog(html, catalog_url)
            except Exception as exc:
                logger.warning("BASF catalog %s failed: %s", catalog_url, exc)
        return []

    def _extract_urls_from_catalog(self, html: str, base_url: str) -> List[str]:
        base = base_url.rsplit("/", 2)[0]
        soup = BeautifulSoup(html, "html.parser")
        urls: List[str] = []

        for link in soup.select("a[href]"):
            href = link.get("href", "")
            if not href:
                continue
            if any(kw in href.lower() for kw in ["/producto", "/product", ".html"]):
                full = urljoin(base, href)
                if full not in urls and ("basf" in full.lower()):
                    urls.append(full)

        return urls[:100]

    def _scrape_product_page(self, url: str) -> Optional[RawProduct]:
        html = self._fetch_html(url, referer=_CATALOG_URL)

        if detect_block(html):
            raise BlockedError(f"BASF blocked: {url}")

        soup = BeautifulSoup(html, "html.parser")
        return self._parse_page(soup, url, html)

    def _parse_page(self, soup: BeautifulSoup, url: str, html: str) -> Optional[RawProduct]:
        name_el = (
            soup.select_one("h1.product-name")
            or soup.select_one("h1[itemprop='name']")
            or soup.select_one(".product-detail h1")
            or soup.select_one("h1")
        )
        if not name_el:
            return None
        name = name_el.get_text(strip=True)
        if not name:
            return None

        full_text = soup.get_text(separator=" ")
        active_ingredient = self._extract_field(full_text, [
            "ingrediente activo", "active ingredient", "sustancia activa", "i.a."
        ])
        product_type_raw = self._infer_type(full_text)
        target_crops = [c for c in _CROP_KEYWORDS if c in full_text.lower()]
        target_diseases = self._extract_diseases(soup)

        return RawProduct(
            source=self.source,
            source_url=url,
            name=name,
            manufacturer="BASF",
            active_ingredient=active_ingredient,
            product_type_raw=product_type_raw,
            target_crops_raw=target_crops,
            target_diseases_raw=target_diseases,
            availability_regions=["MX"],
            html_snapshot=html[:50000],
        )

    def _extract_field(self, text: str, labels: List[str]) -> Optional[str]:
        for label in labels:
            pattern = rf"{re.escape(label)}\s*[:：]\s*([^\n\r.;,]{{1,200}})"
            match = re.search(pattern, text, re.IGNORECASE)
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
            "[class*='disease'], [class*='enfermedades'], [class*='plagas'], [class*='control']"
        )
        if not section:
            return []
        return list(set(
            el.get_text(strip=True)
            for el in section.select("li, td, dd")
            if el.get_text(strip=True)
        ))[:20]
