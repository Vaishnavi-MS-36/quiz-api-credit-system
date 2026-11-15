from tests.helpers import answers_with_correct, create_quiz, make_admin, make_user, quiz_payload


def test_admin_routes_require_auth_and_admin_role(client):
    user = make_user(client)
    assert client.post("/admin/quizzes", json=quiz_payload()).status_code == 401
    assert client.post("/admin/quizzes", json=quiz_payload(), headers=user).status_code == 403
    assert client.get("/admin/quizzes", headers=user).status_code == 403


def test_admin_can_create_quiz_with_questions(client):
    admin = make_admin(client)
    quiz = create_quiz(client, admin)
    assert quiz["title"] == "Python Basics"
    assert len(quiz["questions"]) == 3
    assert "correct_option" in quiz["questions"][0]


def test_user_list_shows_question_count(client):
    admin = make_admin(client)
    user = make_user(client)
    create_quiz(client, admin)
    r = client.get("/quizzes", headers=user)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["question_count"] == 3


def test_user_quiz_detail_hides_correct_answers(client):
    admin = make_admin(client)
    user = make_user(client)
    quiz = create_quiz(client, admin)
    r = client.get(f"/quizzes/{quiz['id']}", headers=user)
    assert r.status_code == 200
    assert len(r.json()["questions"]) == 3
    for q in r.json()["questions"]:
        assert "correct_option" not in q


def test_quiz_validation(client):
    admin = make_admin(client)
    bad = quiz_payload()
    bad["questions"][0]["correct_option"] = 9
    assert client.post("/admin/quizzes", json=bad, headers=admin).status_code == 422

    bad2 = quiz_payload(stake=0)
    assert client.post("/admin/quizzes", json=bad2, headers=admin).status_code == 422

    bad3 = quiz_payload(pass_percentage=101)
    assert client.post("/admin/quizzes", json=bad3, headers=admin).status_code == 422


def test_quiz_not_found(client):
    user = make_user(client)
    assert client.get("/quizzes/999", headers=user).status_code == 404
    assert client.get("/quizzes/abc", headers=user).status_code == 422


def test_inactive_quiz_hidden_from_users(client):
    admin = make_admin(client)
    user = make_user(client, "u@example.com")
    quiz = create_quiz(client, admin)
    r = client.patch(f"/admin/quizzes/{quiz['id']}", json={"is_active": False}, headers=admin)
    assert r.status_code == 200
    assert client.get("/quizzes", headers=user).json() == []
    assert client.get(f"/quizzes/{quiz['id']}", headers=user).status_code == 404
    assert client.post(f"/quizzes/{quiz['id']}/start", headers=user).status_code == 404


def test_admin_update_quiz(client):
    admin = make_admin(client)
    quiz = create_quiz(client, admin)
    r = client.patch(f"/admin/quizzes/{quiz['id']}", json={"title": "New Title"}, headers=admin)
    assert r.status_code == 200
    assert r.json()["title"] == "New Title"
    assert r.json()["stake_amount"] == 100  # untouched


def test_admin_add_update_delete_question(client):
    admin = make_admin(client)
    quiz = create_quiz(client, admin)
    qid = quiz["id"]

    r = client.post(
        f"/admin/quizzes/{qid}/questions",
        json={"text": "Extra?", "options": ["x", "y"], "correct_option": 0},
        headers=admin,
    )
    assert r.status_code == 201
    question_id = r.json()["id"]

    r = client.patch(
        f"/admin/quizzes/{qid}/questions/{question_id}",
        json={"correct_option": 9},
        headers=admin,
    )
    assert r.status_code == 422

    r = client.patch(
        f"/admin/quizzes/{qid}/questions/{question_id}",
        json={"text": "Changed?"},
        headers=admin,
    )
    assert r.status_code == 200
    assert r.json()["text"] == "Changed?"

    assert (
        client.delete(f"/admin/quizzes/{qid}/questions/{question_id}", headers=admin).status_code
        == 204
    )
    assert (
        client.delete(f"/admin/quizzes/{qid}/questions/{question_id}", headers=admin).status_code
        == 404
    )


def test_delete_quiz_without_attempts_ok_but_with_attempts_conflict(client):
    admin = make_admin(client)
    user = make_user(client)

    empty = create_quiz(client, admin, title="Delete me")
    assert client.delete(f"/admin/quizzes/{empty['id']}", headers=admin).status_code == 204

    used = create_quiz(client, admin, title="Used")
    assert client.post(f"/quizzes/{used['id']}/start", headers=user).status_code == 201
    r = client.delete(f"/admin/quizzes/{used['id']}", headers=admin)
    assert r.status_code == 409