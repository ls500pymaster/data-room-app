from __future__ import annotations

import mimetypes
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, Request, Response, File, UploadFile, Form
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db import get_session
from backend.app.deps import get_current_user
from backend.app.models import File, User
from backend.app.services.file_storage import save_imported_file, get_file_path, delete_file
from backend.app.services.google_drive import (
    create_credentials_from_tokens,
    download_drive_file,
    get_file_metadata,
    list_drive_files,
    refresh_access_token,
    upload_file_to_drive,
    check_drive_upload_permission,
    create_drive_folder,
)
from datetime import datetime, timedelta, timezone


router = APIRouter(prefix="/files", tags=["files"])


class DriveFileOut(BaseModel):
    id: str
    name: str
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    modified_time: Optional[str] = None
    web_view_link: Optional[str] = None
    is_folder: bool = False


class DriveFilesResponse(BaseModel):
    files: List[DriveFileOut]
    next_page_token: Optional[str] = None


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_name: str
    mime_type: Optional[str] = None
    extension: Optional[str] = None
    size_bytes: int
    status: str
    drive_file_id: Optional[str] = None
    storage_key: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    web_view_link: Optional[str] = None


class ImportFilesRequest(BaseModel):
    file_ids: List[str] = Field(..., min_length=1, max_length=20)


class CreateFolderRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    parent_folder_id: Optional[str] = None


class ImportSkippedItem(BaseModel):
    file_id: str
    reason: str
    file_name: Optional[str] = None  # Optional file name for better UX


class ImportFailureItem(BaseModel):
    file_id: str
    error: str


class ImportFilesResponse(BaseModel):
    imported: List[FileOut]
    skipped: List[ImportSkippedItem]
    failed: List[ImportFailureItem]


def _normalize_extension(name: Optional[str], mime_type: Optional[str]) -> Optional[str]:
    if name and "." in name:
        ext = name.rsplit(".", 1)[1]
        if ext:
            return ext.lower()
    if mime_type:
        guessed = mimetypes.guess_extension(mime_type)
        if guessed:
            return guessed.lstrip(".")
    return None


def _get_valid_web_view_link(web_view_link: Optional[str], drive_file_id: Optional[str]) -> Optional[str]:
    """
    Validates and returns a valid Google Drive web view link.
    If the provided link is invalid or None, generates one from drive_file_id.
    """
    # Validate existing link
    if web_view_link:
        # Check if it's a valid Google Drive link
        if web_view_link.startswith("https://drive.google.com/"):
            return web_view_link
        # If it's not a valid Drive link (e.g., aistudio.google.com), ignore it
        # and generate a new one
    
    # Generate link from drive_file_id if available
    if drive_file_id:
        return f"https://drive.google.com/file/d/{drive_file_id}/view"
    
    return None


def _serialize_file(file_obj: File) -> Dict[str, Any]:
    metadata = file_obj.scan_report or {}
    web_view_link = metadata.get("webViewLink")
    return {
        "id": str(file_obj.id),
        "original_name": file_obj.original_name,
        "mime_type": file_obj.mime_type,
        "extension": file_obj.extension,
        "size_bytes": file_obj.size_bytes,
        "status": file_obj.status,
        "drive_file_id": file_obj.drive_file_id,
        "storage_key": file_obj.storage_key,
        "created_at": file_obj.created_at.isoformat() if file_obj.created_at else None,
        "updated_at": file_obj.updated_at.isoformat() if file_obj.updated_at else None,
        "web_view_link": _get_valid_web_view_link(web_view_link, file_obj.drive_file_id),
    }


def _ensure_drive_tokens(user: User) -> None:
    if not user.google_access_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Google Drive is not connected. Please sign in with Google to upload files to Google Drive.",
        )


async def _refresh_and_save_user_tokens(
    user: User,
    session: AsyncSession,
) -> None:
    """Refreshes user tokens if expired and saves to database."""
    from google.oauth2.credentials import Credentials as GoogleCredentials
    
    # Create credentials
    credentials = create_credentials_from_tokens(
        user.google_access_token,
        user.google_refresh_token,
        user.google_token_expires_at,
    )
    
    # CRITICAL: ALWAYS create new Credentials with guaranteed correct expiry
    # before any valid/expired check to avoid timezone issues
    fixed_expiry = None
    if credentials.expiry:
        if credentials.expiry.tzinfo is None:
            fixed_expiry = credentials.expiry.replace(tzinfo=timezone.utc)
        else:
            fixed_expiry = credentials.expiry.astimezone(timezone.utc)
    else:
        # If expiry is missing, set default value
        fixed_expiry = datetime.now(timezone.utc) + timedelta(seconds=3600)
    
    # Create new credentials with correct expiry
    credentials = GoogleCredentials(
        token=credentials.token,
        refresh_token=credentials.refresh_token,
        token_uri=credentials.token_uri,
        client_id=credentials.client_id,
        client_secret=credentials.client_secret,
        scopes=credentials.scopes,
        expiry=fixed_expiry,
    )
    
    # Check if token needs refresh using direct expiry check
    # instead of credentials.valid/expired to avoid timezone issues
    needs_refresh = False
    if credentials.token and credentials.refresh_token:
        if fixed_expiry:
            # Check if token expired (with 60 second buffer)
            now_utc = datetime.now(timezone.utc)
            if fixed_expiry <= now_utc + timedelta(seconds=60):
                needs_refresh = True
        else:
            # If expiry is missing, consider token expired
            needs_refresh = True
    
    if needs_refresh:
        old_token = credentials.token
        try:
            credentials = refresh_access_token(credentials)
            
            # Ensure refreshed expiry has timezone
            refreshed_expiry = credentials.expiry
            if refreshed_expiry:
                if refreshed_expiry.tzinfo is None:
                    refreshed_expiry = refreshed_expiry.replace(tzinfo=timezone.utc)
                else:
                    refreshed_expiry = refreshed_expiry.astimezone(timezone.utc)
                
                # Create new credentials with correct expiry
                credentials = GoogleCredentials(
                    token=credentials.token,
                    refresh_token=credentials.refresh_token,
                    token_uri=credentials.token_uri,
                    client_id=credentials.client_id,
                    client_secret=credentials.client_secret,
                    scopes=credentials.scopes,
                    expiry=refreshed_expiry,
                )
            
            # If token changed, save to database
            if credentials.token != old_token and refreshed_expiry:
                user.google_access_token = credentials.token
                user.google_token_expires_at = refreshed_expiry
                await session.commit()
                await session.refresh(user)
        except Exception as e:
            # If token refresh failed, log and continue with current token
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to refresh token for user {user.id}: {e}")


@router.get("", response_model=List[FileOut])
async def list_imported_files(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    result = await session.execute(
        select(File)
        .where(File.uploader_id == current_user.id, File.deleted_at.is_(None))
        .order_by(File.created_at.desc())
    )
    files = result.scalars().all()
    return [_serialize_file(record) for record in files]


@router.get("/drive", response_model=DriveFilesResponse)
async def list_drive_files_endpoint(
    page_size: int = Query(20, ge=1, le=100),
    page_token: Optional[str] = Query(None),
    parent_folder_id: Optional[str] = Query(None, description="Parent folder ID (None or 'root' for root folder)"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _ensure_drive_tokens(current_user)
    
    # Refresh tokens if needed
    await _refresh_and_save_user_tokens(current_user, session)

    drive_listing = await list_drive_files(
        current_user.google_access_token,
        current_user.google_refresh_token,
        current_user.google_token_expires_at,
        page_size=page_size,
        page_token=page_token,
        parent_folder_id=parent_folder_id,
    )

    files: List[DriveFileOut] = []
    for item in drive_listing.get("files", []):
        mime_type = item.get("mimeType")
        is_folder = mime_type == "application/vnd.google-apps.folder"
        
        # Show all files including Google Docs/Sheets/folders
        size_raw = item.get("size")
        size_bytes = int(size_raw) if size_raw is not None else None
        drive_file_id = item.get("id")
        raw_web_view_link = item.get("webViewLink")
        valid_web_view_link = _get_valid_web_view_link(raw_web_view_link, drive_file_id)
        
        files.append(
            DriveFileOut(
                id=drive_file_id,
                name=item.get("name"),
                mime_type=mime_type,
                size_bytes=size_bytes,
                modified_time=item.get("modifiedTime"),
                web_view_link=valid_web_view_link,
                is_folder=is_folder,
            )
        )

    return DriveFilesResponse(
        files=files,
        next_page_token=drive_listing.get("next_page_token"),
    )


@router.post("/drive/upload", response_model=DriveFileOut)
async def upload_file_to_drive_endpoint(
    file: UploadFile = File(),
    parent_folder_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Uploads a file to Google Drive.
    """
    _ensure_drive_tokens(current_user)
    
    # Refresh tokens if needed
    await _refresh_and_save_user_tokens(current_user, session)
    
    # Check if user has upload permission
    credentials = create_credentials_from_tokens(
        current_user.google_access_token,
        current_user.google_refresh_token,
        current_user.google_token_expires_at,
    )
    credentials = refresh_access_token(credentials)
    
    if not check_drive_upload_permission(credentials):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission to upload files to Google Drive. Please sign in again with Google to grant upload permissions.",
        )
    
    # Read file content
    file_content = await file.read()
    if not file_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty",
        )
    
    # Determine MIME type
    mime_type = file.content_type
    if not mime_type:
        import mimetypes
        mime_type, _ = mimetypes.guess_type(file.filename or "")
    
    # Upload to Google Drive
    try:
        drive_file = await upload_file_to_drive(
            access_token=current_user.google_access_token,
            refresh_token=current_user.google_refresh_token,
            expires_at=current_user.google_token_expires_at,
            file_content=file_content,
            file_name=file.filename or "untitled",
            mime_type=mime_type,
            parent_folder_id=parent_folder_id if parent_folder_id and parent_folder_id != "root" else None,
        )
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "unauthorized" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google Drive authorization error. Please try logging in again",
            )
        elif "403" in error_msg or "forbidden" in error_msg.lower() or "insufficient permission" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No permission to upload files to Google Drive. Please sign in again with Google to grant upload permissions.",
            )
        elif "quota" in error_msg.lower() or "storage" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Google Drive storage quota exceeded",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error uploading file to Google Drive: {error_msg}",
            )
    
    # Convert to DriveFileOut format
    size_raw = drive_file.get("size")
    size_bytes = int(size_raw) if size_raw is not None else None
    drive_file_id = drive_file.get("id")
    raw_web_view_link = drive_file.get("webViewLink")
    valid_web_view_link = _get_valid_web_view_link(raw_web_view_link, drive_file_id)
    
    return DriveFileOut(
        id=drive_file_id,
        name=drive_file.get("name"),
        mime_type=drive_file.get("mimeType"),
        size_bytes=size_bytes,
        modified_time=drive_file.get("modifiedTime"),
        web_view_link=valid_web_view_link,
        is_folder=False,
    )


class DrivePermissionsResponse(BaseModel):
    has_read_permission: bool
    has_upload_permission: bool
    scopes: List[str]


@router.get("/drive/permissions", response_model=DrivePermissionsResponse)
async def check_drive_permissions(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Checks Google Drive permissions for the current user.
    """
    _ensure_drive_tokens(current_user)
    
    # Refresh tokens if needed
    await _refresh_and_save_user_tokens(current_user, session)
    
    credentials = create_credentials_from_tokens(
        current_user.google_access_token,
        current_user.google_refresh_token,
        current_user.google_token_expires_at,
    )
    credentials = refresh_access_token(credentials)
    
    user_scopes = credentials.scopes or []
    
    has_read_permission = (
        "https://www.googleapis.com/auth/drive.readonly" in user_scopes or
        "https://www.googleapis.com/auth/drive" in user_scopes
    )
    
    has_upload_permission = check_drive_upload_permission(credentials)
    
    return DrivePermissionsResponse(
        has_read_permission=has_read_permission,
        has_upload_permission=has_upload_permission,
        scopes=user_scopes,
    )


@router.post("/drive/folder", response_model=DriveFileOut)
async def create_drive_folder_endpoint(
    payload: CreateFolderRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Creates a folder in Google Drive.
    """
    _ensure_drive_tokens(current_user)
    
    # Refresh tokens if needed
    await _refresh_and_save_user_tokens(current_user, session)
    
    # Check if user has upload permission
    credentials = create_credentials_from_tokens(
        current_user.google_access_token,
        current_user.google_refresh_token,
        current_user.google_token_expires_at,
    )
    credentials = refresh_access_token(credentials)
    
    if not check_drive_upload_permission(credentials):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission to create folders in Google Drive. Please sign in again with Google to grant upload permissions.",
        )
    
    # Validate folder name
    folder_name = payload.name.strip()
    if not folder_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Folder name cannot be empty",
        )
    
    # Create folder in Google Drive
    try:
        drive_folder = await create_drive_folder(
            access_token=current_user.google_access_token,
            refresh_token=current_user.google_refresh_token,
            expires_at=current_user.google_token_expires_at,
            folder_name=folder_name,
            parent_folder_id=payload.parent_folder_id,
        )
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "unauthorized" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google Drive authorization error. Please try logging in again",
            )
        elif "403" in error_msg or "forbidden" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No permission to create folders in Google Drive",
            )
        elif "404" in error_msg or "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent folder not found",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error creating folder in Google Drive: {error_msg}",
            )
    
    # Convert to DriveFileOut format
    drive_folder_id = drive_folder.get("id")
    raw_web_view_link = drive_folder.get("webViewLink")
    valid_web_view_link = _get_valid_web_view_link(raw_web_view_link, drive_folder_id)
    
    return DriveFileOut(
        id=drive_folder_id,
        name=drive_folder.get("name"),
        mime_type=drive_folder.get("mimeType"),
        size_bytes=None,
        modified_time=drive_folder.get("modifiedTime"),
        web_view_link=valid_web_view_link,
        is_folder=True,
    )


@router.post("/import", response_model=ImportFilesResponse)
async def import_files(
    payload: ImportFilesRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    _ensure_drive_tokens(current_user)
    
    # Refresh tokens if needed
    await _refresh_and_save_user_tokens(current_user, session)

    imported_files: List[File] = []
    skipped: List[ImportSkippedItem] = []
    failed: List[ImportFailureItem] = []

    for drive_file_id in payload.file_ids:
        # Check if file already exists (only non-deleted files)
        exists_result = await session.execute(
            select(File).where(
                File.drive_file_id == drive_file_id,
                File.deleted_at.is_(None)
            )
        )
        existing_file = exists_result.scalar_one_or_none()
        if existing_file:
            # File already imported and not deleted - skip it
            file_name = existing_file.original_name if existing_file else None
            skipped.append(ImportSkippedItem(
                file_id=drive_file_id, 
                reason="already_imported",
                file_name=file_name
            ))
            continue
        
        # Check if file was previously deleted (soft-deleted)
        deleted_result = await session.execute(
            select(File).where(
                File.drive_file_id == drive_file_id,
                File.deleted_at.isnot(None)
            )
        )
        deleted_file = deleted_result.scalar_one_or_none()
        if deleted_file:
            # File was deleted - allow re-import by removing old record
            # This allows re-importing deleted files
            await session.delete(deleted_file)
            await session.flush()  # Flush to ensure deletion happens before new insert
            # Continue to import process below

        try:
            metadata = await get_file_metadata(
                current_user.google_access_token,
                current_user.google_refresh_token,
                current_user.google_token_expires_at,
                drive_file_id,
            )

            mime_type = metadata.get("mimeType")
            original_name = metadata.get("name") or "untitled"
            
            # Skip folders (can't import folders)
            if mime_type == "application/vnd.google-apps.folder":
                skipped.append(ImportSkippedItem(
                    file_id=drive_file_id, 
                    reason="unsupported_type",
                    file_name=original_name
                ))
                continue
            # Skip Google Apps files (Docs, Sheets, etc.) and Google AI Studio prompts
            if mime_type and (
                mime_type.startswith("application/vnd.google-apps.") or
                mime_type.startswith("application/vnd.google-makersuite.")
            ):
                skipped.append(ImportSkippedItem(
                    file_id=drive_file_id, 
                    reason="unsupported_type",
                    file_name=original_name
                ))
                continue
            extension = _normalize_extension(original_name, mime_type)

            file_bytes = await download_drive_file(
                current_user.google_access_token,
                current_user.google_refresh_token,
                current_user.google_token_expires_at,
                drive_file_id,
            )

            if not file_bytes:
                failed.append(ImportFailureItem(file_id=drive_file_id, error="empty_file"))
                continue

            file_uuid = uuid.uuid4()
            storage_key, checksum = save_imported_file(
                current_user.id,
                file_uuid,
                extension,
                file_bytes,
            )

            size_bytes = len(file_bytes)
            try:
                size_from_meta_value = metadata.get("size")
                size_from_meta = int(size_from_meta_value) if size_from_meta_value is not None else None
            except (TypeError, ValueError):
                size_from_meta = None
            final_size = size_from_meta if size_from_meta and size_from_meta > 0 else size_bytes

            # Validate and fix webViewLink if needed
            raw_web_view_link = metadata.get("webViewLink")
            valid_web_view_link = _get_valid_web_view_link(raw_web_view_link, drive_file_id)
            
            new_file = File(
                id=file_uuid,
                uploader_id=current_user.id,
                storage_key=storage_key,
                drive_file_id=drive_file_id,
                original_name=original_name,
                extension=extension,
                mime_type=mime_type,
                size_bytes=final_size,
                checksum_sha256=checksum,
                status="ready",
                scan_report={
                    "source": "google_drive",
                    "driveFileId": drive_file_id,
                    "webViewLink": valid_web_view_link,
                    "owners": metadata.get("owners"),
                },
            )
            session.add(new_file)
            imported_files.append(new_file)

        except HTTPException:
            raise
        except Exception as exc:
            # Handle IntegrityError (duplicate drive_file_id) as already_imported
            from sqlalchemy.exc import IntegrityError
            if isinstance(exc, IntegrityError) and "files_drive_file_id_key" in str(exc):
                # Try to get file name from metadata if available
                file_name = None
                try:
                    metadata = await get_file_metadata(
                        current_user.google_access_token,
                        current_user.google_refresh_token,
                        current_user.google_token_expires_at,
                        drive_file_id,
                    )
                    file_name = metadata.get("name")
                except:
                    pass
                skipped.append(ImportSkippedItem(
                    file_id=drive_file_id, 
                    reason="already_imported",
                    file_name=file_name
                ))
                continue
            
            # Improve error messages
            error_msg = str(exc)
            if "404" in error_msg or "not found" in error_msg.lower():
                error_msg = "File not found in Google Drive"
            elif "403" in error_msg or "forbidden" in error_msg.lower() or "permission" in error_msg.lower():
                error_msg = "No access to file in Google Drive"
            elif "401" in error_msg or "unauthorized" in error_msg.lower():
                error_msg = "Google Drive authorization error. Please try logging in again"
            elif "quota" in error_msg.lower() or "storage" in error_msg.lower():
                error_msg = "Google Drive storage quota exceeded"
            failed.append(ImportFailureItem(file_id=drive_file_id, error=error_msg))

    if imported_files:
        try:
            await session.commit()
            for file_obj in imported_files:
                await session.refresh(file_obj)
        except Exception as exc:
            await session.rollback()
            # Handle IntegrityError (duplicate drive_file_id) - move failed imports to skipped
            from sqlalchemy.exc import IntegrityError
            if isinstance(exc, IntegrityError) and "files_drive_file_id_key" in str(exc):
                # Find which file caused the error and move it to skipped
                for file_obj in imported_files:
                    if file_obj.drive_file_id:
                        skipped.append(ImportSkippedItem(
                            file_id=file_obj.drive_file_id, 
                            reason="already_imported",
                            file_name=file_obj.original_name
                        ))
                imported_files = []
            else:
                # For other errors, move all to failed
                for file_obj in imported_files:
                    if file_obj.drive_file_id:
                        failed.append(ImportFailureItem(file_id=file_obj.drive_file_id, error=str(exc)))
                imported_files = []
    else:
        await session.rollback()

    return ImportFilesResponse(
        imported=[FileOut(**_serialize_file(f)) for f in imported_files],
        skipped=skipped,
        failed=failed,
    )


@router.get("/{file_id}/view")
async def view_file(
    file_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    View file in browser.
    Supports range requests for large files.
    """
    try:
        file_uuid = uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file ID format",
        )
    
    # Get file from database
    result = await session.execute(
        select(File).where(
            File.id == file_uuid,
            File.uploader_id == current_user.id,
            File.deleted_at.is_(None)
        )
    )
    file_obj = result.scalar_one_or_none()
    
    if not file_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found or access denied",
        )
    
    if file_obj.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File is not ready for viewing. Status: {file_obj.status}",
        )
    
    # Get file path
    file_path = get_file_path(file_obj.storage_key)
    
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on disk",
        )
    
    # Determine MIME type
    mime_type = file_obj.mime_type
    if not mime_type:
        mime_type, _ = mimetypes.guess_type(file_obj.original_name)
        if not mime_type:
            mime_type = "application/octet-stream"
    
    file_size = file_obj.size_bytes
    
    # Support range requests for large files
    range_header = request.headers.get("range")
    
    if range_header:
        # Parse range header (e.g., "bytes=0-1023")
        try:
            range_match = range_header.replace("bytes=", "").split("-")
            start = int(range_match[0]) if range_match[0] else 0
            end = int(range_match[1]) if range_match[1] else file_size - 1
            
            if start < 0 or end >= file_size or start > end:
                raise HTTPException(
                    status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
                    detail=f"Range not satisfiable. File size: {file_size}",
                    headers={"Content-Range": f"bytes */{file_size}"},
                )
            
            content_range = f"bytes {start}-{end}/{file_size}"
            chunk_size = end - start + 1
            
            # Read only the needed chunk of the file
            def generate_chunk():
                with open(file_path, "rb") as f:
                    f.seek(start)
                    remaining = chunk_size
                    while remaining > 0:
                        chunk = f.read(min(8192, remaining))  # Read 8KB at a time
                        if not chunk:
                            break
                        yield chunk
                        remaining -= len(chunk)
            
            return StreamingResponse(
                generate_chunk(),
                status_code=206,
                media_type=mime_type,
                headers={
                    "Content-Range": content_range,
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(chunk_size),
                    "Content-Disposition": f'inline; filename="{file_obj.original_name}"',
                },
            )
        except (ValueError, IndexError):
            # If range header is invalid, return entire file
            pass
    
    # Return entire file via FileResponse for efficiency
    return FileResponse(
        path=str(file_path),
        media_type=mime_type,
        filename=file_obj.original_name,
        headers={
            "Accept-Ranges": "bytes",
        },
    )


@router.delete("/{file_id}")
async def delete_file_endpoint(
    file_id: str,
    response: Response,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Deletes file from Data Room (soft delete).
    Deletes file from disk and sets deleted_at in database.
    """
    try:
        file_uuid = uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file ID format",
        )
    
    # Get file from database
    result = await session.execute(
        select(File).where(
            File.id == file_uuid,
            File.uploader_id == current_user.id,
            File.deleted_at.is_(None)  # Only non-deleted files
        )
    )
    file_obj = result.scalar_one_or_none()
    
    if not file_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found or access denied",
        )
    
    # Delete file from disk
    try:
        delete_file(file_obj.storage_key)
    except FileNotFoundError:
        # File already deleted from disk, but record exists in DB - continue soft delete
        pass
    except Exception as e:
        # Log error but continue soft delete in database
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to delete file from disk: {e}")
    
    # Soft delete in database (set deleted_at)
    file_obj.deleted_at = datetime.now(timezone.utc)
    await session.commit()
    
    response.status_code = status.HTTP_204_NO_CONTENT
    return None

