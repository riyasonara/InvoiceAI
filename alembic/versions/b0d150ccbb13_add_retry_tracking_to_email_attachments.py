"""add retry tracking to email attachments

Revision ID: b0d150ccbb13
Revises: ad91f789bba6
Create Date: 2026-08-21 22:37:59.612723

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b0d150ccbb13'
down_revision: Union[str, Sequence[str], None] = 'ad91f789bba6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default backfills existing rows to 0 (required: NOT NULL on a
    # non-empty table). The 6 unrelated "removed index" ops autogenerate
    # produced here were stripped — those indexes are real, just never
    # mirrored as index=True on the model columns; not this migration's job.
    op.add_column('email_attachments', sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('email_attachments', sa.Column('next_retry_at', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('email_attachments', 'next_retry_at')
    op.drop_column('email_attachments', 'retry_count')
