"""
SQLAlchemy ORM Models (Database Schema)
This module defines the three core tables for the Multi-Factor Digital
Identification system.  Each model maps directly to a PostgreSQL table.

Tables

1. **users**              – Stores login credentials (username, hashed password).
2. **facial_profiles**    – Stores the 128-dimensional facial embedding vector.
3. **behavioral_profiles** – Stores the reaction-time baseline (mean, std, n).

Relationships

    User  1 ──── 1  FacialProfile
    User  1 ──── 1  BehavioralProfile

"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Text,
)
from sqlalchemy.orm import relationship
from app.database import Base
# 1 USER MODEL
class User(Base):

    __tablename__ = "users"

    #  Primary Key 
    id = Column(Integer, primary_key=True, index=True)

    # Credentials
    username = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique login identifier",
    )
    email = Column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique contact email",
    )
    hashed_password = Column(
        Text,
        nullable=False,
        comment="bcrypt hash — NEVER store plaintext",
    )

    # Profile 
    full_name = Column(
        String(100),
        nullable=True,
        comment="Optional display name",
    )
    interests = Column(
        JSON,
        nullable=True,
        comment="List of chosen emoji IDs/names for visual behavioral test",
    )
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="False = account locked / soft-deleted",
    )

    # Timestamps 
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Row creation time (UTC)",
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Last modification time (UTC)",
    )

    # Relationships 
    # uselist=False enforces 1-to-1 on the ORM side.
    # cascade="all, delete-orphan" ensures child rows are removed when the
    # parent User is deleted.
    facial_profile = relationship(
        "FacialProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    behavioral_profile = relationship(
        "BehavioralProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}')>"



# 2 FACIAL PROFILE MODEL

class FacialProfile(Base):
    __tablename__ = "facial_profiles"

    #  Primary Key 
    id = Column(Integer, primary_key=True, index=True)

    # Foreign Key (one-to-one)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
        comment="FK to users — unique enforces 1-to-1",
    )

    # Embedding Data 
    embedding = Column(
        JSON,
        nullable=False,
    )

    # Timestamps 
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    #  Relationship 
    user = relationship("User", back_populates="facial_profile")

    def __repr__(self) -> str:
        return f"<FacialProfile(id={self.id}, user_id={self.user_id})>"


# 3 BEHAVIORAL PROFILE MODEL
class BehavioralProfile(Base):
    __tablename__ = "behavioral_profiles"

    #  Primary Key 
    id = Column(Integer, primary_key=True, index=True)

    # Foreign Key (one-to-one)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
        comment="FK to users — unique enforces 1-to-1",
    )

    # Behavioral Statistics 
    stats = Column(
        JSON,
        nullable=False,
        default=lambda: {
            "math": {"mean": 0.0, "std": 0.0, "n": 0},
            "visual": {"mean": 0.0, "std": 0.0, "n": 0}
        },
        comment="JSON storing mean, std, n for different challenge types (math, visual)",
    )

    #  Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    #  Relationship 
    user = relationship("User", back_populates="behavioral_profile")

    def __repr__(self) -> str:
        return (
            f"<BehavioralProfile(id={self.id}, user_id={self.user_id}, "
            f"stats={self.stats})>"
        )
