from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, field_validator

from app.models import UserRole, RegistrationStatus


# ---------- Auth ----------
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: UserRole
    college_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: UserRole
    college_name: Optional[str] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Fest ----------
class FestCreate(BaseModel):
    name: str
    college_name: str
    location: str
    description: Optional[str] = None
    category: List[str] = []
    start_date: datetime
    end_date: datetime


class FestOut(BaseModel):
    id: int
    name: str
    college_name: str
    location: str
    description: Optional[str] = None
    category: List[str]
    start_date: datetime
    end_date: datetime
    interested_count: int = 0
    event_count: int = 0
    user_interested: Optional[bool] = None  # null when nobody's logged in

    class Config:
        from_attributes = True

    @field_validator("category", mode="before")
    @classmethod
    def split_category(cls, v):
        if isinstance(v, str):
            return [c.strip() for c in v.split(",") if c.strip()]
        return v or []


# ---------- Event ----------
class EventCreate(BaseModel):
    name: str
    category: Optional[str] = None
    description: Optional[str] = None
    event_date: datetime
    location: Optional[str] = None
    max_participants: Optional[int] = None
    entry_fee: int = 0


class EventOut(BaseModel):
    id: int
    fest_id: int
    name: str
    category: Optional[str] = None
    description: Optional[str] = None
    event_date: datetime
    location: Optional[str] = None
    max_participants: Optional[int] = None
    entry_fee: int
    registered_count: int = 0

    class Config:
        from_attributes = True


# ---------- Interest ----------
class InterestOut(BaseModel):
    fest_id: int
    interested: bool
    interested_count: int


# ---------- Registration ----------
class RegistrationOut(BaseModel):
    id: int
    event_id: int
    status: RegistrationStatus
    amount: int  # paise. 0 = free event, no payment needed
    razorpay_order_id: Optional[str] = None
    razorpay_key_id: Optional[str] = None  # public key — safe to send to frontend
    message: str


class VerifyPaymentRequest(BaseModel):
    registration_id: int
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class VerifyPaymentResponse(BaseModel):
    status: RegistrationStatus
    message: str


# ---------- Insights ----------
class InsightsOut(BaseModel):
    insights: List[str]
    stats: dict
