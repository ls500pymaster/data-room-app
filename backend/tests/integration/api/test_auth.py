from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, Mock
import pytest

from backend.app.models.user import User


@pytest.mark.asyncio
class TestAuthIntegration:
    async def test_register_flow(self, test_client, test_db_session):
        """Test complete registration flow."""
        response = await test_client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "password123",
                "full_name": "New User",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["full_name"] == "New User"
        assert data["status"] == "active"
        
        # Check that session cookie was set
        assert "session" in response.cookies
    
    async def test_login_flow(self, test_client, test_db_session, test_user):
        """Test complete login flow."""
        response = await test_client.post(
            "/api/auth/login",
            json={
                "email": test_user.email,
                "password": "testpassword123",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        
        # Check that session cookie was set
        assert "session" in response.cookies
    
    async def test_login_wrong_password(self, test_client, test_db_session, test_user):
        """Test login with wrong password."""
        response = await test_client.post(
            "/api/auth/login",
            json={
                "email": test_user.email,
                "password": "wrongpassword",
            },
        )
        
        assert response.status_code == 401
    
    async def test_get_user_authenticated(self, test_client, test_db_session, test_user, auth_cookies):
        """Test getting current user when authenticated."""
        test_client.cookies.update(auth_cookies)
        response = await test_client.get(
            "/api/auth/user",
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["id"] == str(test_user.id)
    
    async def test_get_user_unauthenticated(self, test_client):
        """Test getting current user when not authenticated."""
        response = await test_client.get("/api/auth/user")
        
        assert response.status_code == 401
    
    async def test_refresh_flow(self, test_client, test_db_session, test_user, auth_cookies):
        """Test refreshing session token."""
        test_client.cookies.update(auth_cookies)
        response = await test_client.post(
            "/api/auth/refresh",
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        
        # Check that new session cookie was set
        assert "session" in response.cookies
    
    async def test_logout_flow(self, test_client, auth_cookies):
        """Test logout flow."""
        test_client.cookies.update(auth_cookies)
        response = await test_client.post(
            "/api/auth/logout",
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    async def test_google_oauth_login_new_user(self, test_client, test_db_session):
        """Test Google OAuth login for new user."""
        response = await test_client.post(
            "/api/auth/login",
            json={
                "email": "google@example.com",
                "google_access_token": "test_token",
                "google_refresh_token": "test_refresh",
                "expires_in": 3600,
                "full_name": "Google User",
                "avatar_url": "https://example.com/avatar.jpg",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "google@example.com"
        assert data["full_name"] == "Google User"
        assert "session" in response.cookies
    
    async def test_register_duplicate_email(self, test_client, test_db_session, test_user):
        """Test registering with duplicate email."""
        response = await test_client.post(
            "/api/auth/register",
            json={
                "email": test_user.email,
                "password": "password123",
            },
        )
        
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()
    
    async def test_register_short_password(self, test_client, test_db_session):
        """Test registering with short password."""
        response = await test_client.post(
            "/api/auth/register",
            json={
                "email": "user@example.com",
                "password": "short",
            },
        )
        
        assert response.status_code == 400
        assert "8 characters" in response.json()["detail"].lower()
    
    async def test_login_suspended_user(self, test_client, test_db_session):
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
        
        response = await test_client.post(
            "/api/auth/login",
            json={
                "email": suspended_user.email,
                "password": "password123",
            },
        )
        
        assert response.status_code == 403
        assert "suspended" in response.json()["detail"].lower()
    
    async def test_get_avatar(self, test_client, test_db_session, test_user_with_google, auth_cookies):
        """Test getting user avatar."""
        test_user_with_google.avatar_url = "https://example.com/avatar.jpg"
        await test_db_session.commit()
        
        # Update auth cookies for the correct user
        from backend.app.security import create_session_token
        auth_cookies = {"session": create_session_token(str(test_user_with_google.id))}
        
        with patch("backend.api.auth.requests.get") as mock_get:
            mock_response = Mock()
            mock_response.headers = {"Content-Type": "image/jpeg"}
            mock_response.iter_content.return_value = [b"image_data"]
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            test_client.cookies.update(auth_cookies)
            response = await test_client.get(
                "/api/auth/avatar",
            )
            
            assert response.status_code == 200
            mock_get.assert_called_once()
    
    async def test_get_avatar_not_found(self, test_client, test_db_session, test_user, auth_cookies):
        """Test getting avatar when user has no avatar."""
        test_client.cookies.update(auth_cookies)
        response = await test_client.get(
            "/api/auth/avatar",
        )
        
        assert response.status_code == 404
    
    async def test_oauth_initiate_flow(self, test_client):
        """Test initiating OAuth flow."""
        with patch("backend.api.auth.settings") as mock_settings, \
             patch("backend.api.auth.get_authorization_url") as mock_auth_url:
            
            mock_settings.GOOGLE_CLIENT_ID = "test_client_id"
            mock_auth_url.return_value = "https://accounts.google.com/o/oauth2/auth"
            
            response = await test_client.get("/api/auth/login")
            
            # Should redirect
            assert response.status_code in [302, 307]
    
    async def test_oauth_callback_success(self, test_client, test_db_session):
        """Test OAuth callback success."""
        with patch("backend.api.auth.exchange_code_for_tokens") as mock_exchange, \
             patch("backend.api.auth.requests.get") as mock_get, \
             patch("backend.api.auth.settings") as mock_settings:
            
            mock_settings.CORS_ORIGINS = ["http://localhost:3000"]
            mock_settings.IS_PRODUCTION = False
            
            # Mock token exchange
            from google.oauth2.credentials import Credentials
            
            mock_tokens = {
                "access_token": "test_token",
                "refresh_token": "test_refresh",
                "expires_in": 3600,
            }
            mock_creds = Mock(spec=Credentials)
            mock_creds.token = "test_token"
            mock_creds.refresh_token = "test_refresh"
            mock_exchange.return_value = (mock_tokens, mock_creds)
            
            # Mock userinfo API call
            mock_userinfo_response = Mock()
            mock_userinfo_response.json.return_value = {
                "email": "oauth@example.com",
                "id": "google123",
                "name": "OAuth User",
                "picture": "https://example.com/pic.jpg",
            }
            mock_userinfo_response.raise_for_status = Mock()
            mock_get.return_value = mock_userinfo_response
            
            response = await test_client.get(
                "/api/auth/callback",
                params={"code": "test_code"},
            )
            
            # Should redirect
            assert response.status_code in [302, 307]

