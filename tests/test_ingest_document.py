"""Unit tests for the source-agnostic ingest core — no DB, no AI calls.

ingest_document is what every intake source (Gmail, WhatsApp) funnels through,
so its success/failure branching is worth pinning down in isolation. The AI
extractor and the save/lookup are monkeypatched; we're testing the control
flow, not Gemini or the database.
"""
import pytest

from services import processing_service as ps

BYTES = b"%PDF-1.4 fake"


@pytest.fixture
def saved(monkeypatch):
    """Capture save_invoice calls and make the id lookup deterministic."""
    calls = []
    monkeypatch.setattr(ps, "save_invoice", lambda result, user_id, org_id: calls.append((result, user_id, org_id)))
    monkeypatch.setattr(ps, "get_invoice_id", lambda org_id, vendor, number: 42)
    return calls


def test_success_saves_and_returns_invoice_id(monkeypatch, saved):
    monkeypatch.setattr(ps, "_extract", lambda b, m, f: {
        "vendor": "Acme", "invoice_number": "INV-1", "total": 100,
    })
    out = ps.ingest_document(7, BYTES, "application/pdf", "bill.pdf", user_id=None)
    assert out == {"success": True, "invoice_id": 42, "vendor": "Acme", "invoice_number": "INV-1", "total": 100}
    assert len(saved) == 1 and saved[0][2] == 7  # saved under org_id=7


def test_ai_failure_is_passed_through(monkeypatch, saved):
    monkeypatch.setattr(ps, "_extract", lambda b, m, f: {
        "success": False, "code": "ai_unavailable", "error": "Gemini down",
    })
    out = ps.ingest_document(7, BYTES, "application/pdf", "bill.pdf")
    assert out["success"] is False and out["code"] == "ai_unavailable"
    assert saved == []  # nothing saved on failure


def test_not_an_invoice_is_rejected(monkeypatch, saved):
    # A logo/signature image extracts to no number AND no total.
    monkeypatch.setattr(ps, "_extract", lambda b, m, f: {
        "vendor": "Acme", "invoice_number": None, "total": None,
    })
    out = ps.ingest_document(7, BYTES, "image/png", "logo.png")
    assert out["success"] is False and out["code"] == "no_invoice_data"
    assert saved == []


def test_extractor_exception_becomes_extraction_error(monkeypatch, saved):
    def boom(b, m, f):
        raise RuntimeError("pdf parser crashed")
    monkeypatch.setattr(ps, "_extract", boom)
    out = ps.ingest_document(7, BYTES, "application/pdf", "bill.pdf")
    assert out["success"] is False and out["code"] == "extraction"
    assert saved == []
