from __future__ import annotations
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from scraping.api.routes import products, crops, diseases, admin, llm, auth
from scraping.config import settings
from scraping.utils.logging_config import setup_logging

setup_logging("DEBUG" if settings.DEBUG else "INFO")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AgroGraph Scraping API",
    description=(
        "Catálogo dinámico de productos fitosanitarios (fungicidas, insecticidas, "
        "herbicidas, fertilizantes) para los 14 cultivos principales de AgroGraph. "
        "Todos los endpoints requieren X-API-Key + Authorization: Bearer <JWT>."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s %s — %s", request.method, request.url, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "message": "An unexpected error occurred"},
    )


@app.get("/health", tags=["health"], summary="Health check (no auth required)")
def health_check():
    return {"status": "ok", "service": "agrograph-scraping-api"}


app.include_router(auth.router,     prefix="/auth",     tags=["auth"])
app.include_router(products.router, prefix="/products", tags=["products"])
app.include_router(crops.router,    prefix="/crops",    tags=["crops"])
app.include_router(diseases.router, prefix="/diseases", tags=["diseases"])
app.include_router(llm.router,      prefix="/llm",      tags=["llm"])
app.include_router(admin.router,    prefix="/admin",    tags=["admin"])
