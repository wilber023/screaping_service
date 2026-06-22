from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


logger = logging.getLogger(__name__)


@dataclass
class RawProduct:
    """Raw product data as extracted from a source, before normalization."""
    source: str
    source_url: str
    name: str
    manufacturer: Optional[str] = None
    active_ingredient: Optional[str] = None
    product_type_raw: Optional[str] = None   # free-text, normalizer maps to enum
    target_crops_raw: List[str] = field(default_factory=list)
    target_diseases_raw: List[str] = field(default_factory=list)
    price_raw: Optional[str] = None          # free-text e.g. "$1,234.56 MXN"
    price_amount: Optional[float] = None
    price_currency: Optional[str] = None
    stock_raw: Optional[str] = None          # free-text
    availability_regions: List[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict) # any source-specific extra fields
    scraped_at: datetime = field(default_factory=datetime.utcnow)
    html_snapshot: Optional[str] = None      # raw HTML for S3 archival


class BaseScraper(ABC):
    """Abstract base for all product scrapers."""

    source: str = ""

    def __init__(self) -> None:
        self.logger = logging.getLogger(f"scraper.{self.source}")

    @abstractmethod
    def scrape(self) -> List[RawProduct]:
        """Fetch and return raw products. Implementations must be tolerant of
        network errors — catch, log, and return whatever was collected so far.
        """

    def _safe_scrape(self) -> List[RawProduct]:
        try:
            return self.scrape()
        except Exception as exc:
            self.logger.error("Scrape failed for source=%s: %s", self.source, exc, exc_info=True)
            return []
