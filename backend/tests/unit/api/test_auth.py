from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, AsyncMock
import pytest
from fastapi import HTTPException, status

from backend.api.auth import (
    register,
    login,
    logout,
    refresh,
    get_user,
    get_avatar,
    RegisterRequest,
    LoginRequest,
)
from backend.app.models.user import User


@pytest.mark.asyncio
class TestRegister:
    async def test_register_success(self, test_db_session):
        """Test successful user registration."""
        payload = RegisterRequest(
            email="newuser@example.com",
            password="password123",
            full_name="New User",
        )
        
        from fastapi import Response
        response = Response()
        
        result = await register(
            payload=payload,
            response=response,
            session=test_db_session,
        )
        
        assert result.email == payload.email
        assert result.full_name == payload.full_name
        assert result.status == "active"
        
        # Check that session cookie was set
        set_cookie_headers = [header[1].decode() for header in response.raw_headers if b"set-cookie" in header[0].lower()]
        assert any("session=" in cookie for cookie in set_cookie_headers)
    
    async def test_register_duplicate_email(self, test_db_session, test_user):
        """Test registration with duplicate email."""
        payload = RegisterRequest(
            email=test_user.email,
            password="password123",
        )
        
        from fastapi import Response
        response = Response()
        
        with pytest.raises(HTTPException) as exc_info:
            await register(
                payload=payload,
                response=response,
                session=test_db_session,
            )
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "already exists" in exc_info.value.detail.lower()
    
    async def test_register_short_password(self, test_db_session):
        """Test registration with short password."""
        payload = RegisterRequest(
            email="user@example.com",
            password="short",  # Less than 8 characters
        )
        
        from fastapi import Response
        response = Response()
        
        with pytest.raises(HTTPException) as exc_info:
            await register(
                payload=payload,
                response=response,
                session=test_db_session,
            )
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "8 characters" in exc_info.value.detail.lower()
    
    async def test_register_long_password(self, test_db_session):
        """Test registration with password longer than 72 bytes."""
        payload = RegisterRequest(
            email="user@example.com",
            password="a" * 100,  # More than 72 bytes
        )
        
        from fastapi import Response
        response = Response()
        
        with pytest.raises(HTTPException) as exc_info:
            await register(
                payload=payload,
                response=response,
                session=test_db_session,
            )
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "72 bytes" in exc_info.value.detail.lower()


@pytest.mark.asyncio
class TestLogin:
    async def test_login_with_password_success(self, test_db_session, test_user):
        """Test successful login with password."""
        payload = LoginRequest(
            email=test_user.email,
            password="testpassword123",
        )
        
        from fastapi import Response
        response = Response()
        
        result = await login(
            payload=payload,
            response=response,
            session=test_db_session,
        )
        
        assert result.email == test_user.email
        set_cookie_headers = [header[1].decode() for header in response.raw_headers if b"set-cookie" in header[0].lower()]
        assert any("session=" in cookie for cookie in set_cookie_headers)
    
    async def test_login_wrong_password(self, test_db_session, test_user):
        """Test login with wrong password."""
        payload = LoginRequest(
            email=test_user.email,
            password="wrongpassword",
        )
        
        from fastapi import Response
        response = Response()
        
        with pytest.raises(HTTPException) as exc_info:
            await login(
                payload=payload,
                response=response,
                session=test_db_session,
            )
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid email or password" in exc_info.value.detail
    
    async def test_login_nonexistent_user(self, test_db_session):
        """Test login with nonexistent user."""
        payload = LoginRequest(
            email="nonexistent@example.com",
            password="password123",
        )
        
        from fastapi import Response
        response = Response()
        
        with pytest.raises(HTTPException) as exc_info:
            await login(
                payload=payload,
                response=response,
                session=test_db_session,
            )
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_login_suspended_user(self, test_db_session):
        """Test login with suspended user."""
        from backend.app.security import hash_password
        
        suspended_user = User(
            id=uuid.uuid4(),
            email="suspended@example.com",
            password_hash=hash_password("password123"),
            status="suspended",
        )
        test_db_session.add(suspended_user)
        await test_db_session.commit()
        
        payload = LoginRequest(
            email=suspended_user.email,
            password="password123",
        )
        
        from fastapi import Response
        response = Response()
        
        with pytest.raises(HTTPException) as exc_info:
            await login(
                payload=payload,
                response=response,
                session=test_db_session,
            )
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "suspended" in exc_info.value.detail.lower()
    
    async def test_login_google_oauth_new_user(self, test_db_session):
        """Test login with Google OAuth for new user."""
        payload = LoginRequest(
            email="google@example.com",
            google_access_token="test_token",
            google_refresh_token="test_refresh",
            expires_in=3600,
            full_name="Google User",
            avatar_url="https://example.com/avatar.jpg",
        )
        
        from fastapi import Response
        response = Response()
        
        result = await login(
            payload=payload,
            response=response,
            session=test_db_session,
        )
        
        assert result.email == payload.email
        assert result.full_name == payload.full_name
    
    async def test_login_google_oauth_existing_user(self, test_db_session, test_user_with_google):
        """Test login with Google OAuth for existing user."""
        payload = LoginRequest(
            email=test_user_with_google.email,
            google_access_token="new_token",
            google_refresh_token="new_refresh",
            expires_in=3600,
        )
        
        from fastapi import Response
        response = Response()
        
        result = await login(
            payload=payload,
            response=response,
            session=test_db_session,
        )
        
        assert result.email == test_user_with_google.email
        # Verify tokens were updated
        await test_db_session.refresh(test_user_with_google)
        assert test_user_with_google.google_access_token == "new_token"


@pytest.mark.asyncio
class TestLogout:
    async def test_logout(self):
        """Test logout."""
        from fastapi import Response
        response = Response()
        
        result = await logout(response=response)
        
        assert result["status"] == "ok"
        # Check that session cookie was deleted
        cookies = [cookie for cookie in response.raw_headers if b"set-cookie" in cookie[0].lower()]
        # Logout should delete the session cookie
        assert any(b"session=" in cookie[1] or b"Max-Age=0" in cookie[1] for cookie in cookies)


@pytest.mark.asyncio
class TestRefresh:
    async def test_refresh_success(self, test_user):
        """Test refreshing session token."""
        from fastapi import Response
        response = Response()
        
        result = await refresh(
            response=response,
            current_user=test_user,
        )
        
        assert result.email == test_user.email
        set_cookie_headers = [header[1].decode() for header in response.raw_headers if b"set-cookie" in header[0].lower()]
        assert any("session=" in cookie for cookie in set_cookie_headers)


@pytest.mark.asyncio
class TestGetUser:
    async def test_get_user(self, test_user):
        """Test getting current user."""
        result = await get_user(current_user=test_user)
        
        assert result.email == test_user.email
        assert result.id == str(test_user.id)


@pytest.mark.asyncio
class TestGetAvatar:
    async def test_get_avatar_success(self, test_user_with_google):
        """Test getting user avatar."""
        test_user_with_google.avatar_url = "https://example.com/avatar.jpg"
        
        with patch("backend.api.auth.requests.get") as mock_get:
            mock_response = Mock()
            mock_response.headers = {"Content-Type": "image/jpeg"}
            mock_response.iter_content.return_value = [b"image_data"]
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            result = await get_avatar(current_user=test_user_with_google)
            
            assert result is not None
            mock_get.assert_called_once_with(
                test_user_with_google.avatar_url,
                stream=True,
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0 (compatible; DataRoom/1.0)"},
            )
    
    async def test_get_avatar_not_found(self, test_user):
        """Test getting avatar when user has no avatar."""
        test_user.avatar_url = None
        
        with pytest.raises(HTTPException) as exc_info:
            await get_avatar(current_user=test_user)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "Avatar not found" in exc_info.value.detail

