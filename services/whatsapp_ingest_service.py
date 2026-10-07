"""WhatsApp intake: persistence, routing, and processing.

Provider-agnostic above the whatsapp_service (Twilio) adapter. Routes an
inbound message to the right org by the business number it was sent to, stores
the message + its media, downloads the bytes, and runs each file through the
shared ingest_document core. Mirrors services/email_service.py plus the email
half of services/processing_service.py — WhatsApp is just a different front door
onto the same pipeline.
"""
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError

from db import SessionLocal
from models import WhatsAppAccount, WhatsAppMessage, WhatsAppAttachment, InvoiceProcessingLog
from services import billing_service, whatsapp_service
from services.billing_service import QuotaExceeded
# Reuse the shared core AND the email path's retry policy, so both sources
# back off identically (5 / 15 / 30 min) on transient failures.
from services.processing_service import (
    ingest_document, RETRYABLE_ERRORS, RETRY_DELAY_MINUTES, MAX_RETRIES,
)

# Where downloaded WhatsApp media is kept so processing/retry can re-read it
# (Twilio's URL needs auth and Meta's media ids expire). Swap this for an
# object store later without touching the pipeline — the one storage seam.
MEDIA_DIR = os.getenv("MEDIA_DIR", "uploads")
WHATSAPP_SUBDIR = "whatsapp"

_EXT_BY_TYPE = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
}


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _now_stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _normalize_number(value):
    """Strip Twilio's "whatsapp:" prefix and whitespace, keep the E.164 digits."""
    if value is None:
        return value
    v = value.strip()
    if v.lower().startswith("whatsapp:"):
        v = v[len("whatsapp:"):]
    return v.strip()


# ===== Account / routing =====

def _account_to_dict(a):
    return {
        "id": a.id, "org_id": a.org_id, "phone_number": a.phone_number,
        "label": a.label, "status": a.status,
        "connected_at": a.connected_at, "last_received_at": a.last_received_at,
    }


def connect_account(org_id, phone_number, label=None):
    """Register (or update) this org's WhatsApp Business number. The number is
    globally unique, so IntegrityError means another workspace already claims it.
    """
    phone_number = _normalize_number(phone_number)
    db = SessionLocal()
    try:
        account = db.query(WhatsAppAccount).filter_by(org_id=org_id).first()
        if account is None:
            account = WhatsAppAccount(org_id=org_id, connected_at=_now_iso())
            db.add(account)
        account.phone_number = phone_number
        account.label = label
        account.status = "connected"
        db.commit()
        return _account_to_dict(account)
    except IntegrityError:
        db.rollback()
        raise
    finally:
        db.close()


def get_account(org_id):
    db = SessionLocal()
    try:
        a = db.query(WhatsAppAccount).filter_by(org_id=org_id).first()
        return _account_to_dict(a) if a else None
    finally:
        db.close()


def get_account_by_number(phone_number):
    """Route an inbound message's To-number back to the org that owns it."""
    phone_number = _normalize_number(phone_number)
    db = SessionLocal()
    try:
        a = db.query(WhatsAppAccount).filter_by(phone_number=phone_number).first()
        return _account_to_dict(a) if a else None
    finally:
        db.close()


def disconnect_account(org_id):
    db = SessionLocal()
    try:
        a = db.query(WhatsAppAccount).filter_by(org_id=org_id).first()
        if a:
            db.delete(a)
            db.commit()
    finally:
        db.close()


def list_whatsapp_org_ids():
    """Orgs with a connected WhatsApp number (the scheduler's retry-drain list)."""
    db = SessionLocal()
    try:
        return [a.org_id for a in db.query(WhatsAppAccount).all()]
    finally:
        db.close()


def _touch_last_received(org_id):
    db = SessionLocal()
    try:
        a = db.query(WhatsAppAccount).filter_by(org_id=org_id).first()
        if a:
            a.last_received_at = _now_iso()
            db.commit()
    finally:
        db.close()


# ===== Inbound receipt =====

def _store_media(provider_sid, index, content_type, file_bytes):
    """Write one media file to disk and return its path."""
    base = (content_type or "").split(";")[0].strip().lower()
    ext = _EXT_BY_TYPE.get(base, "")
    safe_sid = "".join(c for c in (provider_sid or "msg") if c.isalnum() or c in "-_") or "msg"
    dir_path = os.path.join(MEDIA_DIR, WHATSAPP_SUBDIR)
    os.makedirs(dir_path, exist_ok=True)
    path = os.path.join(dir_path, f"{safe_sid}_{index}{ext}")
    with open(path, "wb") as f:
        f.write(file_bytes)
    return path


def _create_message_if_new(org_id, account_id, provider_sid, sender_waid, sender_name, body):
    """Insert the inbound message, or return None if it's a webhook redelivery
    (deduped on the provider message id, including the concurrent-retry race).
    """
    db = SessionLocal()
    try:
        existing = db.query(WhatsAppMessage).filter_by(
            whatsapp_account_id=account_id, provider_message_sid=provider_sid,
        ).first()
        if existing:
            return None
        msg = WhatsAppMessage(
            org_id=org_id, whatsapp_account_id=account_id,
            provider_message_sid=provider_sid, sender_waid=sender_waid,
            sender_name=sender_name, body=body,
            received_at=_now_iso(), created_at=_now_iso(),
        )
        db.add(msg)
        db.commit()
        return msg.id
    except IntegrityError:
        db.rollback()
        return None
    finally:
        db.close()


def _create_attachments(org_id, message_id, stored):
    """Insert WhatsAppAttachment rows (status=pending) for stored media."""
    db = SessionLocal()
    try:
        ids = []
        for path, content_type, size in stored:
            att = WhatsAppAttachment(
                org_id=org_id, whatsapp_message_id=message_id,
                filename=os.path.basename(path), mime_type=content_type,
                media_path=path, size=size, status="pending", created_at=_now_iso(),
            )
            db.add(att)
            db.flush()
            ids.append(att.id)
        db.commit()
        return ids
    finally:
        db.close()


def receive_inbound(to_number, provider_sid, sender_waid, sender_name, body, media):
    """Store an inbound WhatsApp message and its invoice-eligible media.

    `media` is a list of {"url", "content_type"}. Media bytes are downloaded
    here (outside any DB transaction, so a slow CDN can't hold a connection)
    and saved to disk; the attachments are left `pending` for processing.
    Returns a summary with the new attachment ids (empty on duplicate / no
    mapped account / no supported media).
    """
    account = get_account_by_number(to_number)
    if account is None:
        # No org owns this number — can't attribute it. Caller still returns
        # 200 so the provider doesn't retry a message we'll never accept.
        return {"status": "no_account", "attachment_ids": []}

    org_id, account_id = account["org_id"], account["id"]

    message_id = _create_message_if_new(
        org_id, account_id, provider_sid, sender_waid, sender_name, body,
    )
    if message_id is None:
        return {"status": "duplicate", "attachment_ids": []}

    # Download supported media with NO db session held (network I/O).
    stored = []
    for i, part in enumerate(media):
        if not whatsapp_service.is_supported_media(part.get("content_type")):
            continue
        file_bytes, ctype = whatsapp_service.download_media(part["url"])
        path = _store_media(provider_sid, i, ctype or part.get("content_type"), file_bytes)
        stored.append((path, ctype or part.get("content_type"), len(file_bytes)))

    attachment_ids = _create_attachments(org_id, message_id, stored) if stored else []
    _touch_last_received(org_id)
    return {"status": "received", "attachment_ids": attachment_ids}


# ===== Processing (mirrors the email half of processing_service) =====

def _wa_log(org_id, wa_attachment_id, step, message, status="info"):
    """Audit line. invoice_processing_logs.attachment_id FKs email_attachments,
    so WhatsApp rows log with attachment_id=None and carry the id in the text.
    """
    db = SessionLocal()
    try:
        db.add(InvoiceProcessingLog(
            org_id=org_id, attachment_id=None, step=step, status=status,
            message=f"[whatsapp:{wa_attachment_id}] {message}", created_at=_now_iso(),
        ))
        db.commit()
    finally:
        db.close()


def _set_status(attachment_id, status, invoice_id=None):
    db = SessionLocal()
    try:
        att = db.query(WhatsAppAttachment).filter_by(id=attachment_id).first()
        if att:
            att.status = status
            if invoice_id is not None:
                att.invoice_id = invoice_id
            db.commit()
    finally:
        db.close()


def _fail(org_id, attachment_id, error_code, message):
    """Mark failed and, for a retryable code with retries left, schedule the
    next attempt — identical backoff to the email path's _fail_attachment.
    """
    db = SessionLocal()
    try:
        att = db.query(WhatsAppAttachment).filter_by(id=attachment_id).first()
        if att is None:
            return
        att.status = "failed"
        if error_code in RETRYABLE_ERRORS and att.retry_count < MAX_RETRIES:
            delay = RETRY_DELAY_MINUTES[att.retry_count]
            att.retry_count += 1
            att.next_retry_at = (datetime.now(timezone.utc) + timedelta(minutes=delay)).strftime("%Y-%m-%d %H:%M:%S")
            note = f" · Retrying in {delay} min (attempt {att.retry_count}/{MAX_RETRIES})."
        else:
            att.next_retry_at = None
            note = " · Giving up — no more automatic retries." if att.retry_count > 0 else ""
        db.commit()
    finally:
        db.close()

    _wa_log(org_id, attachment_id, "failed", message + note, status="error")


def process_whatsapp_attachment(attachment_id):
    """Read stored bytes -> ingest. The unit of work for WhatsApp intake."""
    db = SessionLocal()
    try:
        att = db.query(WhatsAppAttachment).filter_by(id=attachment_id).first()
        if att is None:
            return {"status": "not_found"}
        org_id = att.org_id
        media_path, mime_type, filename = att.media_path, att.mime_type, att.filename
    finally:
        db.close()

    # Plan quota — WhatsApp invoices count too. Left pending (not failed) so the
    # queue drains automatically once the org upgrades or the month rolls.
    try:
        billing_service.check_invoice_quota(org_id)
    except QuotaExceeded as exc:
        _wa_log(org_id, attachment_id, "quota_exceeded", str(exc), status="error")
        return {"status": "skipped", "error": "quota_exceeded"}

    _set_status(attachment_id, "processing")
    _wa_log(org_id, attachment_id, "processing_started", f"Processing {filename}")

    try:
        with open(media_path, "rb") as f:
            file_bytes = f.read()
    except OSError as exc:
        _fail(org_id, attachment_id, "download", f"Stored media unavailable: {exc}")
        return {"status": "failed", "error": "download"}

    outcome = ingest_document(org_id, file_bytes, mime_type, filename, user_id=None)
    if not outcome["success"]:
        _fail(org_id, attachment_id, outcome["code"], outcome["error"])
        return {"status": "failed", "error": outcome["code"]}

    _wa_log(org_id, attachment_id, "extracted",
            f"Vendor {outcome['vendor']}, #{outcome['invoice_number']}, total {outcome['total']}")
    invoice_id = outcome["invoice_id"]
    _set_status(attachment_id, "completed", invoice_id=invoice_id)
    _wa_log(org_id, attachment_id, "completed", f"Saved invoice #{invoice_id}")
    return {"status": "completed", "invoice_id": invoice_id}


def process_pending(org_id):
    """Drain this org's pending WhatsApp attachments, plus any failed one whose
    scheduled retry has come due. Runs from the manual endpoint and the
    background scheduler — same shape as processing_service.process_pending.
    """
    db = SessionLocal()
    try:
        ids = [
            a.id for a in db.query(WhatsAppAttachment)
            .filter(
                WhatsAppAttachment.org_id == org_id,
                or_(
                    WhatsAppAttachment.status == "pending",
                    and_(
                        WhatsAppAttachment.status == "failed",
                        WhatsAppAttachment.next_retry_at.isnot(None),
                        WhatsAppAttachment.next_retry_at <= _now_stamp(),
                    ),
                ),
            ).all()
        ]
    finally:
        db.close()

    completed = failed = 0
    for attachment_id in ids:
        if process_whatsapp_attachment(attachment_id).get("status") == "completed":
            completed += 1
        else:
            failed += 1
    return {"processed": len(ids), "completed": completed, "failed": failed}
