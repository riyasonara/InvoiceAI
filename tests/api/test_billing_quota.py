from plans import PLANS, FREE
from services.billing_service import set_plan
from services.database_service import save_invoice

FREE_LIMIT = PLANS[FREE]["invoice_limit"]


def _seed_invoices(org_id, count):
    for i in range(count):
        save_invoice(
            {"vendor": "Acme Supplies", "invoice_number": f"INV-{i}", "invoice_date": "2026-01-01", "gst": "1.00", "total": "11.00"},
            user_id=None,
            org_id=org_id,
        )


def _attempt_extract(client):
    # A deliberately non-PDF file: if the quota guard (Guard 0, checked
    # first) lets this through, it should then fail Guard 1 (content-type)
    # with 415 — never touching Gemini. That 415, not a 200, is how we know
    # the request reached past the quota check without spending an AI call.
    return client.post("/extract", files={"file": ("not-an-invoice.txt", b"hello", "text/plain")})


def test_free_plan_blocks_extraction_with_402_once_the_monthly_limit_is_hit(register_org):
    org = register_org("owner@example.com", "strongpass1", organization_name="Org A")
    org_id = org.get("/me").json()["organization"]["id"]
    _seed_invoices(org_id, FREE_LIMIT)

    response = _attempt_extract(org)

    assert response.status_code == 402
    assert "Upgrade to Pro" in response.json()["detail"]


def test_free_plan_allows_extraction_below_the_monthly_limit(register_org):
    org = register_org("owner@example.com", "strongpass1", organization_name="Org A")
    org_id = org.get("/me").json()["organization"]["id"]
    _seed_invoices(org_id, FREE_LIMIT - 1)

    response = _attempt_extract(org)

    # Not blocked by quota (402) — it got far enough to fail the *next*
    # guard (bad content-type) instead, proving Guard 0 let it through.
    assert response.status_code == 415


def test_pro_plan_has_no_monthly_limit(register_org):
    org = register_org("owner@example.com", "strongpass1", organization_name="Org A")
    org_id = org.get("/me").json()["organization"]["id"]
    set_plan(org_id, "pro")
    _seed_invoices(org_id, FREE_LIMIT + 5)  # well past what Free would allow

    response = _attempt_extract(org)

    assert response.status_code == 415  # never 402


def test_usage_endpoint_reports_accurate_counts(register_org):
    org = register_org("owner@example.com", "strongpass1", organization_name="Org A")
    org_id = org.get("/me").json()["organization"]["id"]
    _seed_invoices(org_id, 5)

    usage = org.get("/billing/usage").json()

    assert usage["invoices_used"] == 5
    assert usage["invoice_limit"] == FREE_LIMIT
    assert usage["invoices_remaining"] == FREE_LIMIT - 5
    assert usage["limit_reached"] is False
