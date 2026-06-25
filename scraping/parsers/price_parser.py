from __future__ import annotations
import re
from typing import Optional, Tuple

_CURRENCY_PATTERNS = {
    "MXN": [r"\$", r"mxn", r"pesos? mexicanos?"],
    "USD": [r"usd", r"u\.s\.\$", r"dólares? americanos?"],
    "ARS": [r"ars", r"\$\s*ar", r"pesos? argentinos?"],
    "COP": [r"cop", r"pesos? colombianos?"],
    "BRL": [r"brl", r"r\$", r"reais?"],
}

# Two alternatives (tried left-to-right by the engine):
# 1. Thousands-formatted: 1-3 digits + one or more sep+3digit groups + optional decimal
# 2. Plain number: any digits + optional decimal
# This correctly handles "1500,00" (option 2 → 1500.0) vs "1,500" (option 1 → 1500)
_AMOUNT_RE = re.compile(
    r"(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,4})?|\d+(?:[.,]\d{1,4})?)"
)


class PriceParser:
    """Extracts a numeric amount and currency code from a raw price string."""

    @staticmethod
    def parse(
        raw: Optional[str],
        default_currency: str = "MXN",
        amount_override: Optional[float] = None,
        currency_override: Optional[str] = None,
    ) -> Tuple[Optional[float], str]:
        if amount_override is not None and currency_override:
            return amount_override, currency_override

        if not raw:
            return amount_override, currency_override or default_currency

        amount = PriceParser._extract_amount(raw)
        currency = PriceParser._detect_currency(raw, default_currency)
        return amount, currency

    @staticmethod
    def _extract_amount(raw: str) -> Optional[float]:
        raw_clean = raw.strip()
        match = _AMOUNT_RE.search(raw_clean)
        if not match:
            return None
        num_str = match.group(1)
        # Normalize: remove thousands separators (. or ,) then parse decimal
        # Handle formats: 1.234,56 | 1,234.56 | 1234.56 | 1234,56
        if re.search(r"\d{1,3}[.,]\d{3}[.,]\d", num_str):
            # e.g. "1.234,56" or "1,234.56"
            if "." in num_str and "," in num_str:
                if num_str.rindex(".") < num_str.rindex(","):
                    num_str = num_str.replace(".", "").replace(",", ".")
                else:
                    num_str = num_str.replace(",", "")
        elif "," in num_str and "." not in num_str:
            # e.g. "1,234" (thousands) or "1,50" (decimal)
            parts = num_str.split(",")
            if len(parts) == 2 and len(parts[1]) <= 2:
                num_str = num_str.replace(",", ".")
            else:
                num_str = num_str.replace(",", "")
        elif "." in num_str and "," not in num_str:
            parts = num_str.split(".")
            if len(parts) == 2 and len(parts[1]) > 2:
                num_str = num_str.replace(".", "")

        try:
            return float(num_str)
        except ValueError:
            return None

    @staticmethod
    def _detect_currency(raw: str, default: str) -> str:
        lower = raw.lower()
        for currency, patterns in _CURRENCY_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, lower):
                    return currency
        return default
