"""
Checks for Google Sign-In + event media (photos/videos). Same style as
smoke_test.py: run with `python test_google_media.py`, unique emails every run.

Google's token verification is mocked — no network calls to Google — so this
tests OUR logic (account creation, linking, role handling, error paths), not
Google's. Needs the schema migration applied if you point it at Neon.
"""
import os
import uuid
from unittest.mock import patch

# must be set before the app imports settings
os.environ["GOOGLE_CLIENT_ID"] = "test-client.apps.googleusercontent.com"

from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)
run_id = uuid.uuid4().hex[:6]


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    if not condition:
        raise SystemExit(1)


def google_signin(sub, email, role=None, verified=True, name="Test User"):
    """POST /auth/google with Google's verification mocked to return this identity."""
    claims = {
        "iss": "https://accounts.google.com", "sub": sub, "email": email,
        "email_verified": verified, "name": name,
    }
    body = {"credential": "fake-id-token"}
    if role:
        body["role"] = role
    with patch("app.routers.auth.google_id_token.verify_oauth2_token", return_value=claims):
        return client.post("/auth/google", json=body)


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- new student via Google ----------
stu_email = f"gstudent_{run_id}@gmail.com"
r = google_signin(f"sub-stu-{run_id}", stu_email, role="student")
check("google sign-in creates a new student", r.status_code == 200 and r.json()["user"]["role"] == "student")
stu = r.json()
check("response matches the normal login shape (token + user)", "access_token" in stu and stu["user"]["email"] == stu_email)

r = client.get("/auth/me", headers=bearer(stu["access_token"]))
check("token from google sign-in works on /auth/me", r.status_code == 200 and r.json()["id"] == stu["user"]["id"])

# ---------- same Google account again: login, not a duplicate ----------
r = google_signin(f"sub-stu-{run_id}", stu_email, role="college_rep")
check("returning google user gets the same account", r.status_code == 200 and r.json()["user"]["id"] == stu["user"]["id"])
check("role param is ignored for an existing account", r.json()["user"]["role"] == "student")

# ---------- new college rep via Google ----------
rep_email = f"grep_{run_id}@gmail.com"
r = google_signin(f"sub-rep-{run_id}", rep_email, role="college_rep")
check("google sign-in creates a college_rep when asked", r.status_code == 200 and r.json()["user"]["role"] == "college_rep")
rep = r.json()
check("google-created rep has no college_name on file", rep["user"]["college_name"] is None)

r = google_signin(f"sub-junk-{run_id}", f"gjunk_{run_id}@gmail.com", role="admin")
check("garbage role falls back to student", r.status_code == 200 and r.json()["user"]["role"] == "student")

# ---------- google-only accounts can't password-login (and don't crash) ----------
r = client.post("/auth/login", json={"email": stu_email, "password": "anything"})
check("password login on a google-only account is a clean 401, not a crash", r.status_code == 401)

# ---------- linking an existing password account ----------
pw_local = f"Linked_{run_id}"
r = client.post("/auth/signup", json={
    "email": f"{pw_local}@Gmail.com", "password": "pass1234", "name": "Pw User", "role": "student",
})
check("password signup", r.status_code == 200)
pw_id = r.json()["user"]["id"]

r = google_signin(f"sub-link-{run_id}", f"{pw_local.lower()}@gmail.com")
check("google sign-in links to the existing account (case-insensitive email), no duplicate",
      r.status_code == 200 and r.json()["user"]["id"] == pw_id and r.json()["user"]["role"] == "student")

r = client.post("/auth/login", json={"email": f"{pw_local}@gmail.com", "password": "pass1234"})
check("password login still works after linking", r.status_code == 200)

# ---------- error paths ----------
with patch("app.routers.auth.google_id_token.verify_oauth2_token", side_effect=ValueError("bad token")):
    r = client.post("/auth/google", json={"credential": "junk"})
check("invalid google token rejected with 401", r.status_code == 401)

r = google_signin(f"sub-unv-{run_id}", f"unverified_{run_id}@gmail.com", verified=False)
check("unverified google email rejected with 401", r.status_code == 401)

r = client.post("/auth/google", json={})
check("missing credential is a 422", r.status_code == 422)

saved = settings.google_client_id
settings.google_client_id = ""
try:
    r = google_signin(f"sub-nocfg-{run_id}", f"nocfg_{run_id}@gmail.com")
finally:
    settings.google_client_id = saved
check("unset GOOGLE_CLIENT_ID gives a clear 503, not a silent 401", r.status_code == 503 and "GOOGLE_CLIENT_ID" in r.json()["detail"])

# ---------- a google-created rep can run the whole list-a-fest flow ----------
r = client.post("/fests", json={
    "name": "Google Fest", "college_name": "Typed In College", "location": "Mumbai",
    "category": ["Technical"], "start_date": "2026-11-01T00:00:00", "end_date": "2026-11-02T00:00:00",
}, headers=bearer(rep["access_token"]))
check("google-created rep can create a fest", r.status_code == 200)
fest_id = r.json()["id"]

# ---------- event media ----------
media = [
    {"url": "https://res.cloudinary.com/demo/image/upload/v1/sample.jpg", "type": "image"},
    {"url": "https://res.cloudinary.com/demo/video/upload/v1/dog.mp4", "type": "video"},
]
event_body = {"name": "Robowar", "event_date": "2026-11-01T10:00:00", "entry_fee": 0}

r = client.post(f"/fests/{fest_id}/events", json={**event_body, "media": media}, headers=bearer(rep["access_token"]))
check("create event with a photo and a video", r.status_code == 200)
check("media comes back on the created event", r.json()["media"] == media)

r = client.post(f"/fests/{fest_id}/events", json={**event_body, "name": "No media event"}, headers=bearer(rep["access_token"]))
check("event without media still works", r.status_code == 200 and r.json()["media"] == [])

r = client.get(f"/fests/{fest_id}/events")
by_name = {e["name"]: e for e in r.json()}
check("media persists and is public on the events list", by_name["Robowar"]["media"] == media)
check("event with no media lists as an empty array", by_name["No media event"]["media"] == [])

r = client.post(f"/fests/{fest_id}/events", json={**event_body, "media": [{"url": "http://insecure.example/a.jpg", "type": "image"}]},
                headers=bearer(rep["access_token"]))
check("non-https media url rejected", r.status_code == 422)

r = client.post(f"/fests/{fest_id}/events", json={**event_body, "media": [{"url": "https://x.example/a.pdf", "type": "document"}]},
                headers=bearer(rep["access_token"]))
check("unknown media type rejected", r.status_code == 422)

r = client.post(f"/fests/{fest_id}/events", json={**event_body, "media": media}, headers=bearer(stu["access_token"]))
check("student still can't create events", r.status_code == 403)

print("\nAll checks passed.")
