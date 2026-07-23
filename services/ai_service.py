from google import genai
from google.genai import types
from google.genai.errors import ServerError
from pydantic import BaseModel, field_validator, ValidationError
from dotenv import load_dotenv
from typing import Optional
import os
import json
import time

# Load environment variables
load_dotenv()

# Create Gemini client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


class ExtractedInvoice(BaseModel):
    """Normalizes the AI's raw output into clean, typed data.

    LLMs are inconsistent: gst/total may come back as "3,600.00" (a string with
    commas/currency), a number, or null. These validators clean every value at
    the boundary so the rest of the app only ever sees floats-or-None.
    """
    vendor: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    gst: Optional[float] = None
    total: Optional[float] = None

    @field_validator("vendor", "invoice_number", "invoice_date", mode="before")
    @classmethod
    def clean_text(cls, value):
        if value is None:
            return None
        value = str(value).strip()
        return value or None  # turn "" into None

    @field_validator("gst", "total", mode="before")
    @classmethod
    def clean_number(cls, value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        # Strip thousands separators, currency symbols, and spaces, then parse.
        cleaned = str(value).replace(",", "").replace("₹", "").replace("$", "").strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None  # unparseable -> None rather than crashing the request


def _extract_json(text):
    """Pull the JSON object out of a raw model response.

    Even with JSON mode on, LLMs can occasionally wrap output in markdown
    fences or add stray text. Taking the substring from the first '{' to the
    last '}' recovers the object in those cases. If there are no braces, we
    return the text unchanged so json.loads raises a clean error.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return text
    return text[start:end + 1]


MAX_ATTEMPTS = 3


def _generate_invoice_json(contents):
    """Call Gemini with the given contents (text and/or file parts), constrained
    to JSON output, then validate/normalize the result through ExtractedInvoice.
    Returns a clean invoice dict — or a structured error dict. Both the text and
    vision paths funnel through here, so parsing and error handling live once.

    Gemini occasionally returns transient 503 "high demand" errors — those are
    retried with a short backoff before giving up.
    """
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.models.generate_content(
                model="gemini-flash-latest",
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
            )
            raw = json.loads(_extract_json(response.text))
            # Coerce the raw AI output into clean, typed fields.
            return ExtractedInvoice(**raw).model_dump()

        except ServerError:
            # Transient overload/outage on Google's side — back off and retry.
            if attempt < MAX_ATTEMPTS:
                time.sleep(2 * attempt)
                continue
            return {
                "success": False,
                "code": "ai_unavailable",
                "error": "Gemini service is temporarily unavailable. Please try again later."
            }

        except (json.JSONDecodeError, ValidationError, TypeError):
            return {
                "success": False,
                "code": "invalid_ai_response",
                "error": "Gemini returned invalid JSON."
            }


def extract_invoice(prompt, invoice_text):
    """TEXT path: used for digital PDFs where pypdf already extracted the text.
    The invoice text is appended to the prompt.
    """
    return _generate_invoice_json(prompt + "\n" + invoice_text)


def extract_invoice_from_file(prompt, file_bytes, mime_type):
    """VISION path for any supported file (PDF or image): send the raw bytes to
    Gemini with the correct mime type so it reads the pixels (OCR + extraction).
    """
    part = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
    return _generate_invoice_json([prompt, part])


def extract_invoice_from_pdf(prompt, pdf_bytes):
    """VISION path for scanned/photo PDFs (kept for the existing upload flow)."""
    return extract_invoice_from_file(prompt, pdf_bytes, "application/pdf")
