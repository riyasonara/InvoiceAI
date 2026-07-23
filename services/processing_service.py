"""Invoice processing pipeline: turn a downloaded email attachment into an
Invoice. `process_attachment(id)` is the unit of work — a Celery/Redis worker
would call exactly this per job; `process_pending` just loops it for now.

Statuses: pending -> processing -> completed | failed. Every step is logged to
invoice_processing_logs for a full audit trail.
"""
import os
import tempfile
from datetime import datetime, timezone

from db import SessionLocal
from models import EmailAttachment, EmailMessage, InvoiceProcessingLog
from readers.pdf_reader import read_pdf
from services import ai_service, gmail_service
from services.database_service import save_invoice, get_invoice_id
from services.email_service import _get_account_credentials

PROMPT_PATH = "prompts/invoice_prompt.txt"


def _now():
    return datetime.now(timezone.utc).isoformat()


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

    _set_attachment(attachment_id, "processing")
    _log(org_id, attachment_id, "processing_started", f"Processing {filename}")

    account = _get_account_credentials(org_id)
    if account is None:
        _set_attachment(attachment_id, "failed")
        _log(org_id, attachment_id, "failed", "No connected Gmail account.", status="error")
        return {"status": "failed", "error": "no_account"}

    # 1. Download
    try:
        creds = gmail_service.build_credentials(account["access_token"], account["refresh_token"])
        file_bytes = gmail_service.download_attachment(creds, gmail_message_id, gmail_attachment_id)
        _log(org_id, attachment_id, "downloaded", f"Downloaded {len(file_bytes)} bytes")
    except Exception as exc:
        _set_attachment(attachment_id, "failed")
        _log(org_id, attachment_id, "failed", f"Download failed: {exc}", status="error")
        return {"status": "failed", "error": "download"}

    # 2. Extract
    try:
        result = _extract(file_bytes, mime_type, filename)
    except Exception as exc:
        _set_attachment(attachment_id, "failed")
        _log(org_id, attachment_id, "failed", f"Extraction error: {exc}", status="error")
        return {"status": "failed", "error": "extraction"}

    if result.get("success") is False:
        _set_attachment(attachment_id, "failed")
        _log(org_id, attachment_id, "failed", result.get("error", "AI extraction failed"), status="error")
        return {"status": "failed", "error": result.get("code")}

    # 3. Validate — must actually look like an invoice (not a logo/signature image).
    if not (result.get("invoice_number") or result.get("total")):
        _set_attachment(attachment_id, "failed")
        _log(org_id, attachment_id, "failed", "No invoice data found — not an invoice.", status="error")
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
    """Process every pending attachment for an org. A queue would enqueue one
    job per attachment instead of this loop — process_attachment stays the same.
    """
    db = SessionLocal()
    try:
        ids = [
            a.id for a in db.query(EmailAttachment)
            .filter_by(org_id=org_id, status="pending").all()
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
