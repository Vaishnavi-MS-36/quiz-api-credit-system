import os

# Must be set BEFORE the app is imported, so the app connects to the test database.
os.environ["DATABASE_URL"] = "postgresql+psycopg2://quiz:quiz@127.0.0.1:5433/quizdb_test"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import engine  # noqa: E402
from app.main import app  # noqa: E402

assert "quizdb_test" in str(engine.url), "Tests must never run against the dev database"


@pytest.fixture(autouse=True)
def clean_db():
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE users, quizzes, questions, quiz_attempts, transactions "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest.fixture
def client():
    return TestClient(app)