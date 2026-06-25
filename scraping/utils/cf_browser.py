"""
Cloudflare Browser Rendering — renderiza páginas con Chromium real.
Free tier: 10 min/día, 1 req/10s.
Docs: https://developers.cloudflare.com/browser-rendering/
"""
from __future__ import annotations
import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_ENDPOINT = "https://api.cloudflare.com/client/v4/accounts/{account_id}/browser-rendering/content"
_last_call: float = 0.0
_MIN_INTERVAL = 11.0  # free tier: 1 req/10s


def _get_credentials():
    from scraping.config import settings
    return settings.CLOUDFLARE_ACCOUNT_ID, settings.CLOUDFLARE_API_TOKEN


def is_available() -> bool:
    account_id, api_token = _get_credentials()
    return bool(account_id and api_token)


def render_page(
    url: str,
    wait_selector: Optional[str] = None,
    timeout_ms: int = 60000,
) -> str:
    """
    Renderiza una URL con Chromium de Cloudflare y devuelve el HTML completo.
    Aplica rate-limiting automático (1 req/10s en free tier).
    """
    global _last_call

    account_id, api_token = _get_credentials()
    if not account_id or not api_token:
        raise RuntimeError("CLOUDFLARE_ACCOUNT_ID y CLOUDFLARE_API_TOKEN no configurados")

    # Rate limiting: espera si la última llamada fue hace menos de 11 segundos
    elapsed = time.time() - _last_call
    if elapsed < _MIN_INTERVAL:
        wait = _MIN_INTERVAL - elapsed
        logger.debug("CF Browser rate-limit: esperando %.1fs", wait)
        time.sleep(wait)

    payload = {
        "url": url,
        "gotoOptions": {
            "waitUntil": "domcontentloaded",
            "timeout": timeout_ms,
        },
        "rejectResourceTypes": ["image", "font", "media"],
        "bestAttempt": True,
    }

    if wait_selector:
        # Espera a que aparezcan los cards/contenido específicos del sitio
        payload["waitForSelector"] = {
            "selector": wait_selector,
            "timeout": 30000,
        }
    else:
        # Espera a que #challenge-form desaparezca: cuando el challenge CF se resuelve
        # y redirige al sitio real, ese elemento deja de existir
        payload["waitForSelector"] = {
            "selector": "#challenge-form, #cf-challenge-running",
            "hidden": True,
            "timeout": 30000,
        }

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }

    endpoint = _ENDPOINT.format(account_id=account_id)

    try:
        _last_call = time.time()
        with httpx.Client(timeout=90) as client:
            resp = client.post(endpoint, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        if not data.get("success"):
            errors = data.get("errors", [])
            raise RuntimeError(f"CF Browser error: {errors}")

        html = data.get("result", "")
        logger.info("CF Browser rendered %s (%d bytes)", url, len(html))
        return html

    except httpx.HTTPStatusError as exc:
        logger.error("CF Browser HTTP error %s for %s: %s", exc.response.status_code, url, exc)
        raise
    except Exception as exc:
        logger.error("CF Browser failed for %s: %s", url, exc)
        raise