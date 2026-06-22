from __future__ import annotations
from celery import Celery
from scraping.config import settings

celery_app = Celery(
    "agrograph",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["scraping.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=86400,  # 24h

    # Beat schedule — one full cycle per source per configured interval
    beat_schedule={
        "scrape-agrofy": {
            "task": "scraping.workers.tasks.run_scraper",
            "schedule": settings.SCRAPE_INTERVAL_HOURS * 3600,
            "args": ["agrofy"],
            "options": {"queue": "scraping"},
        },
        "scrape-mercadolibre": {
            "task": "scraping.workers.tasks.run_scraper",
            "schedule": settings.SCRAPE_INTERVAL_HOURS * 3600,
            "args": ["mercadolibre"],
            "options": {"queue": "scraping"},
        },
        "scrape-syngenta": {
            "task": "scraping.workers.tasks.run_scraper",
            "schedule": settings.SCRAPE_INTERVAL_HOURS * 3600,
            "args": ["syngenta"],
            "options": {"queue": "scraping"},
        },
        "scrape-bayer": {
            "task": "scraping.workers.tasks.run_scraper",
            "schedule": settings.SCRAPE_INTERVAL_HOURS * 3600,
            "args": ["bayer"],
            "options": {"queue": "scraping"},
        },
        "scrape-basf": {
            "task": "scraping.workers.tasks.run_scraper",
            "schedule": settings.SCRAPE_INTERVAL_HOURS * 3600,
            "args": ["basf"],
            "options": {"queue": "scraping"},
        },
    },
    task_routes={
        "scraping.workers.tasks.run_scraper": {"queue": "scraping"},
    },
)
