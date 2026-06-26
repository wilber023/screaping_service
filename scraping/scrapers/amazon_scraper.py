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

# Queries con cultivos asociados explícitamente para tagging
# Formato: (query_string, [cultivos_que_aplican])
_QUERIES: list[tuple[str, list[str]]] = [
    # Fungicidas por cultivo
    ("fungicida tomate fresa botrytis tizón",          ["tomate", "fresa"]),
    ("fungicida papa tizón tardío phytophthora",        ["papa", "tomate"]),
    ("fungicida maiz roya tizón foliar",                ["maiz"]),
    ("fungicida frijol antracnosis roya agricola",      ["frijol", "maiz"]),
    ("fungicida mora fresa botrytis monilia",           ["mora", "fresa"]),
    ("fungicida tebuconazol trifloxystrobin agricola",  ["tomate", "papa", "fresa", "maiz"]),
    # Insecticidas por cultivo
    ("insecticida tomate mosca blanca minador trips",   ["tomate", "papa", "fresa"]),
    ("insecticida maiz gusano cogollero pulgón",        ["maiz", "frijol"]),
    ("insecticida papa frijol pulgón diabrótica",       ["papa", "frijol", "maiz"]),
    ("insecticida abamectina araña roja ácaros",        ["tomate", "fresa", "papa", "mora"]),
    ("insecticida imidacloprid mosca blanca áfidos",    ["tomate", "calabaza", "papa"]),
    ("insecticida espinosad trips mosca blanca cultivos", ["tomate", "fresa", "papa"]),
    # Herbicidas por cultivo
    ("herbicida maiz atrazina coquillo pre-emergente",  ["maiz"]),
    ("herbicida clethodim jitomate tomate gramíneas",   ["tomate", "frijol", "papa"]),
    ("herbicida glifosato maleza agricola",             ["maiz", "frijol"]),
    # Fertilizantes por cultivo
    ("fertilizante tomate fresa NPK soluble",           ["tomate", "fresa"]),
    ("fertilizante maiz papa NPK agricola",             ["maiz", "papa", "frijol", "calabaza"]),
    ("humus lombriz abono organico cultivos",           ["tomate", "papa", "maiz", "fresa", "frijol", "mora", "calabaza"]),
    ("fertilizante foliar micronutrientes hortalizas",  ["tomate", "papa", "fresa", "calabaza"]),
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

# Palabras que indican que el producto NO es un agroquímico aplicable al cultivo
_EXCLUDE_PHRASES = [
    # ── Herramientas / equipo de aplicación ──────────────────────────────────
    "esparcidor de fertilizante", "esparcidor de abono", "esparcidora de fertilizante",
    "distribuidor de fertilizante", "distribuidor manual de fertilizante",
    "herramienta de fertiliz", "herramienta esparcidora",
    "dispensador de fertilizante", "dispensador manual",
    "aplicador de fertilizante", "aplicador de estiércol",
    "mochila topdressing", "mochila de fertilizantes",
    "bolsa dispensadora", "bolsa de estiércol",
    "sembradora", "herramienta de siembra", "herramienta agrícola portátil",
    "espolvoreador de polvos", "espolvoreador de tierra",
    # Boquillas y accesorios de aspersión
    "boquilla", "nozzle", "inyector venturi", "accesorios para drone",
    "accesorios pulverizador", "fumigador con varilla",
    "refaccion", "pieza de repuesto", "cabezal agrícola",
    "pulverizador de presión", "rociador de presión",
    # ── Sustratos, contenedores y medios de siembra (no agroquímicos) ────────
    "bolsa de cultivo", "bolsa tejida tipo mochila", "bolsa geográfica",
    "contenedor de cultivo", "maceta de tela", "paca de paja",
    "pellets de coco", "piso de coco", "fibra de coco",
    "sustrato de germinación", "sustrato orgánico para árboles",
    "sustrato para semillas",
    "perlita mineral", "vermiculita",
    "film mulch", "mulch aumenta", "película gruesa", "red mulch",
    "para terraza y flores",
    # ── Hidropónico / aeropónico ─────────────────────────────────────────────
    "hidropónico", "hidroponica", "hidroponico", "aeropónico",
    # ── Productos de plomería / limpieza de drenaje (falsos positivos críticos)
    "coladera", "drenaje de baño", "tubería", "lavabo", "fregadero",
    "regadera", "mal olor en", "olores en tuberías", "obstrucción",
    "odour stop", "tratamiento contra malos olores",
    # ── Uso doméstico / jardinería de balcón ─────────────────────────────────
    "plantas de interior", "plantas en el hogar", "planta de balcón",
    "refuerzo de plantas de balcón", "soporte para de plantas en el hogar",
    "purificador de aire", "hogar con macetas", "palma de areca",
    "jardinería básica", "macetas y áreas verdes",
    "para el hogar y jardín decorativo", "cuidado de plantas y hogar",
    "uso en casa", "cocina jardín terraza",
    "palitos de fertilizante para plantas", "palitos de comida vegetal",
    "barras de fertilizante para plantas",
    "paquete de 40", "paquete de 20",  # palitos/barras fertilizante doméstico
    # ── Enraizantes / estimulantes ornamentales ──────────────────────────────
    "enraizante para plantas", "promueve raíces sanas en esquejes",
    "leaf shine", "plant shine",
    # ── Activadores de suelo para césped / jardín (no cultivo agrícola) ──────
    "para jardín, césped", "para jardín y cesped", "para cesped y jardin",
    "activador de suelo", "activadores de suelo",
    "para pasto y jardín", "para pasto y jardín",
    # ── Herbicidas para caminos/césped (no cultivos agrícolas) ───────────────
    "para caminos", "para patios y", "para terrazas o accesos",
    "eliminación de malezas en caminos",
    "para césped de temporada", "control de malezas de hoja ancha",
    "base de aceto", "sustancia básica acetum",
    # ── Repelentes de animales vertebrados ───────────────────────────────────
    "repelente de conejos", "repelente de ciervos", "repelente de topos",
    "repelente de armadillo", "repelente de gopher", "repelente de venado",
    # ── Trampas físicas / adhesivas ──────────────────────────────────────────
    "trampa adhesiva", "trampa amarilla", "sticky", "fly trap",
    "trampa para moscas", "trampa para insectos voladores",
    "atrapamoscas", "trampa de doble cara", "trampa sin olor",
    "trampas para moscas de la fruta", "trampa para ventana",
    "cebo especial y embudo",
    "yellow sticky", "trampas adhesivas amarillas",
    # ── Repelentes eléctricos ─────────────────────────────────────────────────
    "bug zapper", "fly killer", "raqueta exterminador", "raqueta eléctric",
    "bocinas repelentes",
    # ── Plantas ornamentales ─────────────────────────────────────────────────
    "orquídea", "orquidea", "bromelia", "anturio", "keikis",
    "cactácea", "cactacea", "suculenta", "suculentas",
    # ── Mascotas ─────────────────────────────────────────────────────────────
    "seguro para mascotas", "para mascotas", "uso en mascotas",
    # ── Semillas ─────────────────────────────────────────────────────────────
    "semilla de", "paquete de semillas",
    # ── Selladores de poda ───────────────────────────────────────────────────
    "pruning seal", "sellador de poda",
    # ── Cosméticos capilares ─────────────────────────────────────────────────
    "cabello", "queratina", "acondicionador profundo", "bond repair",
    # ── Señuelos de feromonas ────────────────────────────────────────────────
    "señuelo de feromona", "señuelo feromona",
    # ── Otros sin utilidad agrícola ──────────────────────────────────────────
    "colector protector", "mosquitero",
    "kit nutriente + enraizante",  # kits ornamentales
]

# Precio máximo razonable por unidad en MXN
# Fertilizantes 25kg pueden llegar a $2,000; productos importados desde EEUU son outliers
_MAX_PRICE_MXN = 5_000


class AmazonScraper(BaseScraper):
    source = "amazon"

    def scrape(self) -> List[RawProduct]:
        products: List[RawProduct] = []
        seen_asins: set[str] = set()

        for query, query_crops in _QUERIES:
            try:
                url = _SEARCH.format(query=quote_plus(query))
                logger.info("Amazon: query=%s crops=%s", query, query_crops)
                html = self._fetch_html(url, wait_selector=".s-search-results, #search")
                if not html or len(html) < 5000:
                    logger.warning("Amazon: respuesta muy corta query=%s (%d bytes)", query, len(html or ""))
                    random_delay(11, 14)
                    continue

                page_products = self._parse_search_page(html, query, query_crops, seen_asins)
                products.extend(page_products)
                logger.info("Amazon: query=%s → %d productos aceptados", query, len(page_products))

                random_delay(11, 15)

            except Exception as exc:
                logger.warning("Amazon query=%s failed: %s", query, exc)

        logger.info("Amazon scrape complete: %d productos", len(products))
        return products

    def _parse_search_page(self, html: str, query: str, query_crops: list, seen_asins: set) -> List[RawProduct]:
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

            product = self._parse_card(card, asin, query, query_crops)
            if product:
                seen_asins.add(asin)
                products.append(product)

        return products

    def _parse_card(self, card, asin: str, query: str, query_crops: list = None) -> Optional[RawProduct]:
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
        # Cultivos detectados en el nombre + cultivos del query (para productos que no los mencionan explícitamente)
        name_crops = [c for c in _CROP_KEYWORDS if c in name.lower()]
        target_crops = list(dict.fromkeys(name_crops + (query_crops or [])))

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
        """Devuelve True si el producto es accesorio, equipo o no aplicable al cultivo."""
        name_lower = name.lower()
        if any(phrase in name_lower for phrase in _EXCLUDE_PHRASES):
            return True
        # Herramientas / equipo que no son agroquímicos
        tool_words = [
            "esparcidor", "espolvoreador", "sembradora", "dispensador",
            "distribuidor de abono", "aplicador de", "mochila toping",
            "kit de preparación", "pulverizador de presión", "rociador de presión",
        ]
        if any(w in name_lower for w in tool_words):
            return True
        # Producto de plomería/hogar (BIOPURE Odour Stop y similares)
        plumbing = ["coladera", "tubería", "drenaje", "lavabo", "fregadero", "obstrucción"]
        if any(w in name_lower for w in plumbing):
            return True
        # Producto claramente decorativo/hogar con macetas
        home_signals = [
            "para el hogar", "para tu hogar", "aire de interior",
            "plantas de la casa", "balcón y terraza",
        ]
        if any(w in name_lower for w in home_signals):
            return True
        # El producto se auto-declara no agrícola
        if "no agrícola" in name_lower or "no agricola" in name_lower:
            return True
        return False

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
