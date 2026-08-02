from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app import models, schemas, auth

router = APIRouter(prefix="/fests", tags=["fests"])


def _to_fest_out(fest: models.Fest) -> schemas.FestOut:
    return schemas.FestOut(
        id=fest.id,
        name=fest.name,
        college_name=fest.college_name,
        location=fest.location,
        description=fest.description,
        category=fest.category,
        start_date=fest.start_date,
        end_date=fest.end_date,
        interested_count=len(fest.interests),
        event_count=len(fest.events),
    )


@router.get("", response_model=List[schemas.FestOut])
def list_fests(category: Optional[str] = None, search: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.Fest)
    if category and category.lower() != "all":
        query = query.filter(models.Fest.category.ilike(f"%{category}%"))
    if search:
        query = query.filter(
            or_(models.Fest.name.ilike(f"%{search}%"), models.Fest.college_name.ilike(f"%{search}%"))
        )
    fests = query.order_by(models.Fest.start_date).all()
    return [_to_fest_out(f) for f in fests]


@router.get("/{fest_id}", response_model=schemas.FestOut)
def get_fest(fest_id: int, db: Session = Depends(get_db)):
    fest = db.query(models.Fest).filter(models.Fest.id == fest_id).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    return _to_fest_out(fest)


@router.post("", response_model=schemas.FestOut)
def create_fest(
    payload: schemas.FestCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.college_rep)),
):
    fest = models.Fest(
        name=payload.name,
        college_name=payload.college_name,
        location=payload.location,
        description=payload.description,
        category=",".join(payload.category),
        start_date=payload.start_date,
        end_date=payload.end_date,
        created_by=current_user.id,
    )
    db.add(fest)
    db.commit()
    db.refresh(fest)
    return _to_fest_out(fest)


@router.post("/{fest_id}/interest", response_model=schemas.InterestOut)
def toggle_interest(
    fest_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.student)),
):
    fest = db.query(models.Fest).filter(models.Fest.id == fest_id).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")

    existing = (
        db.query(models.Interest)
        .filter(models.Interest.fest_id == fest_id, models.Interest.user_id == current_user.id)
        .first()
    )
    if existing:
        db.delete(existing)
        db.commit()
        interested = False
    else:
        db.add(models.Interest(fest_id=fest_id, user_id=current_user.id))
        db.commit()
        interested = True

    count = db.query(models.Interest).filter(models.Interest.fest_id == fest_id).count()
    return schemas.InterestOut(fest_id=fest_id, interested=interested, interested_count=count)
