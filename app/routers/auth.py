from fastapi import APIRouter, Depends, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app import models, schemas, auth

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=schemas.Token)
def signup(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = models.User(
        email=payload.email,
        password_hash=auth.hash_password(payload.password),
        name=payload.name,
        role=payload.role,
        college_name=payload.college_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = auth.create_access_token({"sub": str(user.id)})
    return schemas.Token(access_token=token, user=user)


@router.post("/login", response_model=schemas.Token)
def login(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    # user.password_hash is None for Google-only accounts — guard before verify_password,
    # which can't hash-compare against nothing
    if not user or not user.password_hash or not auth.verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = auth.create_access_token({"sub": str(user.id)})
    return schemas.Token(access_token=token, user=user)


@router.post("/google", response_model=schemas.Token)
def google_auth(payload: schemas.GoogleAuthRequest, db: Session = Depends(get_db)):
    if not settings.google_client_id:
        raise HTTPException(status_code=503, detail="Google sign-in isn't configured on the server (GOOGLE_CLIENT_ID missing)")

    try:
        idinfo = google_id_token.verify_oauth2_token(
            payload.credential,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    if idinfo.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise HTTPException(status_code=401, detail="Invalid token issuer")
    if not idinfo.get("email_verified", False):
        raise HTTPException(status_code=401, detail="Google email not verified")

    google_id = idinfo["sub"]
    email = idinfo["email"]
    name = idinfo.get("name") or email.split("@")[0]

    user = db.query(models.User).filter(models.User.google_id == google_id).first()

    if user is None:
        # fall back to matching by email so an existing password account
        # gets linked instead of duplicated
        user = db.query(models.User).filter(func.lower(models.User.email) == email.lower()).first()

    if user is None:
        role = models.UserRole.college_rep if payload.role == "college_rep" else models.UserRole.student
        user = models.User(
            email=email,
            name=name,
            google_id=google_id,
            password_hash=None,
            role=role,
        )
        db.add(user)
    elif user.google_id is None:
        user.google_id = google_id  # link the existing password account to this Google identity

    db.commit()
    db.refresh(user)

    token = auth.create_access_token({"sub": str(user.id)})
    return schemas.Token(access_token=token, user=user)


@router.get("/me", response_model=schemas.UserOut)
def get_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user
