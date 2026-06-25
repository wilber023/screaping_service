"""
COFEPRIS scraper — Registro oficial de plaguicidas de México.
Fuente: Comisión Federal para la Protección contra Riesgos Sanitarios (gob.mx)
Sin anti-bot: sitio gubernamental de acceso libre.

Estrategia:
  1. Intentar descargar el Excel/CSV de la lista de plaguicidas registrados
  2. Si falla, raspar la tabla HTML de búsqueda
"""
from __future__ import annotations
import io
import logging
from typing import List, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from scraping.scrapers.base_scraper import BaseScraper, RawProduct
from scraping.utils.headers import get_browser_headers

logger = logging.getLogger(__name__)

_BASE = "https://www.gob.mx"

# Páginas candidatas con listas de plaguicidas registrados
_CATALOG_URLS = [
    "https://www.gob.mx/cofepris/documentos/plaguicidas-y-nutrientes-vegetales",
    "https://www.gob.mx/cofepris/documentos/plaguicidas-y-nutrientes-vegetales-registrados",
    "https://www.gob.mx/cms/uploads/attachment/file/",  # base para Excel
]

# Búsqueda directa en el portal de COFEPRIS
_SEARCH_URL = "https://www.cofepris.gob.mx/busqueda/plaguicidas/"
_SEARCH_API  = "https://www.cofepris.gob.mx/AZ/Paginas/Plaguicidas/ConsultaPlaguicidas.aspx"

_CROP_KEYWORDS = [
    "calabaza", "frijol", "manzana", "mora", "cereza", "maíz", "maiz",
    "durazno", "uva", "naranja", "pimienta", "papa", "frambuesa",
    "soja", "fresa", "tomate", "trigo", "arroz", "sorgo", "chile",
    "jitomate", "aguacate", "cítrico", "citrico",
]

_TYPE_MAP = {
    "fungicida": "fungicida",
    "insecticida": "insecticida",
    "herbicida": "herbicida",
    "fertilizante": "fertilizante",
    "biofertilizante": "fertilizante",
    "nutriente": "fertilizante",
    "acaricida": "insecticida",
    "nematicida": "insecticida",
    "rodenticida": "insecticida",
}


class CofeprisScraper(BaseScraper):
    source = "cofepris"

    def __init__(self) -> None:
        super().__init__()
        self._client = httpx.Client(
            timeout=30,
            follow_redirects=True,
            headers=get_browser_headers(),
        )

    def scrape(self) -> List[RawProduct]:
        products: List[RawProduct] = []

        # Intento 1: descargar Excel/CSV publicado por COFEPRIS
        products = self._try_download_excel()
        if products:
            logger.info("COFEPRIS: %d productos desde Excel", len(products))
            return products

        # Intento 2: raspar tablas HTML del portal
        products = self._try_html_table()
        if products:
            logger.info("COFEPRIS: %d productos desde HTML", len(products))
            return products

        # Intento 3: búsqueda paginada en el portal antiguo
        products = self._try_search_pagination()
        logger.info("COFEPRIS: %d productos desde búsqueda", len(products))
        return products

    # ── Intento 1: Excel ──────────────────────────────────────────────────────

    def _try_download_excel(self) -> List[RawProduct]:
        for url in _CATALOG_URLS[:2]:
            try:
                resp = self._client.get(url)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                # Buscar links a Excel o CSV
                for link in soup.select("a[href]"):
                    href = link.get("href", "")
                    if any(ext in href.lower() for ext in [".xlsx", ".xls", ".csv"]):
                        file_url = urljoin(_BASE, href)
                        result = self._parse_excel(file_url)
                        if result:
                            return result
            except Exception as exc:
                logger.debug("COFEPRIS Excel discovery failed: %s", exc)
        return []

    def _parse_excel(self, url: str) -> List[RawProduct]:
        try:
            import openpyxl
            resp = self._client.get(url, timeout=60)
            if resp.status_code != 200:
                return []
            wb = openpyxl.load_workbook(io.BytesIO(resp.content), read_only=True, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                return []

            # Detectar header row
            headers = [str(c or "").lower().strip() for c in rows[0]]
            col = {h: i for i, h in enumerate(headers)}

            name_col  = self._find_col(col, ["nombre", "producto", "name"])
            mfr_col   = self._find_col(col, ["titular", "fabricante", "empresa", "manufacturer"])
            ing_col   = self._find_col(col, ["ingrediente", "ingrediente activo", "active", "i.a."])
            type_col  = self._find_col(col, ["tipo", "category", "type", "clase"])
            crop_col  = self._find_col(col, ["cultivo", "cultivos", "uso", "crop"])

            if name_col is None:
                return []

            products: List[RawProduct] = []
            for row in rows[1:]:
                name = str(row[name_col] or "").strip()
                if not name or name.lower() == "none":
                    continue
                mfr   = str(row[mfr_col]  or "").strip() if mfr_col  is not None else None
                ing   = str(row[ing_col]  or "").strip() if ing_col  is not None else None
                tipo  = str(row[type_col] or "").strip() if type_col is not None else ""
                crops_raw = str(row[crop_col] or "").strip() if crop_col is not None else ""

                products.append(self._make_product(
                    name=name,
                    manufacturer=mfr or None,
                    ingredient=ing or None,
                    type_raw=tipo,
                    crops_text=crops_raw,
                    url=url,
                ))
                if len(products) >= 500:
                    break
            return products
        except Exception as exc:
            logger.warning("COFEPRIS parse_excel failed: %s", exc)
            return []

    def _find_col(self, col_map: dict, candidates: list) -> Optional[int]:
        for c in candidates:
            if c in col_map:
                return col_map[c]
            for k, v in col_map.items():
                if c in k:
                    return v
        return None

    # ── Intento 2: HTML Table ─────────────────────────────────────────────────

    def _try_html_table(self) -> List[RawProduct]:
        for url in _CATALOG_URLS[:2]:
            try:
                resp = self._client.get(url)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                tables = soup.select("table")
                for table in tables:
                    products = self._parse_html_table(table, url)
                    if products:
                        return products
            except Exception as exc:
                logger.debug("COFEPRIS HTML table failed: %s", exc)
        return []

    def _parse_html_table(self, table, source_url: str) -> List[RawProduct]:
        rows = table.select("tr")
        if len(rows) < 2:
            return []
        headers = [th.get_text(strip=True).lower() for th in rows[0].select("th, td")]
        col = {h: i for i, h in enumerate(headers)}

        name_col = self._find_col(col, ["nombre", "producto"])
        if name_col is None:
            return []

        mfr_col  = self._find_col(col, ["titular", "fabricante", "empresa"])
        ing_col  = self._find_col(col, ["ingrediente", "i.a."])
        type_col = self._find_col(col, ["tipo", "clase"])
        crop_col = self._find_col(col, ["cultivo", "uso"])

        products = []
        for row in rows[1:]:
            cells = [td.get_text(strip=True) for td in row.select("td")]
            if len(cells) <= name_col:
                continue
            name = cells[name_col].strip()
            if not name:
                continue
            products.append(self._make_product(
                name=name,
                manufacturer=cells[mfr_col].strip() if mfr_col is not None and len(cells) > mfr_col else None,
                ingredient=cells[ing_col].strip() if ing_col is not None and len(cells) > ing_col else None,
                type_raw=cells[type_col].strip() if type_col is not None and len(cells) > type_col else "",
                crops_text=cells[crop_col].strip() if crop_col is not None and len(cells) > crop_col else "",
                url=source_url,
            ))
        return products

    # ── Intento 3: Búsqueda paginada ──────────────────────────────────────────

    def _try_search_pagination(self) -> List[RawProduct]:
        products: List[RawProduct] = []
        # Buscar por cada tipo de producto
        for query in ["fungicida", "insecticida", "herbicida", "fertilizante"]:
            try:
                url = f"{_SEARCH_URL}?tipo={query}"
                resp = self._client.get(url)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                for table in soup.select("table"):
                    products.extend(self._parse_html_table(table, url))
                if len(products) >= 200:
                    break
            except Exception as exc:
                logger.debug("COFEPRIS search failed query=%s: %s", query, exc)
        return products

    # ── Helper ────────────────────────────────────────────────────────────────

    def _make_product(
        self,
        name: str,
        manufacturer: Optional[str],
        ingredient: Optional[str],
        type_raw: str,
        crops_text: str,
        url: str,
    ) -> RawProduct:
        tipo = "otro"
        lower = type_raw.lower()
        for kw, mapped in _TYPE_MAP.items():
            if kw in lower:
                tipo = mapped
                break

        crops_lower = crops_text.lower()
        target_crops = [c for c in _CROP_KEYWORDS if c in crops_lower]

        return RawProduct(
            source=self.source,
            source_url=url,
            name=name[:512],
            manufacturer=manufacturer,
            active_ingredient=ingredient,
            product_type_raw=tipo,
            target_crops_raw=target_crops,
            target_diseases_raw=[],
            availability_regions=["MX"],
        )
