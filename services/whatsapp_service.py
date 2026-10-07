"""Twilio WhatsApp adapter: verify inbound webhooks and download media.

WhatsApp works the opposite way to Gmail — there's no API to read a user's
existing chats. Each org gets a WhatsApp Business *number*; vendors send
invoices to it, and Twilio POSTs each inbound message to our webhook. This
module is the thin Twilio-specific layer: everything above it (persist the
message, download the file, run it through extraction) stays provider-agnostic,
so swapping Twilio for Meta's Cloud API later means rewriting only this file.
"""
import os

import requests
from dotenv import load_dotenv
from twilio.request_validator import RequestValidator

load_dotenv()

ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

# Only these are turned into invoices; a vendor might also send a voice note,
# sticker, or vCard, which we ignore. Same allowlist spirit as the Gmail
# attachment walk (services/gmail_service._collect_attachments).
ALLOWED_MEDIA = {"application/pdf", "image/png", "image/jpeg", "image/jpg"}

# How long we'll wait on Twilio's media CDN before giving up (seconds). A hung
# download would otherwise tie up the request worker; failing fast lets the
# processing pipeline's retry/backoff reschedule it.
MEDIA_TIMEOUT = 30


def is_configured():
    """True only if the server has Twilio credentials (for graceful degrade)."""
    return bool(ACCOUNT_SID and AUTH_TOKEN)


def verify_signature(url, params, signature):
    """Confirm an inbound webhook really came from Twilio.

    Twilio signs each request: it HMAC-SHA1s the exact public URL plus the
    sorted POST parameters with our auth token, and sends the result as the
    X-Twilio-Signature header. RequestValidator recomputes it and compares in
    constant time. This signature is the ONLY thing that makes the webhook
    trustworthy — exactly like the Stripe webhook — so main.py rejects anything
    that fails here with a 403, before reading the body as real.

    `url` must be the full public URL Twilio hit (scheme + host + path, exactly
    as configured in the Twilio console), and `params` the raw POST form dict.
    Behind a proxy that rewrites host/scheme, pass the externally-visible URL
    (see WHATSAPP_WEBHOOK_URL handling in main.py) or validation fails on an
    otherwise-valid request.
    """
    if not AUTH_TOKEN:
        return False
    validator = RequestValidator(AUTH_TOKEN)
    return validator.validate(url, params, signature or "")


def is_supported_media(content_type):
    """Whether a media part is a file we can turn into an invoice."""
    if not content_type:
        return False
    # Twilio may send "image/jpeg; charset=..." — compare only the base type.
    return content_type.split(";")[0].strip().lower() in ALLOWED_MEDIA


def download_media(media_url):
    """Download one inbound media file's raw bytes.

    Twilio's MediaUrl needs HTTP Basic auth (our SID/token); it then redirects
    to the file on Twilio's CDN. `requests` drops the Authorization header on a
    cross-host redirect (which the CDN would otherwise reject), so a plain
    authenticated GET with redirects is correct here. Returns
    (bytes, content_type); raises on any HTTP error for the caller to handle.
    """
    resp = requests.get(media_url, auth=(ACCOUNT_SID, AUTH_TOKEN), timeout=MEDIA_TIMEOUT)
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "").split(";")[0].strip()
    return resp.content, content_type
