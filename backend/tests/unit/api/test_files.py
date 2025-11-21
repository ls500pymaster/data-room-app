from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, AsyncMock
import pytest
from fastapi import HTTPException, status

from backend.api.files import (
    list_imported_files,
    list_drive_files_endpoint,
    import_files,
    view_file,
    delete_file_endpoint,
    ImportFilesRequest,
    _get_valid_web_view_link,
)
from backend.app.models.file import File


@pytest.mark.asyncio
class TestListImportedFiles:
    async def test_list_imported_files_empty(self, test_db_session, test_user):
        """Test listing files when user has no files."""
        result = await list_imported_files(
            session=test_db_session,
            current_user=test_user,
        )
        
        assert result == []
    
    async def test_list_imported_files_with_files(self, test_db_session, test_user, test_file):
        """Test listing files when user has files."""
        result = await list_imported_files(
            session=test_db_session,
            current_user=test_user,
        )
        
        assert len(result) == 1
        assert result[0]["id"] == str(test_file.id)
        assert result[0]["original_name"] == test_file.original_name
    
    async def test_list_imported_files_excludes_deleted(self, test_db_session, test_user):
        """Test that deleted files are excluded."""
        deleted_file = File(
            id=uuid.uuid4(),
            uploader_id=test_user.id,
            storage_key="users/test/deleted.pdf",
            original_name="deleted.pdf",
            extension="pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            status="ready",
            deleted_at=datetime.now(timezone.utc),
        )
        test_db_session.add(deleted_file)
        await test_db_session.commit()
        
        result = await list_imported_files(
            session=test_db_session,
            current_user=test_user,
        )
        
        assert len(result) == 0


@pytest.mark.asyncio
class TestListDriveFiles:
    async def test_list_drive_files_success(self, test_db_session, test_user_with_google):
        """Test listing Google Drive files."""
        with patch("backend.api.files._refresh_and_save_user_tokens"), \
             patch("backend.api.files.list_drive_files") as mock_list:
            
            mock_list.return_value = {
                "files": [
                    {
                        "id": "drive_file_1",
                        "name": "test.pdf",
                        "mimeType": "application/pdf",
                        "size": "1024",
                        "modifiedTime": "2024-01-01T00:00:00Z",
                        "webViewLink": "https://drive.google.com/file1",
                    }
                ],
                "next_page_token": None,
            }
            
            result = await list_drive_files_endpoint(
                page_size=20,
                page_token=None,
                current_user=test_user_with_google,
                session=test_db_session,
            )
            
            assert len(result.files) == 1
            assert result.files[0].id == "drive_file_1"
            assert result.files[0].name == "test.pdf"
            assert result.files[0].is_folder is False
    
    async def test_list_drive_files_includes_folders(self, test_db_session, test_user_with_google):
        """Test listing Google Drive files includes folders."""
        with patch("backend.api.files._refresh_and_save_user_tokens"), \
             patch("backend.api.files.list_drive_files") as mock_list:
            
            mock_list.return_value = {
                "files": [
                    {
                        "id": "drive_file_1",
                        "name": "test.pdf",
                        "mimeType": "application/pdf",
                        "size": "1024",
                        "modifiedTime": "2024-01-01T00:00:00Z",
                        "webViewLink": "https://drive.google.com/file1",
                    },
                    {
                        "id": "drive_folder_1",
                        "name": "My Folder",
                        "mimeType": "application/vnd.google-apps.folder",
                        "modifiedTime": "2024-01-01T00:00:00Z",
                        "webViewLink": "https://drive.google.com/folder1",
                    }
                ],
                "next_page_token": None,
            }
            
            result = await list_drive_files_endpoint(
                page_size=20,
                page_token=None,
                current_user=test_user_with_google,
                session=test_db_session,
            )
            
            assert len(result.files) == 2
            # Check file
            file_item = next(f for f in result.files if f.id == "drive_file_1")
            assert file_item.name == "test.pdf"
            assert file_item.is_folder is False
            # Check folder
            folder_item = next(f for f in result.files if f.id == "drive_folder_1")
            assert folder_item.name == "My Folder"
            assert folder_item.is_folder is True
    
    async def test_list_drive_files_includes_google_docs(self, test_db_session, test_user_with_google):
        """Test listing Google Drive files includes Google Docs/Sheets."""
        with patch("backend.api.files._refresh_and_save_user_tokens"), \
             patch("backend.api.files.list_drive_files") as mock_list:
            
            mock_list.return_value = {
                "files": [
                    {
                        "id": "drive_doc_1",
                        "name": "My Document",
                        "mimeType": "application/vnd.google-apps.document",
                        "modifiedTime": "2024-01-01T00:00:00Z",
                        "webViewLink": "https://drive.google.com/doc1",
                    },
                    {
                        "id": "drive_sheet_1",
                        "name": "My Spreadsheet",
                        "mimeType": "application/vnd.google-apps.spreadsheet",
                        "modifiedTime": "2024-01-01T00:00:00Z",
                        "webViewLink": "https://drive.google.com/sheet1",
                    }
                ],
                "next_page_token": None,
            }
            
            result = await list_drive_files_endpoint(
                page_size=20,
                page_token=None,
                current_user=test_user_with_google,
                session=test_db_session,
            )
            
            # All files should be included (no filtering)
            assert len(result.files) == 2
            doc_item = next(f for f in result.files if f.id == "drive_doc_1")
            assert doc_item.name == "My Document"
            assert doc_item.mime_type == "application/vnd.google-apps.document"
            assert doc_item.is_folder is False
    
    async def test_list_drive_files_no_token(self, test_db_session, test_user):
        """Test listing drive files without Google token."""
        with pytest.raises(HTTPException) as exc_info:
            await list_drive_files_endpoint(
                page_size=20,
                page_token=None,
                current_user=test_user,
                session=test_db_session,
            )
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Google Drive access token" in exc_info.value.detail


@pytest.mark.asyncio
class TestImportFiles:
    async def test_import_files_success(self, test_db_session, test_user_with_google, temp_storage_dir):
        """Test importing files from Google Drive."""
        with patch("backend.api.files._refresh_and_save_user_tokens"), \
             patch("backend.api.files.get_file_metadata") as mock_metadata, \
             patch("backend.api.files.download_drive_file") as mock_download:
            
            mock_metadata.return_value = {
                "id": "drive_file_1",
                "name": "test.pdf",
                "mimeType": "application/pdf",
                "size": "1024",
                "webViewLink": "https://drive.google.com/file1",
            }
            mock_download.return_value = b"file content"
            
            payload = ImportFilesRequest(file_ids=["drive_file_1"])
            
            result = await import_files(
                payload=payload,
                session=test_db_session,
                current_user=test_user_with_google,
            )
            
            assert len(result.imported) == 1
            assert len(result.skipped) == 0
            assert len(result.failed) == 0
    
    async def test_import_files_already_imported(self, test_db_session, test_user_with_google, test_file):
        """Test importing file that's already imported."""
        # Set drive_file_id on test_file
        test_file.drive_file_id = "drive_file_1"
        await test_db_session.commit()
        
        payload = ImportFilesRequest(file_ids=["drive_file_1"])
        
        result = await import_files(
            payload=payload,
            session=test_db_session,
            current_user=test_user_with_google,
        )
        
        assert len(result.imported) == 0
        assert len(result.skipped) == 1
        assert result.skipped[0].reason == "already_imported"
    
    async def test_import_files_already_imported_but_deleted(self, test_db_session, test_user_with_google, temp_storage_dir):
        """Test importing file that was previously imported but deleted (soft delete) - should allow re-import."""
        from datetime import datetime, timezone
        # Create a deleted file with drive_file_id
        deleted_file = File(
            id=uuid.uuid4(),
            uploader_id=test_user_with_google.id,
            storage_key="users/test/deleted.pdf",
            drive_file_id="drive_file_deleted",
            original_name="deleted.pdf",
            extension="pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            status="ready",
            deleted_at=datetime.now(timezone.utc),
        )
        test_db_session.add(deleted_file)
        await test_db_session.commit()
        
        with patch("backend.api.files._refresh_and_save_user_tokens"), \
             patch("backend.api.files.get_file_metadata") as mock_metadata, \
             patch("backend.api.files.download_drive_file") as mock_download:
            
            mock_metadata.return_value = {
                "id": "drive_file_deleted",
                "name": "deleted.pdf",
                "mimeType": "application/pdf",
                "size": "1024",
                "webViewLink": "https://drive.google.com/file_deleted",
            }
            mock_download.return_value = b"file content"
            
            payload = ImportFilesRequest(file_ids=["drive_file_deleted"])
            
            result = await import_files(
                payload=payload,
                session=test_db_session,
                current_user=test_user_with_google,
            )
            
            # Should allow re-import of deleted file
            assert len(result.imported) == 1
            assert len(result.skipped) == 0
            assert len(result.failed) == 0
            assert result.imported[0].original_name == "deleted.pdf"
    
    async def test_import_files_unsupported_type(self, test_db_session, test_user_with_google):
        """Test importing unsupported file type (Google Docs)."""
        with patch("backend.api.files._refresh_and_save_user_tokens"), \
             patch("backend.api.files.get_file_metadata") as mock_metadata:
            
            mock_metadata.return_value = {
                "id": "drive_file_1",
                "name": "test.gdoc",
                "mimeType": "application/vnd.google-apps.document",
            }
            
            payload = ImportFilesRequest(file_ids=["drive_file_1"])
            
            result = await import_files(
                payload=payload,
                session=test_db_session,
                current_user=test_user_with_google,
            )
            
            assert len(result.imported) == 0
            assert len(result.skipped) == 1
            assert result.skipped[0].reason == "unsupported_type"
    
    async def test_import_files_unsupported_type_ai_studio(self, test_db_session, test_user_with_google):
        """Test importing unsupported file type (Google AI Studio prompt)."""
        with patch("backend.api.files._refresh_and_save_user_tokens"), \
             patch("backend.api.files.get_file_metadata") as mock_metadata:
            
            mock_metadata.return_value = {
                "id": "drive_file_1",
                "name": "prompt.prompt",
                "mimeType": "application/vnd.google-makersuite.prompt",
            }
            
            payload = ImportFilesRequest(file_ids=["drive_file_1"])
            
            result = await import_files(
                payload=payload,
                session=test_db_session,
                current_user=test_user_with_google,
            )
            
            assert len(result.imported) == 0
            assert len(result.skipped) == 1
            assert result.skipped[0].reason == "unsupported_type"
    
    async def test_import_files_skips_folders(self, test_db_session, test_user_with_google):
        """Test importing folders is skipped."""
        with patch("backend.api.files._refresh_and_save_user_tokens"), \
             patch("backend.api.files.get_file_metadata") as mock_metadata:
            
            mock_metadata.return_value = {
                "id": "drive_folder_1",
                "name": "My Folder",
                "mimeType": "application/vnd.google-apps.folder",
            }
            
            payload = ImportFilesRequest(file_ids=["drive_folder_1"])
            
            result = await import_files(
                payload=payload,
                session=test_db_session,
                current_user=test_user_with_google,
            )
            
            assert len(result.imported) == 0
            assert len(result.skipped) == 1
            assert result.skipped[0].file_id == "drive_folder_1"
            assert result.skipped[0].reason == "unsupported_type"
    
    async def test_import_files_download_error(self, test_db_session, test_user_with_google):
        """Test importing file with download error."""
        with patch("backend.api.files._refresh_and_save_user_tokens"), \
             patch("backend.api.files.get_file_metadata") as mock_metadata, \
             patch("backend.api.files.download_drive_file") as mock_download:
            
            mock_metadata.return_value = {
                "id": "drive_file_1",
                "name": "test.pdf",
                "mimeType": "application/pdf",
            }
            mock_download.side_effect = Exception("Download failed")
            
            payload = ImportFilesRequest(file_ids=["drive_file_1"])
            
            result = await import_files(
                payload=payload,
                session=test_db_session,
                current_user=test_user_with_google,
            )
            
            assert len(result.imported) == 0
            assert len(result.failed) == 1


@pytest.mark.asyncio
class TestViewFile:
    async def test_view_file_success(self, test_db_session, test_user, test_file, temp_storage_dir):
        """Test viewing a file."""
        # Create the actual file on disk
        from backend.app.services.file_storage import get_file_path
        file_path = get_file_path(test_file.storage_key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"test file content")
        
        from fastapi import Request
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        
        result = await view_file(
            file_id=str(test_file.id),
            request=mock_request,
            session=test_db_session,
            current_user=test_user,
        )
        
        assert result is not None
    
    async def test_view_file_not_found(self, test_db_session, test_user):
        """Test viewing non-existent file."""
        from fastapi import Request
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        
        with pytest.raises(HTTPException) as exc_info:
            await view_file(
                file_id=str(uuid.uuid4()),
                request=mock_request,
                session=test_db_session,
                current_user=test_user,
            )
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    
    async def test_view_file_wrong_user(self, test_db_session, test_user, test_file):
        """Test viewing file owned by another user."""
        # Create another user
        from backend.app.models.user import User
        
        other_user = User(
            id=uuid.uuid4(),
            email="other@example.com",
            status="active",
        )
        test_db_session.add(other_user)
        await test_db_session.commit()
        
        from fastapi import Request
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        
        with pytest.raises(HTTPException) as exc_info:
            await view_file(
                file_id=str(test_file.id),
                request=mock_request,
                session=test_db_session,
                current_user=other_user,
            )
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
class TestDeleteFile:
    async def test_delete_file_success(self, test_db_session, test_user, test_file, temp_storage_dir):
        """Test deleting a file."""
        # Create the actual file on disk
        from backend.app.services.file_storage import get_file_path
        file_path = get_file_path(test_file.storage_key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"test content")
        
        from fastapi import Response
        response = Response()
        
        result = await delete_file_endpoint(
            file_id=str(test_file.id),
            response=response,
            session=test_db_session,
            current_user=test_user,
        )
        
        assert result is None
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify file is soft-deleted
        await test_db_session.refresh(test_file)
        assert test_file.deleted_at is not None
    
    async def test_delete_file_not_found(self, test_db_session, test_user):
        """Test deleting non-existent file."""
        from fastapi import Response
        response = Response()
        
        with pytest.raises(HTTPException) as exc_info:
            await delete_file_endpoint(
                file_id=str(uuid.uuid4()),
                response=response,
                session=test_db_session,
                current_user=test_user,
            )
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


class TestWebViewLinkValidation:
    """Test webViewLink validation and generation."""
    
    def test_valid_web_view_link(self):
        """Test that valid Google Drive link is returned as-is."""
        link = "https://drive.google.com/file/d/abc123/view"
        result = _get_valid_web_view_link(link, "abc123")
        assert result == link
    
    def test_invalid_web_view_link_replaced(self):
        """Test that invalid link (e.g., aistudio.google.com) is replaced with correct one."""
        invalid_link = "https://aistudio.google.com/app/prompts/"
        drive_file_id = "abc123"
        result = _get_valid_web_view_link(invalid_link, drive_file_id)
        assert result == "https://drive.google.com/file/d/abc123/view"
        assert result != invalid_link
    
    def test_none_web_view_link_generated(self):
        """Test that None link is generated from drive_file_id."""
        drive_file_id = "abc123"
        result = _get_valid_web_view_link(None, drive_file_id)
        assert result == "https://drive.google.com/file/d/abc123/view"
    
    def test_no_link_no_id_returns_none(self):
        """Test that None is returned when both link and drive_file_id are None."""
        result = _get_valid_web_view_link(None, None)
        assert result is None
    
    def test_empty_string_link_generated(self):
        """Test that empty string link is treated as None and generated."""
        drive_file_id = "abc123"
        result = _get_valid_web_view_link("", drive_file_id)
        assert result == "https://drive.google.com/file/d/abc123/view"

