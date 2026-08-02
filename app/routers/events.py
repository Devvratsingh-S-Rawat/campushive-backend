from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas, auth

router = APIRouter(tags=["events"])


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
    # Week 2 — Jeet wires Razorpay in here. For now this creates a pending registration
    # so Akshay can build the register-button UI against a real response today.
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    registration = models.Registration(user_id=current_user.id, event_id=event_id)
    db.add(registration)
    db.commit()
    db.refresh(registration)
    return schemas.RegistrationOut(
        id=registration.id,
        event_id=event_id,
        status=registration.status,
        message="Registered — payment integration lands week 2",
    )
