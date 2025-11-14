from __future__ import annotations

import base64
import hmac
import json
import time
from hashlib import sha256
from typing import Any, Dict, Optional

import bcrypt

from backend.core.config import settings


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(payload_b64: str) -> str:
    mac = hmac.new(settings.SECRET_KEY.encode("utf-8"), payload_b64.encode("utf-8"), sha256).digest()
    return _b64encode(mac)


def create_session_token(user_id: str, ttl_minutes: int | None = None) -> str:
    ttl = ttl_minutes if ttl_minutes is not None else settings.SESSION_TTL_MINUTES
    exp = int(time.time()) + ttl * 60
    payload: Dict[str, Any] = {"sub": user_id, "exp": exp}
    payload_b64 = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = _sign(payload_b64)
    return f"{payload_b64}.{sig}"


def verify_session_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload_b64, sig = token.split(".", 1)
    except ValueError:
        return None
    expected_sig = _sign(payload_b64)
    if not hmac.compare_digest(sig, expected_sig):
        return None
    try:
        payload = json.loads(_b64decode(payload_b64))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        return None
    return payload


def hash_password(password: str) -> str:
    """
    Hashes password using bcrypt.
    
    Args:
        password: Plain text password (maximum 72 bytes)
        
    Returns:
        Hashed password (string)
    """
    # Bcrypt has a 72-byte limit for passwords
    # Convert to bytes and truncate if needed
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    
    # Generate salt and hash password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies password against hash.
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password from database
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        # Bcrypt has a 72-byte limit for passwords
        password_bytes = plain_password.encode('utf-8')
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


