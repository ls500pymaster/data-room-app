"""increase_avatar_url_length

Revision ID: 32194587e9bd
Revises: 9c7dc1e8dabe
Create Date: 2025-11-13 12:22:51.932913
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '32194587e9bd'
down_revision = '9c7dc1e8dabe'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Increase avatar_url field size from 512 to 2048 characters
    op.alter_column('users', 'avatar_url',
                    existing_type=sa.String(length=512),
                    type_=sa.String(length=2048),
                    existing_nullable=True)


def downgrade() -> None:
    # Revert back to 512 characters
    op.alter_column('users', 'avatar_url',
                    existing_type=sa.String(length=2048),
                    type_=sa.String(length=512),
                    existing_nullable=True)


