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
- `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` — free test-mode keys from your Razorpay
  dashboard (Settings → API Keys). No KYC needed for test mode. Endpoints that touch
  Razorpay will fail without these set — everything else works fine without them.

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

## What's next

- Razorpay is done on the backend (order creation + signature verification, see
  `API_CONTRACT.md`). Jeet builds the frontend checkout flow that calls it — the secret
  key stays server-side, only the public `razorpay_key_id` goes to the frontend.
- `GET /fests/{id}/insights` — next up: aggregates interest/registration data and calls
  Gemini to generate the AI insights card for the college-rep dashboard.

## A note on testing

`smoke_test.py` mocks the Razorpay API calls (no real test keys were available when this
was built) — it verifies order creation, duplicate-registration blocking, signature
verification, and free-event handling all work correctly, but hasn't hit Razorpay's
actual servers. Once real test keys are in `.env`, do one real manual test through
`/docs` or the frontend to confirm end-to-end before demo day.
