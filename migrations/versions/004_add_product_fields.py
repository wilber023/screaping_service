"""Add rating, reviews, presentacion to products

Revision ID: 004
Revises: 003
Create Date: 2026-06-25 00:00:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("rating", sa.Float(), nullable=True))
    op.add_column("products", sa.Column("reviews", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("presentacion", sa.String(256), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "presentacion")
    op.drop_column("products", "reviews")
    op.drop_column("products", "rating")
