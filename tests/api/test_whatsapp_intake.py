"""End-to-end tests for WhatsApp invoice intake.

Exercises the whole path — signature gate, org routing, dedupe, media storage,
the shared ingest core, and the retry drain — with the two external edges
(Twilio media download and Gemini extraction) monkeypatched. The database,
routing, and pipeline wiring are all real.
"""
from decimal import Decimal

import pytest

import db
from models import WhatsAppMessage, WhatsAppAttachment, Invoice
from services import whatsapp_ingest_service as wis
from services import whatsapp_service, processing_service

SANDBOX = "+14155238886"


def _org_id(client_for_user):
    return client_for_user.get("/me").json()["organization"]["id"]


@pytest.fixture
def fake_edges(monkeypatch, tmp_path):
    """Stub the two external edges: Twilio media download and Gemini extraction.
    Media is written under a tmp dir so tests never touch the repo's uploads/.
    """
    monkeypatch.setattr(wis, "MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr(whatsapp_service, "download_media", lambda url: (b"%PDF-1.4 fake invoice", "application/pdf"))
    monkeypatch.setattr(processing_service, "_extract", lambda b, m, f: {
        "vendor": "WA Vendor", "invoice_number": "WA-1",
        "invoice_date": "2026-10-01", "gst": None, "total": Decimal("250.00"),
    })


def _webhook_form(to=SANDBOX, sid="SM1", content_type="application/pdf"):
    return {
        "To": f"whatsapp:{to}", "From": "whatsapp:+19998887777", "WaId": "19998887777",
        "ProfileName": "A Vendor", "Body": "Here is the invoice", "MessageSid": sid,
        "NumMedia": "1", "MediaUrl0": "https://api.twilio.com/media/ME1",
        "MediaContentType0": content_type,
    }


def test_webhook_rejects_bad_signature(client):
    # No monkeypatch of verify_signature → a bogus signature must be rejected,
    # before any routing or storage happens. (Works with or without a real
    # TWILIO_AUTH_TOKEN present: an invalid signature fails either way.)
    resp = client.post("/whatsapp/webhook", data=_webhook_form(),
                       headers={"X-Twilio-Signature": "definitely-not-valid"})
    assert resp.status_code == 403


def test_webhook_ignores_unmapped_number(client, monkeypatch, fake_edges):
    # Signature OK, but no org owns this number → accept (200, no retry) and
    # store nothing. An attacker can't inject invoices into a random org.
    monkeypatch.setattr(whatsapp_service, "verify_signature", lambda url, params, sig: True)
    resp = client.post("/whatsapp/webhook", data=_webhook_form(to="+10000000000"),
                       headers={"X-Twilio-Signature": "ok"})
    assert resp.status_code == 200

    session = db.SessionLocal()
    try:
        assert session.query(WhatsAppMessage).count() == 0
        assert session.query(Invoice).count() == 0
    finally:
        session.close()


def test_receive_inbound_dedupes_redelivery(register_org, fake_edges):
    owner = register_org("owner@example.com", "password123", organization_name="Acme WA")
    org_id = _org_id(owner)
    wis.connect_account(org_id, SANDBOX, "sandbox")

    media = [{"url": "https://api.twilio.com/media/ME1", "content_type": "application/pdf"}]
    first = wis.receive_inbound(f"whatsapp:{SANDBOX}", "SM-DUP", "19998887777", "Vendor", "hi", media)
    second = wis.receive_inbound(f"whatsapp:{SANDBOX}", "SM-DUP", "19998887777", "Vendor", "hi", media)

    assert first["status"] == "received" and len(first["attachment_ids"]) == 1
    assert second["status"] == "duplicate" and second["attachment_ids"] == []

    session = db.SessionLocal()
    try:
        assert session.query(WhatsAppMessage).count() == 1          # redelivery deduped
        assert session.query(WhatsAppAttachment).count() == 1
    finally:
        session.close()


def test_webhook_creates_invoice_end_to_end(client, register_org, monkeypatch, fake_edges):
    monkeypatch.setattr(whatsapp_service, "verify_signature", lambda url, params, sig: True)

    owner = register_org("owner2@example.com", "password123", organization_name="Acme WA 2")
    org_id = _org_id(owner)
    wis.connect_account(org_id, SANDBOX, "sandbox")

    # TestClient runs the BackgroundTask (extraction) synchronously before returning.
    resp = client.post("/whatsapp/webhook", data=_webhook_form(sid="SM-E2E"),
                       headers={"X-Twilio-Signature": "ok"})
    assert resp.status_code == 200

    invoices = owner.get("/invoices").json()
    assert any(i["invoice_number"] == "WA-1" and i["vendor"] == "WA Vendor" for i in invoices)

    session = db.SessionLocal()
    try:
        att = session.query(WhatsAppAttachment).first()
        assert att.status == "completed" and att.invoice_id is not None
    finally:
        session.close()


def test_process_pending_runs_due_retry(register_org, monkeypatch, tmp_path, fake_edges):
    # A previously-failed attachment whose retry is now due should be drained
    # and completed by process_pending (the scheduler's WhatsApp path).
    owner = register_org("owner3@example.com", "password123", organization_name="Acme WA 3")
    org_id = _org_id(owner)
    wis.connect_account(org_id, SANDBOX, "sandbox")

    media_file = tmp_path / "due.pdf"
    media_file.write_bytes(b"%PDF-1.4 fake")

    session = db.SessionLocal()
    try:
        msg = WhatsAppMessage(org_id=org_id, whatsapp_account_id=wis.get_account(org_id)["id"],
                              provider_message_sid="SM-RETRY", created_at="2026-10-01T00:00:00+00:00")
        session.add(msg)
        session.flush()
        att = WhatsAppAttachment(
            org_id=org_id, whatsapp_message_id=msg.id, filename="due.pdf",
            mime_type="application/pdf", media_path=str(media_file), status="failed",
            retry_count=1, next_retry_at="2000-01-01 00:00:00",  # long overdue
        )
        session.add(att)
        session.commit()
        att_id = att.id
    finally:
        session.close()

    result = wis.process_pending(org_id)
    assert result == {"processed": 1, "completed": 1, "failed": 0}

    session = db.SessionLocal()
    try:
        refreshed = session.query(WhatsAppAttachment).filter_by(id=att_id).first()
        assert refreshed.status == "completed" and refreshed.invoice_id is not None
    finally:
        session.close()
