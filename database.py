from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from datetime import datetime
from enum import Enum
from config import settings

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()


class ReminderStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ReminderRecurrence(str, Enum):
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class FocusStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class FocusWarningStyle(str, Enum):
    GENTLE = "gentle"
    STRICT = "strict"
    BRUTAL = "brutal"


class FocusVisibility(str, Enum):
    GROUP = "group"
    PRIVATE = "private"
    SILENT = "silent"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False)
    username = Column(String, nullable=True)
    timezone = Column(String, default=settings.default_timezone)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    reminders = relationship("Reminder", back_populates="user")
    focus_sessions = relationship("FocusSession", back_populates="user")
    afk_status = relationship("AFK", back_populates="user", uselist=False)
    focus_statistics = relationship("FocusStatistics", back_populates="user", uselist=False)


class AFK(Base):
    __tablename__ = "afk"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), unique=True, nullable=False)
    reason = Column(String, nullable=True)
    set_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="afk_status")


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    group_id = Column(Integer, nullable=True)
    text = Column(String, nullable=False)
    scheduled_at = Column(DateTime, nullable=False)
    recurrence = Column(SQLEnum(ReminderRecurrence), default=ReminderRecurrence.ONCE)
    status = Column(SQLEnum(ReminderStatus), default=ReminderStatus.ACTIVE)
    personality = Column(String, default="normal")
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="reminders")


class FocusSession(Base):
    __tablename__ = "focus_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    group_id = Column(Integer, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    ends_at = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    mode = Column(String, nullable=False)
    status = Column(SQLEnum(FocusStatus), default=FocusStatus.ACTIVE)
    warning_style = Column(SQLEnum(FocusWarningStyle), default=FocusWarningStyle.GENTLE)
    visibility = Column(SQLEnum(FocusVisibility), default=FocusVisibility.PRIVATE)
    warning_cooldown_minutes = Column(Integer, default=10)
    max_warnings = Column(Integer, default=3)
    warnings_sent = Column(Integer, default=0)
    last_warning_at = Column(DateTime, nullable=True)
    paused_at = Column(DateTime, nullable=True)
    pause_duration_minutes = Column(Integer, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="focus_sessions")


class FocusStatistics(Base):
    __tablename__ = "focus_statistics"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), unique=True, nullable=False)
    total_sessions = Column(Integer, default=0)
    completed_sessions = Column(Integer, default=0)
    cancelled_sessions = Column(Integer, default=0)
    total_focus_minutes = Column(Integer, default=0)
    longest_session_minutes = Column(Integer, default=0)
    current_streak = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="focus_statistics")


def init_db():
    Base.metadata.create_all(bind=engine)


def get_session():
    return SessionLocal()
