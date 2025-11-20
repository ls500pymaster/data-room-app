from __future__ import annotations

import time
import pytest

from backend.app.security import (
    create_session_token,
    verify_session_token,
    hash_password,
    verify_password,
)
from backend.core.config import settings


class TestSessionTokens:
    def test_create_session_token(self):
        """Test creating a session token."""
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        token = create_session_token(user_id)
        
        assert token is not None
        assert isinstance(token, str)
        assert "." in token  # Should have payload.signature format
    
    def test_verify_valid_token(self):
        """Test verifying a valid token."""
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        token = create_session_token(user_id)
        
        payload = verify_session_token(token)
        assert payload is not None
        assert payload["sub"] == user_id
        assert "exp" in payload
    
    def test_verify_invalid_token_format(self):
        """Test verifying an invalid token format."""
        invalid_token = "not.a.valid.token.format"
        payload = verify_session_token(invalid_token)
        assert payload is None
    
    def test_verify_expired_token(self):
        """Test verifying an expired token."""
        from unittest.mock import patch
        
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        # Create token with 0 TTL (expires immediately)
        token = create_session_token(user_id, ttl_minutes=0)
        
        # Mock time.time() to return a time after expiration
        with patch("backend.app.security.time.time", return_value=int(time.time()) + 100):
            payload = verify_session_token(token)
            assert payload is None
    
    def test_verify_tampered_token(self):
        """Test verifying a tampered token."""
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        token = create_session_token(user_id)
        # Tamper with the signature
        tampered_token = token[:-5] + "xxxxx"
        
        payload = verify_session_token(tampered_token)
        assert payload is None
    
    def test_token_with_custom_ttl(self):
        """Test creating token with custom TTL."""
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        token = create_session_token(user_id, ttl_minutes=120)
        
        payload = verify_session_token(token)
        assert payload is not None
        exp = payload["exp"]
        # Should expire in approximately 120 minutes
        expected_exp = int(time.time()) + 120 * 60
        assert abs(exp - expected_exp) < 5  # Allow 5 second tolerance


class TestPasswordHashing:
    def test_hash_password(self):
        """Test password hashing."""
        password = "testpassword123"
        hashed = hash_password(password)
        
        assert hashed is not None
        assert isinstance(hashed, str)
        assert hashed != password
        assert len(hashed) > 0
    
    def test_verify_correct_password(self):
        """Test verifying correct password."""
        password = "testpassword123"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True
    
    def test_verify_incorrect_password(self):
        """Test verifying incorrect password."""
        password = "testpassword123"
        wrong_password = "wrongpassword"
        hashed = hash_password(password)
        
        assert verify_password(wrong_password, hashed) is False
    
    def test_hash_different_passwords_different_hashes(self):
        """Test that different passwords produce different hashes."""
        password1 = "password1"
        password2 = "password2"
        
        hashed1 = hash_password(password1)
        hashed2 = hash_password(password2)
        
        assert hashed1 != hashed2
    
    def test_hash_same_password_different_hashes(self):
        """Test that same password produces different hashes (due to salt)."""
        password = "testpassword123"
        
        hashed1 = hash_password(password)
        hashed2 = hash_password(password)
        
        # Hashes should be different due to random salt
        assert hashed1 != hashed2
        # But both should verify correctly
        assert verify_password(password, hashed1) is True
        assert verify_password(password, hashed2) is True
    
    def test_password_72_byte_limit(self):
        """Test that passwords longer than 72 bytes are truncated."""
        # Create a password longer than 72 bytes
        long_password = "a" * 100
        hashed = hash_password(long_password)
        
        # Should still hash successfully
        assert hashed is not None
        # Should verify correctly (truncated version)
        assert verify_password(long_password, hashed) is True
    
    def test_verify_password_with_invalid_hash(self):
        """Test verifying password with invalid hash."""
        password = "testpassword123"
        invalid_hash = "not_a_valid_bcrypt_hash"
        
        # Should return False, not raise exception
        assert verify_password(password, invalid_hash) is False
    
    def test_empty_password(self):
        """Test hashing and verifying empty password."""
        password = ""
        hashed = hash_password(password)
        
        assert hashed is not None
        assert verify_password(password, hashed) is True

