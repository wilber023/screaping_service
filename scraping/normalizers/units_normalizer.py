from __future__ import annotations
import re
from typing import Optional, Tuple

_UNIT_PATTERNS = [
    (r"(\d+(?:\.\d+)?)\s*kg\b", "kg", 1.0),
    (r"(\d+(?:\.\d+)?)\s*g\b", "g", 0.001),
    (r"(\d+(?:\.\d+)?)\s*mg\b", "mg", 0.000001),
    (r"(\d+(?:\.\d+)?)\s*l(?:itros?)?\b", "L", 1.0),
    (r"(\d+(?:\.\d+)?)\s*ml\b", "mL", 0.001),
    (r"(\d+(?:\.\d+)?)\s*oz\b", "oz", 0.02835),
    (r"(\d+(?:\.\d+)?)\s*lb\b", "lb", 0.4536),
    (r"(\d+(?:\.\d+)?)\s*fl\.?\s*oz\b", "fl oz", 0.02957),
    (r"(\d+(?:\.\d+)?)\s*gal(?:ones?)?\b", "gal", 3.785),
    (r"(\d+(?:\.\d+)?)\s*ton(?:eladas?)?\b", "ton", 1000.0),
]


class UnitsNormalizer:
    """Extracts quantity + unit from a product name or description,
    and normalizes weight to kg and volume to L."""

    @staticmethod
    def extract(text: str) -> Tuple[Optional[float], Optional[str]]:
        lower = text.lower()
        for pattern, unit, factor in _UNIT_PATTERNS:
            match = re.search(pattern, lower)
            if match:
                raw_qty = float(match.group(1))
                if unit in ("g", "mg", "oz", "lb", "ton"):
                    return round(raw_qty * factor, 6), "kg"
                if unit in ("mL", "fl oz", "gal"):
                    return round(raw_qty * factor, 6), "L"
                return raw_qty, unit
        return None, None

    @staticmethod
    def normalize_name(name: str) -> str:
        """Strip trailing whitespace and normalize common encoding issues."""
        name = name.strip()
        name = re.sub(r"\s+", " ", name)
        return name
