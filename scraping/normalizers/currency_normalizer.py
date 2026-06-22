from __future__ import annotations
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Static exchange rates to MXN (updated manually / via config)
# In production, these should be refreshed from an exchange-rate API.
_RATES_TO_MXN: dict[str, float] = {
    "MXN": 1.0,
    "USD": 17.5,
    "ARS": 0.012,    # ~MXN per ARS (approximate)
    "COP": 0.0043,
    "BRL": 3.5,
    "EUR": 19.0,
    "PEN": 4.7,
    "CLP": 0.020,
}


class CurrencyNormalizer:
    """Normalizes any supported currency amount to MXN (or USD)."""

    @staticmethod
    def to_mxn(
        amount: Optional[float], currency: str
    ) -> Tuple[Optional[float], str]:
        if amount is None:
            return None, currency
        rate = _RATES_TO_MXN.get(currency.upper())
        if rate is None:
            logger.debug("Unknown currency %s, keeping as-is", currency)
            return amount, currency
        return round(amount * rate, 2), "MXN"

    @staticmethod
    def to_usd(
        amount: Optional[float], currency: str
    ) -> Tuple[Optional[float], str]:
        if amount is None:
            return None, currency
        mxn_amount, _ = CurrencyNormalizer.to_mxn(amount, currency)
        if mxn_amount is None:
            return None, "USD"
        usd_rate = _RATES_TO_MXN.get("USD", 17.5)
        return round(mxn_amount / usd_rate, 4), "USD"

    @staticmethod
    def normalize(
        amount: Optional[float],
        original_currency: str,
        target: str = "MXN",
    ) -> Tuple[Optional[float], str]:
        target = target.upper()
        if target == "MXN":
            return CurrencyNormalizer.to_mxn(amount, original_currency)
        if target == "USD":
            return CurrencyNormalizer.to_usd(amount, original_currency)
        return amount, original_currency
