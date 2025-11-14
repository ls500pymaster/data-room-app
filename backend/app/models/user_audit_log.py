from __future__ import annotations

import datetime as dt

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ENUM, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime, func

from .base import Base


AuditEventEnum = ENUM(
    "login",
    "logout",
    "token_refresh",
    "role_change",
    name="audit_event",
    create_type=False,
)


class UserAuditLog(Base):
    __tablename__ = "user_audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event: Mapped[str] = mapped_column(AuditEventEnum, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


