def test_register_creates_admin_of_a_new_org(client):
    response = client.post("/register", json={
        "email": "alice@example.com",
        "password": "strongpass1",
        "organization_name": "Acme Test Co",
    })

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert "hashed_password" not in body  # response_model must never leak the hash


def test_register_rejects_a_duplicate_email(client):
    payload = {
        "email": "alice@example.com",
        "password": "strongpass1",
        "organization_name": "Acme Test Co",
    }
    client.post("/register", json=payload)

    response = client.post("/register", json=payload)

    assert response.status_code == 409


def test_login_with_correct_password_sets_the_session_cookie(client):
    client.post("/register", json={
        "email": "alice@example.com",
        "password": "strongpass1",
        "organization_name": "Acme Test Co",
    })

    response = client.post("/login", json={
        "email": "alice@example.com",
        "password": "strongpass1",
    })

    assert response.status_code == 200
    assert "access_token" in response.cookies
    assert "access_token" not in response.text  # token must never appear in the body


def test_login_with_wrong_password_and_unknown_email_give_the_same_error(client):
    client.post("/register", json={
        "email": "alice@example.com",
        "password": "strongpass1",
        "organization_name": "Acme Test Co",
    })

    wrong_password = client.post("/login", json={
        "email": "alice@example.com",
        "password": "not-the-password",
    })
    unknown_email = client.post("/login", json={
        "email": "nobody@example.com",
        "password": "strongpass1",
    })

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert wrong_password.json()["detail"] == unknown_email.json()["detail"]
