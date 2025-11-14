from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID, ENUM, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, SoftDeleteMixin


FileStatusEnum = ENUM(
    "processing",
    "ready",
    "failed",
    "archived",
    name="file_status",
    create_type=False,
)


class File(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    uploader_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    storage_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    drive_file_id: Mapped[Optional[str]] = mapped_column(String(256), unique=True, nullable=True)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    extension: Mapped[Optional[str]] = mapped_column(String(32))
    mime_type: Mapped[Optional[str]] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[Optional[str]] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(FileStatusEnum, default="processing", nullable=False)
    scan_report: Mapped[Optional[dict]] = mapped_column(JSONB)

    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="ck_files_size_positive"),
        CheckConstraint("version >= 1", name="ck_files_version_positive"),
    )


