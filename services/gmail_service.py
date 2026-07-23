"""Gmail OAuth 2.0 flow + minimal Gmail API access.

Builds the Google consent URL, exchanges the returned code for tokens, and
reads the connected account's email address. Credentials come from .env.
"""
import base64
import os

# Google sometimes returns the granted scopes in a different order; relax the
# strict scope check so token exchange doesn't raise a spurious error.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

from datetime import datetime, timezone

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

TOKEN_URI = "https://oauth2.googleapis.com/token"
ALLOWED_MIME = {"application/pdf", "image/png", "image/jpeg", "image/jpg"}
ALLOWED_EXT = (".pdf", ".png", ".jpg", ".jpeg")

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/gmail/callback")


def is_configured():
    """True only if the server has Google OAuth credentials (for graceful degrade)."""
    return bool(CLIENT_ID and CLIENT_SECRET)


def _client_config():
    return {
        "web": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI],
        }
    }


def _build_flow():
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES)
    flow.redirect_uri = REDIRECT_URI
    # Disable PKCE: connect and callback use separate Flow instances, so the
    # generated code_verifier wouldn't survive between them. We're a confidential
    # client (have a client secret), so PKCE isn't required — without it the code
    # exchange doesn't need the verifier, fixing the invalid_grant error.
    flow.autogenerate_code_verifier = False
    flow.code_verifier = None
    return flow


def build_auth_url(state):
    """The Google consent URL the user is redirected to. `state` is echoed back
    to the callback for CSRF verification. access_type=offline + prompt=consent
    ensure we receive a refresh token.
    """
    flow = _build_flow()
    url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return url


def exchange_code(code):
    """Swap the authorization code for tokens, then read the account's email."""
    flow = _build_flow()
    flow.fetch_token(code=code)
    creds = flow.credentials

    service = build("gmail", "v1", credentials=creds)
    profile = service.users().getProfile(userId="me").execute()

    return {
        "email": profile["emailAddress"],
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
    }


def build_credentials(access_token, refresh_token):
    """Rebuild Credentials from stored tokens. With the refresh_token + client
    secret, google-auth auto-refreshes the access token when it's expired.
    """
    return Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=SCOPES,
    )


def _header(headers, name):
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _collect_attachments(payload):
    """Walk the MIME tree and return invoice-eligible attachments (PDF/PNG/JPG)."""
    found = []

    def walk(part):
        filename = part.get("filename") or ""
        body = part.get("body", {}) or {}
        attachment_id = body.get("attachmentId")
        mime = part.get("mimeType", "")
        if filename and attachment_id and (
            mime in ALLOWED_MIME or filename.lower().endswith(ALLOWED_EXT)
        ):
            found.append({
                "filename": filename,
                "mime_type": mime,
                "gmail_attachment_id": attachment_id,
                "size": body.get("size", 0),
            })
        for child in part.get("parts", []) or []:
            walk(child)

    walk(payload)
    return found


def list_invoice_messages(creds, max_results=25):
    """Unread messages with invoice-eligible attachments. Returns
    (messages, current_access_token) — the token may have been refreshed.
    """
    service = build("gmail", "v1", credentials=creds)
    listed = service.users().messages().list(
        userId="me", q="is:unread has:attachment", maxResults=max_results,
    ).execute()

    messages = []
    for ref in listed.get("messages", []):
        full = service.users().messages().get(userId="me", id=ref["id"], format="full").execute()
        payload = full.get("payload", {})
        attachments = _collect_attachments(payload)
        if not attachments:
            continue  # ignore emails without a supported attachment

        internal = int(full.get("internalDate", "0") or 0)
        received_at = (
            datetime.fromtimestamp(internal / 1000, timezone.utc).isoformat() if internal else None
        )
        headers = payload.get("headers", [])
        messages.append({
            "gmail_message_id": full["id"],
            "sender": _header(headers, "From"),
            "subject": _header(headers, "Subject"),
            "received_at": received_at,
            "attachments": attachments,
        })

    return messages, creds.token


def download_attachment(creds, gmail_message_id, gmail_attachment_id):
    """Download a single attachment's raw bytes."""
    service = build("gmail", "v1", credentials=creds)
    attachment = service.users().messages().attachments().get(
        userId="me", messageId=gmail_message_id, id=gmail_attachment_id,
    ).execute()
    return base64.urlsafe_b64decode(attachment.get("data", ""))
