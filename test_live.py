"""
Standalone live check — makes REAL calls using whatever is in your .env right now,
including a real Razorpay order creation. No mocking, no second window, no server
process to juggle. Run with: python test_live.py
"""
import os
import traceback

if os.path.exists("campushive.db"):
    os.remove("campushive.db")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def show(label, r):
    print(f"\n--- {label} ---")
    print("status:", r.status_code)
    try:
        print("body:", r.json())
    except Exception:
        print("body (not json):", r.text[:500])


try:
    r = client.post("/auth/signup", json={
        "email": "rep@test.com", "password": "test1234", "name": "Test Rep",
        "role": "college_rep", "college_name": "Test College",
    })
    show("signup rep", r)
    r.raise_for_status()
    rep_token = r.json()["access_token"]

    r = client.post("/fests", json={
        "name": "Test Fest", "college_name": "Test College", "location": "Mumbai",
        "category": ["Technical"], "start_date": "2026-08-14T00:00:00", "end_date": "2026-08-16T00:00:00",
    }, headers={"Authorization": f"Bearer {rep_token}"})
    show("create fest", r)
    r.raise_for_status()
    fest_id = r.json()["id"]

    r = client.post(f"/fests/{fest_id}/events", json={
        "name": "Test Event", "event_date": "2026-08-14T10:00:00", "entry_fee": 100,
    }, headers={"Authorization": f"Bearer {rep_token}"})
    show("create event", r)
    r.raise_for_status()
    event_id = r.json()["id"]

    r = client.post("/auth/signup", json={
        "email": "student@test.com", "password": "test1234", "name": "Test Student", "role": "student",
    })
    show("signup student", r)
    r.raise_for_status()
    student_token = r.json()["access_token"]

    r = client.post(f"/events/{event_id}/register", headers={"Authorization": f"Bearer {student_token}"})
    show("register (real Razorpay call happens here)", r)

    if r.status_code == 200 and str(r.json().get("razorpay_order_id", "")).startswith("order_"):
        print("\n>>> SUCCESS — real Razorpay order created, your keys work. <<<")
    else:
        print("\n>>> Registration responded but without a real order_id — see body above. <<<")

    # a second, free-mode registration on a new event so insights has non-zero data to work with
    r = client.post(f"/fests/{fest_id}/events", json={
        "name": "Free Workshop", "event_date": "2026-08-14T14:00:00", "entry_fee": 0,
    }, headers={"Authorization": f"Bearer {rep_token}"})
    free_event_id = r.json()["id"]
    client.post(f"/events/{free_event_id}/register", headers={"Authorization": f"Bearer {student_token}"})

    r = client.get(f"/fests/{fest_id}/insights", headers={"Authorization": f"Bearer {rep_token}"})
    show("get insights (real Gemini call happens here)", r)

    if r.status_code == 200 and len(r.json().get("insights", [])) > 0:
        print("\n>>> SUCCESS — real Gemini response, your key works. <<<")
    else:
        print("\n>>> Insights call didn't return usable data — see body above. <<<")

except Exception:
    print("\n>>> Exception raised — full traceback below, this is what we actually need <<<\n")
    traceback.print_exc()
