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


def test_new_invoice_starts_unreviewed(register_org):
    org = register_org("owner@example.com", "strongpass1", organization_name="Org A")
    org_id = org.get("/me").json()["organization"]["id"]
    invoice_id = _seed(org_id)

    assert org.get(f"/invoices/{invoice_id}").json()["reviewed"] is False


def test_mark_reviewed_persists(register_org):
    org = register_org("owner@example.com", "strongpass1", organization_name="Org A")
    org_id = org.get("/me").json()["organization"]["id"]
    invoice_id = _seed(org_id)

    response = org.patch(f"/invoices/{invoice_id}", json={"reviewed": True})

    assert response.status_code == 200
    assert response.json()["reviewed"] is True
    assert org.get(f"/invoices/{invoice_id}").json()["reviewed"] is True


def test_reviewer_can_correct_extracted_fields(register_org):
    org = register_org("owner@example.com", "strongpass1", organization_name="Org A")
    org_id = org.get("/me").json()["organization"]["id"]
    invoice_id = _seed(org_id, total="110.00")

    response = org.patch(f"/invoices/{invoice_id}", json={"vendor": "Acme Corp", "total": "999.50"})

    assert response.status_code == 200
    body = response.json()
    assert body["vendor"] == "Acme Corp"
    assert float(body["total"]) == 999.50


def test_renaming_onto_an_existing_vendor_number_pair_is_409(register_org):
    org = register_org("owner@example.com", "strongpass1", organization_name="Org A")
    org_id = org.get("/me").json()["organization"]["id"]
    _seed(org_id, vendor="Acme Supplies", invoice_number="INV-1")
    second = _seed(org_id, vendor="Globex", invoice_number="INV-2")

    # Rename the second onto the first's (vendor, number) — hits the unique index.
    response = org.patch(f"/invoices/{second}", json={"vendor": "Acme Supplies", "invoice_number": "INV-1"})

    assert response.status_code == 409


def test_reviewed_filter_returns_only_unreviewed(register_org):
    org = register_org("owner@example.com", "strongpass1", organization_name="Org A")
    org_id = org.get("/me").json()["organization"]["id"]
    reviewed_id = _seed(org_id, vendor="Acme Supplies", invoice_number="INV-1")
    _seed(org_id, vendor="Globex", invoice_number="INV-2")  # stays unreviewed
    org.patch(f"/invoices/{reviewed_id}", json={"reviewed": True})

    unreviewed = org.get("/invoices", params={"reviewed": "false"}).json()

    assert [i["invoice_number"] for i in unreviewed] == ["INV-2"]


def test_re_extraction_resets_reviewed_to_false(register_org):
    org = register_org("owner@example.com", "strongpass1", organization_name="Org A")
    org_id = org.get("/me").json()["organization"]["id"]
    invoice_id = _seed(org_id)
    org.patch(f"/invoices/{invoice_id}", json={"reviewed": True})

    # Same (vendor, number) extracted again -> upsert updates the row.
    _seed(org_id, total="222.00")

    assert org.get(f"/invoices/{invoice_id}").json()["reviewed"] is False
