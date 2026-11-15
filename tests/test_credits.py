from tests.helpers import (
    answers_with_correct,
    assert_ledger_consistent,
    create_quiz,
    get_balance,
    make_admin,
    make_user,
)


def test_balance_requires_auth(client):
    assert client.get("/credits/balance").status_code == 401
    assert client.get("/credits/transactions").status_code == 401
    assert client.post("/credits/purchase", json={"amount": 10}).status_code == 401


def test_new_user_balance_is_500(client):
    user = make_user(client)
    assert get_balance(client, user) == 500


def test_purchase_success_adds_credits_and_ledger_row(client):
    user = make_user(client)
    r = client.post(
        "/credits/purchase",
        json={"amount": 1000, "payment_method": "mock_card_success"},
        headers=user,
    )
    assert r.status_code == 201
    assert r.json()["payment_status"] == "succeeded"
    assert r.json()["balance"] == 1500
    assert get_balance(client, user) == 1500

    rows = client.get("/credits/transactions", headers=user).json()
    assert rows[0]["type"] == "purchase"
    assert rows[0]["amount"] == 1000
    assert rows[0]["balance_after"] == 1500
    assert_ledger_consistent()


def test_declined_payment_changes_nothing(client):
    user = make_user(client)
    r = client.post(
        "/credits/purchase",
        json={"amount": 500, "payment_method": "mock_card_decline"},
        headers=user,
    )
    assert r.status_code == 402
    assert get_balance(client, user) == 500
    assert len(client.get("/credits/transactions", headers=user).json()) == 1  # signup only
    assert_ledger_consistent()


def test_purchase_validation(client):
    user = make_user(client)
    for body in (
        {"amount": 0},
        {"amount": -5},
        {"amount": 20000},
        {"amount": 100, "payment_method": "bitcoin"},
    ):
        assert client.post("/credits/purchase", json=body, headers=user).status_code == 422
    assert get_balance(client, user) == 500


def test_transaction_history_order_filter_and_pagination(client):
    admin = make_admin(client)
    user = make_user(client)
    quiz = create_quiz(client, admin)

    attempt_id = client.post(f"/quizzes/{quiz['id']}/start", headers=user).json()["attempt_id"]
    client.post(
        f"/attempts/{attempt_id}/submit",
        json={"answers": answers_with_correct(quiz, 3)},
        headers=user,
    )
    client.post("/credits/purchase", json={"amount": 50}, headers=user)

    rows = client.get("/credits/transactions", headers=user).json()
    assert [r["type"] for r in rows] == ["purchase", "reward", "stake", "signup_bonus"]

    stakes = client.get("/credits/transactions", params={"type": "stake"}, headers=user).json()
    assert len(stakes) == 1
    assert stakes[0]["amount"] == -100

    page = client.get("/credits/transactions", params={"limit": 2, "offset": 1}, headers=user)
    assert [r["type"] for r in page.json()] == ["reward", "stake"]

    assert (
        client.get("/credits/transactions", params={"limit": 0}, headers=user).status_code == 422
    )


def test_users_only_see_their_own_transactions(client):
    a = make_user(client, "a@example.com")
    b = make_user(client, "b@example.com")
    client.post("/credits/purchase", json={"amount": 100}, headers=a)

    assert len(client.get("/credits/transactions", headers=a).json()) == 2
    assert len(client.get("/credits/transactions", headers=b).json()) == 1