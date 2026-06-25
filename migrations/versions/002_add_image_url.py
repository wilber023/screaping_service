"""Add image_url column to products

Revision ID: 002
Revises: 001
Create Date: 2026-06-25 00:00:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("image_url", sa.String(2048), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "image_url")
