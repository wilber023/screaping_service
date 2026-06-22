from __future__ import annotations
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from scraping.api.dependencies import get_db, get_current_user
from scraping.models.product import Product
from scraping.schemas.auth import TokenPayload, UserType
from scraping.schemas.product import ProductListResponse, ProductResponse, PriceInfo, StockInfo
from scraping.storage.redis_client import cache_get, cache_set

router = APIRouter()

_VALID_CROPS = [
    "calabaza", "frijol", "manzana", "mora", "cereza", "maíz",
    "durazno", "uva", "naranja", "pimienta", "papa", "frambuesa",
    "soja", "fresa", "tomate",
]

_CACHE_TTL = 1800


@router.get("", summary="List all supported crops")
def list_crops(current_user: TokenPayload = Depends(get_current_user)):
    return {"crops": _VALID_CROPS}


@router.get(
    "/{crop}/treatments",
    response_model=ProductListResponse,
    summary="Products available to treat diseases of a specific crop",
)
def get_treatments_for_crop(
    crop: str,
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
):
    crop = crop.lower().strip()
    if crop not in _VALID_CROPS and crop.replace("i", "í") not in _VALID_CROPS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Crop '{crop}' not found. Valid crops: {_VALID_CROPS}",
        )

    cache_key = f"crops:{crop}:treatments:page{page}:per{per_page}:{current_user.user_type}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    query = (
        db.query(Product)
        .filter(Product.is_active == True)
        .filter(Product.target_crops.contains([crop]))
    )
    total = query.count()
    offset = (page - 1) * per_page
    db_products = query.order_by(Product.scraped_at.desc()).offset(offset).limit(per_page).all()

    from scraping.api.routes.products import _serialize_product
    items = [_serialize_product(p, current_user.user_type) for p in db_products]
    result = ProductListResponse(total=total, page=page, per_page=per_page, items=items)

    cache_set(cache_key, result.model_dump(), ttl_seconds=_CACHE_TTL)
    return result
