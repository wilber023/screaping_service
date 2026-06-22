"""
Lightweight HTTP service that renders pages using Playwright.
The main worker container calls this service to get rendered HTML for
dynamic sites (Agrofy, MercadoLibre) without bundling browsers into
every worker image.

Endpoints:
    POST /render   { url, wait_for?, timeout? }  → { html }
    GET  /health                                  → { status }
"""
from __future__ import annotations
import asyncio
import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright.async_api import async_playwright, TimeoutError as PwTimeoutError

app = FastAPI(title="AgroGraph Playwright Render Service")
logger = logging.getLogger(__name__)


class RenderRequest(BaseModel):
    url: str
    wait_for: str = "networkidle"  # CSS selector OR "networkidle" / "domcontentloaded"
    timeout: int = 15000           # milliseconds


class RenderResponse(BaseModel):
    html: str
    url: str
    status: int


@app.get("/health")
def health():
    return {"status": "ok", "service": "playwright-renderer"}


@app.post("/render", response_model=RenderResponse)
async def render_page(req: RenderRequest) -> RenderResponse:
    try:
        html, final_url, status_code = await _render(req.url, req.wait_for, req.timeout)
        return RenderResponse(html=html, url=final_url, status=status_code)
    except PwTimeoutError:
        raise HTTPException(status_code=504, detail=f"Timeout rendering {req.url}")
    except Exception as exc:
        logger.error("Render error for %s: %s", req.url, exc)
        raise HTTPException(status_code=502, detail=str(exc))


async def _render(url: str, wait_for: str, timeout: int) -> tuple[str, str, int]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="es-MX",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        status_code = response.status if response else 0

        # Wait for content
        if wait_for and wait_for not in ("networkidle", "domcontentloaded", "load", "commit"):
            try:
                await page.wait_for_selector(wait_for, timeout=timeout)
            except PwTimeoutError:
                pass  # return whatever rendered so far
        elif wait_for == "networkidle":
            try:
                await page.wait_for_load_state("networkidle", timeout=timeout)
            except PwTimeoutError:
                pass

        html = await page.content()
        final_url = page.url
        await browser.close()
        return html, final_url, status_code


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
