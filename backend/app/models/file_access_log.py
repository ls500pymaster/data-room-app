from __future__ import annotations

import datetime as dt

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, ENUM, INET
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime, func

from .base import Base


AccessEventEnum = ENUM(
    "view",
    "download",
    "share",
    name="access_event",
    create_type=False,
)


class FileAccessLog(Base):
    __tablename__ = "file_access_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    file_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    event: Mapped[str] = mapped_column(AccessEventEnum, nullable=False)
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


