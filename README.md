# Quiz API with Credit System

REST API for a quiz application with a stake-and-reward credit system, plus a React frontend called **Quiz Arena**.
Built with FastAPI, PostgreSQL and SQLAlchemy, containerised with Docker and deployed on GCP Cloud Run.

- **Quiz Arena (frontend):** `https://quiz-arena-vaishnavi.vercel.app`
- **Live API:** `https://quiz-api-967410411564.asia-south1.run.app`
- **Swagger docs:** `https://quiz-api-967410411564.asia-south1.run.app/docs`
- **DigitalAPI Gateway URL:** `https://vaish-quiz-api-test.ft-gateway.digitalapicraft.com`
- **DigitalAPI Developer Portal:** `https://vaish-quiz-api.trial.digitalapi.ai/quiz-api-credit-system` (the portal asks for a free signup)
- **Source code:** `https://github.com/Vaishnavi-MS-36/quiz-api-credit-system`

## Try it

Open Quiz Arena, click **New here? Create an account**, and you get 500 credits. Pick a quiz, stake credits, answer the questions and see whether you win the reward. The Wallet tab shows your ledger and lets you buy more credits (simulated payment, including a declined card).

Reviewer logins for a ready-made user and an admin are in the submission email.

## Features

- Register and log in (JWT bearer tokens, bcrypt-hashed passwords)
- Role-based access: `user` and `admin`
- Admins create, update and delete quizzes and questions
- Users list quizzes, start a quiz (stake credits), answer, submit and get a score
- Credit system: 500 signup credits, stake to enter, reward on pass, stake lost on fail
- Buy credits through a mock payment
- Balance and full transaction history (append-only ledger)
- Input validation, consistent error responses, 39 automated tests
- React frontend: login and register, quiz tables, play and results, wallet and ledger, admin quiz publishing and removal

## Credit rules

| Event | Effect |
|---|---|
| Register | +500 credits (`signup_bonus`) |
| Start a quiz | `-stake_amount` immediately (`stake`) |
| Submit and pass (score >= `pass_percentage`) | `+reward_amount` (`reward`) |
| Submit and fail | nothing more; the stake is lost |
| Buy credits | `+amount` (`purchase`); `mock_card_decline` returns 402 and changes nothing |

Example: stake 100, reward 200. Passing nets +100, failing nets -100.

## Tech stack

- **Backend:** Python 3.13, FastAPI, SQLAlchemy 2.x, PostgreSQL 16, Pydantic v2, python-jose (JWT), bcrypt, pytest, Docker
- **Frontend:** React 18, Vite, plain CSS (no UI library)
- **Hosting:** GCP Cloud Run (API), Neon (PostgreSQL), Vercel (frontend), DigitalAPI Gateway and Developer Portal

## Architecture and deployment

```
Quiz Arena (React, Vercel) -> Cloud Run (FastAPI container) -> PostgreSQL (Neon)
Other clients -> DigitalAPI Gateway -> Cloud Run (FastAPI container)
                        |
        DigitalAPI Developer Portal (API catalogue, docs, "Test this API")
```

- The FastAPI app is built into a Docker image and deployed to **GCP Cloud Run** (region `asia-south1`).
- The database is a hosted **PostgreSQL** instance (Neon). The connection string is passed as an environment variable and is never stored in the repository.
- The API is imported into the **DigitalAPI Gateway** from its OpenAPI spec, with the Cloud Run service as the upstream, and published on the **DigitalAPI Developer Portal**.
- The frontend is a static Vite build hosted on Vercel. It calls the API directly, using `VITE_API_URL`.

## Project structure

```
app/
  main.py          app setup, CORS, routers, error handlers
  config.py        settings from environment variables
  database.py      engine and session
  models.py        users, quizzes, questions, quiz_attempts, transactions
  schemas.py       request/response models (public vs admin views)
  security.py      password hashing and JWT
  deps.py          get_current_user, require_admin
  errors.py        exception handlers
  seed.py          optional admin creation on startup
  services/credits.py   row locking and ledger writes
  routers/         auth, quizzes, attempts, credits
tests/             pytest suite (incl. concurrency tests)
frontend/          Quiz Arena (React + Vite)
  src/App.jsx      all screens: auth, quizzes, play, result, wallet, admin
  src/styles.css   casino-table theme
```

## Run the backend locally

Requirements: Python 3.13, Docker.

```bash
# 1. Start PostgreSQL (host port 5433)
docker compose up -d

# 2. Create a virtualenv and install dependencies
python -m venv venv
venv\Scripts\activate          # Mac/Linux: source venv/bin/activate
pip install -r requirements.txt

# 3. Configure environment
copy .env.example .env         # Mac/Linux: cp .env.example .env

# 4. Run
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs. If `ADMIN_EMAIL` and `ADMIN_PASSWORD` are set,
an admin user is created on startup.

## Run the frontend locally

Requirements: Node.js 20 or newer.

```bash
cd frontend
npm install
echo VITE_API_URL=https://quiz-api-967410411564.asia-south1.run.app > .env
npm run dev
```

Open http://localhost:5173. To use a local backend, set `VITE_API_URL=http://127.0.0.1:8000` instead.
The frontend deploys to Vercel from the `frontend` folder, with `VITE_API_URL` set as an environment variable.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | yes | SQLAlchemy URL, e.g. `postgresql+psycopg2://user:pass@host:5432/db` |
| `SECRET_KEY` | yes | JWT signing key (use a long random value) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | Token lifetime, default 60 |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | no | Creates an admin on startup if it does not exist |
| `VITE_API_URL` | frontend | Base URL of the API, used at build time |

## Run with Docker

```bash
docker build -t quiz-api .
docker run --rm -p 8080:8080 \
  -e DATABASE_URL=postgresql+psycopg2://quiz:quiz@host.docker.internal:5433/quizdb \
  -e SECRET_KEY=change-me \
  -e ADMIN_EMAIL=admin@example.com -e ADMIN_PASSWORD=AdminPass123 \
  quiz-api
```

## Deploy to Cloud Run

```bash
gcloud run deploy quiz-api --source . --region asia-south1 --allow-unauthenticated \
  --set-env-vars "DATABASE_URL=...,SECRET_KEY=...,ADMIN_EMAIL=...,ADMIN_PASSWORD=..."
```

Use your own database URL, a long random secret key and a strong admin password.
Do not commit real values.

## Tests

Tests run against a separate database (`quizdb_test`) and never touch dev data.

```bash
docker compose exec db psql -U quiz -d quizdb -c "CREATE DATABASE quizdb_test;"
python -m pytest -v
```

The suite covers auth, authorization, validation, the full quiz flow, the credit
ledger, and concurrency (parallel stakes, double submits and purchases).

## API overview

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/health` | public | Health check |
| POST | `/auth/register` | public | Register (+500 credits) |
| POST | `/auth/login` | public | Get a JWT |
| GET | `/auth/me` | user | Current user |
| GET | `/quizzes` | user | List active quizzes |
| GET | `/quizzes/{id}` | user | Quiz with questions (no answers) |
| POST | `/quizzes/{id}/start` | user | Stake credits and start an attempt |
| POST | `/attempts/{id}/submit` | user | Submit answers, get score, reward or loss |
| GET | `/attempts`, `/attempts/{id}` | user | Own attempts |
| GET | `/credits/balance` | user | Current balance |
| GET | `/credits/transactions` | user | History (`type`, `limit`, `offset`) |
| POST | `/credits/purchase` | user | Mock payment to buy credits |
| POST, GET | `/admin/quizzes` | admin | Create / list quizzes (with answers) |
| GET, PATCH, DELETE | `/admin/quizzes/{id}` | admin | Read / update / delete a quiz |
| POST | `/admin/quizzes/{id}/questions` | admin | Add a question |
| PATCH, DELETE | `/admin/quizzes/{id}/questions/{qid}` | admin | Update / delete a question |

Full request and response schemas are in Swagger at `/docs`.

## Error format

- `401` missing or invalid token, `403` not an admin, `404` not found
- `409` conflict (duplicate email, attempt in progress, already submitted)
- `402` insufficient credits or declined payment
- `422` validation: `{"detail": "Validation failed", "errors": [{"field": "...", "message": "..."}]}`
- `500` `{"detail": "Internal server error"}` (details are logged, never returned)

## How credit balances stay consistent

1. **Single transaction:** the balance change, the attempt update and the ledger row are committed together or rolled back together.
2. **Row locks:** `SELECT ... FOR UPDATE` on the user row for every credit change, so concurrent requests queue instead of overwriting each other (no lost updates, no double spend).
3. **Attempt lock on submit:** the attempt row is locked, so a double or parallel submit pays the reward exactly once.
4. **Database constraint:** `CHECK (credits >= 0)` on `users`, so a negative balance is impossible even if application code has a bug.
5. **Append-only ledger:** every change is a `transactions` row with `balance_after`. For every user, `balance == SUM(ledger)`, and the tests assert this.
6. **Stake snapshot:** the stake is stored on the attempt, so editing a quiz later does not change past attempts.

## Design choices

- **PostgreSQL** for real transactions and row-level locking.
- **Separate public and admin schemas**, so correct answers never leak to normal users.
- **Admins cannot self-register**; the admin comes from environment variables or a database update.
- **Quizzes with attempts cannot be deleted**, only hidden, to keep history intact. The frontend offers to hide them.
- **Resumable attempts:** if a player leaves a quiz halfway, the open attempt can be resumed without a second stake.
- **Mock payment** is simulated with a `payment_method` field; a real gateway would slot in at the same place.
- **Tables are created on startup** for simplicity; Alembic migrations would be the production upgrade.
- **CORS is open (`*`)** so the frontend and API tools can call the API. A production setup would allow only the frontend origin.