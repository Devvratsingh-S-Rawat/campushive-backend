# CampusHive API contract

Base URL locally: `http://localhost:8000`. Once deployed, Devvrat will share the Render URL.

All authenticated requests need a header: `Authorization: Bearer <access_token>`.

You can also just open `/docs` in the browser and try every endpoint interactively —
easier than reading this if you want to poke around.

---

## Auth

### `POST /auth/signup`
```json
// request
{
  "email": "you@college.ac.in",
  "password": "at least something",
  "name": "Your Name",
  "role": "student",          // or "college_rep"
  "college_name": "IIT Bombay" // optional, mainly for college_rep
}
```
```json
// response 200
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": { "id": 1, "email": "...", "name": "...", "role": "student", "college_name": null }
}
```
`400` if email already registered.

### `POST /auth/login`
Same request/response shape as signup, minus `name`/`role`/`college_name` in the request.
`401` on wrong email/password.

### `GET /auth/me` (auth required)
Returns the current user object (same shape as `user` above).

---

## Fests

### `GET /fests?category=Technical&search=iit`
Both query params optional. Returns a list:
```json
[
  {
    "id": 1, "name": "Techfest 2026", "college_name": "IIT Bombay",
    "location": "Mumbai, Maharashtra", "description": "...",
    "category": ["Technical", "Cultural"],
    "start_date": "2026-08-14T00:00:00", "end_date": "2026-08-16T00:00:00",
    "interested_count": 2147, "event_count": 5
  }
]
```

### `GET /fests/{id}`
Same shape as one item above. `404` if not found.

### `POST /fests` (auth required, college_rep only)
```json
// request
{
  "name": "Techfest 2026", "college_name": "IIT Bombay", "location": "Mumbai, Maharashtra",
  "description": "Asia's largest tech fest.", "category": ["Technical", "Cultural"],
  "start_date": "2026-08-14T00:00:00", "end_date": "2026-08-16T00:00:00"
}
```
Returns the created fest (same shape as `GET`). `403` if you're a student.

### `POST /fests/{id}/interest` (auth required, student only)
Toggles — call it again to un-interest. No request body.
```json
// response
{ "fest_id": 1, "interested": true, "interested_count": 2148 }
```

---

## Events

### `GET /fests/{fest_id}/events`
```json
[
  {
    "id": 1, "fest_id": 1, "name": "Robowar Championship", "category": "Technical",
    "description": "Battle of autonomous robots.", "event_date": "2026-08-14T10:00:00",
    "location": "Sports Complex, IITB", "max_participants": 64, "entry_fee": 500,
    "registered_count": 12
  }
]
```

### `POST /fests/{fest_id}/events` (auth required, college_rep who owns the fest)
```json
// request
{
  "name": "Robowar Championship", "category": "Technical",
  "description": "Battle of autonomous robots.", "event_date": "2026-08-14T10:00:00",
  "location": "Sports Complex, IITB", "max_participants": 64, "entry_fee": 500
}
```
`entry_fee` is in plain rupees (500 = ₹500), not paise. `403` if you don't own the parent fest.

### `POST /events/{id}/register` (auth required, student only)
No request body yet.
```json
// response — week 1 (payment not wired yet)
{ "id": 1, "event_id": 1, "status": "pending", "message": "Registered — payment integration lands week 2" }
```
Week 2: this will return `status: "paid"` once Razorpay is wired in, and will need a
payment token in the request. Contract update coming when that's ready — build your UI
against `pending` for now, the button/flow won't need to change, just the response detail.

---

## Coming in week 2 (don't build against these yet, just know they're coming)

- `GET /fests/{id}/insights` (college_rep, owner only) — returns AI-generated insight
  bullets for the dashboard card.
- Registration request body will need a Razorpay order/payment id once that's wired in.
