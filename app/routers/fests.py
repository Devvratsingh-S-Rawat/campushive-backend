import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from google import genai
from google.genai import types as genai_types

from app.config import settings
from app.database import get_db
from app import models, schemas, auth

router = APIRouter(prefix="/fests", tags=["fests"])

_gemini_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=settings.gemini_api_key)
    return _gemini_client


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


def _aggregate_fest_stats(fest: models.Fest) -> dict:
    total_interested = len(fest.interests)
    events_stats = []
    total_paid = 0
    total_pending = 0

    for event in fest.events:
        paid = sum(1 for r in event.registrations if r.status == models.RegistrationStatus.paid)
        pending = sum(1 for r in event.registrations if r.status == models.RegistrationStatus.pending)
        total_paid += paid
        total_pending += pending
        events_stats.append({
            "name": event.name,
            "category": event.category,
            "entry_fee": event.entry_fee,
            "max_participants": event.max_participants,
            "paid_registrations": paid,
            "pending_registrations": pending,
            "fill_rate_pct": round(paid / event.max_participants * 100, 1) if event.max_participants else None,
        })

    return {
        "fest_name": fest.name,
        "total_interested": total_interested,
        "total_events": len(fest.events),
        "total_paid_registrations": total_paid,
        "total_pending_registrations": total_pending,
        "conversion_rate_pct": round(total_paid / total_interested * 100, 1) if total_interested else 0,
        "events": events_stats,
    }


def _generate_ai_insights(stats: dict) -> List[str]:
    if not settings.gemini_api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not set in .env")

    prompt = (
        "You are an event analytics assistant for a college fest organizer. "
        "Based on this data, write 3-4 concise, specific, actionable insights to help "
        "them plan next year's fest better. Focus on what worked, what underperformed, "
        "and concrete suggestions. Avoid generic filler advice.\n\n"
        f"Data: {json.dumps(stats)}\n\n"
        'Respond with JSON only, in this exact shape: {"insights": ["insight 1", "insight 2"]}'
    )

    client = _get_gemini_client()
    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not reach Gemini: {e}")

    try:
        parsed = json.loads(response.text)
        insights = parsed.get("insights") or []
        if insights:
            return insights
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass

    # Model didn't cooperate with JSON mode — fall back to parsing plain text lines
    lines = [l.strip("-•* ").strip() for l in (response.text or "").split("\n") if l.strip()]
    if lines:
        return lines[:5]

    raise HTTPException(status_code=502, detail="Gemini returned an empty response")


@router.get("/{fest_id}/insights", response_model=schemas.InsightsOut)
def get_fest_insights(
    fest_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.college_rep)),
):
    fest = db.query(models.Fest).filter(models.Fest.id == fest_id).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    if fest.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="You don't own this fest")

    stats = _aggregate_fest_stats(fest)

    if stats["total_interested"] == 0 and stats["total_paid_registrations"] == 0:
        return schemas.InsightsOut(
            insights=["Not enough activity yet — check back once students start showing interest or registering."],
            stats=stats,
        )

    insights = _generate_ai_insights(stats)
    return schemas.InsightsOut(insights=insights, stats=stats)
