from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel, EmailStr
import requests
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db import get_session
from backend.app.models import User
from backend.app.security import create_session_token, hash_password, verify_password
from backend.app.deps import get_current_user
from backend.app.services.google_drive import (
    get_authorization_url,
    exchange_code_for_tokens,
)
from backend.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


def _ensure_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensures that datetime has UTC timezone."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    # Convert to UTC if timezone is different
    if dt.tzinfo != timezone.utc:
        return dt.astimezone(timezone.utc)
    return dt


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    phone: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: Optional[str] = None  # For password authentication
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    google_access_token: Optional[str] = None
    google_refresh_token: Optional[str] = None
    expires_in: Optional[int] = None


class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    status: str

    @staticmethod
    def from_model(u: User) -> "UserOut":
        return UserOut(
            id=str(u.id),
            email=u.email,
            full_name=u.full_name,
            avatar_url=u.avatar_url,
            status=u.status,
        )


@router.get("/login")
async def initiate_oauth_flow(request: Request):
    """Initiates OAuth 2.0 flow - redirects to Google authorization."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth not configured",
        )
    
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    # Save state in cookie (in production better to use Redis/session)
    authorization_url = get_authorization_url(state=state)
    
    response = RedirectResponse(url=authorization_url)
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=settings.IS_PRODUCTION,  # True in production (HTTPS)
        samesite="lax",
        max_age=600,  # 10 minutes
        path="/",
    )
    return response


@router.get("/callback")
async def oauth_callback(
    code: str,
    state: Optional[str] = None,
    error: Optional[str] = None,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """Handles OAuth callback from Google."""
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth error: {error}",
        )
    
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing authorization code",
        )
    
    # In production check state from cookie
    # oauth_state = request.cookies.get("oauth_state")
    # if not oauth_state or oauth_state != state:
    #     raise HTTPException(status_code=403, detail="Invalid state")
    
    try:
        # Exchange code for tokens
        tokens, credentials = await exchange_code_for_tokens(code)
        
        # Get user information from Google via direct API request
        # This bypasses the credentials.expiry timezone issue
        import requests
        userinfo_response = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )
        userinfo_response.raise_for_status()
        user_info = userinfo_response.json()
        
        email = user_info.get("email")
        google_id = user_info.get("id")
        full_name = user_info.get("name")
        avatar_url = user_info.get("picture")
        
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get user email from Google",
            )
        
        # Find or create user
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        expires_at = tokens.get("expires_at")
        if isinstance(expires_at, datetime):
            token_expires_at = _ensure_aware(expires_at)
        elif tokens.get("expires_in"):
            token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])
        else:
            token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        if not user:
            user = User(
                id=uuid.uuid4(),
                email=email,
                full_name=full_name,
                avatar_url=avatar_url,
                status="active",
                google_id=google_id,
                google_access_token=tokens["access_token"],
                google_refresh_token=tokens["refresh_token"],
                google_token_expires_at=token_expires_at,
            )
            session.add(user)
        else:
            # Update user data and tokens
            user.full_name = full_name or user.full_name
            user.avatar_url = avatar_url or user.avatar_url
            user.google_id = google_id or user.google_id
            user.google_access_token = tokens["access_token"]
            user.google_refresh_token = tokens["refresh_token"]
            user.google_token_expires_at = token_expires_at
            if user.status == "pending":
                user.status = "active"
        
        await session.commit()
        await session.refresh(user)
        
        # Create session
        session_token = create_session_token(str(user.id))
        # Use root URL for redirect (frontend handles /auth/callback)
        frontend_url = settings.CORS_ORIGINS[0] if settings.CORS_ORIGINS and settings.CORS_ORIGINS[0] != "*" else "http://localhost:3000"
        # Redirect to root - frontend will handle auth callback
        redirect_url = f"{frontend_url}/?auth=success"
        
        # Log for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"OAuth callback successful for user {email}, redirecting to {redirect_url}")
        
        response = RedirectResponse(url=redirect_url, status_code=302)
        response.set_cookie(
            key="session",
            value=session_token,
            httponly=True,
            secure=settings.IS_PRODUCTION,  # True in production (HTTPS)
            samesite="lax",
            max_age=settings.SESSION_TTL_MINUTES * 60,
            path="/",
        )
        response.delete_cookie("oauth_state", path="/")
        return response
        
    except Exception as e:
        error_msg = str(e)
        # Log error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"OAuth callback error: {error_msg}", exc_info=True)
        
        # If error is related to scope changes, it's normal - Google may add openid
        # or user may not grant permission for some scopes
        frontend_url = settings.CORS_ORIGINS[0] if settings.CORS_ORIGINS and settings.CORS_ORIGINS[0] != "*" else "http://localhost:3000"
        if "Scope has changed" in error_msg:
            # Continue with scopes that Google returned
            # This is normal for development - just redirect to frontend with error
            response = RedirectResponse(url=f"{frontend_url}/?auth=error&reason=scope_changed")
            return response
        else:
            # Redirect to frontend with error
            response = RedirectResponse(url=f"{frontend_url}/?auth=error&reason=oauth_failed")
            return response


@router.post("/register", response_model=UserOut)
async def register(
    payload: RegisterRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    """
    Register new user with email and password.
    """
    # Password validation
    if len(payload.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long",
        )
    
    # Bcrypt has a 72-byte limit for passwords
    password_bytes = payload.password.encode('utf-8')
    if len(password_bytes) > 72:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is too long (maximum 72 bytes)",
        )
    
    # Check if user exists
    result = await session.execute(select(User).where(User.email == payload.email))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )
    
    # Hash password
    password_hash = hash_password(payload.password)
    
    # Create user
    user = User(
        id=uuid.uuid4(),
        email=payload.email,
        password_hash=password_hash,
        full_name=payload.full_name,
        phone=payload.phone,
        status="active",  # Can be changed to "pending" if email verification is needed
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    
    # Create session
    session_token = create_session_token(str(user.id))
    response.set_cookie(
        key="session",
        value=session_token,
        httponly=True,
        secure=settings.IS_PRODUCTION,  # True in production (HTTPS)
        samesite="lax",
        max_age=settings.SESSION_TTL_MINUTES * 60,
        path="/",
    )
    
    return UserOut.from_model(user)


@router.post("/login", response_model=UserOut)
async def login(payload: LoginRequest, response: Response, session: AsyncSession = Depends(get_session)):
    """
    User login. Supports two methods:
    1. Password authentication (email + password)
    2. Google OAuth (accepts tokens from frontend)
    """
    result = await session.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    
    # Password authentication
    if payload.password:
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        
        if not user.password_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Password authentication not available for this user",
            )
        
        if not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        
        # Check user status
        if user.status == "suspended":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is suspended",
            )
        
        # Create session
        session_token = create_session_token(str(user.id))
        response.set_cookie(
            key="session",
            value=session_token,
            httponly=True,
            secure=settings.IS_PRODUCTION,  # True in production (HTTPS)
            samesite="lax",
            max_age=settings.SESSION_TTL_MINUTES * 60,
            path="/",
        )
        
        return UserOut.from_model(user)
    
    # Google OAuth authentication (existing logic)
    if not payload.google_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either password or Google OAuth tokens required",
        )
    
    # Calculate expires_at from expires_in
    expires_at = None
    if payload.expires_in:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=payload.expires_in)
    
    if not user:
        user = User(
            id=uuid.uuid4(),
            email=payload.email,
            full_name=payload.full_name,
            avatar_url=payload.avatar_url,
            status="active",
            google_access_token=payload.google_access_token,
            google_refresh_token=payload.google_refresh_token,
            google_token_expires_at=expires_at,
        )
        session.add(user)
    else:
        # Update basic profile data and tokens
        user.full_name = payload.full_name or user.full_name
        user.avatar_url = payload.avatar_url or user.avatar_url
        if payload.google_access_token:
            user.google_access_token = payload.google_access_token
        if payload.google_refresh_token:
            user.google_refresh_token = payload.google_refresh_token
        if expires_at:
            user.google_token_expires_at = expires_at
        if user.status == "pending":
            user.status = "active"
    
    await session.commit()

    # Use expires_in if provided (in seconds), otherwise use default TTL
    if payload.expires_in is not None:
        token_ttl_seconds = min(payload.expires_in, settings.SESSION_TTL_MINUTES * 60)
    else:
        token_ttl_seconds = settings.SESSION_TTL_MINUTES * 60
    session_token = create_session_token(str(user.id), ttl_minutes=token_ttl_seconds // 60)
    response.set_cookie(
        key="session",
        value=session_token,
        httponly=True,
        secure=settings.IS_PRODUCTION,  # True in production (HTTPS)
        samesite="lax",
        max_age=token_ttl_seconds,
        path="/",
    )
    return UserOut.from_model(user)


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("session", path="/")
    return {"status": "ok"}


@router.post("/refresh", response_model=UserOut)
async def refresh(response: Response, current_user: User = Depends(get_current_user)):
    session_token = create_session_token(str(current_user.id))
    response.set_cookie(
        key="session",
        value=session_token,
        httponly=True,
        secure=settings.IS_PRODUCTION,  # True in production (HTTPS)
        samesite="lax",
        max_age=settings.SESSION_TTL_MINUTES * 60,
        path="/",
    )
    return UserOut.from_model(current_user)


@router.get("/user", response_model=UserOut)
async def get_user(current_user: User = Depends(get_current_user)):
    return UserOut.from_model(current_user)


@router.get("/avatar")
async def get_avatar(current_user: User = Depends(get_current_user)):
    """
    Proxies user avatar from Google to avoid CORS and rate limiting issues.
    """
    if not current_user.avatar_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avatar not found"
        )
    
    try:
        # Load image from Google servers
        response = requests.get(
            current_user.avatar_url,
            stream=True,
            timeout=10,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; DataRoom/1.0)"
            }
        )
        response.raise_for_status()
        
        # Determine content-type from Google response
        content_type = response.headers.get("Content-Type", "image/jpeg")
        
        # Return image as stream
        def generate():
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        
        return StreamingResponse(
            generate(),
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
            }
        )
    except requests.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch avatar: {str(e)}"
        )


