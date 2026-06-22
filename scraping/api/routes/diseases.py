from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from scraping.api.dependencies import get_db, get_current_user
from scraping.models.product import Product
from scraping.schemas.auth import TokenPayload
from scraping.schemas.product import ProductListResponse
from scraping.storage.redis_client import cache_get, cache_set

router = APIRouter()

_CACHE_TTL = 1800


@router.get(
    "/{disease}/products",
    response_model=ProductListResponse,
    summary="Products that treat a specific disease",
)
def get_products_for_disease(
    disease: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
):
    disease = disease.lower().strip()

    cache_key = f"diseases:{disease}:products:page{page}:per{per_page}:{current_user.user_type}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    query = (
        db.query(Product)
        .filter(Product.is_active == True)
        .filter(sa.cast(Product.target_diseases, sa.Text).ilike(f"%{disease}%"))
    )
    total = query.count()
    offset = (page - 1) * per_page
    db_products = query.order_by(Product.scraped_at.desc()).offset(offset).limit(per_page).all()

    from scraping.api.routes.products import _serialize_product
    items = [_serialize_product(p, current_user.user_type) for p in db_products]
    result = ProductListResponse(total=total, page=page, per_page=per_page, items=items)

    cache_set(cache_key, result.model_dump(), ttl_seconds=_CACHE_TTL)
    return result
