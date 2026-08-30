from typing import List

import razorpay
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app import models, schemas, auth

router = APIRouter(tags=["events"])

razorpay_client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


def _to_event_out(event: models.Event) -> schemas.EventOut:
    return schemas.EventOut(
        id=event.id,
        fest_id=event.fest_id,
        name=event.name,
        category=event.category,
        description=event.description,
        event_date=event.event_date,
        location=event.location,
        max_participants=event.max_participants,
        entry_fee=event.entry_fee,
        registered_count=len(event.registrations),
    )


@router.get("/fests/{fest_id}/events", response_model=List[schemas.EventOut])
def list_events(fest_id: int, db: Session = Depends(get_db)):
    fest = db.query(models.Fest).filter(models.Fest.id == fest_id).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    return [_to_event_out(e) for e in fest.events]


@router.post("/fests/{fest_id}/events", response_model=schemas.EventOut)
def create_event(
    fest_id: int,
    payload: schemas.EventCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.college_rep)),
):
    fest = db.query(models.Fest).filter(models.Fest.id == fest_id).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    if fest.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="You don't own this fest")

    event = models.Event(fest_id=fest_id, **payload.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return _to_event_out(event)


@router.post("/events/{event_id}/register", response_model=schemas.RegistrationOut)
def register_for_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.student)),
):
    """
    Step 1 of registration. Free events confirm immediately. Paid events create a
    Razorpay order and return the order_id + public key — frontend uses that to open
    Razorpay Checkout, then calls /verify-payment with the result.
    """
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    existing = (
        db.query(models.Registration)
        .filter(
            models.Registration.event_id == event_id,
            models.Registration.user_id == current_user.id,
            models.Registration.status != models.RegistrationStatus.failed,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Already registered for this event")

    amount_paise = event.entry_fee * 100
    registration = models.Registration(user_id=current_user.id, event_id=event_id)

    if amount_paise == 0:
        registration.status = models.RegistrationStatus.paid
        db.add(registration)
        db.commit()
        db.refresh(registration)
        return schemas.RegistrationOut(
            id=registration.id, event_id=event_id, status=registration.status,
            amount=0, message="Registered — this event is free, no payment needed",
        )

    try:
        order = razorpay_client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": f"event{event_id}_user{current_user.id}",
        })
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not create Razorpay order: {e}")

    registration.razorpay_order_id = order["id"]
    db.add(registration)
    db.commit()
    db.refresh(registration)

    return schemas.RegistrationOut(
        id=registration.id,
        event_id=event_id,
        status=registration.status,
        amount=amount_paise,
        razorpay_order_id=order["id"],
        razorpay_key_id=settings.razorpay_key_id,
        message="Order created — complete payment to confirm registration",
    )


@router.post("/events/{event_id}/verify-payment", response_model=schemas.VerifyPaymentResponse)
def verify_payment(
    event_id: int,
    payload: schemas.VerifyPaymentRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.student)),
):
    """Step 2 — frontend calls this with what Razorpay Checkout returned on success."""
    registration = (
        db.query(models.Registration)
        .filter(
            models.Registration.id == payload.registration_id,
            models.Registration.event_id == event_id,
            models.Registration.user_id == current_user.id,
        )
        .first()
    )
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")

    try:
        razorpay_client.utility.verify_payment_signature({
            "razorpay_order_id": payload.razorpay_order_id,
            "razorpay_payment_id": payload.razorpay_payment_id,
            "razorpay_signature": payload.razorpay_signature,
        })
    except razorpay.errors.SignatureVerificationError:
        registration.status = models.RegistrationStatus.failed
        db.commit()
        raise HTTPException(status_code=400, detail="Payment verification failed")

    registration.status = models.RegistrationStatus.paid
    registration.payment_id = payload.razorpay_payment_id
    db.commit()

    return schemas.VerifyPaymentResponse(status=registration.status, message="Payment verified, registration confirmed")
