from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime
from sqlalchemy.dialects.postgresql import UUID, CITEXT, ENUM
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, SoftDeleteMixin


UserStatusEnum = ENUM(
    "pending",
    "active",
    "suspended",
    name="user_status",
    create_type=False,  # created by migrations
)


class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )
    email: Mapped[str] = mapped_column(CITEXT(), unique=True, nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(UserStatusEnum, nullable=False, default="pending")
    full_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    
    # Google OAuth fields
    google_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, unique=True)
    google_access_token: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    google_refresh_token: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    google_token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


