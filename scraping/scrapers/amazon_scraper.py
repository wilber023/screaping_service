"""
Amazon México scraper — amazon.com.mx búsqueda de agroquímicos.
Queries específicos por tipo de producto agrícola para los 7 cultivos objetivo.
"""
from __future__ import annotations
import logging
import re
import time
from typing import List, Optional
from urllib.parse import urljoin, quote_plus

from bs4 import BeautifulSoup

from scraping.scrapers.base_scraper import BaseScraper, RawProduct
from scraping.utils.anti_blocking import random_delay

logger = logging.getLogger(__name__)

_BASE = "https://www.amazon.com.mx"
_SEARCH = "https://www.amazon.com.mx/s?k={query}&i=garden"

# Queries específicos — productos agrícolas comerciales México, rangos $100-$2000 MXN
_QUERIES = [
    # Fungicidas comerciales México
    "fungicida tebuconazol trifloxystrobin agricola",
    "fungicida polvo humectable mancozeb clorotalonil cultivos",
    "fungicida oxicloruro cobre tomate papa fresa agricola",
    "fungicida azoxistrobina propiconazol hortalizas",
    # Insecticidas comerciales México
    "insecticida imidacloprid agricola plagas cultivos",
    "insecticida abamectina minador araña tomate agricola",
    "insecticida clorpirifos diazinon maiz frijol agricola",
    "insecticida lambda cihalotrina cipermetrina cultivos",
    "insecticida espinosad trips mosca blanca agricola",
    # Herbicidas comerciales México
    "herbicida atrazina maiz sellador agricola",
    "herbicida mesotriona coquillo maiz agricola",
    "herbicida clethodim jitomate soya maleza",
    "herbicida 2 4 D hierbamina agricola hoja ancha",
    "herbicida glifosato concentrado agricola",
    # Fertilizantes agrícolas México
    "fertilizante ultrasol NPK hortalizas tomate",
    "fertilizante novatec NPK maiz papa fresa agricola",
    "humus lombriz abono organico agricola cultivos",
    "fertilizante foliar micronutrientes agricola",
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
    "bioinsecticida": "insecticida",
    "biofungicida": "fungicida",
    "biofertilizante": "fertilizante",
    "bactericida": "fungicida",
}

# Palabras que indican que el producto NO es aplicable al cultivo
_EXCLUDE_PHRASES = [
    # Accesorios y equipo
    "boquilla", "nozzle", "inyector venturi", "accesorios para drone",
    "accesorios pulverizador", "fumigador con varilla", "bomba de mochila",
    "refaccion", "pieza de repuesto", "cabezal agrícola",
    # Repelentes de animales (no plagas agrícolas)
    "repelente de conejos", "repelente de ciervos", "repelente de topos",
    "repelente de armadillo", "repelente de gopher", "gopher", "ciervo campo",
    "repelente de venado", "disuasión de tobos",
    # Repelentes eléctricos/físicos
    "bug zapper", "fly killer", "raqueta exterminador", "raqueta eléctric",
    "bocinas repelentes", "eliminador de insectos fly",
    # Plantas ornamentales / uso doméstico
    "orquídea", "orquidea", "bromelia", "anturio", "keikis",
    "plantas de interior", "uso en casa", "jardinería básica",
    "macetas y áreas verdes", "para el hogar y jardín decorativo",
    # Trampas / señuelos (no químicos aplicables)
    "señuelo de feromona", "señuelo feromona",
    "trampa para insectos",
    # Productos para mascotas
    "seguro para mascotas", "para mascotas",
    # Repelentes de mosquitos domésticos
    "mosquitero", "patio al aire", "cocina jardín terraza",
]

# Precio máximo razonable por unidad en MXN
# Fertilizantes 25kg pueden llegar a $2,000; productos importados desde EEUU son outliers
_MAX_PRICE_MXN = 5_000


class AmazonScraper(BaseScraper):
    source = "amazon"

    def scrape(self) -> List[RawProduct]:
        products: List[RawProduct] = []
        seen_asins: set[str] = set()

        for query in _QUERIES:
            try:
                url = _SEARCH.format(query=quote_plus(query))
                logger.info("Amazon: query=%s", query)
                html = self._fetch_html(url, wait_selector=".s-search-results, #search")
                if not html or len(html) < 5000:
                    logger.warning("Amazon: respuesta muy corta query=%s (%d bytes)", query, len(html or ""))
                    random_delay(11, 14)
                    continue

                page_products = self._parse_search_page(html, query, seen_asins)
                products.extend(page_products)
                logger.info("Amazon: query=%s → %d productos aceptados", query, len(page_products))

                random_delay(11, 15)

            except Exception as exc:
                logger.warning("Amazon query=%s failed: %s", query, exc)

        logger.info("Amazon scrape complete: %d productos", len(products))
        return products

    def _parse_search_page(self, html: str, query: str, seen_asins: set) -> List[RawProduct]:
        soup = BeautifulSoup(html, "html.parser")
        products = []

        if self._is_blocked(soup):
            logger.warning("Amazon: página de bloqueo detectada")
            return []

        cards = soup.select('[data-component-type="s-search-result"]')
        if not cards:
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
        if not name or len(name) < 5:
            return None

        # Filtrar accesorios y productos no aplicables
        if self._should_exclude(name):
            logger.debug("Amazon: excluido '%s'", name[:60])
            return None

        # URL del producto
        link_el = card.select_one("h2 a") or card.select_one("a.a-link-normal[href*='/dp/']")
        source_url = urljoin(_BASE, link_el.get("href", f"/dp/{asin}")) if link_el else f"{_BASE}/dp/{asin}"

        # Precio — Amazon MX usa "$1,299.00" (coma=miles, punto=decimal)
        price_amount = self._parse_price(card)

        # Filtrar precios absurdos (productos de EEUU en USD sin convertir bien)
        if price_amount is not None and price_amount > _MAX_PRICE_MXN:
            logger.debug("Amazon: precio descartado %.0f > %d MXN para '%s'", price_amount, _MAX_PRICE_MXN, name[:50])
            price_amount = None

        # Imagen
        img_el = card.select_one("img.s-image") or card.select_one(".s-product-image-container img")
        image_url = img_el.get("src") if img_el else None

        # Marca/fabricante — evitar texto promocional
        manufacturer = self._extract_manufacturer(card)

        # Rating
        rating = None
        rating_el = card.select_one(".a-icon-alt") or card.select_one("[aria-label*='estrellas']")
        if rating_el:
            text = rating_el.get_text(strip=True).replace(",", ".")
            try:
                rating = float(text.split()[0])
                if rating > 5:
                    rating = None
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
            active_ingredient=self._extract_active_ingredient(name),
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

    def _parse_price(self, card) -> Optional[float]:
        """Extrae precio MXN. Amazon usa '$1,299.00' → coma=miles, punto=decimal."""
        price_el = (
            card.select_one(".a-price .a-offscreen")
            or card.select_one(".a-price-whole")
        )
        if not price_el:
            return None
        raw = price_el.get_text(strip=True)
        # Quitar símbolo de moneda y espacios, mantener dígitos, coma y punto
        cleaned = re.sub(r"[^\d,.]", "", raw)
        if not cleaned:
            return None
        # Eliminar coma (separador de miles); el punto es el decimal
        cleaned = cleaned.replace(",", "")
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _extract_manufacturer(self, card) -> Optional[str]:
        """Extrae marca evitando texto promocional como 'x 12 meses'."""
        promo_signals = ["mes", "comprados", "anterior", "intereses", "sin interés", "oferta"]
        for selector in [
            ".a-size-base-plus.a-color-base",
            ".a-row .a-size-small span",
            ".a-size-base.a-color-secondary",
        ]:
            el = card.select_one(selector)
            if el:
                text = el.get_text(strip=True)
                if text and not any(s in text.lower() for s in promo_signals) and len(text) < 80:
                    return text
        return None

    def _should_exclude(self, name: str) -> bool:
        """Devuelve True si el producto es accesorio, equipo o no aplicable."""
        name_lower = name.lower()
        return any(phrase in name_lower for phrase in _EXCLUDE_PHRASES)

    def _infer_type(self, name: str, query: str) -> str:
        text = (name + " " + query).lower()
        for kw, mapped in _TYPE_MAP.items():
            if kw in text:
                return mapped
        return "otro"

    def _extract_active_ingredient(self, name: str) -> Optional[str]:
        """Intenta extraer ingrediente activo del nombre del producto."""
        known = [
            "glifosato", "mancozeb", "clorotalonil", "clorpirifos", "malathion",
            "lambda cihalotrina", "cipermetrina", "abamectina", "imidacloprid",
            "oxicloruro de cobre", "azoxistrobina", "propiconazol", "tiram",
            "paraquat", "diquat", "atrazina", "metribuzin", "pendimetalina",
            "2,4-d", "glifosato", "neem", "bacillus thuringiensis",
        ]
        name_lower = name.lower()
        for ai in known:
            if ai in name_lower:
                return ai
        return None

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
