from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import Transaction, User, UserRole

PASSWORD = "password123"


def register(client, email, password=PASSWORD):
    return client.post(
        "/auth/register",
        json={"email": email, "full_name": "Test User", "password": password},
    )


def auth_headers(client, email, password=PASSWORD):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def make_user(client, email="user@example.com"):
    r = register(client, email)
    assert r.status_code == 201, r.text
    return auth_headers(client, email)


def make_admin(client, email="admin@example.com"):
    r = register(client, email)
    assert r.status_code == 201, r.text
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        user.role = UserRole.ADMIN
        db.commit()
    return auth_headers(client, email)


def quiz_payload(stake=100, reward=200, pass_percentage=60, title="Python Basics"):
    return {
        "title": title,
        "description": "Test quiz",
        "stake_amount": stake,
        "reward_amount": reward,
        "pass_percentage": pass_percentage,
        "questions": [
            {"text": "Q1?", "options": ["a", "b", "c", "d"], "correct_option": 1},
            {"text": "Q2?", "options": ["a", "b", "c", "d"], "correct_option": 1},
            {"text": "Q3?", "options": ["a", "b", "c", "d"], "correct_option": 2},
        ],
    }


def create_quiz(client, admin_headers, **kwargs):
    r = client.post("/admin/quizzes", json=quiz_payload(**kwargs), headers=admin_headers)
    assert r.status_code == 201, r.text
    return r.json()


def answers_with_correct(quiz, n_correct):
    """First n_correct answers are right, the rest are wrong."""
    answers = []
    for i, q in enumerate(quiz["questions"]):
        if i < n_correct:
            selected = q["correct_option"]
        else:
            selected = (q["correct_option"] + 1) % len(q["options"])
        answers.append({"question_id": q["id"], "selected_option": selected})
    return answers


def get_balance(client, headers):
    r = client.get("/credits/balance", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["credits"]


def assert_ledger_consistent():
    """For every user: balance == sum of all ledger rows."""
    with SessionLocal() as db:
        for user in db.scalars(select(User)).all():
            total = db.scalar(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    Transaction.user_id == user.id
                )
            )
            assert user.credits == total, f"{user.email}: balance {user.credits} != ledger {total}"