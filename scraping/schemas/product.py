from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ProductSource(str, Enum):
    agrofy = "agrofy"
    mercadolibre = "mercadolibre"
    syngenta = "syngenta"
    bayer = "bayer"
    basf = "basf"
    cofepris = "cofepris"
    amazon = "amazon"


class ProductType(str, Enum):
    fungicida = "fungicida"
    insecticida = "insecticida"
    herbicida = "herbicida"
    fertilizante = "fertilizante"
    otro = "otro"


class StockStatus(str, Enum):
    in_stock = "in_stock"
    out_of_stock = "out_of_stock"
    unknown = "unknown"


class PriceInfo(BaseModel):
    amount: Optional[float] = None
    currency: Optional[str] = None
    original_currency: Optional[str] = None
    last_updated: Optional[datetime] = None


class StockInfo(BaseModel):
    status: StockStatus = StockStatus.unknown
    quantity: Optional[int] = None


class ProductResponse(BaseModel):
    id: str
    source: ProductSource
    source_url: str
    name: str
    manufacturer: Optional[str] = None
    active_ingredient: Optional[str] = None
    product_type: ProductType
    target_crops: List[str] = Field(default_factory=list)
    target_diseases: List[str] = Field(default_factory=list)
    price: PriceInfo
    stock: StockInfo
    availability_regions: List[str] = Field(default_factory=list)
    scraped_at: datetime
    image_url: Optional[str] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None
    presentacion: Optional[str] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_product(cls, p: object) -> "ProductResponse":
        return cls(
            id=p.id,  # type: ignore[attr-defined]
            source=p.source,  # type: ignore[attr-defined]
            source_url=p.source_url,  # type: ignore[attr-defined]
            name=p.name,  # type: ignore[attr-defined]
            manufacturer=p.manufacturer,  # type: ignore[attr-defined]
            active_ingredient=p.active_ingredient,  # type: ignore[attr-defined]
            product_type=p.product_type,  # type: ignore[attr-defined]
            target_crops=p.target_crops or [],  # type: ignore[attr-defined]
            target_diseases=p.target_diseases or [],  # type: ignore[attr-defined]
            price=PriceInfo(
                amount=p.price_amount,  # type: ignore[attr-defined]
                currency=p.price_currency,  # type: ignore[attr-defined]
                original_currency=p.price_original_currency,  # type: ignore[attr-defined]
                last_updated=p.price_last_updated,  # type: ignore[attr-defined]
            ),
            stock=StockInfo(
                status=p.stock_status,  # type: ignore[attr-defined]
                quantity=p.stock_quantity,  # type: ignore[attr-defined]
            ),
            availability_regions=p.availability_regions or [],  # type: ignore[attr-defined]
            scraped_at=p.scraped_at,  # type: ignore[attr-defined]
            image_url=p.image_url,  # type: ignore[attr-defined]
            rating=p.rating,  # type: ignore[attr-defined]
            reviews=p.reviews,  # type: ignore[attr-defined]
            presentacion=p.presentacion,  # type: ignore[attr-defined]
        )


class ProductListResponse(BaseModel):
    total: int
    page: int
    per_page: int
    items: List[ProductResponse]


class PriceHistoryItem(BaseModel):
    amount: float
    currency: str
    original_currency: str
    recorded_at: datetime


class PriceHistoryResponse(BaseModel):
    product_id: str
    product_name: str
    history: List[PriceHistoryItem]


class LLMProductSummary(BaseModel):
    id: str
    name: str
    type: str
    active_ingredient: Optional[str] = None
    manufacturer: Optional[str] = None
    crops: List[str] = Field(default_factory=list)
    diseases: List[str] = Field(default_factory=list)
    price_usd: Optional[float] = None
    stock: str = "unknown"


class LLMCatalogResponse(BaseModel):
    total_products: int
    by_crop: dict
    by_type: dict
    products: List[LLMProductSummary]
    generated_at: datetime
