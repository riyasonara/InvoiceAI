"""Invoice processing pipeline: turn a downloaded email attachment into an
Invoice. `process_attachment(id)` is the unit of work — a Celery/Redis worker
would call exactly this per job; `process_pending` just loops it for now.

Statuses: pending -> processing -> completed | failed. Every step is logged to
invoice_processing_logs for a full audit trail.
"""
import os
import tempfile
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_

from db import SessionLocal
from models import EmailAttachment, EmailMessage, InvoiceProcessingLog
from readers.pdf_reader import read_pdf
from services import ai_service, billing_service, gmail_service
from services.billing_service import QuotaExceeded
from services.database_service import save_invoice, get_invoice_id
from services.email_service import _get_account_credentials

PROMPT_PATH = "prompts/invoice_prompt.txt"

# Auto-retry only failures that plausibly resolve on their own (a down AI
# provider, a flaky download, an occasionally-truncated response) — never
# "no_account" (needs the user to reconnect Gmail) or "no_invoice_data"
# (the document will never become an invoice no matter how many times it's
# read). Backoff matches what was asked for: 5 min, then 15, then 30.
RETRYABLE_ERRORS = {"download", "extraction", "ai_unavailable", "invalid_ai_response"}
RETRY_DELAY_MINUTES = [5, 15, 30]
MAX_RETRIES = len(RETRY_DELAY_MINUTES)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _now_stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _log(org_id, attachment_id, step, message, status="info"):
    db = SessionLocal()
    try:
        db.add(InvoiceProcessingLog(
            org_id=org_id, attachment_id=attachment_id,
            step=step, status=status, message=message, created_at=_now(),
        ))
        db.commit()
    finally:
        db.close()


def _set_attachment(attachment_id, status, invoice_id=None):
    db = SessionLocal()
    try:
        att = db.query(EmailAttachment).filter_by(id=attachment_id).first()
        if att:
            att.status = status
            if invoice_id is not None:
                att.invoice_id = invoice_id
            db.commit()
    finally:
        db.close()


def _fail_attachment(org_id, attachment_id, error_code, message):
    """Mark an attachment failed, and — for a retryable error code, while
    retries remain — schedule the next attempt instead of leaving it
    permanently stuck. Reads/writes retry_count in the same transaction so
    concurrent failures on the same attachment can't race past MAX_RETRIES.
    """
    db = SessionLocal()
    try:
        att = db.query(EmailAttachment).filter_by(id=attachment_id).first()
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

    _log(org_id, attachment_id, "failed", message + note, status="error")


def _extract(file_bytes, mime_type, filename):
    """Route to the right existing extractor: digital PDF -> text, otherwise
    (scanned PDF or image) -> Gemini vision. Reuses ai_service unchanged.
    """
    with open(PROMPT_PATH, "r") as f:
        prompt = f.read()

    is_pdf = mime_type == "application/pdf" or (filename or "").lower().endswith(".pdf")
    if is_pdf:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(file_bytes)
            path = tmp.name
        try:
            text = read_pdf(path)
        finally:
            os.remove(path)
        if text and text.strip():
            return ai_service.extract_invoice(prompt, text)
        return ai_service.extract_invoice_from_pdf(prompt, file_bytes)

    return ai_service.extract_invoice_from_file(prompt, file_bytes, mime_type)


def process_attachment(attachment_id):
    """Download -> extract -> validate -> save invoice. The unit a worker runs."""
    # Load what we need, then release the session (long AI calls shouldn't hold it).
    db = SessionLocal()
    try:
        att = db.query(EmailAttachment).filter_by(id=attachment_id).first()
        if att is None:
            return {"status": "not_found"}
        org_id = att.org_id
        filename, mime_type, gmail_attachment_id = att.filename, att.mime_type, att.gmail_attachment_id
        message = db.query(EmailMessage).filter_by(id=att.email_message_id).first()
        gmail_message_id = message.gmail_message_id if message else None
    finally:
        db.close()

    # Plan quota — email-sourced invoices count too. Left pending (not failed)
    # so the queue drains automatically once the org upgrades or the month rolls.
    try:
        billing_service.check_invoice_quota(org_id)
    except QuotaExceeded as exc:
        _log(org_id, attachment_id, "quota_exceeded", str(exc), status="error")
        return {"status": "skipped", "error": "quota_exceeded"}

    _set_attachment(attachment_id, "processing")
    _log(org_id, attachment_id, "processing_started", f"Processing {filename}")

    account = _get_account_credentials(org_id)
    if account is None:
        _fail_attachment(org_id, attachment_id, "no_account", "No connected Gmail account.")
        return {"status": "failed", "error": "no_account"}

    # 1. Download
    try:
        creds = gmail_service.build_credentials(account["access_token"], account["refresh_token"])
        file_bytes = gmail_service.download_attachment(creds, gmail_message_id, gmail_attachment_id)
        _log(org_id, attachment_id, "downloaded", f"Downloaded {len(file_bytes)} bytes")
    except Exception as exc:
        _fail_attachment(org_id, attachment_id, "download", f"Download failed: {exc}")
        return {"status": "failed", "error": "download"}

    # 2. Extract
    try:
        result = _extract(file_bytes, mime_type, filename)
    except Exception as exc:
        _fail_attachment(org_id, attachment_id, "extraction", f"Extraction error: {exc}")
        return {"status": "failed", "error": "extraction"}

    if result.get("success") is False:
        code = result.get("code")
        _fail_attachment(org_id, attachment_id, code, result.get("error", "AI extraction failed"))
        return {"status": "failed", "error": code}

    # 3. Validate — must actually look like an invoice (not a logo/signature image).
    if not (result.get("invoice_number") or result.get("total")):
        _fail_attachment(org_id, attachment_id, "no_invoice_data", "No invoice data found — not an invoice.")
        return {"status": "failed", "error": "no_invoice_data"}

    _log(org_id, attachment_id, "extracted",
         f"Vendor {result.get('vendor')}, #{result.get('invoice_number')}, total {result.get('total')}")

    # 4. Save (email-sourced -> no uploading user) + link back to the attachment.
    save_invoice(result, None, org_id)
    invoice_id = get_invoice_id(org_id, result.get("vendor"), result.get("invoice_number"))
    _set_attachment(attachment_id, "completed", invoice_id=invoice_id)
    _log(org_id, attachment_id, "completed", f"Saved invoice #{invoice_id}")
    return {"status": "completed", "invoice_id": invoice_id}


def process_pending(org_id):
    """Process every pending attachment for an org, PLUS any failed one whose
    scheduled retry has come due. Runs from both the manual "Process" button
    and the background scheduler's own 5-minute cycle — that existing cadence
    doubles as the retry check, no separate scheduler needed.

    A queue would enqueue one job per attachment instead of this loop;
    process_attachment stays the same either way.
    """
    db = SessionLocal()
    try:
        ids = [
            a.id for a in db.query(EmailAttachment)
            .filter(
                EmailAttachment.org_id == org_id,
                or_(
                    EmailAttachment.status == "pending",
                    and_(
                        EmailAttachment.status == "failed",
                        EmailAttachment.next_retry_at.isnot(None),
                        EmailAttachment.next_retry_at <= _now_stamp(),
                    ),
                ),
            ).all()
        ]
    finally:
        db.close()

    completed = failed = 0
    for attachment_id in ids:
        outcome = process_attachment(attachment_id)
        if outcome.get("status") == "completed":
            completed += 1
        else:
            failed += 1

    return {"processed": len(ids), "completed": completed, "failed": failed}


def list_processing_logs(org_id, limit=100):
    """Recent processing-log entries for the org, newest first."""
    db = SessionLocal()
    try:
        rows = (
            db.query(InvoiceProcessingLog)
            .filter_by(org_id=org_id)
            .order_by(InvoiceProcessingLog.id.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id, "attachment_id": r.attachment_id, "step": r.step,
                "status": r.status, "message": r.message, "created_at": r.created_at,
            }
            for r in rows
        ]
    finally:
        db.close()
