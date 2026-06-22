from __future__ import annotations
from fastapi import Header, HTTPException, status
from scraping.config import settings


def _build_valid_keys() -> dict[str, str]:
    return {
        settings.API_KEY_FRONTEND: "frontend",
        settings.API_KEY_LLM: "llm",
    }


async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    valid_keys = _build_valid_keys()
    if x_api_key not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_api_key", "message": "API key is missing or invalid"},
        )
    return valid_keys[x_api_key]
