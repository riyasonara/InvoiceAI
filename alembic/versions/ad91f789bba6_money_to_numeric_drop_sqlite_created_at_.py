"""money to numeric, drop sqlite created_at trigger, add indexes

Revision ID: ad91f789bba6
Revises: 93d372c238b8
Create Date: 2026-08-03 01:03:14.248204

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ad91f789bba6'
down_revision: Union[str, Sequence[str], None] = '93d372c238b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Sprint 1 data-foundation fixes.

    1. Money -> NUMERIC(14,2). Floats cannot represent decimal currency
       exactly, and the error compounds when summed for reporting.
    2. Drop the SQLite-only `invoices_set_created_at` trigger. It would not
       exist on Postgres, leaving created_at NULL and silently breaking the
       billing usage count (every tenant would appear to have used 0
       invoices). created_at is now set by the application layer instead.
    3. Backfill any NULL created_at so the billing query can never miss rows.
    4. Add the indexes every hot query needs; only one existed before.
    """
    bind = op.get_bind()

    # --- 1. Money columns -> exact numeric ---
    with op.batch_alter_table("invoices") as batch:
        batch.alter_column("gst", type_=sa.Numeric(14, 2), existing_type=sa.Float())
        batch.alter_column("total", type_=sa.Numeric(14, 2), existing_type=sa.Float())

    # --- 2. Remove the dialect-specific trigger (SQLite only; no-op elsewhere) ---
    if bind.dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS invoices_set_created_at")

    # --- 3. Backfill missing timestamps so usage metering can't undercount ---
    op.execute(
        "UPDATE invoices SET created_at = '1970-01-01 00:00:00' "
        "WHERE created_at IS NULL OR created_at = ''"
    )

    # --- 4. Indexes for the org-scoped hot paths ---
    op.create_index("ix_invoices_org_created", "invoices", ["org_id", "created_at"])
    op.create_index("ix_invoices_org_status", "invoices", ["org_id", "status"])
    op.create_index("ix_users_org", "users", ["org_id"])
    op.create_index("ix_email_messages_org", "email_messages", ["org_id"])
    op.create_index("ix_email_attachments_org_status", "email_attachments", ["org_id", "status"])
    op.create_index("ix_email_attachments_message", "email_attachments", ["email_message_id"])
    op.create_index("ix_processing_logs_org", "invoice_processing_logs", ["org_id", "attachment_id"])


def downgrade() -> None:
    """Reverse the schema changes (the created_at backfill is not undone)."""
    op.drop_index("ix_processing_logs_org", table_name="invoice_processing_logs")
    op.drop_index("ix_email_attachments_message", table_name="email_attachments")
    op.drop_index("ix_email_attachments_org_status", table_name="email_attachments")
    op.drop_index("ix_email_messages_org", table_name="email_messages")
    op.drop_index("ix_users_org", table_name="users")
    op.drop_index("ix_invoices_org_status", table_name="invoices")
    op.drop_index("ix_invoices_org_created", table_name="invoices")

    with op.batch_alter_table("invoices") as batch:
        batch.alter_column("total", type_=sa.Float(), existing_type=sa.Numeric(14, 2))
        batch.alter_column("gst", type_=sa.Float(), existing_type=sa.Numeric(14, 2))
