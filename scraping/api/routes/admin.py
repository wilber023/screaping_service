from __future__ import annotations
import logging
from datetime import datetime
from typing import Dict, Any

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, status

from scraping.api.dependencies import require_admin
from scraping.schemas.auth import TokenPayload
from scraping.workers.celery_worker import celery_app

logger = logging.getLogger(__name__)
router = APIRouter()

_VALID_SOURCES = ["agrofy", "mercadolibre", "syngenta", "bayer", "basf"]


@router.post(
    "/trigger-scrape",
    summary="Manually trigger a scraper job (admin only)",
)
def trigger_scrape(
    source: str,
    _: TokenPayload = Depends(require_admin),
) -> Dict[str, Any]:
    if source not in _VALID_SOURCES and source != "all":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid source '{source}'. Valid: {_VALID_SOURCES + ['all']}",
        )

    if source == "all":
        task = celery_app.send_task(
            "scraping.workers.tasks.run_all_scrapers",
            queue="scraping",
        )
    else:
        task = celery_app.send_task(
            "scraping.workers.tasks.run_scraper",
            args=[source],
            queue="scraping",
        )

    return {
        "status": "queued",
        "source": source,
        "task_id": task.id,
        "queued_at": datetime.utcnow().isoformat(),
    }


@router.get(
    "/scrape-status",
    summary="Status of scraping jobs (admin only)",
)
def scrape_status(
    task_id: str = None,
    _: TokenPayload = Depends(require_admin),
) -> Dict[str, Any]:
    if task_id:
        result = AsyncResult(task_id, app=celery_app)
        return {
            "task_id": task_id,
            "state": result.state,
            "result": result.result if result.ready() else None,
            "traceback": result.traceback if result.failed() else None,
        }

    # Return active/reserved tasks from all workers
    inspect = celery_app.control.inspect(timeout=5)
    active = inspect.active() or {}
    reserved = inspect.reserved() or {}
    scheduled = inspect.scheduled() or {}

    return {
        "active": active,
        "reserved": reserved,
        "scheduled": scheduled,
        "queried_at": datetime.utcnow().isoformat(),
    }
