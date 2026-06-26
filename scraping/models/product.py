from __future__ import annotations
import uuid
import enum
from datetime import datetime

from sqlalchemy import String, Float, Integer, Boolean, DateTime, JSON
from sqlalchemy import Enum as SAEnum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from scraping.models.base import Base


class ProductSource(str, enum.Enum):
    agrofy = "agrofy"
    mercadolibre = "mercadolibre"
    syngenta = "syngenta"
    bayer = "bayer"
    basf = "basf"
    cofepris = "cofepris"
    amazon = "amazon"


class ProductType(str, enum.Enum):
    fungicida = "fungicida"
    insecticida = "insecticida"
    herbicida = "herbicida"
    fertilizante = "fertilizante"
    otro = "otro"


class StockStatus(str, enum.Enum):
    in_stock = "in_stock"
    out_of_stock = "out_of_stock"
    unknown = "unknown"


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("hash_dedup", name="uq_products_hash_dedup"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    source: Mapped[str] = mapped_column(
        SAEnum(ProductSource, name="productsource"), nullable=False, index=True
    )
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    manufacturer: Mapped[str] = mapped_column(String(256), nullable=True)
    active_ingredient: Mapped[str] = mapped_column(String(512), nullable=True)
    product_type: Mapped[str] = mapped_column(
        SAEnum(ProductType, name="producttype"),
        nullable=False,
        default=ProductType.otro,
        index=True,
    )
    target_crops: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    target_diseases: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Price fields (denormalized for fast reads)
    price_amount: Mapped[float] = mapped_column(Float, nullable=True)
    price_currency: Mapped[str] = mapped_column(String(10), nullable=True)
    price_original_currency: Mapped[str] = mapped_column(String(10), nullable=True)
    price_last_updated: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # Stock fields
    stock_status: Mapped[str] = mapped_column(
        SAEnum(StockStatus, name="stockstatus"),
        nullable=False,
        default=StockStatus.unknown,
    )
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=True)

    availability_regions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    hash_dedup: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    image_url: Mapped[str] = mapped_column(String(2048), nullable=True)
    rating: Mapped[float] = mapped_column(Float, nullable=True)
    reviews: Mapped[int] = mapped_column(Integer, nullable=True)
    presentacion: Mapped[str] = mapped_column(String(256), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
