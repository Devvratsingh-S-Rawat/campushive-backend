# CampusHive API

FastAPI backend for CampusHive. Handles auth, fests, events, interest tracking, and
registration. Payment (Razorpay) and AI insights land in week 2 — see `API_CONTRACT.md`
for what's coming.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and fill in:
- `DATABASE_URL` — your Neon connection string (Neon dashboard → Connection Details).
  Leave it as the sqlite default if you just want to run locally without Neon yet.
- `SECRET_KEY` — generate one with `python3 -c "import secrets; print(secrets.token_hex(32))"`

## Run it

```bash
uvicorn app.main:app --reload
```

- API: http://localhost:8000
- Interactive docs (test every endpoint from the browser): http://localhost:8000/docs

Tables are created automatically on startup — no migration step needed for now.

## Verify it works

```bash
python3 smoke_test.py
```

Runs the full flow (signup, login, create fest, create event, interest, register) against
a throwaway sqlite db and prints PASS/FAIL for each step. Run this after pulling changes
to make sure nothing broke.

## Project layout

```
app/
├── main.py           # FastAPI app + router registration
├── config.py         # env var loading
├── database.py        # DB engine/session
├── models.py          # SQLAlchemy models — the schema
├── schemas.py          # Pydantic request/response shapes
├── auth.py            # password hashing, JWT, role-checking dependencies
└── routers/
    ├── auth.py         # signup, login, me
    ├── fests.py         # fest CRUD + interest toggle
    └── events.py       # event CRUD + registration
```

## Deploying

Same as WebGuard/CodeCrew — pin Python 3.11 on Render, set the env vars in the Render
dashboard (don't commit `.env`), start command:

```
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## What's next (week 2)

- `POST /events/{id}/register` currently creates a `pending` registration with no real
  payment. Jeet wires Razorpay checkout in here and flips status to `paid`.
- `GET /fests/{id}/insights` — Devvrat adds this: aggregates interest/registration data
  and calls Gemini to generate the AI insights card for the college-rep dashboard.
