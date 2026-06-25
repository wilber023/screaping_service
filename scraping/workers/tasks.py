from __future__ import annotations
import logging
from datetime import datetime
from typing import Any, Dict

from scraping.workers.celery_worker import celery_app
from scraping.scrapers import AgrofyScraper, MercadoLibreScraper, SyngentaScraper, BayerScraper, BasfScraper, CofeprisScraper
from scraping.parsers import ProductParser
from scraping.normalizers import ProductNormalizer
from scraping.storage.database import SessionLocal
from scraping.storage.redis_client import cache_delete_pattern
from scraping.storage.s3_client import s3_store
from scraping.models.product import Product
from scraping.models.price_history import PriceHistory

logger = logging.getLogger(__name__)

_SCRAPER_MAP = {
    "agrofy": AgrofyScraper,
    "mercadolibre": MercadoLibreScraper,
    "syngenta": SyngentaScraper,
    "bayer": BayerScraper,
    "basf": BasfScraper,
    "cofepris": CofeprisScraper,
}


@celery_app.task(
    name="scraping.workers.tasks.run_scraper",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def run_scraper(self, source: str) -> Dict[str, Any]:
    """Run a full scrape cycle for one source, persist results, invalidate cache."""
    scraper_cls = _SCRAPER_MAP.get(source)
    if not scraper_cls:
        return {"status": "error", "message": f"Unknown source: {source}"}

    logger.info("Starting scrape: source=%s task_id=%s", source, self.request.id)
    start = datetime.utcnow()

    try:
        scraper = scraper_cls()
        raw_products = scraper._safe_scrape()
    except Exception as exc:
        logger.error("Scraper crashed source=%s: %s", source, exc, exc_info=True)
        raise self.retry(exc=exc)

    saved = 0
    updated = 0
    errors = 0

    db = SessionLocal()
    try:
        for raw in raw_products:
            try:
                # Archive HTML snapshot to S3
                if raw.html_snapshot:
                    s3_store.save_snapshot(source, raw.source_url, raw.html_snapshot)

                # Parse
                parsed = ProductParser.parse(raw)
                if not parsed:
                    continue

                # Normalize
                normalized = ProductNormalizer.normalize(parsed)
                if not normalized:
                    continue

                # Upsert by hash_dedup
                existing = (
                    db.query(Product)
                    .filter(Product.hash_dedup == normalized.hash_dedup)
                    .first()
                )

                if existing:
                    # Check if price changed — if so, record history
                    if (
                        normalized.price_amount is not None
                        and existing.price_amount != normalized.price_amount
                    ):
                        history = PriceHistory(
                            product_id=existing.id,
                            amount=normalized.price_amount,
                            currency=normalized.price_currency,
                            original_currency=normalized.price_original_currency or normalized.price_currency,
                            recorded_at=normalized.scraped_at,
                        )
                        db.add(history)

                    # Update mutable fields
                    existing.price_amount = normalized.price_amount
                    existing.price_currency = normalized.price_currency
                    existing.price_original_currency = normalized.price_original_currency
                    existing.price_last_updated = normalized.price_last_updated
                    existing.stock_status = normalized.stock_status
                    existing.stock_quantity = normalized.stock_quantity
                    existing.scraped_at = normalized.scraped_at
                    existing.is_active = True
                    updated += 1
                else:
                    product = Product(
                        id=normalized.id,
                        source=normalized.source,
                        source_url=normalized.source_url,
                        name=normalized.name,
                        manufacturer=normalized.manufacturer,
                        active_ingredient=normalized.active_ingredient,
                        product_type=normalized.product_type,
                        target_crops=normalized.target_crops,
                        target_diseases=normalized.target_diseases,
                        price_amount=normalized.price_amount,
                        price_currency=normalized.price_currency,
                        price_original_currency=normalized.price_original_currency,
                        price_last_updated=normalized.price_last_updated,
                        stock_status=normalized.stock_status,
                        stock_quantity=normalized.stock_quantity,
                        availability_regions=normalized.availability_regions,
                        scraped_at=normalized.scraped_at,
                        hash_dedup=normalized.hash_dedup,
                        image_url=getattr(normalized, "image_url", None),
                    )
                    db.add(product)

                    if normalized.price_amount is not None:
                        history = PriceHistory(
                            product_id=normalized.id,
                            amount=normalized.price_amount,
                            currency=normalized.price_currency,
                            original_currency=normalized.price_original_currency or normalized.price_currency,
                            recorded_at=normalized.scraped_at,
                        )
                        db.add(history)

                    saved += 1

            except Exception as exc:
                logger.warning("Failed to persist product source=%s name=%s: %s", source, getattr(raw, "name", "?"), exc)
                errors += 1
                db.rollback()

        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("DB commit failed source=%s: %s", source, exc, exc_info=True)
        raise
    finally:
        db.close()

    # Invalidate all product-related Redis cache
    cache_delete_pattern("products:*")
    cache_delete_pattern("crops:*")
    cache_delete_pattern("diseases:*")
    cache_delete_pattern("llm:context")

    elapsed = (datetime.utcnow() - start).total_seconds()
    result = {
        "status": "ok",
        "source": source,
        "scraped": len(raw_products),
        "saved": saved,
        "updated": updated,
        "errors": errors,
        "elapsed_seconds": elapsed,
        "finished_at": datetime.utcnow().isoformat(),
    }
    logger.info("Scrape complete: %s", result)
    return result


@celery_app.task(name="scraping.workers.tasks.run_all_scrapers")
def run_all_scrapers() -> Dict[str, Any]:
    """Trigger all scrapers sequentially (used for manual full refresh)."""
    results = {}
    for source in _SCRAPER_MAP:
        task = run_scraper.apply_async(args=[source], queue="scraping")
        results[source] = task.id
    return {"status": "triggered", "tasks": results}
