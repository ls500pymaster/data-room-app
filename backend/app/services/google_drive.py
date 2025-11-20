from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from backend.core.config import settings

# === FIX GOOGLE NAIVE TZ BUG ===
_original_expired = Credentials.expired.fget

def _fixed_expired(self):
    exp = self.expiry
    if exp is None:
        return True
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
        self.expiry = exp
    return datetime.now(timezone.utc) >= exp

Credentials.expired = property(_fixed_expired)
# === END FIX ===


def _ensure_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensures that datetime has UTC timezone."""
    if dt is None:
        return None
    # If datetime is timezone-naive, add UTC
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    # Convert to UTC if timezone is different
    return dt.astimezone(timezone.utc)




def create_oauth_flow() -> Flow:
    """Creates OAuth 2.0 flow for Google."""
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": settings.GOOGLE_AUTH_URI,
                "token_uri": settings.GOOGLE_TOKEN_URI,
                "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
            }
        },
        scopes=settings.GOOGLE_SCOPES,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,  # Explicitly specify redirect_uri for Flow
    )
    return flow


def get_authorization_url(state: Optional[str] = None) -> str:
    """Generates URL for Google OAuth authorization."""
    flow = create_oauth_flow()
    # redirect_uri is already set in create_oauth_flow(), don't pass it again
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",  # Force refresh_token request
        state=state,
    )
    return authorization_url


async def exchange_code_for_tokens(code: str) -> tuple:
    """Exchanges authorization code for access and refresh tokens."""
    from google.oauth2.credentials import Credentials
    
    flow = create_oauth_flow()
    
    # Disable scope change validation - Google may add openid automatically
    # or user may not grant permission for some scopes
    # Save original validation method
    original_validate_granted_scopes = getattr(flow.oauth2session, '_validate_granted_scopes', None)
    
    def patched_validate_granted_scopes(*args, **kwargs):
        # Ignore scope validation - accept any scopes that Google returned
        pass
    
    # Patch scope validation method if it exists
    if hasattr(flow.oauth2session, '_validate_granted_scopes'):
        flow.oauth2session._validate_granted_scopes = patched_validate_granted_scopes
    
    try:
        # redirect_uri is already set in create_oauth_flow(), don't pass it again
        flow.fetch_token(code=code)
    except ValueError as e:
        # If error still occurs, try to bypass validation using another method
        error_msg = str(e)
        if "Scope has changed" in error_msg:
            # Use requests directly to exchange code for tokens
            import requests
            token_response = requests.post(
                settings.GOOGLE_TOKEN_URI,
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
            token_response.raise_for_status()
            token_data = token_response.json()
            
            # Create credentials from received tokens
            expires_at = (
                datetime.now(timezone.utc) + timedelta(seconds=token_data.get("expires_in", 3600))
                if token_data.get("expires_in")
                else None
            )
            credentials = Credentials(
                token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token"),
                token_uri=settings.GOOGLE_TOKEN_URI,
                client_id=settings.GOOGLE_CLIENT_ID,
                client_secret=settings.GOOGLE_CLIENT_SECRET,
                scopes=token_data.get("scope", "").split() if token_data.get("scope") else settings.GOOGLE_SCOPES,
                expiry=_ensure_aware(expires_at),
            )
            tokens_dict = {
                "access_token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "expires_in": token_data.get("expires_in"),
                "expires_at": _ensure_aware(expires_at),
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": credentials.scopes,
            }
            return tokens_dict, credentials
        else:
            raise
    
    credentials = flow.credentials
    
    # Fix expiry in credentials object if it's timezone-naive
    if credentials.expiry:
        if credentials.expiry.tzinfo is None:
            # Create new Credentials with correct expiry
            fixed_expiry = credentials.expiry.replace(tzinfo=timezone.utc)
            credentials = Credentials(
                token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_uri=credentials.token_uri,
                client_id=credentials.client_id,
                client_secret=credentials.client_secret,
                scopes=credentials.scopes,
                expiry=fixed_expiry,
            )
        elif credentials.expiry.tzinfo != timezone.utc:
            fixed_expiry = credentials.expiry.astimezone(timezone.utc)
            credentials = Credentials(
                token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_uri=credentials.token_uri,
                client_id=credentials.client_id,
                client_secret=credentials.client_secret,
                scopes=credentials.scopes,
                expiry=fixed_expiry,
            )
    
    # Final check: ensure expiry in credentials has UTC timezone
    if credentials.expiry:
        if credentials.expiry.tzinfo is None or credentials.expiry.tzinfo != timezone.utc:
            fixed_expiry = credentials.expiry.replace(tzinfo=timezone.utc) if credentials.expiry.tzinfo is None else credentials.expiry.astimezone(timezone.utc)
            credentials = Credentials(
                token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_uri=credentials.token_uri,
                client_id=credentials.client_id,
                client_secret=credentials.client_secret,
                scopes=credentials.scopes,
                expiry=fixed_expiry,
            )
    elif not credentials.expiry:
        # If expiry is not set, set default value
        default_expiry = datetime.now(timezone.utc) + timedelta(seconds=3600)
        credentials = Credentials(
            token=credentials.token,
            refresh_token=credentials.refresh_token,
            token_uri=credentials.token_uri,
            client_id=credentials.client_id,
            client_secret=credentials.client_secret,
            scopes=credentials.scopes,
            expiry=default_expiry,
        )
    
    # Calculate expires_at for return
    expires_at = credentials.expiry
    if not expires_at:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=3600)
    
    tokens_dict = {
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "expires_in": int((expires_at.timestamp() - time.time())) if expires_at else 3600,
        "expires_at": expires_at,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }
    return tokens_dict, credentials


def create_credentials_from_tokens(
    access_token: str,
    refresh_token: Optional[str],
    expires_at: Optional[datetime],
) -> Credentials:
    aware_expiry = _ensure_aware(expires_at)

    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri=settings.GOOGLE_TOKEN_URI,
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=settings.GOOGLE_SCOPES,
        expiry=aware_expiry,
    )

    return _force_credentials_utc(creds)


def refresh_access_token(credentials: Credentials) -> Credentials:
    credentials = _force_credentials_utc(credentials)

    exp = credentials.expiry
    now = datetime.now(timezone.utc)

    needs_refresh = (exp is None) or (exp <= now + timedelta(seconds=60))

    if not needs_refresh:
        return credentials

    credentials.refresh(Request())

    # Google writes naive datetime again after refresh → fix it
    return _force_credentials_utc(credentials)


def get_drive_service(credentials: Credentials):
    """Creates Google Drive API service."""
    return build("drive", "v3", credentials=credentials)


async def list_drive_files(
    access_token: str,
    refresh_token: Optional[str],
    expires_at: Optional[datetime],
    page_size: int = 100,
    page_token: Optional[str] = None,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Gets list of files from Google Drive.
    
    Args:
        access_token: Google access token
        refresh_token: Google refresh token
        expires_at: Access token expiration time
        page_size: Number of files per page
        page_token: Token for pagination
        query: Query filter (e.g., "mimeType='application/pdf'")
    
    Returns:
        Dictionary with files and next_page_token
    """
    credentials = create_credentials_from_tokens(access_token, refresh_token, expires_at)
    credentials = refresh_access_token(credentials)
    
    try:
        service = get_drive_service(credentials)
        
        # Query parameters
        params = {
            "pageSize": page_size,
            "fields": "nextPageToken, files(id, name, mimeType, size, modifiedTime, webViewLink)",
            "q": "trashed=false",  # Only non-deleted files
        }
        
        if query:
            params["q"] = f"{params['q']} and {query}"
        
        if page_token:
            params["pageToken"] = page_token
        
        results = service.files().list(**params).execute()
        
        return {
            "files": results.get("files", []),
            "next_page_token": results.get("nextPageToken"),
        }
    except HttpError as e:
        raise Exception(f"Google Drive API error: {e}")


async def download_drive_file(
    access_token: str,
    refresh_token: Optional[str],
    expires_at: Optional[datetime],
    file_id: str,
) -> bytes:
    """
    Downloads file from Google Drive.
    
    Args:
        access_token: Google access token
        refresh_token: Google refresh token
        expires_at: Access token expiration time
        file_id: File ID in Google Drive
    
    Returns:
        File content as bytes
    """
    credentials = create_credentials_from_tokens(access_token, refresh_token, expires_at)
    credentials = refresh_access_token(credentials)
    
    try:
        service = get_drive_service(credentials)
        
        # Get file metadata
        file_metadata = service.files().get(fileId=file_id).execute()
        
        # Download file
        request = service.files().get_media(fileId=file_id)
        file_content = request.execute()
        
        return file_content
    except HttpError as e:
        raise Exception(f"Error downloading file from Google Drive: {e}")


async def get_file_metadata(
    access_token: str,
    refresh_token: Optional[str],
    expires_at: Optional[datetime],
    file_id: str,
) -> Dict[str, Any]:
    """
    Gets file metadata from Google Drive.
    
    Args:
        access_token: Google access token
        refresh_token: Google refresh token
        expires_at: Access token expiration time
        file_id: File ID in Google Drive
    
    Returns:
        File metadata
    """
    credentials = create_credentials_from_tokens(access_token, refresh_token, expires_at)
    credentials = refresh_access_token(credentials)
    
    try:
        service = get_drive_service(credentials)
        file_metadata = service.files().get(
            fileId=file_id,
            fields="id, name, mimeType, size, modifiedTime, createdTime, webViewLink, owners",
        ).execute()
        
        return file_metadata
    except HttpError as e:
        raise Exception(f"Error getting file metadata from Google Drive: {e}")


def _force_credentials_utc(credentials: Credentials) -> Credentials:
    """Returns Credentials where expiry is ALWAYS timezone-aware UTC."""
    exp = credentials.expiry

    if exp is None:
        fixed_expiry = datetime.now(timezone.utc) + timedelta(seconds=3600)
    else:
        if exp.tzinfo is None:
            fixed_expiry = exp.replace(tzinfo=timezone.utc)
        else:
            fixed_expiry = exp.astimezone(timezone.utc)

    return Credentials(
        token=credentials.token,
        refresh_token=credentials.refresh_token,
        token_uri=credentials.token_uri,
        client_id=credentials.client_id,
        client_secret=credentials.client_secret,
        scopes=credentials.scopes,
        expiry=fixed_expiry,
    )
