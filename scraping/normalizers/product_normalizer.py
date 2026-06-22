from __future__ import annotations
import logging
import uuid
from datetime import datetime
from typing import List, Optional

from scraping.normalizers.currency_normalizer import CurrencyNormalizer
from scraping.normalizers.units_normalizer import UnitsNormalizer
from scraping.parsers.product_parser import ParsedProduct

logger = logging.getLogger(__name__)

# Canonical 14 crops (also accept common typos/aliases)
_CROP_ALIASES: dict[str, str] = {
    "calabaza": "calabaza", "squash": "calabaza", "pumpkin": "calabaza",
    "frijol": "frijol", "frijoles": "frijol", "bean": "frijol", "beans": "frijol",
    "manzana": "manzana", "apple": "manzana",
    "mora": "mora", "blackberry": "mora",
    "cereza": "cereza", "cherry": "cereza",
    "maíz": "maíz", "maiz": "maíz", "corn": "maíz", "maize": "maíz",
    "durazno": "durazno", "peach": "durazno", "melocotón": "durazno",
    "uva": "uva", "grape": "uva", "vid": "uva",
    "naranja": "naranja", "orange": "naranja",
    "pimienta": "pimienta", "pepper": "pimienta", "pimiento": "pimienta",
    "papa": "papa", "potato": "papa", "patata": "papa",
    "frambuesa": "frambuesa", "raspberry": "frambuesa",
    "soja": "soja", "soy": "soja", "soybean": "soja", "soya": "soja",
    "fresa": "fresa", "strawberry": "fresa",
    "tomate": "tomate", "tomato": "tomate", "jitomate": "tomate",
}

_VALID_CROPS = set(_CROP_ALIASES.values())

_PRODUCT_TYPE_MAP: dict[str, str] = {
    "fungicida": "fungicida", "fungicide": "fungicida",
    "insecticida": "insecticida", "insecticide": "insecticida",
    "herbicida": "herbicida", "herbicide": "herbicida",
    "fertilizante": "fertilizante", "fertilizer": "fertilizante",
    "abono": "fertilizante", "biofertilizante": "fertilizante",
    "nutricion": "fertilizante", "nutrición": "fertilizante",
    "acaricida": "insecticida", "nematicida": "insecticida",
    "bactericida": "fungicida",
    "otro": "otro",
}


class NormalizedProduct:
    __slots__ = (
        "id", "source", "source_url", "name", "manufacturer", "active_ingredient",
        "product_type", "target_crops", "target_diseases",
        "price_amount", "price_currency", "price_original_currency",
        "price_last_updated", "stock_status", "stock_quantity",
        "availability_regions", "scraped_at", "hash_dedup",
    )

    def __init__(self, **kwargs) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


class ProductNormalizer:
    """Converts a ParsedProduct into a fully normalized NormalizedProduct."""

    @staticmethod
    def normalize(parsed: ParsedProduct) -> Optional[NormalizedProduct]:
        if not parsed.name:
            return None

        name = UnitsNormalizer.normalize_name(parsed.name)
        product_type = ProductNormalizer._normalize_type(parsed.product_type_raw)
        target_crops = ProductNormalizer._normalize_crops(parsed.target_crops_raw, name)
        target_diseases = ProductNormalizer._normalize_diseases(parsed.target_diseases_raw)

        normalized_amount, normalized_currency = CurrencyNormalizer.normalize(
            parsed.price_amount, parsed.price_currency, target="MXN"
        )

        return NormalizedProduct(
            id=str(uuid.uuid4()),
            source=parsed.source,
            source_url=parsed.source_url,
            name=name,
            manufacturer=parsed.manufacturer,
            active_ingredient=parsed.active_ingredient,
            product_type=product_type,
            target_crops=target_crops,
            target_diseases=target_diseases,
            price_amount=normalized_amount,
            price_currency=normalized_currency,
            price_original_currency=parsed.price_currency,
            price_last_updated=parsed.scraped_at if normalized_amount else None,
            stock_status=parsed.stock_status,
            stock_quantity=parsed.stock_quantity,
            availability_regions=parsed.availability_regions,
            scraped_at=parsed.scraped_at,
            hash_dedup=parsed.hash_dedup,
        )

    @staticmethod
    def _normalize_type(raw: Optional[str]) -> str:
        if not raw:
            return "otro"
        lower = raw.lower().strip()
        for key, value in _PRODUCT_TYPE_MAP.items():
            if key in lower:
                return value
        return "otro"

    @staticmethod
    def _normalize_crops(crops_raw: List[str], name: str = "") -> List[str]:
        found: set[str] = set()
        all_text = " ".join(crops_raw + [name]).lower()
        for alias, canonical in _CROP_ALIASES.items():
            if alias in all_text:
                found.add(canonical)
        return sorted(found)

    @staticmethod
    def _normalize_diseases(diseases_raw: List[str]) -> List[str]:
        cleaned = []
        seen: set[str] = set()
        for d in diseases_raw:
            d_clean = d.strip().lower()[:100]
            if d_clean and d_clean not in seen:
                seen.add(d_clean)
                cleaned.append(d.strip()[:100])
        return cleaned[:30]
