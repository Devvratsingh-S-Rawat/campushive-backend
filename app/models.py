import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class UserRole(str, enum.Enum):
    student = "student"
    college_rep = "college_rep"


class RegistrationStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    failed = "failed"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=True)  # nullable: Google-only accounts have no password
    google_id = Column(String, unique=True, nullable=True, index=True)
    name = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    college_name = Column(String, nullable=True)  # only meaningful for college_rep
    created_at = Column(DateTime, default=datetime.utcnow)

    fests = relationship("Fest", back_populates="creator")
    interests = relationship("Interest", back_populates="user", cascade="all, delete-orphan")
    registrations = relationship("Registration", back_populates="user", cascade="all, delete-orphan")


class Fest(Base):
    __tablename__ = "fests"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    college_name = Column(String, nullable=False)
    location = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=True)  # comma-separated, e.g. "Technical,Cultural"
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    creator = relationship("User", back_populates="fests")
    events = relationship("Event", back_populates="fest", cascade="all, delete-orphan")
    interests = relationship("Interest", back_populates="fest", cascade="all, delete-orphan")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    fest_id = Column(Integer, ForeignKey("fests.id"), nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    event_date = Column(DateTime, nullable=False)
    location = Column(String, nullable=True)
    max_participants = Column(Integer, nullable=True)
    entry_fee = Column(Integer, default=0)  # in rupees — x100 for paise when calling Razorpay
    media = Column(JSON, nullable=True, default=list)  # [{"url": ..., "type": "image"|"video"}, ...]
    created_at = Column(DateTime, default=datetime.utcnow)

    fest = relationship("Fest", back_populates="events")
    registrations = relationship("Registration", back_populates="event", cascade="all, delete-orphan")


class Interest(Base):
    """Tracks the 'I'm Interested' toggle on a fest (not payment, just intent)."""
    __tablename__ = "interests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    fest_id = Column(Integer, ForeignKey("fests.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="interests")
    fest = relationship("Fest", back_populates="interests")


class Registration(Base):
    """An actual sign-up for a specific event. Payment gets wired in week 2."""
    __tablename__ = "registrations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    status = Column(Enum(RegistrationStatus), default=RegistrationStatus.pending)
    razorpay_order_id = Column(String, nullable=True)
    payment_id = Column(String, nullable=True)  # razorpay_payment_id once verified
    registered_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="registrations")
    event = relationship("Event", back_populates="registrations")
