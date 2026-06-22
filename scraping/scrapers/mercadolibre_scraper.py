"""
MercadoLibre scraper — uses the public MercadoLibre REST API (no auth needed,
rate-limited by IP). Site ID MLM = México.
"""
from __future__ import annotations
import logging
import re
import time
from typing import List, Optional

import httpx

from scraping.scrapers.base_scraper import BaseScraper, RawProduct
from scraping.utils.anti_blocking import random_delay
from scraping.utils.headers import get_api_headers

logger = logging.getLogger(__name__)

_API_SEARCH = "https://api.mercadolibre.com/sites/MLM/search"
_API_ITEM = "https://api.mercadolibre.com/items/{item_id}"

_SEARCH_QUERIES = [
    "fungicida agricola",
    "insecticida agricola",
    "herbicida agricola",
    "fertilizante agricola",
    "plaguicida cultivos",
]

_TARGET_CROPS = [
    "calabaza", "frijol", "manzana", "mora", "cereza", "maíz", "maiz",
    "durazno", "uva", "naranja", "pimienta", "papa", "frambuesa",
    "soja", "fresa", "tomate",
]


class MercadoLibreScraper(BaseScraper):
    source = "mercadolibre"

    def scrape(self) -> List[RawProduct]:
        products: List[RawProduct] = []
        seen_ids: set[str] = set()

        with httpx.Client(timeout=30, headers=get_api_headers(), follow_redirects=True) as client:
            for query in _SEARCH_QUERIES:
                try:
                    items = self._search(client, query)
                    for item_data in items:
                        item_id = item_data.get("id")
                        if not item_id or item_id in seen_ids:
                            continue
                        seen_ids.add(item_id)

                        product = self._build_product_from_search(item_data, query)
                        if product:
                            products.append(product)

                    random_delay(1.5, 3.5)
                except Exception as exc:
                    logger.warning("MercadoLibre query='%s' failed: %s", query, exc)

        logger.info("MercadoLibre scrape complete: %d products", len(products))
        return products

    def _search(self, client: httpx.Client, query: str) -> List[dict]:
        params = {
            "q": query,
            "limit": 50,
            "offset": 0,
            "category": "MLM1403",  # Fertilizantes, Plaguicidas y Semillas
        }
        resp = client.get(_API_SEARCH, params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])

    def _build_product_from_search(self, item: dict, query: str) -> Optional[RawProduct]:
        name = item.get("title", "").strip()
        if not name:
            return None

        price = item.get("price")
        currency = item.get("currency_id", "MXN")
        permalink = item.get("permalink", "")
        condition = item.get("condition", "")
        available_qty = item.get("available_quantity")
        sold_qty = item.get("sold_quantity", 0)

        stock_raw = "in_stock" if (available_qty and available_qty > 0) else "unknown"
        if available_qty == 0:
            stock_raw = "out_of_stock"

        seller_info = item.get("seller", {})
        manufacturer = seller_info.get("nickname") if seller_info else None

        attributes = item.get("attributes", [])
        active_ingredient = None
        for attr in attributes:
            attr_id = attr.get("id", "").lower()
            attr_name = attr.get("name", "").lower()
            if "ingrediente" in attr_name or "ingredient" in attr_id:
                active_ingredient = attr.get("value_name")
                break

        product_type_raw = self._infer_type(name, query)
        target_crops = self._extract_crops(name)

        return RawProduct(
            source=self.source,
            source_url=permalink,
            name=name,
            manufacturer=manufacturer,
            active_ingredient=active_ingredient,
            product_type_raw=product_type_raw,
            target_crops_raw=target_crops,
            price_amount=float(price) if price else None,
            price_currency=currency,
            stock_raw=stock_raw,
            availability_regions=["MX"],
        )

    def _infer_type(self, name: str, query: str) -> str:
        lower = (name + " " + query).lower()
        if "fungicida" in lower:
            return "fungicida"
        if "insecticida" in lower:
            return "insecticida"
        if "herbicida" in lower:
            return "herbicida"
        if "fertilizante" in lower or "abono" in lower:
            return "fertilizante"
        return "otro"

    def _extract_crops(self, name: str) -> List[str]:
        lower = name.lower()
        found = []
        for crop in _TARGET_CROPS:
            if crop in lower:
                found.append(crop)
        return found
