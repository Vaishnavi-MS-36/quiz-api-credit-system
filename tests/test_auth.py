from tests.helpers import auth_headers, make_user, register


def test_register_gives_500_credits_and_user_role(client):
    r = register(client, "a@example.com")
    assert r.status_code == 201
    body = r.json()
    assert body["credits"] == 500
    assert body["role"] == "user"
    assert "password" not in body and "hashed_password" not in body


def test_register_creates_signup_bonus_ledger_row(client):
    headers = make_user(client)
    r = client.get("/credits/transactions", headers=headers)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["type"] == "signup_bonus"
    assert rows[0]["amount"] == 500
    assert rows[0]["balance_after"] == 500


def test_register_duplicate_email_conflict_case_insensitive(client):
    assert register(client, "dup@example.com").status_code == 201
    assert register(client, "DUP@example.com").status_code == 409


def test_register_validation_errors(client):
    r = client.post(
        "/auth/register", json={"email": "bad", "full_name": "", "password": "abc"}
    )
    assert r.status_code == 422
    fields = {e["field"] for e in r.json()["errors"]}
    assert {"email", "full_name", "password"} <= fields


def test_register_password_over_72_bytes_rejected(client):
    r = client.post(
        "/auth/register",
        json={"email": "emoji@example.com", "full_name": "E", "password": "😀" * 30},
    )
    assert r.status_code == 422


def test_login_success(client):
    register(client, "l@example.com")
    r = client.post("/auth/login", json={"email": "l@example.com", "password": "password123"})
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert r.json()["access_token"]


def test_login_wrong_password_and_unknown_user(client):
    register(client, "l@example.com")
    r1 = client.post("/auth/login", json={"email": "l@example.com", "password": "wrongpass"})
    r2 = client.post("/auth/login", json={"email": "nobody@example.com", "password": "password123"})
    assert r1.status_code == 401
    assert r2.status_code == 401
    assert r1.json()["detail"] == r2.json()["detail"]  # no user enumeration


def test_me_requires_valid_token(client):
    assert client.get("/auth/me").status_code == 401
    bad = {"Authorization": "Bearer not-a-real-token"}
    assert client.get("/auth/me", headers=bad).status_code == 401


def test_me_returns_current_user(client):
    register(client, "me@example.com")
    r = client.get("/auth/me", headers=auth_headers(client, "me@example.com"))
    assert r.status_code == 200
    assert r.json()["email"] == "me@example.com"