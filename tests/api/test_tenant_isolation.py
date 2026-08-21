from services.database_service import save_invoice


def test_invoices_are_isolated_between_organizations(register_org):
    org_a = register_org("admin-a@example.com", "strongpass1", organization_name="Org A")
    org_b = register_org("admin-b@example.com", "strongpass1", organization_name="Org B")

    org_a_id = org_a.get("/me").json()["organization"]["id"]
    save_invoice(
        {"vendor": "Acme Supplies", "invoice_number": "INV-1", "invoice_date": "2026-01-01", "gst": "10.00", "total": "110.00"},
        user_id=None,
        org_id=org_a_id,
    )

    assert len(org_a.get("/invoices").json()) == 1
    assert org_b.get("/invoices").json() == []


def test_members_list_is_scoped_to_own_organization(register_org):
    org_a = register_org("admin-a@example.com", "strongpass1", organization_name="Org A")
    org_b = register_org("admin-b@example.com", "strongpass1", organization_name="Org B")

    org_a_emails = {m["email"] for m in org_a.get("/organization/members").json()}
    org_b_emails = {m["email"] for m in org_b.get("/organization/members").json()}

    assert org_a_emails == {"admin-a@example.com"}
    assert org_b_emails == {"admin-b@example.com"}


def test_admin_cannot_manage_a_member_of_another_organization(register_org):
    org_a = register_org("admin-a@example.com", "strongpass1", organization_name="Org A")
    org_b = register_org("admin-b@example.com", "strongpass1", organization_name="Org B")
    org_b_admin_id = org_b.get("/me").json()["id"]

    promote = org_a.patch(f"/organization/members/{org_b_admin_id}", json={"role": "member"})
    remove = org_a.delete(f"/organization/members/{org_b_admin_id}")

    assert promote.status_code == 404
    assert remove.status_code == 404
    # and it genuinely didn't work, not just a misleading status code:
    assert org_b.get("/me").json()["role"] == "admin"
