"""
Quick end-to-end check — not the real test suite, just verifying the skeleton
actually works before handing it off. Safe to re-run repeatedly against either a
throwaway local sqlite db OR a real persistent database (Neon) — every run uses
fresh, unique emails so it never collides with data from a previous run.
"""
import os
import uuid
from unittest.mock import patch, MagicMock

import razorpay

# clears a local sqlite file if that's what DATABASE_URL points to. Harmless no-op
# if you're on Postgres/Neon — there's no local file to clear, which is fine, because
# the run_id below is what actually keeps re-runs from colliding either way.
if os.path.exists("campushive.db"):
    os.remove("campushive.db")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

run_id = uuid.uuid4().hex[:6]
rep_email = f"rep_{run_id}@iitb.ac.in"
student_email = f"student_{run_id}@atharva.ac.in"
other_rep_email = f"otherrep_{run_id}@vit.ac.in"


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    if not condition:
        raise SystemExit(1)


# root
r = client.get("/")
check("root endpoint", r.status_code == 200)

# signup college rep
r = client.post("/auth/signup", json={
    "email": rep_email, "password": "pass1234", "name": "Fest Rep",
    "role": "college_rep", "college_name": "IIT Bombay",
})
check("signup college_rep", r.status_code == 200)
rep_token = r.json()["access_token"]

# signup student
r = client.post("/auth/signup", json={
    "email": student_email, "password": "pass1234", "name": "Devvrat",
    "role": "student",
})
check("signup student", r.status_code == 200)
student_token = r.json()["access_token"]

# duplicate signup should fail
r = client.post("/auth/signup", json={
    "email": rep_email, "password": "pass1234", "name": "Dup",
    "role": "college_rep",
})
check("duplicate signup rejected", r.status_code == 400)

# login
r = client.post("/auth/login", json={"email": rep_email, "password": "pass1234"})
check("login works", r.status_code == 200)

# wrong password
r = client.post("/auth/login", json={"email": rep_email, "password": "wrong"})
check("wrong password rejected", r.status_code == 401)

# /me
r = client.get("/auth/me", headers={"Authorization": f"Bearer {rep_token}"})
check("get me", r.status_code == 200 and r.json()["email"] == rep_email)

# create fest as college rep
r = client.post("/fests", json={
    "name": "Techfest 2026", "college_name": "IIT Bombay", "location": "Mumbai, Maharashtra",
    "description": "Asia's largest science and tech festival.",
    "category": ["Technical", "Cultural"],
    "start_date": "2026-08-14T00:00:00", "end_date": "2026-08-16T00:00:00",
}, headers={"Authorization": f"Bearer {rep_token}"})
check("create fest as college_rep", r.status_code == 200)
fest = r.json()
check("category parsed back to list", fest["category"] == ["Technical", "Cultural"])
fest_id = fest["id"]

# student can't create a fest
r = client.post("/fests", json={
    "name": "Nope", "college_name": "X", "location": "Y",
    "category": [], "start_date": "2026-08-14T00:00:00", "end_date": "2026-08-16T00:00:00",
}, headers={"Authorization": f"Bearer {student_token}"})
check("student blocked from creating fest", r.status_code == 403)

# list fests
r = client.get("/fests")
check("list fests", r.status_code == 200 and any(f["id"] == fest_id for f in r.json()))

# filter by category
r = client.get("/fests?category=Technical")
check("filter by category", r.status_code == 200 and any(f["id"] == fest_id for f in r.json()))

# get fest detail
r = client.get(f"/fests/{fest_id}")
check("get fest detail", r.status_code == 200)

# create event under fest
r = client.post(f"/fests/{fest_id}/events", json={
    "name": "Robowar Championship", "category": "Technical",
    "description": "Battle of autonomous robots.",
    "event_date": "2026-08-14T10:00:00", "location": "Sports Complex, IITB",
    "max_participants": 64, "entry_fee": 500,
}, headers={"Authorization": f"Bearer {rep_token}"})
check("create event", r.status_code == 200)
event_id = r.json()["id"]

# list events for fest
r = client.get(f"/fests/{fest_id}/events")
check("list events", r.status_code == 200 and len(r.json()) == 1)

# student toggles interest
r = client.post(f"/fests/{fest_id}/interest", headers={"Authorization": f"Bearer {student_token}"})
check("toggle interest on", r.status_code == 200 and r.json()["interested"] is True and r.json()["interested_count"] == 1)

r = client.post(f"/fests/{fest_id}/interest", headers={"Authorization": f"Bearer {student_token}"})
check("toggle interest off", r.status_code == 200 and r.json()["interested"] is False and r.json()["interested_count"] == 0)

# --- paid registration flow (Razorpay mocked — no real keys in this sandbox) ---
with patch("app.routers.events.razorpay_client.order.create") as mock_create:
    mock_create.return_value = {"id": "order_test123", "amount": 50000, "currency": "INR"}
    r = client.post(f"/events/{event_id}/register", headers={"Authorization": f"Bearer {student_token}"})
    check(
        "register creates razorpay order",
        r.status_code == 200 and r.json()["razorpay_order_id"] == "order_test123" and r.json()["amount"] == 50000,
    )
    reg_id = r.json()["id"]

r = client.post(f"/events/{event_id}/register", headers={"Authorization": f"Bearer {student_token}"})
check("duplicate registration blocked", r.status_code == 400)

with patch("app.routers.events.razorpay_client.utility.verify_payment_signature") as mock_verify:
    mock_verify.return_value = True
    r = client.post(f"/events/{event_id}/verify-payment", json={
        "registration_id": reg_id, "razorpay_order_id": "order_test123",
        "razorpay_payment_id": "pay_test456", "razorpay_signature": "fake_sig_ok",
    }, headers={"Authorization": f"Bearer {student_token}"})
    check("verify payment success marks paid", r.status_code == 200 and r.json()["status"] == "paid")

with patch("app.routers.events.razorpay_client.utility.verify_payment_signature") as mock_verify:
    mock_verify.side_effect = razorpay.errors.SignatureVerificationError("bad signature")
    r = client.post(f"/fests/{fest_id}/events", json={
        "name": "Coding Sprint", "category": "Technical", "event_date": "2026-08-15T10:00:00",
        "entry_fee": 200,
    }, headers={"Authorization": f"Bearer {rep_token}"})
    paid_event_2 = r.json()["id"]
    with patch("app.routers.events.razorpay_client.order.create") as mock_create:
        mock_create.return_value = {"id": "order_test999", "amount": 20000}
        r = client.post(f"/events/{paid_event_2}/register", headers={"Authorization": f"Bearer {student_token}"})
        reg_id_2 = r.json()["id"]
    r = client.post(f"/events/{paid_event_2}/verify-payment", json={
        "registration_id": reg_id_2, "razorpay_order_id": "order_test999",
        "razorpay_payment_id": "pay_bad", "razorpay_signature": "fake_sig_bad",
    }, headers={"Authorization": f"Bearer {student_token}"})
    check("bad signature rejected and marked failed", r.status_code == 400)

# --- free event: no payment needed at all ---
r = client.post(f"/fests/{fest_id}/events", json={
    "name": "Intro Workshop", "category": "Technical", "event_date": "2026-08-15T14:00:00",
    "entry_fee": 0,
}, headers={"Authorization": f"Bearer {rep_token}"})
free_event_id = r.json()["id"]

r = client.post(f"/events/{free_event_id}/register", headers={"Authorization": f"Bearer {student_token}"})
check("free event registers with no payment step", r.status_code == 200 and r.json()["status"] == "paid" and r.json()["amount"] == 0)

# --- AI insights (Gemini mocked — no real key in this sandbox) ---
class FakeGeminiResponse:
    def __init__(self, text):
        self.text = text


# fresh fest with zero activity — should short-circuit before ever calling Gemini
r = client.post("/fests", json={
    "name": "Empty Fest", "college_name": "IIT Bombay", "location": "Mumbai",
    "category": [], "start_date": "2026-09-01T00:00:00", "end_date": "2026-09-02T00:00:00",
}, headers={"Authorization": f"Bearer {rep_token}"})
empty_fest_id = r.json()["id"]

with patch("app.routers.fests._get_gemini_client") as mock_client:
    r = client.get(f"/fests/{empty_fest_id}/insights", headers={"Authorization": f"Bearer {rep_token}"})
    check(
        "insights on empty fest skips Gemini entirely",
        r.status_code == 200 and not mock_client.called and "Not enough activity" in r.json()["insights"][0],
    )

# real fest (has interest + a paid registration from earlier) — mocked clean JSON response
import app.config as config_module
config_module.settings.gemini_api_key = "dummy-key-for-mocked-tests"

mock_gemini = MagicMock()
mock_gemini.models.generate_content.return_value = FakeGeminiResponse(
    '{"insights": ["Technical events drew far more interest than Cultural — lean into that next year.", '
    '"Nearly half of interested students never registered — send a reminder closer to the deadline."]}'
)
with patch("app.routers.fests._get_gemini_client", return_value=mock_gemini):
    r = client.get(f"/fests/{fest_id}/insights", headers={"Authorization": f"Bearer {rep_token}"})
    check("insights with clean JSON response", r.status_code == 200 and len(r.json()["insights"]) == 2)
    check("insights include real stats", r.json()["stats"]["fest_name"] == "Techfest 2026")

# malformed / non-JSON response from the model — should still recover via line-split fallback
mock_gemini_bad = MagicMock()
mock_gemini_bad.models.generate_content.return_value = FakeGeminiResponse(
    "- Technical events performed best this year\n- Consider more workshops next time\n"
)
with patch("app.routers.fests._get_gemini_client", return_value=mock_gemini_bad):
    r = client.get(f"/fests/{fest_id}/insights", headers={"Authorization": f"Bearer {rep_token}"})
    check("insights falls back to text parsing on bad JSON", r.status_code == 200 and len(r.json()["insights"]) == 2)

# student can't access insights at all
r = client.get(f"/fests/{fest_id}/insights", headers={"Authorization": f"Bearer {student_token}"})
check("student blocked from insights", r.status_code == 403)

# a different college_rep (not the owner) can't access this fest's insights
r = client.post("/auth/signup", json={
    "email": other_rep_email, "password": "test1234", "name": "Other Rep",
    "role": "college_rep", "college_name": "VIT Vellore",
})
other_rep_token = r.json()["access_token"]
r = client.get(f"/fests/{fest_id}/insights", headers={"Authorization": f"Bearer {other_rep_token}"})
check("non-owner college_rep blocked from insights", r.status_code == 403)

# missing GEMINI_API_KEY should fail clearly, not crash unhandled
config_module.settings.gemini_api_key = ""
r = client.get(f"/fests/{fest_id}/insights", headers={"Authorization": f"Bearer {rep_token}"})
check("missing gemini key gives clear 500, not a crash", r.status_code == 500 and "GEMINI_API_KEY" in r.json()["detail"])

# no auth token at all
r = client.post(f"/fests/{fest_id}/interest")
check("unauthenticated request rejected", r.status_code == 401)

print("\nAll checks passed.")
