from __future__ import annotations
import hashlib
import logging
from datetime import datetime
from typing import Optional

from scraping.parsers.price_parser import PriceParser
from scraping.parsers.stock_parser import StockParser
from scraping.scrapers.base_scraper import RawProduct

logger = logging.getLogger(__name__)


class ParsedProduct:
    """Intermediate representation after parsing, before full normalization."""

    __slots__ = (
        "source", "source_url", "name", "manufacturer", "active_ingredient",
        "product_type_raw", "target_crops_raw", "target_diseases_raw",
        "price_amount", "price_currency", "stock_status", "stock_quantity",
        "availability_regions", "scraped_at", "hash_dedup", "image_url",
        "rating", "reviews", "presentacion",
    )

    def __init__(
        self,
        source: str,
        source_url: str,
        name: str,
        manufacturer: Optional[str],
        active_ingredient: Optional[str],
        product_type_raw: str,
        target_crops_raw: list,
        target_diseases_raw: list,
        price_amount: Optional[float],
        price_currency: str,
        stock_status: str,
        stock_quantity: Optional[int],
        availability_regions: list,
        scraped_at: datetime,
        hash_dedup: str,
        image_url: Optional[str] = None,
        rating: Optional[float] = None,
        reviews: Optional[int] = None,
        presentacion: Optional[str] = None,
    ) -> None:
        self.source = source
        self.source_url = source_url
        self.name = name
        self.manufacturer = manufacturer
        self.active_ingredient = active_ingredient
        self.product_type_raw = product_type_raw
        self.target_crops_raw = target_crops_raw
        self.target_diseases_raw = target_diseases_raw
        self.price_amount = price_amount
        self.price_currency = price_currency
        self.stock_status = stock_status
        self.stock_quantity = stock_quantity
        self.availability_regions = availability_regions
        self.scraped_at = scraped_at
        self.hash_dedup = hash_dedup
        self.image_url = image_url
        self.rating = rating
        self.reviews = reviews
        self.presentacion = presentacion


class ProductParser:
    """Converts a RawProduct into a ParsedProduct by running price/stock parsers."""

    @staticmethod
    def parse(raw: RawProduct) -> Optional[ParsedProduct]:
        if not raw.name or not raw.source_url:
            return None

        default_currency = ProductParser._default_currency_for_source(raw.source)
        price_amount, price_currency = PriceParser.parse(
            raw.price_raw,
            default_currency=default_currency,
            amount_override=raw.price_amount,
            currency_override=raw.price_currency,
        )

        stock_status, stock_quantity = StockParser.parse(raw.stock_raw)

        hash_dedup = ProductParser._compute_hash(
            raw.source, raw.name, raw.active_ingredient or "", raw.source_url
        )

        return ParsedProduct(
            source=raw.source,
            source_url=raw.source_url,
            name=raw.name.strip()[:512],
            manufacturer=raw.manufacturer,
            active_ingredient=raw.active_ingredient,
            product_type_raw=raw.product_type_raw or "otro",
            target_crops_raw=raw.target_crops_raw or [],
            target_diseases_raw=raw.target_diseases_raw or [],
            price_amount=price_amount,
            price_currency=price_currency or default_currency,
            stock_status=stock_status,
            stock_quantity=stock_quantity,
            availability_regions=raw.availability_regions or [],
            scraped_at=raw.scraped_at,
            hash_dedup=hash_dedup,
            image_url=raw.image_url,
            rating=getattr(raw, "rating", None),
            reviews=getattr(raw, "reviews", None),
            presentacion=getattr(raw, "presentacion", None),
        )

    @staticmethod
    def _default_currency_for_source(source: str) -> str:
        return {"agrofy": "ARS", "mercadolibre": "MXN"}.get(source, "MXN")

    @staticmethod
    def _compute_hash(source: str, name: str, active_ingredient: str, url: str) -> str:
        key = f"{source}|{name.lower().strip()}|{active_ingredient.lower().strip()}|{url}"
        return hashlib.sha256(key.encode()).hexdigest()
