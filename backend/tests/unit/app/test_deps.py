from __future__ import annotations

import uuid
import pytest
from fastapi import HTTPException, status

from backend.app.deps import get_current_user
from backend.app.models.user import User
from backend.app.security import create_session_token


@pytest.mark.asyncio
async def test_get_current_user_valid_token(test_db_session, test_user):
    """Test getting current user with valid token."""
    session_token = create_session_token(str(test_user.id))
    
    user = await get_current_user(
        session=test_db_session,
        session_token=session_token,
    )
    
    assert user is not None
    assert user.id == test_user.id
    assert user.email == test_user.email


@pytest.mark.asyncio
async def test_get_current_user_no_token():
    """Test getting current user without token."""
    from sqlalchemy.ext.asyncio import AsyncSession
    
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            session=None,  # type: ignore
            session_token=None,
        )
    
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Not authenticated" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_user_invalid_token(test_db_session):
    """Test getting current user with invalid token."""
    invalid_token = "invalid.token.here"
    
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            session=test_db_session,
            session_token=invalid_token,
        )
    
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid session" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_user_nonexistent_user(test_db_session):
    """Test getting current user that doesn't exist."""
    nonexistent_user_id = str(uuid.uuid4())
    session_token = create_session_token(nonexistent_user_id)
    
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            session=test_db_session,
            session_token=session_token,
        )
    
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "User not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_user_deleted_user(test_db_session, test_user):
    """Test getting current user that is soft-deleted."""
    from datetime import datetime, timezone
    
    # Soft delete the user
    test_user.deleted_at = datetime.now(timezone.utc)
    await test_db_session.commit()
    
    session_token = create_session_token(str(test_user.id))
    
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            session=test_db_session,
            session_token=session_token,
        )
    
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "User not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_user_invalid_uuid_format(test_db_session):
    """Test getting current user with invalid UUID format in token."""
    # Create token with invalid UUID format
    invalid_user_id = "not-a-valid-uuid"
    session_token = create_session_token(invalid_user_id)
    
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            session=test_db_session,
            session_token=session_token,
        )
    
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid user ID format" in exc_info.value.detail

