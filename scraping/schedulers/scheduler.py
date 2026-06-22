"""
Celery Beat entry point.
The beat scheduler is started via:
    celery -A scraping.workers.celery_worker beat --loglevel=info

This module re-exports the configured celery_app so the beat process can
be started with either:
    celery -A scraping.schedulers.scheduler beat
or
    celery -A scraping.workers.celery_worker beat
"""
from scraping.workers.celery_worker import celery_app  # noqa: F401
