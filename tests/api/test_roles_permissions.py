import pytest

from services.organization_service import LastAdminError, remove_member


def test_sole_admin_cannot_demote_themselves(register_org):
    admin = register_org("owner@example.com", "strongpass1", organization_name="Org A")
    admin_id = admin.get("/me").json()["id"]

    response = admin.patch(f"/organization/members/{admin_id}", json={"role": "member"})

    assert response.status_code == 409
    assert admin.get("/me").json()["role"] == "admin"  # unchanged


def test_sole_admin_cannot_remove_themselves(register_org):
    admin = register_org("owner@example.com", "strongpass1", organization_name="Org A")
    admin_id = admin.get("/me").json()["id"]

    response = admin.delete(f"/organization/members/{admin_id}")

    assert response.status_code == 400


def test_a_member_is_blocked_from_admin_only_actions(register_org):
    admin = register_org("owner@example.com", "strongpass1", organization_name="Org A")
    invite_code = admin.get("/me").json()["organization"]["invite_code"]
    member = register_org("teammate@example.com", "strongpass1", invite_code=invite_code)
    member_id = member.get("/me").json()["id"]
    admin_id = admin.get("/me").json()["id"]

    promote_attempt = member.patch(f"/organization/members/{admin_id}", json={"role": "member"})
    remove_attempt = member.delete(f"/organization/members/{admin_id}")
    gmail_attempt = member.post("/gmail/disconnect")

    assert promote_attempt.status_code == 403
    assert remove_attempt.status_code == 403
    assert gmail_attempt.status_code == 403
    # and nothing actually happened to the admin:
    assert admin.get("/me").json()["role"] == "admin"


def test_demoting_one_of_two_admins_is_allowed(register_org):
    admin = register_org("owner@example.com", "strongpass1", organization_name="Org A")
    invite_code = admin.get("/me").json()["organization"]["invite_code"]
    teammate = register_org("teammate@example.com", "strongpass1", invite_code=invite_code)
    teammate_id = teammate.get("/me").json()["id"]
    admin.patch(f"/organization/members/{teammate_id}", json={"role": "admin"})  # now 2 admins

    response = admin.patch(f"/organization/members/{teammate_id}", json={"role": "member"})

    assert response.status_code == 200
    assert response.json()["role"] == "member"


def test_removing_one_of_two_admins_is_allowed(register_org):
    admin = register_org("owner@example.com", "strongpass1", organization_name="Org A")
    invite_code = admin.get("/me").json()["organization"]["invite_code"]
    teammate = register_org("teammate@example.com", "strongpass1", invite_code=invite_code)
    teammate_id = teammate.get("/me").json()["id"]
    admin.patch(f"/organization/members/{teammate_id}", json={"role": "admin"})  # now 2 admins

    response = admin.delete(f"/organization/members/{teammate_id}")

    assert response.status_code == 200
    assert [m["id"] for m in admin.get("/organization/members").json()] == [
        admin.get("/me").json()["id"]
    ]


def test_the_last_admin_invariant_also_holds_at_the_service_layer(register_org):
    """The API can never actually reach remove_member()'s own LastAdminError
    for an admin: the self-removal check in main.py always fires first for
    a sole admin, since they'd have to be removing themselves. That makes
    this branch dead code from the HTTP layer's point of view — but the
    service function is still a public part of organization_service, and
    the invariant it protects (never end up with zero admins) belongs to
    the data layer, not to whichever caller happens to guard it today.
    """
    admin = register_org("owner@example.com", "strongpass1", organization_name="Org A")
    org_id = admin.get("/me").json()["organization"]["id"]
    admin_id = admin.get("/me").json()["id"]

    with pytest.raises(LastAdminError):
        remove_member(org_id, admin_id)
