"""Add amazon and cofepris to productsource enum

Revision ID: 003
Revises: 002
Create Date: 2026-06-25 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE productsource ADD VALUE IF NOT EXISTS 'cofepris'")
    op.execute("ALTER TYPE productsource ADD VALUE IF NOT EXISTS 'amazon'")


def downgrade() -> None:
    pass
