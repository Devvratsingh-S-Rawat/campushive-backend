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

### `POST /events/{id}/register` (auth required, student only) — step 1
No request body. Two possible outcomes:

**Free event** (`entry_fee` was 0) — confirms immediately, no payment needed:
```json
{ "id": 5, "event_id": 1, "status": "paid", "amount": 0, "message": "Registered — this event is free, no payment needed" }
```

**Paid event** — creates a Razorpay order, does NOT confirm registration yet:
```json
{
  "id": 5, "event_id": 1, "status": "pending", "amount": 50000,
  "razorpay_order_id": "order_GAWN9beXgaqRyO",
  "razorpay_key_id": "rzp_test_xxxxxxxxxxxx",
  "message": "Order created — complete payment to confirm registration"
}
```
`amount` is in paise (50000 = ₹500). `razorpay_key_id` is the **public** key — safe to
use in the frontend to open Checkout. `400` if already registered for this event.

### `POST /events/{id}/verify-payment` (auth required, student only) — step 2
Only needed for paid events. Call this with what Razorpay Checkout's success handler
gives you:
```json
// request
{
  "registration_id": 5,
  "razorpay_order_id": "order_GAWN9beXgaqRyO",
  "razorpay_payment_id": "pay_xxxxxxxxxxxx",
  "razorpay_signature": "generated_signature"
}
```
```json
// response 200
{ "status": "paid", "message": "Payment verified, registration confirmed" }
```
`400` if the signature doesn't check out — registration gets marked `failed`, student
can retry by calling `/register` again.

**Frontend flow for Jeet:** call `/register` → if `amount > 0`, load Razorpay's
`checkout.js`, open it with `{ key: razorpay_key_id, order_id: razorpay_order_id, amount }`
→ on success callback you get `razorpay_payment_id` + `razorpay_signature` → POST those
plus `registration_id` to `/verify-payment` → show confirmed/failed based on the response.
The secret key never touches the frontend — only `razorpay_key_id` (public) does.

---

## Insights

### `GET /fests/{id}/insights` (auth required, college_rep who owns the fest)
No request body.
```json
{
  "insights": [
    "Technical events drew far more interest than Cultural — lean into that next year.",
    "Nearly half of interested students never registered — a reminder closer to the deadline could help."
  ],
  "stats": {
    "fest_name": "Techfest 2026",
    "total_interested": 42,
    "total_events": 3,
    "total_paid_registrations": 18,
    "conversion_rate_pct": 42.9,
    "events": [
      {"name": "Robowar Championship", "paid_registrations": 12, "fill_rate_pct": 18.8}
    ]
  }
}
```
`stats` is real numbers straight from the database — safe to render directly even if
`insights` (the AI-generated part) is ever slow or unavailable. If the fest has zero
interest and zero registrations, `insights` comes back with a single "not enough
activity yet" message and Gemini never gets called — no cost, no wait.

`403` if you're a student, or a college_rep who doesn't own this fest. `500` if
`GEMINI_API_KEY` isn't set. `502` if Gemini itself fails to respond.
