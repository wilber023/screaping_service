from __future__ import annotations
from typing import List, Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from scraping.api.dependencies import get_db, get_current_user, require_full_access
from scraping.models.product import Product
from scraping.models.price_history import PriceHistory
from scraping.schemas.auth import TokenPayload, UserType
from scraping.schemas.product import (
    ProductListResponse,
    ProductResponse,
    PriceHistoryResponse,
    PriceHistoryItem,
)
from scraping.storage.redis_client import cache_get, cache_set

router = APIRouter()

_CACHE_TTL = 1800  # 30 minutes


def _build_cache_key(prefix: str, **kwargs) -> str:
    parts = "&".join(f"{k}={v}" for k, v in sorted(kwargs.items()) if v is not None)
    return f"{prefix}:{parts}"


@router.get("/cultivo/{cultivo}", response_model=ProductListResponse, summary="Productos por cultivo")
def productos_por_cultivo(
    cultivo: str,
    product_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
):
    return list_products(
        crop=cultivo, disease=None, product_type=product_type,
        manufacturer=None, source=None, active_ingredient=None,
        page=page, per_page=per_page, db=db, current_user=current_user,
    )


@router.get("/enfermedad/{enfermedad}", response_model=ProductListResponse, summary="Productos por enfermedad")
def productos_por_enfermedad(
    enfermedad: str,
    product_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
):
    return list_products(
        crop=None, disease=enfermedad, product_type=product_type,
        manufacturer=None, source=None, active_ingredient=None,
        page=page, per_page=per_page, db=db, current_user=current_user,
    )


@router.get("", response_model=ProductListResponse, summary="List products")
def list_products(
    crop: Optional[str] = Query(None, description="Filter by crop (e.g. tomate)"),
    disease: Optional[str] = Query(None, description="Filter by disease name (partial match)"),
    product_type: Optional[str] = Query(None, description="Filter by type: fungicida, insecticida, herbicida, fertilizante"),
    manufacturer: Optional[str] = Query(None, description="Filter by manufacturer (partial match)"),
    source: Optional[str] = Query(None, description="Filter by source"),
    active_ingredient: Optional[str] = Query(None, description="Filter by active ingredient (partial match)"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
):
    cache_key = _build_cache_key(
        "products:list",
        crop=crop, disease=disease, type=product_type,
        manufacturer=manufacturer, source=source,
        active_ingredient=active_ingredient,
        page=page, per_page=per_page,
        user_type=current_user.user_type,
    )
    cached = cache_get(cache_key)
    if cached:
        return cached

    query = db.query(Product).filter(Product.is_active == True)

    if crop:
        query = query.filter(sa.cast(Product.target_crops, sa.Text).ilike(f'%{crop}%'))
    if product_type:
        query = query.filter(Product.product_type == product_type)
    if manufacturer:
        query = query.filter(Product.manufacturer.ilike(f"%{manufacturer}%"))
    if source:
        query = query.filter(Product.source == source)
    if disease:
        query = query.filter(sa.cast(Product.target_diseases, sa.Text).ilike(f"%{disease}%"))
    if active_ingredient:
        query = query.filter(Product.active_ingredient.ilike(f"%{active_ingredient}%"))

    total = query.count()
    offset = (page - 1) * per_page
    db_products = query.order_by(Product.scraped_at.desc()).offset(offset).limit(per_page).all()

    items = [_serialize_product(p, current_user.user_type) for p in db_products]
    result = ProductListResponse(total=total, page=page, per_page=per_page, items=items)

    cache_set(cache_key, result.model_dump(), ttl_seconds=_CACHE_TTL)
    return result


@router.get("/{product_id}", response_model=ProductResponse, summary="Get product detail")
def get_product(
    product_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
):
    cache_key = f"products:detail:{product_id}:{current_user.user_type}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    product = db.query(Product).filter(Product.id == product_id, Product.is_active == True).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    result = _serialize_product(product, current_user.user_type)
    cache_set(cache_key, result.model_dump(), ttl_seconds=_CACHE_TTL)
    return result


@router.get(
    "/{product_id}/price-history",
    response_model=PriceHistoryResponse,
    summary="Price history for a product (agricultor_experimentado or admin only)",
)
def get_price_history(
    product_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(require_full_access),
):
    product = db.query(Product).filter(Product.id == product_id, Product.is_active == True).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    history_rows = (
        db.query(PriceHistory)
        .filter(PriceHistory.product_id == product_id)
        .order_by(PriceHistory.recorded_at.asc())
        .all()
    )

    return PriceHistoryResponse(
        product_id=product_id,
        product_name=product.name,
        history=[
            PriceHistoryItem(
                amount=h.amount,
                currency=h.currency,
                original_currency=h.original_currency,
                recorded_at=h.recorded_at,
            )
            for h in history_rows
        ],
    )


def _serialize_product(product: Product, user_type: UserType) -> ProductResponse:
    from scraping.schemas.product import PriceInfo, StockInfo, ProductSource, ProductType, StockStatus

    # aprendiz sees no price or extended stock details
    if user_type == UserType.aprendiz:
        price = PriceInfo()
        stock = StockInfo(status=product.stock_status)
    else:
        price = PriceInfo(
            amount=product.price_amount,
            currency=product.price_currency,
            original_currency=product.price_original_currency,
            last_updated=product.price_last_updated,
        )
        stock = StockInfo(
            status=product.stock_status,
            quantity=product.stock_quantity,
        )

    return ProductResponse(
        id=product.id,
        source=product.source,
        source_url=product.source_url,
        name=product.name,
        manufacturer=product.manufacturer,
        active_ingredient=product.active_ingredient,
        product_type=product.product_type,
        target_crops=product.target_crops or [],
        target_diseases=product.target_diseases or [],
        price=price,
        stock=stock,
        availability_regions=product.availability_regions or [],
        scraped_at=product.scraped_at,
        image_url=product.image_url,
        rating=product.rating,
        reviews=product.reviews,
        presentacion=product.presentacion,
    )
