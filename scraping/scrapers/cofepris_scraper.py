"""
COFEPRIS scraper — Registro oficial de plaguicidas de México.

Estrategias en orden:
  1. datos.gob.mx CKAN API  → JSON sin challenge, da URL directa del Excel
  2. URLs directas de Excel  → archivos estáticos que bypasan el WAF
  3. CF Browser Rendering    → para descubrir el link cuando las otras fallan
"""
from __future__ import annotations
import io
import json
import logging
from typing import List, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from scraping.scrapers.base_scraper import BaseScraper, RawProduct
from scraping.utils.headers import get_browser_headers

logger = logging.getLogger(__name__)

_BASE_GOB = "https://www.gob.mx"

# CKAN API de datos.gob.mx — devuelve JSON con metadatos y URL de descarga
_CKAN_SEARCH = (
    "https://datos.gob.mx/api/3/action/package_search"
    "?q=cofepris+plaguicidas&rows=10"
)
_CKAN_PKG = (
    "https://datos.gob.mx/api/3/action/package_show?id="
    "registro-de-plaguicidas-y-nutrientes-vegetales"
)

# URLs directas de Excel que COFEPRIS ha publicado históricamente.
# Los archivos estáticos en /cms/uploads/ suelen bypass el WAF.
_DIRECT_EXCEL_URLS = [
    # Ajusta estos IDs si COFEPRIS actualiza el archivo
    "https://www.gob.mx/cms/uploads/attachment/file/783559/Plaguicidas_y_Nutrientes_Vegetales_Registrados.xlsx",
    "https://www.gob.mx/cms/uploads/attachment/file/783559/plaguicidas_registrados.xlsx",
    "https://www.cofepris.gob.mx/Documents/Plaguicidas/Plaguicidas_Registrados.xlsx",
    "https://www.cofepris.gob.mx/Documents/Plaguicidas/lista_plaguicidas.xlsx",
]

# Páginas HTML donde COFEPRIS enlaza el Excel (se intentan vía CF Browser)
_HTML_PAGES = [
    "https://www.gob.mx/cofepris/documentos/plaguicidas-y-nutrientes-vegetales",
    "https://www.gob.mx/cofepris/documentos/plaguicidas-y-nutrientes-vegetales-registrados",
]

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
        self._http = httpx.Client(
            timeout=60,
            follow_redirects=True,
            headers=get_browser_headers(),
        )

    def scrape(self) -> List[RawProduct]:
        # 1. datos.gob.mx CKAN API
        products = self._try_ckan_api()
        if products:
            logger.info("COFEPRIS CKAN: %d productos", len(products))
            return products

        # 2. URLs directas de Excel
        products = self._try_direct_excel_urls()
        if products:
            logger.info("COFEPRIS Excel directo: %d productos", len(products))
            return products

        # 3. CF Browser Rendering para descubrir link del Excel
        products = self._try_cf_browser_discovery()
        logger.info("COFEPRIS CF Browser: %d productos", len(products))
        return products

    # ── 1. CKAN API ───────────────────────────────────────────────────────────

    def _try_ckan_api(self) -> List[RawProduct]:
        for url in [_CKAN_PKG, _CKAN_SEARCH]:
            try:
                r = self._http.get(url, timeout=20)
                if r.status_code != 200:
                    continue
                data = r.json()
                if not data.get("success"):
                    continue

                result = data.get("result", {})
                # package_show devuelve un dict; package_search devuelve {results:[...]}
                packages = [result] if isinstance(result, dict) else result.get("results", [])

                for pkg in packages:
                    for resource in pkg.get("resources", []):
                        dl_url = resource.get("url", "")
                        fmt = resource.get("format", "").lower()
                        if any(e in dl_url.lower() or e == fmt for e in ["xlsx", "xls", "csv"]):
                            logger.info("COFEPRIS CKAN: descargando %s", dl_url)
                            products = self._download_and_parse_excel(dl_url)
                            if products:
                                return products
            except Exception as exc:
                logger.debug("COFEPRIS CKAN fallback: %s", exc)
        return []

    # ── 2. URLs directas de Excel ─────────────────────────────────────────────

    def _try_direct_excel_urls(self) -> List[RawProduct]:
        for url in _DIRECT_EXCEL_URLS:
            try:
                r = self._http.head(url, timeout=15)
                ct = r.headers.get("content-type", "")
                if r.status_code == 200 and ("spreadsheet" in ct or "excel" in ct or "octet" in ct):
                    products = self._download_and_parse_excel(url)
                    if products:
                        return products
                elif r.status_code == 200:
                    # HEAD puede no devolver content-type correcto; intenta GET
                    products = self._download_and_parse_excel(url)
                    if products:
                        return products
            except Exception as exc:
                logger.debug("COFEPRIS direct url=%s: %s", url, exc)
        return []

    # ── 3. CF Browser Rendering ───────────────────────────────────────────────

    def _try_cf_browser_discovery(self) -> List[RawProduct]:
        for page_url in _HTML_PAGES:
            try:
                html = self._fetch_html(page_url)
                if not html or len(html) < 2000:
                    continue
                soup = BeautifulSoup(html, "html.parser")
                for a in soup.select("a[href]"):
                    href = a.get("href", "")
                    if any(ext in href.lower() for ext in [".xlsx", ".xls", ".csv"]):
                        file_url = urljoin(_BASE_GOB, href)
                        logger.info("COFEPRIS CF discovered: %s", file_url)
                        products = self._download_and_parse_excel(file_url)
                        if products:
                            return products
            except Exception as exc:
                logger.debug("COFEPRIS CF browser failed url=%s: %s", page_url, exc)
        return []

    # ── Excel parser ──────────────────────────────────────────────────────────

    def _download_and_parse_excel(self, url: str) -> List[RawProduct]:
        try:
            import openpyxl
            r = self._http.get(url, timeout=120)
            if r.status_code != 200:
                logger.debug("COFEPRIS Excel download failed %s: HTTP %s", url, r.status_code)
                return []
            # Detect challenge page (1883 bytes "Challenge Validation")
            if len(r.content) < 5000 and b"Challenge" in r.content:
                logger.debug("COFEPRIS Excel challenge page at %s", url)
                return []

            content_type = r.headers.get("content-type", "")
            # Check it's actually an Excel file
            if "html" in content_type and b"<html" in r.content[:200]:
                logger.debug("COFEPRIS got HTML instead of Excel at %s", url)
                return []

            wb = openpyxl.load_workbook(io.BytesIO(r.content), read_only=True, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                return []

            headers = [str(c or "").lower().strip() for c in rows[0]]
            col = {h: i for i, h in enumerate(headers)}
            logger.info("COFEPRIS Excel headers: %s", headers[:10])

            name_col = self._find_col(col, ["nombre", "producto comercial", "producto", "name"])
            if name_col is None:
                logger.warning("COFEPRIS: no name column found in %s", headers[:10])
                return []

            mfr_col  = self._find_col(col, ["titular", "fabricante", "empresa", "registrante"])
            ing_col  = self._find_col(col, ["ingrediente activo", "ingrediente", "i.a.", "active"])
            type_col = self._find_col(col, ["tipo", "clase", "category", "type"])
            crop_col = self._find_col(col, ["cultivo", "cultivos", "uso", "crop"])

            products: List[RawProduct] = []
            for row in rows[1:]:
                name = str(row[name_col] or "").strip()
                if not name or name.lower() in ("none", "nombre", "producto"):
                    continue
                mfr      = str(row[mfr_col]  or "").strip() if mfr_col  is not None else None
                ing      = str(row[ing_col]  or "").strip() if ing_col  is not None else None
                tipo     = str(row[type_col] or "").strip() if type_col is not None else ""
                crops_raw = str(row[crop_col] or "").strip() if crop_col is not None else ""

                products.append(self._make_product(
                    name=name,
                    manufacturer=mfr or None,
                    ingredient=ing or None,
                    type_raw=tipo,
                    crops_text=crops_raw,
                    url=url,
                ))
                if len(products) >= 1000:
                    break

            logger.info("COFEPRIS Excel parsed: %d productos de %s", len(products), url)
            return products

        except Exception as exc:
            logger.warning("COFEPRIS parse_excel failed url=%s: %s", url, exc)
            return []

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _find_col(self, col_map: dict, candidates: list) -> Optional[int]:
        for c in candidates:
            if c in col_map:
                return col_map[c]
            for k in col_map:
                if c in k:
                    return col_map[k]
        return None

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
        for kw, mapped in _TYPE_MAP.items():
            if kw in type_raw.lower():
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
