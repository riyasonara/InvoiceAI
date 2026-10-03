"""add reviewed flag to invoices

Revision ID: d412dcfb803a
Revises: b0d150ccbb13
Create Date: 2026-10-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd412dcfb803a'
down_revision: Union[str, Sequence[str], None] = 'b0d150ccbb13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Human-review gate. server_default='false' backfills existing rows to
    "already reviewed" — fairer than marking historical invoices as newly
    needing review. New rows get False from the application/model default.
    The unrelated 'drop_index' ops autogenerate produced were stripped (those
    indexes are real, just not declared index=True on the models)."""
    op.add_column(
        "invoices",
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Historical rows predate review; treat them as already reviewed.
    op.execute("UPDATE invoices SET reviewed = true")


def downgrade() -> None:
    op.drop_column("invoices", "reviewed")
