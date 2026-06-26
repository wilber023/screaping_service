"""
Amazon México scraper — amazon.com.mx búsqueda de agroquímicos.
Usa CF Browser Rendering para pasar el bot-check de Amazon desde EC2.
"""
from __future__ import annotations
import logging
import time
from typing import List, Optional
from urllib.parse import urljoin, quote_plus

from bs4 import BeautifulSoup

from scraping.scrapers.base_scraper import BaseScraper, RawProduct
from scraping.utils.anti_blocking import random_delay

logger = logging.getLogger(__name__)

_BASE = "https://www.amazon.com.mx"
_SEARCH = "https://www.amazon.com.mx/s?k={query}&i=garden"

_QUERIES = [
    "fungicida agricola",
    "insecticida agricola cultivos",
    "herbicida agricola",
    "fertilizante agricola plantas",
    "plaguicida campo",
]

_CROP_KEYWORDS = ["calabaza", "frijol", "mora", "maíz", "maiz", "papa", "fresa", "tomate"]

_TYPE_MAP = {
    "fungicida": "fungicida",
    "insecticida": "insecticida",
    "herbicida": "herbicida",
    "fertilizante": "fertilizante",
    "abono": "fertilizante",
    "acaricida": "insecticida",
    "nematicida": "insecticida",
}


class AmazonScraper(BaseScraper):
    source = "amazon"

    def scrape(self) -> List[RawProduct]:
        products: List[RawProduct] = []
        seen_asins: set[str] = set()

        for query in _QUERIES:
            try:
                url = _SEARCH.format(query=quote_plus(query))
                logger.info("Amazon: scraping query=%s", query)
                html = self._fetch_html(url, wait_selector=".s-search-results, #search, .s-result-list")
                if not html or len(html) < 5000:
                    logger.warning("Amazon: respuesta muy corta query=%s (%d bytes)", query, len(html or ""))
                    continue

                page_products = self._parse_search_page(html, query, seen_asins)
                products.extend(page_products)
                logger.info("Amazon: query=%s → %d productos", query, len(page_products))

                # Respetar rate limit: 1 req/10s (CF Browser Rendering free tier)
                random_delay(11, 14)

            except Exception as exc:
                logger.warning("Amazon query=%s failed: %s", query, exc)

        logger.info("Amazon scrape complete: %d productos", len(products))
        return products

    def _parse_search_page(self, html: str, query: str, seen_asins: set) -> List[RawProduct]:
        soup = BeautifulSoup(html, "html.parser")
        products = []

        # Detectar página de captcha/robot
        if self._is_blocked(soup):
            logger.warning("Amazon: página de bloqueo detectada")
            return []

        cards = soup.select('[data-component-type="s-search-result"]')
        if not cards:
            # Fallback: buscar por data-asin
            cards = soup.select("[data-asin]")

        for card in cards:
            asin = card.get("data-asin", "").strip()
            if not asin or asin in seen_asins:
                continue

            product = self._parse_card(card, asin, query)
            if product:
                seen_asins.add(asin)
                products.append(product)

        return products

    def _parse_card(self, card, asin: str, query: str) -> Optional[RawProduct]:
        # Título
        title_el = (
            card.select_one("h2 a span")
            or card.select_one(".a-size-medium.a-color-base.a-text-normal")
            or card.select_one(".a-size-base-plus.a-color-base.a-text-normal")
            or card.select_one("h2 span")
        )
        if not title_el:
            return None
        name = title_el.get_text(strip=True)
        if not name or len(name) < 3:
            return None

        # URL del producto
        link_el = card.select_one("h2 a") or card.select_one("a.a-link-normal[href*='/dp/']")
        source_url = urljoin(_BASE, link_el.get("href", f"/dp/{asin}")) if link_el else f"{_BASE}/dp/{asin}"

        # Precio
        price_amount = None
        price_el = card.select_one(".a-price .a-offscreen") or card.select_one(".a-price-whole")
        if price_el:
            price_str = price_el.get_text(strip=True).replace("$", "").replace(",", "").replace(".", "")
            try:
                price_amount = float(price_str) / (100 if len(price_str) > 6 else 1)
            except ValueError:
                pass

        # Imagen
        img_el = card.select_one("img.s-image") or card.select_one(".s-product-image-container img")
        image_url = img_el.get("src") if img_el else None

        # Vendedor/marca
        brand_el = card.select_one(".a-size-base.a-color-secondary") or card.select_one(".a-row .a-size-small span")
        manufacturer = brand_el.get_text(strip=True) if brand_el else "Amazon MX"

        # Rating
        rating = None
        rating_el = card.select_one(".a-icon-alt") or card.select_one("[aria-label*='estrellas']")
        if rating_el:
            text = rating_el.get_text(strip=True).replace(",", ".")
            try:
                rating = float(text.split()[0])
            except (ValueError, IndexError):
                pass

        # Reviews
        reviews = None
        reviews_el = card.select_one(".a-size-base.s-underline-text") or card.select_one("[aria-label*='valoraciones']")
        if reviews_el:
            text = reviews_el.get_text(strip=True).replace(",", "").replace(".", "")
            try:
                reviews = int("".join(filter(str.isdigit, text)))
            except ValueError:
                pass

        product_type = self._infer_type(name, query)
        target_crops = [c for c in _CROP_KEYWORDS if c in name.lower()]

        return RawProduct(
            source=self.source,
            source_url=source_url,
            name=name[:512],
            manufacturer=manufacturer,
            active_ingredient=None,
            product_type_raw=product_type,
            target_crops_raw=target_crops,
            target_diseases_raw=[],
            price_amount=price_amount,
            price_currency="MXN",
            stock_raw="in_stock",
            availability_regions=["MX"],
            image_url=image_url,
            rating=rating,
            reviews=reviews,
        )

    def _infer_type(self, name: str, query: str) -> str:
        text = (name + " " + query).lower()
        for kw, mapped in _TYPE_MAP.items():
            if kw in text:
                return mapped
        return "otro"

    def _is_blocked(self, soup: BeautifulSoup) -> bool:
        text = soup.get_text(separator=" ", strip=True).lower()
        blocked_signals = [
            "enter the characters you see below",
            "ingresa los caracteres que ves",
            "sorry, we just need to make sure",
            "robot check",
            "prueba que eres humano",
        ]
        return any(s in text for s in blocked_signals)
