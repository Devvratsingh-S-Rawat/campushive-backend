"""
Quick end-to-end check — not the real test suite, just verifying the skeleton
actually works before handing it off. Uses the default sqlite db.
"""
import os

# make sure we're on a clean sqlite file for this run
if os.path.exists("campushive.db"):
    os.remove("campushive.db")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


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
    "email": "rep@iitb.ac.in", "password": "pass1234", "name": "Fest Rep",
    "role": "college_rep", "college_name": "IIT Bombay",
})
check("signup college_rep", r.status_code == 200)
rep_token = r.json()["access_token"]

# signup student
r = client.post("/auth/signup", json={
    "email": "student@atharva.ac.in", "password": "pass1234", "name": "Devvrat",
    "role": "student",
})
check("signup student", r.status_code == 200)
student_token = r.json()["access_token"]

# duplicate signup should fail
r = client.post("/auth/signup", json={
    "email": "rep@iitb.ac.in", "password": "pass1234", "name": "Dup",
    "role": "college_rep",
})
check("duplicate signup rejected", r.status_code == 400)

# login
r = client.post("/auth/login", json={"email": "rep@iitb.ac.in", "password": "pass1234"})
check("login works", r.status_code == 200)

# wrong password
r = client.post("/auth/login", json={"email": "rep@iitb.ac.in", "password": "wrong"})
check("wrong password rejected", r.status_code == 401)

# /me
r = client.get("/auth/me", headers={"Authorization": f"Bearer {rep_token}"})
check("get me", r.status_code == 200 and r.json()["email"] == "rep@iitb.ac.in")

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
check("list fests", r.status_code == 200 and len(r.json()) == 1)

# filter by category
r = client.get("/fests?category=Technical")
check("filter by category", r.status_code == 200 and len(r.json()) == 1)

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

# student registers for event
r = client.post(f"/events/{event_id}/register", headers={"Authorization": f"Bearer {student_token}"})
check("register for event", r.status_code == 200 and r.json()["status"] == "pending")

# no auth token at all
r = client.post(f"/fests/{fest_id}/interest")
check("unauthenticated request rejected", r.status_code == 401)

print("\nAll checks passed.")
