"""Initial schema — products and price_history tables

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column(
            "source",
            sa.Enum("agrofy", "mercadolibre", "syngenta", "bayer", "basf", name="productsource"),
            nullable=False,
        ),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("manufacturer", sa.String(256), nullable=True),
        sa.Column("active_ingredient", sa.String(512), nullable=True),
        sa.Column(
            "product_type",
            sa.Enum("fungicida", "insecticida", "herbicida", "fertilizante", "otro", name="producttype"),
            nullable=False,
            server_default="otro",
        ),
        sa.Column("target_crops", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("target_diseases", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("price_amount", sa.Float(), nullable=True),
        sa.Column("price_currency", sa.String(10), nullable=True),
        sa.Column("price_original_currency", sa.String(10), nullable=True),
        sa.Column("price_last_updated", sa.DateTime(), nullable=True),
        sa.Column(
            "stock_status",
            sa.Enum("in_stock", "out_of_stock", "unknown", name="stockstatus"),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("stock_quantity", sa.Integer(), nullable=True),
        sa.Column("availability_regions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("scraped_at", sa.DateTime(), nullable=False),
        sa.Column("hash_dedup", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hash_dedup", name="uq_products_hash_dedup"),
    )
    op.create_index("ix_products_source", "products", ["source"])
    op.create_index("ix_products_product_type", "products", ["product_type"])
    op.create_index("ix_products_name", "products", ["name"])
    op.create_index("ix_products_hash_dedup", "products", ["hash_dedup"])

    op.create_table(
        "price_history",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("product_id", sa.String(36), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("original_currency", sa.String(10), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_price_history_product_recorded",
        "price_history",
        ["product_id", "recorded_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_price_history_product_recorded", table_name="price_history")
    op.drop_table("price_history")
    op.drop_index("ix_products_hash_dedup", table_name="products")
    op.drop_index("ix_products_name", table_name="products")
    op.drop_index("ix_products_product_type", table_name="products")
    op.drop_index("ix_products_source", table_name="products")
    op.drop_table("products")
    op.execute("DROP TYPE IF EXISTS productsource")
    op.execute("DROP TYPE IF EXISTS producttype")
    op.execute("DROP TYPE IF EXISTS stockstatus")
