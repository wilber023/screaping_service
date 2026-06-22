from __future__ import annotations
from typing import Optional, Tuple

_IN_STOCK_KEYWORDS = [
    "in_stock", "in stock", "disponible", "en stock", "hay existencia",
    "disponibilidad inmediata", "en existencia", "available",
]
_OUT_OF_STOCK_KEYWORDS = [
    "out_of_stock", "out of stock", "agotado", "sin stock", "no disponible",
    "sold out", "no hay existencia", "fuera de stock",
]


class StockParser:
    """Converts a raw stock string into (status_enum_value, quantity)."""

    @staticmethod
    def parse(raw: Optional[str]) -> Tuple[str, Optional[int]]:
        if not raw:
            return "unknown", None

        lower = raw.strip().lower()

        if any(kw in lower for kw in _OUT_OF_STOCK_KEYWORDS):
            return "out_of_stock", 0

        if any(kw in lower for kw in _IN_STOCK_KEYWORDS):
            qty = StockParser._extract_quantity(lower)
            return "in_stock", qty

        # Try to interpret numeric quantity
        qty = StockParser._extract_quantity(lower)
        if qty is not None:
            return ("in_stock" if qty > 0 else "out_of_stock"), qty

        return "unknown", None

    @staticmethod
    def _extract_quantity(text: str) -> Optional[int]:
        import re
        match = re.search(r"(\d+)\s*(unidad|unit|pcs?|piece|item|disponible)?", text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        return None
