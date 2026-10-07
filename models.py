"""SQLAlchemy ORM models — the single source of truth for the schema.

Typed with SQLAlchemy 2.0 `Mapped[...]`. Alembic autogenerates migrations by
diffing the live database against these definitions, so a change here plus
`alembic revision --autogenerate` is the only supported way to evolve schema.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


def utc_timestamp() -> str:
    """Application-side timestamp, in the format existing rows already use.

    Deliberately NOT a database trigger or server_default: the previous
    SQLite-only trigger would silently vanish on Postgres, leaving created_at
    NULL and breaking billing's monthly usage count. Generating it here works
    identically on every dialect.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    invite_code: Mapped[str] = mapped_column(unique=True, nullable=False)
    created_at: Mapped[Optional[str]] = mapped_column(default=None)

    # Billing lives on the tenant: in B2B the company subscribes, not a user.
    # Stripe ids are stored so webhooks can map events back to an org.
    plan: Mapped[str] = mapped_column(default="free")
    subscription_status: Mapped[Optional[str]] = mapped_column(default=None)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(default=None)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(default=None)
    current_period_end: Mapped[Optional[str]] = mapped_column(default=None)

    users: Mapped[list["User"]] = relationship(back_populates="organization")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[Optional[str]] = mapped_column(default=None)
    org_id: Mapped[Optional[int]] = mapped_column(ForeignKey("organizations.id"))
    # "admin" manages the workspace (invite code, Gmail, members);
    # "member" does the day-to-day invoice work.
    role: Mapped[str] = mapped_column(default="member")

    organization: Mapped[Optional["Organization"]] = relationship(back_populates="users")


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("org_id", "vendor", "invoice_number", name="idx_invoices_org_vendor_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    org_id: Mapped[Optional[int]] = mapped_column(ForeignKey("organizations.id"))
    vendor: Mapped[Optional[str]] = mapped_column(default=None)
    invoice_number: Mapped[Optional[str]] = mapped_column(default=None)
    invoice_date: Mapped[Optional[str]] = mapped_column(default=None)
    # Money is NUMERIC(14,2)/Decimal, never float: binary floating point cannot
    # represent decimal currency exactly and the error compounds across sums.
    gst: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), default=None)
    total: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), default=None)
    status: Mapped[Optional[str]] = mapped_column(default="pending")
    due_date: Mapped[Optional[str]] = mapped_column(default=None)
    created_at: Mapped[Optional[str]] = mapped_column(default=utc_timestamp)
    # Human-review gate: every extracted invoice starts unreviewed. Advisory
    # only — totals still count it — but a person must confirm the AI's figures
    # before it's trusted as final. Flipped true via PATCH /invoices/{id}.
    reviewed: Mapped[bool] = mapped_column(default=False)

    organization: Mapped[Optional["Organization"]] = relationship(back_populates="invoices")


class EmailAccount(Base):
    """A connected Gmail account — one per organization. Tokens are stored
    ENCRYPTED (never plaintext); this model only holds ciphertext.
    """
    __tablename__ = "email_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), unique=True)
    email_address: Mapped[str] = mapped_column()
    access_token: Mapped[Optional[str]] = mapped_column(default=None)   # encrypted
    refresh_token: Mapped[Optional[str]] = mapped_column(default=None)  # encrypted
    token_expiry: Mapped[Optional[str]] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(default="connected")
    connected_at: Mapped[Optional[str]] = mapped_column(default=None)
    last_synced_at: Mapped[Optional[str]] = mapped_column(default=None)


class EmailMessage(Base):
    """An email fetched from a connected account that carries invoice attachments."""
    __tablename__ = "email_messages"
    __table_args__ = (
        UniqueConstraint("email_account_id", "gmail_message_id", name="uq_message_per_account"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    email_account_id: Mapped[int] = mapped_column(ForeignKey("email_accounts.id"))
    gmail_message_id: Mapped[str] = mapped_column()
    sender: Mapped[Optional[str]] = mapped_column(default=None)
    subject: Mapped[Optional[str]] = mapped_column(default=None)
    received_at: Mapped[Optional[str]] = mapped_column(default=None)
    created_at: Mapped[Optional[str]] = mapped_column(default=None)

    attachments: Mapped[list["EmailAttachment"]] = relationship(back_populates="message")


class EmailAttachment(Base):
    """A downloadable attachment on an email — the unit the pipeline processes."""
    __tablename__ = "email_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    email_message_id: Mapped[int] = mapped_column(ForeignKey("email_messages.id"))
    filename: Mapped[Optional[str]] = mapped_column(default=None)
    mime_type: Mapped[Optional[str]] = mapped_column(default=None)
    gmail_attachment_id: Mapped[Optional[str]] = mapped_column(default=None)
    size: Mapped[Optional[int]] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(default="pending")  # pending|processing|completed|failed
    invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("invoices.id"), default=None)
    created_at: Mapped[Optional[str]] = mapped_column(default=None)
    # Auto-retry for transient failures (e.g. Gemini temporarily down): how
    # many retries have been scheduled so far, and when the next one is due.
    # NULL next_retry_at means no retry is scheduled (terminal failure, or
    # retries exhausted) — see services/processing_service.py.
    retry_count: Mapped[int] = mapped_column(default=0)
    next_retry_at: Mapped[Optional[str]] = mapped_column(default=None)

    message: Mapped[Optional["EmailMessage"]] = relationship(back_populates="attachments")


class InvoiceProcessingLog(Base):
    """Audit trail: one row per processing step for an attachment."""
    __tablename__ = "invoice_processing_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    attachment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("email_attachments.id"), default=None)
    step: Mapped[str] = mapped_column()
    status: Mapped[str] = mapped_column(default="info")  # info | error
    message: Mapped[Optional[str]] = mapped_column(default=None)
    created_at: Mapped[Optional[str]] = mapped_column(default=None)


# ===== WhatsApp intake =====
# WhatsApp works the opposite way to Gmail: there's no API to read a user's
# existing chats. Instead each org gets a WhatsApp Business *number*; vendors
# send invoices TO it, and each inbound message arrives on our webhook. These
# tables mirror the email_* ones, and the attachments funnel into the SAME
# processing pipeline (see services/processing_service.ingest_document).

class WhatsAppAccount(Base):
    """A connected WhatsApp Business number — one per organization.

    `phone_number` is the business number messages are sent TO, so it's how an
    inbound webhook is routed back to a tenant (the WhatsApp equivalent of
    "which inbox"). Unique per org AND globally, so two orgs can't claim the
    same number. In the Twilio sandbox every tester shares one number, so the
    pilot maps a single org to it; Cloud API gives each org its own number and
    this routing works unchanged.
    """
    __tablename__ = "whatsapp_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), unique=True)
    # E.164 digits, no "whatsapp:" prefix (e.g. "+14155238886").
    phone_number: Mapped[str] = mapped_column(unique=True)
    label: Mapped[Optional[str]] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(default="connected")
    connected_at: Mapped[Optional[str]] = mapped_column(default=None)
    last_received_at: Mapped[Optional[str]] = mapped_column(default=None)


class WhatsAppMessage(Base):
    """An inbound WhatsApp message that carried an invoice attachment."""
    __tablename__ = "whatsapp_messages"
    __table_args__ = (
        # The provider's message id — dedupes webhook redeliveries (Twilio and
        # Meta both retry), the WhatsApp equivalent of uq_message_per_account.
        UniqueConstraint("whatsapp_account_id", "provider_message_sid", name="uq_wa_message_per_account"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    whatsapp_account_id: Mapped[int] = mapped_column(ForeignKey("whatsapp_accounts.id"))
    provider_message_sid: Mapped[str] = mapped_column()
    sender_waid: Mapped[Optional[str]] = mapped_column(default=None)   # sender's WhatsApp id/number
    sender_name: Mapped[Optional[str]] = mapped_column(default=None)   # ProfileName, if shared
    body: Mapped[Optional[str]] = mapped_column(default=None)          # any text alongside the file
    received_at: Mapped[Optional[str]] = mapped_column(default=None)
    created_at: Mapped[Optional[str]] = mapped_column(default=None)

    attachments: Mapped[list["WhatsAppAttachment"]] = relationship(back_populates="message")


class WhatsAppAttachment(Base):
    """A media file on an inbound WhatsApp message — the unit the pipeline processes.

    Unlike email (where we re-download from Gmail on each retry), WhatsApp media
    URLs expire, so the bytes are saved at receipt and `media_path` points at
    them — making retry a local read. Swap media_path for an object-store key
    later without touching the pipeline.
    """
    __tablename__ = "whatsapp_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    whatsapp_message_id: Mapped[int] = mapped_column(ForeignKey("whatsapp_messages.id"))
    filename: Mapped[Optional[str]] = mapped_column(default=None)
    mime_type: Mapped[Optional[str]] = mapped_column(default=None)
    media_path: Mapped[Optional[str]] = mapped_column(default=None)   # where the downloaded bytes live
    size: Mapped[Optional[int]] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(default="pending")  # pending|processing|completed|failed
    invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("invoices.id"), default=None)
    created_at: Mapped[Optional[str]] = mapped_column(default=None)
    # Same auto-retry contract as email attachments.
    retry_count: Mapped[int] = mapped_column(default=0)
    next_retry_at: Mapped[Optional[str]] = mapped_column(default=None)

    message: Mapped[Optional["WhatsAppMessage"]] = relationship(back_populates="attachments")
