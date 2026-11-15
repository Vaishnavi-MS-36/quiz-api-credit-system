from tests.helpers import (
    answers_with_correct,
    assert_ledger_consistent,
    create_quiz,
    get_balance,
    make_admin,
    make_user,
)


def start(client, headers, quiz_id):
    return client.post(f"/quizzes/{quiz_id}/start", headers=headers)


def submit(client, headers, attempt_id, answers):
    return client.post(
        f"/attempts/{attempt_id}/submit", json={"answers": answers}, headers=headers
    )


def test_start_deducts_stake_and_hides_answers(client):
    admin = make_admin(client)
    user = make_user(client)
    quiz = create_quiz(client, admin)

    r = start(client, user, quiz["id"])
    assert r.status_code == 201
    body = r.json()
    assert body["staked_amount"] == 100
    assert body["balance_after"] == 400
    assert get_balance(client, user) == 400
    for q in body["questions"]:
        assert "correct_option" not in q
    assert_ledger_consistent()


def test_pass_wins_reward(client):
    admin = make_admin(client)
    user = make_user(client)
    quiz = create_quiz(client, admin)  # stake 100, reward 200

    attempt_id = start(client, user, quiz["id"]).json()["attempt_id"]
    r = submit(client, user, attempt_id, answers_with_correct(quiz, 3))
    assert r.status_code == 200
    body = r.json()
    assert body["passed"] is True
    assert body["status"] == "passed"
    assert body["score"] == 3
    assert body["reward_amount"] == 200
    assert body["balance"] == 600
    assert get_balance(client, user) == 600
    assert_ledger_consistent()


def test_fail_loses_stake(client):
    admin = make_admin(client)
    user = make_user(client)
    quiz = create_quiz(client, admin)

    attempt_id = start(client, user, quiz["id"]).json()["attempt_id"]
    r = submit(client, user, attempt_id, answers_with_correct(quiz, 0))
    assert r.status_code == 200
    body = r.json()
    assert body["passed"] is False
    assert body["status"] == "failed"
    assert body["reward_amount"] == 0
    assert body["balance"] == 400
    assert_ledger_consistent()


def test_pass_threshold_boundary(client):
    admin = make_admin(client)
    user = make_user(client)
    quiz = create_quiz(client, admin, pass_percentage=60)  # 3 questions

    a1 = start(client, user, quiz["id"]).json()["attempt_id"]
    assert submit(client, user, a1, answers_with_correct(quiz, 2)).json()["passed"] is True  # 66%

    a2 = start(client, user, quiz["id"]).json()["attempt_id"]
    assert submit(client, user, a2, answers_with_correct(quiz, 1)).json()["passed"] is False  # 33%


def test_insufficient_credits_blocks_start(client):
    admin = make_admin(client)
    user = make_user(client)
    quiz = create_quiz(client, admin, stake=600, reward=1000)

    r = start(client, user, quiz["id"])
    assert r.status_code == 402
    assert get_balance(client, user) == 500
    assert client.get("/attempts", headers=user).json() == []
    assert_ledger_consistent()


def test_cannot_start_twice_while_in_progress(client):
    admin = make_admin(client)
    user = make_user(client)
    quiz = create_quiz(client, admin)

    assert start(client, user, quiz["id"]).status_code == 201
    assert start(client, user, quiz["id"]).status_code == 409
    assert get_balance(client, user) == 400  # staked only once


def test_double_submit_rejected_and_reward_paid_once(client):
    admin = make_admin(client)
    user = make_user(client)
    quiz = create_quiz(client, admin)

    attempt_id = start(client, user, quiz["id"]).json()["attempt_id"]
    answers = answers_with_correct(quiz, 3)
    assert submit(client, user, attempt_id, answers).status_code == 200
    assert submit(client, user, attempt_id, answers).status_code == 409
    assert get_balance(client, user) == 600
    assert_ledger_consistent()


def test_user_cannot_touch_another_users_attempt(client):
    admin = make_admin(client)
    owner = make_user(client, "owner@example.com")
    other = make_user(client, "other@example.com")
    quiz = create_quiz(client, admin)

    attempt_id = start(client, owner, quiz["id"]).json()["attempt_id"]
    assert submit(client, other, attempt_id, answers_with_correct(quiz, 3)).status_code == 404
    assert client.get(f"/attempts/{attempt_id}", headers=other).status_code == 404
    assert client.get(f"/attempts/{attempt_id}", headers=owner).status_code == 200


def test_invalid_answers_rejected_and_attempt_stays_open(client):
    admin = make_admin(client)
    user = make_user(client)
    quiz = create_quiz(client, admin)
    attempt_id = start(client, user, quiz["id"]).json()["attempt_id"]

    r = submit(client, user, attempt_id, [{"question_id": 999, "selected_option": 0}])
    assert r.status_code == 422

    q1 = quiz["questions"][0]["id"]
    dup = [{"question_id": q1, "selected_option": 0}, {"question_id": q1, "selected_option": 1}]
    assert submit(client, user, attempt_id, dup).status_code == 422

    bad_option = [{"question_id": q1, "selected_option": 99}]
    assert submit(client, user, attempt_id, bad_option).status_code == 422

    # attempt is still open and can be submitted properly
    assert submit(client, user, attempt_id, answers_with_correct(quiz, 3)).status_code == 200


def test_attempt_history(client):
    admin = make_admin(client)
    user = make_user(client)
    quiz = create_quiz(client, admin)

    a1 = start(client, user, quiz["id"]).json()["attempt_id"]
    submit(client, user, a1, answers_with_correct(quiz, 3))
    a2 = start(client, user, quiz["id"]).json()["attempt_id"]
    submit(client, user, a2, answers_with_correct(quiz, 0))

    r = client.get("/attempts", headers=user)
    assert r.status_code == 200
    statuses = [a["status"] for a in r.json()]
    assert statuses == ["failed", "passed"]  # newest first