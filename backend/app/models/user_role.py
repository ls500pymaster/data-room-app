from __future__ import annotations

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, SoftDeleteMixin


UserRoleEnum = ENUM(
    "owner",
    "manager",
    "viewer",
    "guest",
    name="user_role",
    create_type=False,
)


class UserRole(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "user_roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(UserRoleEnum, nullable=False)


