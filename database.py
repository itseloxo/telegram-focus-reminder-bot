from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum, Text, Boolean, Float
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from datetime import datetime
from enum import Enum
from config import settings

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()


# ============ ENUMS FOR REMINDER & FOCUS ============
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


# ============ ENUMS FOR FAMIGO SOCIAL ============
class RelationshipType(str, Enum):
    FRIEND = "friend"
    BEST_FRIEND = "best_friend"
    CLOSE_FRIEND = "close_friend"
    PARTNER = "partner"
    SIBLING = "sibling"
    COUSIN = "cousin"
    PARENT = "parent"
    CHILD = "child"
    RELATIVE = "relative"
    MENTOR = "mentor"
    COLLEAGUE = "colleague"
    STUDY_BUDDY = "study_buddy"
    GAMING_BUDDY = "gaming_buddy"
    CUSTOM = "custom"


class RelationshipVisibility(str, Enum):
    PUBLIC = "public"
    FRIENDS_ONLY = "friends_only"
    PRIVATE = "private"


class ProfileVisibility(str, Enum):
    PUBLIC = "public"
    GROUP_ONLY = "group_only"
    HIDDEN = "hidden"


class MoodType(str, Enum):
    HAPPY = "happy"
    CHILL = "chill"
    ENERGETIC = "energetic"
    TIRED = "tired"
    SAD = "sad"
    THINKING = "thinking"
    VIBING = "vibing"
    ROMANTIC = "romantic"
    OVERWHELMED = "overwhelmed"
    FOCUSED = "focused"
    EXCITED = "excited"


class BirthdayVisibility(str, Enum):
    HIDDEN = "hidden"
    BIRTHDAY_ONLY = "birthday_only"
    VISIBLE = "visible"


# ============ CORE MODELS ============
class User(Base):
    """Core user model."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False)
    username = Column(String, nullable=True)
    timezone = Column(String, default=settings.default_timezone)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    reminders = relationship("Reminder", back_populates="user")
    focus_sessions = relationship("FocusSession", back_populates="user")
    afk_status = relationship("AFK", back_populates="user", uselist=False)
    focus_statistics = relationship("FocusStatistics", back_populates="user", uselist=False)
    
    # Famigo social relationships
    profiles = relationship("FamigoProfile", back_populates="user")
    interests = relationship("UserInterest", back_populates="user")
    connections = relationship("Connection", foreign_keys="Connection.user_id", back_populates="user")
    received_connections = relationship("Connection", foreign_keys="Connection.connected_user_id", back_populates="connected_user")
    favorites = relationship("Favorite", back_populates="user")
    confessions = relationship("Confession", back_populates="user")
    mood_history = relationship("MoodStatus", back_populates="user")


class AFK(Base):
    """AFK status model - independent system."""
    __tablename__ = "afk"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), unique=True, nullable=False)
    reason = Column(String, nullable=True)
    set_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="afk_status")


class Reminder(Base):
    """Reminder model - independent system."""
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
    """Focus session model - independent system."""
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
    """Focus statistics model - independent system."""
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


# ============ FAMIGO SOCIAL MODELS ============
class FamigoProfile(Base):
    """User's Famigo social profile - GROUP SCOPED."""
    __tablename__ = "famigo_profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    group_id = Column(Integer, nullable=False)
    
    # Identity
    display_name = Column(String, nullable=True)
    profile_photo_url = Column(String, nullable=True)
    city = Column(String, nullable=True)
    country = Column(String, nullable=True)
    pronouns = Column(String, nullable=True)
    age_range = Column(String, nullable=True)
    
    # About
    bio = Column(Text, nullable=True)
    introduction = Column(Text, nullable=True)
    fun_fact = Column(String, nullable=True)
    profession = Column(String, nullable=True)
    education = Column(String, nullable=True)
    languages = Column(String, nullable=True)
    favorite_quote = Column(String, nullable=True)
    favorite_emoji = Column(String, nullable=True)
    personal_tags = Column(String, nullable=True)
    
    # Settings
    visibility = Column(SQLEnum(ProfileVisibility), default=ProfileVisibility.PUBLIC)
    birth_month = Column(Integer, nullable=True)
    birth_day = Column(Integer, nullable=True)
    birth_year = Column(Integer, nullable=True)
    birthday_visibility = Column(SQLEnum(BirthdayVisibility), default=BirthdayVisibility.HIDDEN)
    
    # Stats (group-scoped)
    reputation = Column(Integer, default=0)
    level = Column(Integer, default=1)
    reputation_last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Timestamps
    joined_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="profiles")


class UserInterest(Base):
    """User interests - GROUP SCOPED."""
    __tablename__ = "user_interests"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    group_id = Column(Integer, nullable=False)
    interest = Column(String, nullable=False)
    interest_emoji = Column(String, nullable=True)
    is_custom = Column(Boolean, default=False)
    added_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="interests")


class Connection(Base):
    """Social connection between users - GROUP SCOPED."""
    __tablename__ = "connections"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    connected_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    group_id = Column(Integer, nullable=False)
    relationship_type = Column(SQLEnum(RelationshipType), default=RelationshipType.FRIEND)
    custom_relationship = Column(String, nullable=True)
    visibility = Column(SQLEnum(RelationshipVisibility), default=RelationshipVisibility.PUBLIC)
    status = Column(String, default="pending")  # pending, accepted, declined
    initiated_at = Column(DateTime, default=datetime.utcnow)
    accepted_at = Column(DateTime, nullable=True)
    
    user = relationship("User", foreign_keys=[user_id], back_populates="connections")
    connected_user = relationship("User", foreign_keys=[connected_user_id], back_populates="received_connections")


class Favorite(Base):
    """User's favorite items - GROUP SCOPED."""
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    group_id = Column(Integer, nullable=False)
    category = Column(String, nullable=False)  # Movie, Song, Artist, etc.
    value = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="favorites")


class CurrentlyInto(Base):
    """What user is currently doing - GROUP SCOPED."""
    __tablename__ = "currently_into"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    group_id = Column(Integer, nullable=False)
    category = Column(String, nullable=False)  # Watching, Listening, Reading, Playing, etc.
    value = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    set_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)


class MoodStatus(Base):
    """Current mood - GROUP SCOPED."""
    __tablename__ = "mood_statuses"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    group_id = Column(Integer, nullable=False)
    mood = Column(SQLEnum(MoodType), nullable=False)
    custom_mood = Column(String, nullable=True)
    set_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="mood_history")


class SocialLink(Base):
    """External social profile links - USER LEVEL."""
    __tablename__ = "social_links"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    platform = Column(String, nullable=False)  # Instagram, GitHub, Twitter, etc.
    username_or_url = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Confession(Base):
    """Anonymous confessions - GROUP SCOPED."""
    __tablename__ = "confessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    group_id = Column(Integer, nullable=False)
    confession_text = Column(Text, nullable=False)
    is_anonymous = Column(Boolean, default=True)
    message_id = Column(Integer, nullable=True)  # Telegram message ID
    status = Column(String, default="active")  # active, deleted, flagged
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="confessions")


class ConfessionReaction(Base):
    """Reactions to confessions - GROUP SCOPED."""
    __tablename__ = "confession_reactions"

    id = Column(Integer, primary_key=True)
    confession_id = Column(Integer, ForeignKey("confessions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    reaction_emoji = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Achievement(Base):
    """User achievements - GROUP SCOPED."""
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    group_id = Column(Integer, nullable=False)
    achievement_key = Column(String, nullable=False)
    achievement_name = Column(String, nullable=False)
    achievement_emoji = Column(String, nullable=True)
    description = Column(String, nullable=True)
    unlocked_at = Column(DateTime, default=datetime.utcnow)


class CommunityEvent(Base):
    """Timeline events - GROUP SCOPED."""
    __tablename__ = "community_events"

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, nullable=False)
    event_type = Column(String, nullable=False)  # introduction, connection, achievement, birthday, etc.
    user_id = Column(Integer, nullable=True)
    related_user_id = Column(Integer, nullable=True)
    event_data = Column(Text, nullable=True)
    visibility = Column(String, default="public")
    created_at = Column(DateTime, default=datetime.utcnow)


class GroupJoinHistory(Base):
    """Track member join/leave history - GROUP SCOPED."""
    __tablename__ = "group_join_history"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    group_id = Column(Integer, nullable=False)
    first_joined = Column(DateTime, nullable=False)
    last_joined = Column(DateTime, nullable=False)
    left_count = Column(Integer, default=0)
    total_membership_days = Column(Integer, default=0)
    is_current_member = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserSettings(Base):
    """User privacy and notification settings - USER LEVEL."""
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), unique=True, nullable=False)
    
    # Privacy
    profile_privacy_default = Column(SQLEnum(ProfileVisibility), default=ProfileVisibility.PUBLIC)
    allow_confessions = Column(Boolean, default=True)
    allow_say_hi = Column(Boolean, default=True)
    allow_connections = Column(Boolean, default=True)
    allow_discoveries = Column(Boolean, default=True)
    
    # Notifications
    notify_connections = Column(Boolean, default=True)
    notify_say_hi = Column(Boolean, default=True)
    notify_confessions = Column(Boolean, default=True)
    
    # Preferences
    language = Column(String, default="en")
    show_achievements = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def get_session():
    """Get database session."""
    return SessionLocal()
