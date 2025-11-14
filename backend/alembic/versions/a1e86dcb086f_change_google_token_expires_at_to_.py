"""change_google_token_expires_at_to_timestamptz

Revision ID: a1e86dcb086f
Revises: 32194587e9bd
Create Date: 2025-11-13 12:52:48.297850
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'a1e86dcb086f'
down_revision = '32194587e9bd'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Change google_token_expires_at column type to TIMESTAMPTZ
    # If database already has data, convert from naive to UTC
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN google_token_expires_at
        TYPE TIMESTAMPTZ
        USING CASE 
            WHEN google_token_expires_at IS NULL THEN NULL
            ELSE google_token_expires_at AT TIME ZONE 'UTC'
        END
    """)


def downgrade() -> None:
    # Revert back to TIMESTAMP WITHOUT TIME ZONE
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN google_token_expires_at
        TYPE TIMESTAMP WITHOUT TIME ZONE
        USING google_token_expires_at AT TIME ZONE 'UTC'
    """)


