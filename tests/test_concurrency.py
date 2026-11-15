from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers import (
    answers_with_correct,
    assert_ledger_consistent,
    create_quiz,
    get_balance,
    make_admin,
    make_user,
)


def run_parallel(fn, n):
    """Run fn(i) in n threads at once. Each call uses its own client."""
    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(fn, range(n)))


def test_concurrent_stakes_never_overdraw(client):
    """5 different quizzes, stake 400 each, user has 500: only ONE start may succeed."""
    admin = make_admin(client)
    user = make_user(client)
    quizzes = [create_quiz(client, admin, stake=400, reward=800, title=f"Q{i}") for i in range(5)]

    def attempt(i):
        c = TestClient(app)
        return c.post(f"/quizzes/{quizzes[i]['id']}/start", headers=user).status_code

    codes = run_parallel(attempt, 5)

    assert sorted(codes) == [201, 402, 402, 402, 402]
    assert get_balance(client, user) == 100
    assert_ledger_consistent()


def test_concurrent_double_submit_pays_reward_once(client):
    admin = make_admin(client)
    user = make_user(client)
    quiz = create_quiz(client, admin)  # stake 100, reward 200
    attempt_id = client.post(f"/quizzes/{quiz['id']}/start", headers=user).json()["attempt_id"]
    answers = answers_with_correct(quiz, 3)

    def do_submit(_):
        c = TestClient(app)
        return c.post(
            f"/attempts/{attempt_id}/submit", json={"answers": answers}, headers=user
        ).status_code

    codes = run_parallel(do_submit, 5)

    assert sorted(codes) == [200, 409, 409, 409, 409]
    assert get_balance(client, user) == 600  # 500 - 100 + 200, reward paid exactly once
    assert_ledger_consistent()


def test_concurrent_purchases_all_applied(client):
    user = make_user(client)

    def buy(_):
        c = TestClient(app)
        return c.post("/credits/purchase", json={"amount": 100}, headers=user).status_code

    codes = run_parallel(buy, 10)

    assert codes == [201] * 10
    assert get_balance(client, user) == 1500  # 500 + 10 * 100, no lost updates
    assert_ledger_consistent()