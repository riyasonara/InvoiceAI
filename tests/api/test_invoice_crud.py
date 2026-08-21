from services.database_service import get_invoice_id, save_invoice


def _seed(org_id, **overrides):
    invoice = {
        "vendor": "Acme Supplies",
        "invoice_number": "INV-1",
        "invoice_date": "2026-01-15",
        "gst": "10.00",
        "total": "110.00",
    }
    invoice.update(overrides)
    save_invoice(invoice, user_id=None, org_id=org_id)
    return get_invoice_id(org_id, invoice["vendor"], invoice["invoice_number"])


def test_a_new_invoice_defaults_to_pending_status(register_org):
    org = register_org("owner@example.com", "strongpass1", organization_name="Org A")
    org_id = org.get("/me").json()["organization"]["id"]
    invoice_id = _seed(org_id)

    response = org.get(f"/invoices/{invoice_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "pending"


def test_patch_updates_status_and_due_date(register_org):
    org = register_org("owner@example.com", "strongpass1", organization_name="Org A")
    org_id = org.get("/me").json()["organization"]["id"]
    invoice_id = _seed(org_id)

    response = org.patch(f"/invoices/{invoice_id}", json={"status": "paid", "due_date": "2026-02-01"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "paid"
    assert body["due_date"] == "2026-02-01"
    # and it actually persisted, not just echoed back:
    assert org.get(f"/invoices/{invoice_id}").json()["status"] == "paid"


def test_patch_rejects_an_invalid_status_value(register_org):
    org = register_org("owner@example.com", "strongpass1", organization_name="Org A")
    org_id = org.get("/me").json()["organization"]["id"]
    invoice_id = _seed(org_id)

    response = org.patch(f"/invoices/{invoice_id}", json={"status": "archived"})

    assert response.status_code == 422
    # and nothing changed:
    assert org.get(f"/invoices/{invoice_id}").json()["status"] == "pending"


def test_patch_on_a_nonexistent_invoice_is_404(register_org):
    org = register_org("owner@example.com", "strongpass1", organization_name="Org A")

    response = org.patch("/invoices/999999", json={"status": "paid"})

    assert response.status_code == 404


def test_an_invoice_detail_from_another_org_is_404_not_403(register_org):
    org_a = register_org("admin-a@example.com", "strongpass1", organization_name="Org A")
    org_b = register_org("admin-b@example.com", "strongpass1", organization_name="Org B")
    org_a_id = org_a.get("/me").json()["organization"]["id"]
    invoice_id = _seed(org_a_id)

    response = org_b.get(f"/invoices/{invoice_id}")

    assert response.status_code == 404


def test_search_matches_vendor_or_invoice_number(register_org):
    org = register_org("owner@example.com", "strongpass1", organization_name="Org A")
    org_id = org.get("/me").json()["organization"]["id"]
    _seed(org_id, vendor="Acme Supplies", invoice_number="INV-1")
    _seed(org_id, vendor="Globex Corp", invoice_number="INV-2")

    by_vendor = org.get("/invoices", params={"search": "Acme"}).json()
    by_number = org.get("/invoices", params={"search": "INV-2"}).json()

    assert [i["vendor"] for i in by_vendor] == ["Acme Supplies"]
    assert [i["invoice_number"] for i in by_number] == ["INV-2"]


def test_status_filter_returns_only_matching_invoices(register_org):
    org = register_org("owner@example.com", "strongpass1", organization_name="Org A")
    org_id = org.get("/me").json()["organization"]["id"]
    paid_id = _seed(org_id, vendor="Acme Supplies", invoice_number="INV-1")
    _seed(org_id, vendor="Globex Corp", invoice_number="INV-2")  # stays pending
    org.patch(f"/invoices/{paid_id}", json={"status": "paid"})

    response = org.get("/invoices", params={"status": "paid"}).json()

    assert [i["id"] for i in response] == [paid_id]


def test_date_range_filter_is_inclusive_on_both_ends(register_org):
    org = register_org("owner@example.com", "strongpass1", organization_name="Org A")
    org_id = org.get("/me").json()["organization"]["id"]
    _seed(org_id, vendor="Early Co", invoice_number="INV-1", invoice_date="2026-01-01")
    mid_id = _seed(org_id, vendor="Mid Co", invoice_number="INV-2", invoice_date="2026-01-15")
    _seed(org_id, vendor="Late Co", invoice_number="INV-3", invoice_date="2026-02-01")

    response = org.get("/invoices", params={"from_date": "2026-01-10", "to_date": "2026-01-20"}).json()

    assert [i["id"] for i in response] == [mid_id]
