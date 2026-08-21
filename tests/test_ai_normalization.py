"""Pure-Python tests for services/ai_service.py's output-cleaning layer.

No database, no FastAPI app, no Gemini call — normalize_date() and
ExtractedInvoice are ordinary functions/validators, so these run in
milliseconds and need none of tests/api's Postgres fixtures.
"""
from decimal import Decimal

import pytest

from services.ai_service import ExtractedInvoice, normalize_date


@pytest.mark.parametrize("raw, expected", [
    ("2026-01-05", "2026-01-05"),                # already ISO
    ("2026-1-5", "2026-01-05"),                   # ISO, needs zero-padding
    ("2026-01-05T10:30:00", "2026-01-05"),        # ISO with a time suffix
    ("19/7/2022", "2022-07-19"),                  # day > 12: unambiguous day-first
    ("12/25/2026", "2026-12-25"),                 # month > 12: unambiguous month-first
    ("05/07/2026", "2026-07-05"),                 # ambiguous: our locale reads day-first
    ("19/7/22", "2022-07-19"),                    # 2-digit year
    ("2022/7/19", "2022-07-19"),                  # year-first
    ("19 Jul 2022", "2022-07-19"),                # month-name
    ("Jul 19, 2022", "2022-07-19"),                # month-name, US-style comma
    (None, None),
    ("", None),
    ("   ", None),
    ("31/02/2026", "31/02/2026"),                 # Feb 31 doesn't exist — kept as-is, not dropped
    ("not a date", "not a date"),                 # unrecognized shape — kept as-is
])
def test_normalize_date(raw, expected):
    assert normalize_date(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("3,600.00", Decimal("3600.00")),
    ("₹1,200.50", Decimal("1200.50")),
    ("$45.00", Decimal("45.00")),
    (3600, Decimal("3600")),
    (Decimal("99.99"), Decimal("99.99")),
    (None, None),
    ("", None),
    ("N/A", None),          # unparseable text -> None, not a crash
])
def test_extracted_invoice_cleans_money_fields(raw, expected):
    invoice = ExtractedInvoice(total=raw)
    assert invoice.total == expected


def test_extracted_invoice_never_loses_precision_to_float_rounding():
    invoice = ExtractedInvoice(gst=Decimal("180.55"), total=Decimal("0.45"))
    assert invoice.gst + invoice.total == Decimal("181.00")


@pytest.mark.parametrize("raw, expected", [
    (12345, "12345"),        # the model sometimes returns numbers as ints
    ("  Acme Supplies  ", "Acme Supplies"),
    ("", None),
    (None, None),
])
def test_extracted_invoice_cleans_text_fields(raw, expected):
    invoice = ExtractedInvoice(vendor=raw)
    assert invoice.vendor == expected
