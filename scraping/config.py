from __future__ import annotations
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Optional


class Settings(BaseSettings):
    # Database (required)
    DATABASE_URL: str

    # Redis — optional; caching is disabled gracefully when not set
    REDIS_URL: str = ""

    # S3 — optional; snapshot archival skipped when not set
    S3_BUCKET: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_REGION: str = "us-east-1"
    S3_ENDPOINT_URL: Optional[str] = None

    # Scraping
    PROXY_LIST: str = ""
    SCRAPE_INTERVAL_HOURS: int = 6

    # Auth (required)
    API_KEY_FRONTEND: str
    API_KEY_LLM: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 1440

    # Cloudflare Browser Rendering (optional — habilita scraping anti-403)
    CLOUDFLARE_ACCOUNT_ID: str = ""
    CLOUDFLARE_API_TOKEN: str = ""

    # App
    DEBUG: bool = False

    @field_validator("PROXY_LIST")
    @classmethod
    def parse_proxy_list(cls, v: str) -> str:
        return v.strip()

    def get_proxy_list(self) -> List[str]:
        if not self.PROXY_LIST:
            return []
        return [p.strip() for p in self.PROXY_LIST.split(",") if p.strip()]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()