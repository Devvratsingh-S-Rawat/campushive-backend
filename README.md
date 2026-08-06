# CampusHive API

FastAPI backend for CampusHive. Auth, fests, events, interest tracking, Razorpay
registration, and AI-generated insights for college reps — all built and tested.

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
  dashboard (Settings → API Keys). No KYC needed for test mode.
- `GEMINI_API_KEY` — free key from Google AI Studio (aistudio.google.com/apikey), no
  card needed.

Each of these only breaks the specific endpoint that needs it — missing `GEMINI_API_KEY`
doesn't stop auth, fests, or events from working, it just fails `/insights` specifically,
with a clear error message telling you exactly what's missing.

## Run it

```bash
python -m uvicorn app.main:app --reload
```
(Use `python -m uvicorn ...` instead of a bare `uvicorn` command if your terminal
doesn't have it on PATH — this always works regardless.)

- API: http://localhost:8000
- Interactive docs (test every endpoint from the browser): http://localhost:8000/docs

Tables are created automatically on startup — no migration step needed for now.

## Verify it works

Two different checks, for two different purposes:

```bash
python smoke_test.py
```
Fast, mocks Razorpay and Gemini, no real keys needed. Verifies your endpoint *logic* is
correct — permissions, data handling, error cases. Run this after every change.

```bash
python test_live.py
```
Slower, makes real calls to Razorpay and Gemini using whatever's in your `.env`. Verifies
your actual keys work, not just the code around them. Run this once after setting up real
credentials, and again if either integration ever starts behaving strangely.

## Project layout

```
app/
├── main.py           # FastAPI app + router registration
├── config.py         # env var loading
├── database.py       # DB engine/session
├── models.py         # SQLAlchemy models — the schema
├── schemas.py        # Pydantic request/response shapes
├── auth.py           # password hashing, JWT, role-checking dependencies
└── routers/
    ├── auth.py       # signup, login, me
    ├── fests.py      # fest CRUD, interest toggle, AI insights
    └── events.py     # event CRUD, Razorpay registration
```

## Deploying

Same as WebGuard/CodeCrew — pin Python 3.11 on Render, set the env vars in the Render
dashboard (don't commit `.env`), start command:

```
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Status

Backend is functionally complete — auth, fest/event CRUD, Razorpay registration, and AI
insights are all built and tested (`smoke_test.py`: 29 checks, all passing). Remaining
work is frontend: Akshay (student flows), Atharva (college-rep flows + the insights
card), Jeet (auth UI + Razorpay checkout integration) — see `API_CONTRACT.md`.
