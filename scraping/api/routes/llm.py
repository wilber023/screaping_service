from __future__ import annotations
from datetime import datetime
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from scraping.api.dependencies import get_db, get_current_user
from scraping.models.product import Product
from scraping.schemas.auth import TokenPayload
from scraping.schemas.product import LLMCatalogResponse, LLMProductSummary
from scraping.storage.redis_client import cache_get, cache_set

router = APIRouter()

_CACHE_TTL = 3600  # 1 hour for LLM context (changes slowly)


@router.get(
    "/context",
    response_model=LLMCatalogResponse,
    summary="Compact catalog context optimized for LLM injection",
)
def get_llm_context(
    crop: str = Query(None, description="Limit context to a specific crop"),
    limit: int = Query(200, ge=1, le=500, description="Max products to include"),
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
):
    cache_key = f"llm:context:crop={crop}:limit={limit}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    query = db.query(Product).filter(Product.is_active == True)
    if crop:
        query = query.filter(Product.target_crops.contains([crop.lower()]))

    db_products = (
        query.order_by(Product.scraped_at.desc())
        .limit(limit)
        .all()
    )

    # Build compact summaries
    summaries: List[LLMProductSummary] = []
    by_crop: Dict[str, List[str]] = {}
    by_type: Dict[str, int] = {}

    for p in db_products:
        price_usd = None
        if p.price_amount and p.price_currency == "MXN":
            price_usd = round(p.price_amount / 17.5, 2)
        elif p.price_amount and p.price_currency == "USD":
            price_usd = p.price_amount

        summary = LLMProductSummary(
            id=p.id,
            name=p.name,
            type=p.product_type,
            active_ingredient=p.active_ingredient,
            manufacturer=p.manufacturer,
            crops=p.target_crops or [],
            diseases=p.target_diseases or [],
            price_usd=price_usd,
            stock=p.stock_status,
        )
        summaries.append(summary)

        for c in (p.target_crops or []):
            by_crop.setdefault(c, [])
            if p.name not in by_crop[c]:
                by_crop[c].append(p.name)

        ptype = p.product_type or "otro"
        by_type[ptype] = by_type.get(ptype, 0) + 1

    result = LLMCatalogResponse(
        total_products=len(summaries),
        by_crop={k: v[:10] for k, v in by_crop.items()},  # cap product names per crop
        by_type=by_type,
        products=summaries,
        generated_at=datetime.utcnow(),
    )

    cache_set(cache_key, result.model_dump(), ttl_seconds=_CACHE_TTL)
    return result
