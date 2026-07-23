"""Persistence for connected email accounts (one Gmail per organization).

Tokens are encrypted via crypto_service before storage. Reads never expose
tokens — only the address / status / connected timestamp.
"""
from datetime import datetime, timezone

from db import Base, engine, SessionLocal
from models import EmailAccount, EmailMessage, EmailAttachment
from services.crypto_service import encrypt, decrypt
from services import gmail_service


def create_email_tables():
    """Create the email_accounts table (and any other new ORM tables).
    Idempotent and a no-op for tables that already exist.
    """
    Base.metadata.create_all(engine)


def upsert_email_account(org_id, email_address, access_token, refresh_token, token_expiry):
    """Create or update this org's connected Gmail account (tokens encrypted)."""
    db = SessionLocal()
    try:
        account = db.query(EmailAccount).filter_by(org_id=org_id).first()
        if account is None:
            account = EmailAccount(org_id=org_id)
            db.add(account)

        account.email_address = email_address
        account.access_token = encrypt(access_token)
        # Google only returns a refresh_token on first consent — keep the old one otherwise.
        if refresh_token:
            account.refresh_token = encrypt(refresh_token)
        account.token_expiry = token_expiry
        account.status = "connected"
        account.connected_at = datetime.now(timezone.utc).isoformat()

        db.commit()
        return {"email_address": account.email_address, "connected_at": account.connected_at}
    finally:
        db.close()


def get_email_account(org_id):
    """Return the org's connected account (NO tokens) or None."""
    db = SessionLocal()
    try:
        account = db.query(EmailAccount).filter_by(org_id=org_id).first()
        if account is None:
            return None
        return {
            "email_address": account.email_address,
            "status": account.status,
            "connected_at": account.connected_at,
        }
    finally:
        db.close()


def delete_email_account(org_id):
    """Disconnect: remove the org's stored Gmail account + tokens."""
    db = SessionLocal()
    try:
        account = db.query(EmailAccount).filter_by(org_id=org_id).first()
        if account:
            db.delete(account)
            db.commit()
    finally:
        db.close()


def _get_account_credentials(org_id):
    """Internal: decrypted tokens for the org's account (never leaves this layer)."""
    db = SessionLocal()
    try:
        account = db.query(EmailAccount).filter_by(org_id=org_id).first()
        if account is None:
            return None
        return {
            "id": account.id,
            "access_token": decrypt(account.access_token),
            "refresh_token": decrypt(account.refresh_token),
        }
    finally:
        db.close()


def _persist_access_token(org_id, new_token):
    """Save a refreshed access token (re-encrypted)."""
    db = SessionLocal()
    try:
        account = db.query(EmailAccount).filter_by(org_id=org_id).first()
        if account:
            account.access_token = encrypt(new_token)
            db.commit()
    finally:
        db.close()


def sync_gmail(org_id):
    """Fetch unread emails with invoice attachments, store new ones (deduped).
    Attachment bytes are NOT downloaded here — that's the processing pipeline.
    Returns a summary of what was synced.
    """
    account = _get_account_credentials(org_id)
    if account is None:
        return None  # endpoint turns this into a 400

    creds = gmail_service.build_credentials(account["access_token"], account["refresh_token"])
    messages, current_token = gmail_service.list_invoice_messages(creds)

    # Persist a refreshed access token if google-auth rotated it.
    if current_token and current_token != account["access_token"]:
        _persist_access_token(org_id, current_token)

    new_messages = 0
    new_attachments = 0
    now = datetime.now(timezone.utc).isoformat()

    db = SessionLocal()
    try:
        for msg in messages:
            exists = db.query(EmailMessage).filter_by(
                email_account_id=account["id"], gmail_message_id=msg["gmail_message_id"],
            ).first()
            if exists:
                continue

            record = EmailMessage(
                org_id=org_id,
                email_account_id=account["id"],
                gmail_message_id=msg["gmail_message_id"],
                sender=msg["sender"],
                subject=msg["subject"],
                received_at=msg["received_at"],
                created_at=now,
            )
            db.add(record)
            db.flush()  # assign record.id
            new_messages += 1

            for att in msg["attachments"]:
                db.add(EmailAttachment(
                    org_id=org_id,
                    email_message_id=record.id,
                    filename=att["filename"],
                    mime_type=att["mime_type"],
                    gmail_attachment_id=att["gmail_attachment_id"],
                    size=att["size"],
                    created_at=now,
                ))
                new_attachments += 1

        db.commit()
    finally:
        db.close()

    return {"scanned": len(messages), "new_messages": new_messages, "new_attachments": new_attachments}


def _message_to_dict(m):
    return {
        "id": m.id,
        "sender": m.sender,
        "subject": m.subject,
        "received_at": m.received_at,
        "created_at": m.created_at,
        "attachments": [
            {
                "id": a.id,
                "filename": a.filename,
                "mime_type": a.mime_type,
                "status": a.status,
                "invoice_id": a.invoice_id,
            }
            for a in m.attachments
        ],
    }


def get_email_message(org_id, message_id):
    """One synced email with its attachments, org-scoped. None if not found."""
    db = SessionLocal()
    try:
        m = db.query(EmailMessage).filter_by(org_id=org_id, id=message_id).first()
        return _message_to_dict(m) if m else None
    finally:
        db.close()


def get_email_stats(org_id):
    """Counters for the dashboard tiles: today's synced emails, imported
    invoices, processing errors, and the pending queue.
    """
    db = SessionLocal()
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        synced_today = (
            db.query(EmailMessage)
            .filter(EmailMessage.org_id == org_id, EmailMessage.created_at.like(f"{today}%"))
            .count()
        )

        def att_count(status):
            return db.query(EmailAttachment).filter_by(org_id=org_id, status=status).count()

        return {
            "synced_today": synced_today,
            "imported": att_count("completed"),
            "errors": att_count("failed"),
            "pending": att_count("pending"),
        }
    finally:
        db.close()


def list_email_messages(org_id):
    """Emails for this org, newest first, each with its attachments (metadata)."""
    db = SessionLocal()
    try:
        rows = (
            db.query(EmailMessage)
            .filter_by(org_id=org_id)
            .order_by(EmailMessage.id.desc())
            .all()
        )
        return [_message_to_dict(m) for m in rows]
    finally:
        db.close()
