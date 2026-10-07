"""Unit tests for the Twilio WhatsApp adapter — no network, no database.

The webhook signature is the whole trust boundary (an unverified request could
forge invoices into any org), so it's the part most worth pinning down.
"""
from twilio.request_validator import RequestValidator

from services import whatsapp_service

TOKEN = "test-auth-token-not-a-secret"
URL = "https://api.example.com/whatsapp/webhook"
PARAMS = {
    "From": "whatsapp:+14155551234",
    "To": "whatsapp:+14155238886",
    "Body": "Here's the invoice",
    "NumMedia": "1",
    "MediaUrl0": "https://api.twilio.com/.../Media/ME123",
    "MediaContentType0": "application/pdf",
    "MessageSid": "SM0123456789",
}


def _sign(params):
    """Produce the X-Twilio-Signature Twilio would send for these params."""
    return RequestValidator(TOKEN).compute_signature(URL, params)


def test_valid_signature_passes(monkeypatch):
    monkeypatch.setattr(whatsapp_service, "AUTH_TOKEN", TOKEN)
    assert whatsapp_service.verify_signature(URL, PARAMS, _sign(PARAMS)) is True


def test_tampered_params_fail(monkeypatch):
    monkeypatch.setattr(whatsapp_service, "AUTH_TOKEN", TOKEN)
    signature = _sign(PARAMS)
    forged = {**PARAMS, "From": "whatsapp:+19998887777"}  # attacker swaps the sender
    assert whatsapp_service.verify_signature(URL, forged, signature) is False


def test_missing_signature_fails(monkeypatch):
    monkeypatch.setattr(whatsapp_service, "AUTH_TOKEN", TOKEN)
    assert whatsapp_service.verify_signature(URL, PARAMS, "") is False
    assert whatsapp_service.verify_signature(URL, PARAMS, None) is False


def test_verify_fails_without_token(monkeypatch):
    # No server credentials → never trust a webhook, even a correctly signed one.
    monkeypatch.setattr(whatsapp_service, "AUTH_TOKEN", None)
    assert whatsapp_service.verify_signature(URL, PARAMS, _sign(PARAMS)) is False


def test_is_supported_media():
    assert whatsapp_service.is_supported_media("application/pdf") is True
    assert whatsapp_service.is_supported_media("image/jpeg; charset=utf-8") is True
    assert whatsapp_service.is_supported_media("audio/ogg") is False
    assert whatsapp_service.is_supported_media(None) is False


def test_is_configured(monkeypatch):
    monkeypatch.setattr(whatsapp_service, "ACCOUNT_SID", "AC123")
    monkeypatch.setattr(whatsapp_service, "AUTH_TOKEN", TOKEN)
    assert whatsapp_service.is_configured() is True
    monkeypatch.setattr(whatsapp_service, "AUTH_TOKEN", None)
    assert whatsapp_service.is_configured() is False
