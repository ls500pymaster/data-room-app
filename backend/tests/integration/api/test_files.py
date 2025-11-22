from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, Mock
import pytest

from backend.app.models.file import File
from backend.app.services.file_storage import save_imported_file, get_file_path


@pytest.mark.asyncio
class TestFilesIntegration:
    async def test_list_imported_files_empty(self, test_client, test_user, auth_cookies):
        """Test listing files when user has no files."""
        test_client.cookies.update(auth_cookies)
        response = await test_client.get(
            "/api/files",
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data == []
    
    async def test_list_imported_files_with_files(self, test_client, test_db_session, test_user, test_file, auth_cookies):
        """Test listing files when user has files."""
        test_client.cookies.update(auth_cookies)
        response = await test_client.get(
            "/api/files",
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(test_file.id)
        assert data[0]["original_name"] == test_file.original_name
    
    async def test_list_imported_files_unauthenticated(self, test_client):
        """Test listing files without authentication."""
        response = await test_client.get("/api/files")
        
        assert response.status_code == 401
    
    async def test_list_drive_files_success(self, test_client, test_db_session, test_user_with_google):
        """Test listing Google Drive files."""
        from backend.app.security import create_session_token
        auth_cookies = {"session": create_session_token(str(test_user_with_google.id))}
        
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
            
            test_client.cookies.update(auth_cookies)
            response = await test_client.get(
                "/api/files/drive",
                params={"page_size": 20},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["files"]) == 1
            assert data["files"][0]["id"] == "drive_file_1"
    
    async def test_list_drive_files_no_token(self, test_client, test_user, auth_cookies):
        """Test listing drive files without Google token."""
        test_client.cookies.update(auth_cookies)
        response = await test_client.get(
            "/api/files/drive",
        )
        
        assert response.status_code == 403
        assert "Google Drive is not connected" in response.json()["detail"]
    
    async def test_import_files_success(self, test_client, test_db_session, test_user_with_google, temp_storage_dir):
        """Test importing files from Google Drive."""
        from backend.app.security import create_session_token
        auth_cookies = {"session": create_session_token(str(test_user_with_google.id))}
        
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
            
            test_client.cookies.update(auth_cookies)
            response = await test_client.post(
                "/api/files/import",
                json={"file_ids": ["drive_file_1"]},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["imported"]) == 1
            assert len(data["skipped"]) == 0
            assert len(data["failed"]) == 0
    
    async def test_import_files_already_imported(self, test_client, test_db_session, test_user_with_google, test_file):
        """Test importing file that's already imported."""
        from backend.app.security import create_session_token
        auth_cookies = {"session": create_session_token(str(test_user_with_google.id))}
        
        # Set drive_file_id and uploader_id
        test_file.drive_file_id = "drive_file_1"
        test_file.uploader_id = test_user_with_google.id
        await test_db_session.commit()
        
        test_client.cookies.update(auth_cookies)
        response = await test_client.post(
            "/api/files/import",
            json={"file_ids": ["drive_file_1"]},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["imported"]) == 0
        assert len(data["skipped"]) == 1
        assert data["skipped"][0]["reason"] == "already_imported"
    
    async def test_import_files_unsupported_type(self, test_client, test_db_session, test_user_with_google):
        """Test importing unsupported file type."""
        from backend.app.security import create_session_token
        auth_cookies = {"session": create_session_token(str(test_user_with_google.id))}
        
        with patch("backend.api.files._refresh_and_save_user_tokens"), \
             patch("backend.api.files.get_file_metadata") as mock_metadata:
            
            mock_metadata.return_value = {
                "id": "drive_file_1",
                "name": "test.gdoc",
                "mimeType": "application/vnd.google-apps.document",
            }
            
            test_client.cookies.update(auth_cookies)
            response = await test_client.post(
                "/api/files/import",
                json={"file_ids": ["drive_file_1"]},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["imported"]) == 0
            assert len(data["skipped"]) == 1
            assert data["skipped"][0]["reason"] == "unsupported_type"
    
    async def test_view_file_success(self, test_client, test_db_session, test_user, test_file, temp_storage_dir, auth_cookies):
        """Test viewing a file."""
        # Create the actual file on disk
        file_path = get_file_path(test_file.storage_key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"test file content")
        
        test_client.cookies.update(auth_cookies)
        response = await test_client.get(
            f"/api/files/{test_file.id}/view",
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
    
    async def test_view_file_not_found(self, test_client, test_user, auth_cookies):
        """Test viewing non-existent file."""
        test_client.cookies.update(auth_cookies)
        response = await test_client.get(
            f"/api/files/{uuid.uuid4()}/view",
        )
        
        assert response.status_code == 404
    
    async def test_view_file_wrong_user(self, test_client, test_db_session, test_user, test_file):
        """Test viewing file owned by another user."""
        # Create another user
        from backend.app.models.user import User
        from backend.app.security import create_session_token
        
        other_user = User(
            id=uuid.uuid4(),
            email="other@example.com",
            status="active",
        )
        test_db_session.add(other_user)
        await test_db_session.commit()
        
        other_auth_cookies = {"session": create_session_token(str(other_user.id))}
        
        test_client.cookies.clear()
        test_client.cookies.update(other_auth_cookies)
        response = await test_client.get(
            f"/api/files/{test_file.id}/view",
        )
        
        assert response.status_code == 404
    
    async def test_view_file_range_request(self, test_client, test_db_session, test_user, test_file, temp_storage_dir, auth_cookies):
        """Test viewing file with range request."""
        # Create a larger file
        file_path = get_file_path(test_file.storage_key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_content = b"x" * 10000
        file_path.write_bytes(file_content)
        
        # Update file size in DB
        test_file.size_bytes = len(file_content)
        await test_db_session.commit()
        
        test_client.cookies.update(auth_cookies)
        response = await test_client.get(
            f"/api/files/{test_file.id}/view",
            headers={"Range": "bytes=0-1023"},
        )
        
        assert response.status_code == 206  # Partial Content
        assert "Content-Range" in response.headers
    
    async def test_delete_file_success(self, test_client, test_db_session, test_user, test_file, temp_storage_dir, auth_cookies):
        """Test deleting a file."""
        # Create the actual file on disk
        file_path = get_file_path(test_file.storage_key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"test content")
        
        test_client.cookies.update(auth_cookies)
        response = await test_client.delete(
            f"/api/files/{test_file.id}",
        )
        
        assert response.status_code == 204
        
        # Verify file is soft-deleted
        await test_db_session.refresh(test_file)
        assert test_file.deleted_at is not None
    
    async def test_delete_file_not_found(self, test_client, test_user, auth_cookies):
        """Test deleting non-existent file."""
        test_client.cookies.update(auth_cookies)
        response = await test_client.delete(
            f"/api/files/{uuid.uuid4()}",
        )
        
        assert response.status_code == 404
    
    async def test_delete_file_wrong_user(self, test_client, test_db_session, test_user, test_file):
        """Test deleting file owned by another user."""
        # Create another user
        from backend.app.models.user import User
        from backend.app.security import create_session_token
        
        other_user = User(
            id=uuid.uuid4(),
            email="other@example.com",
            status="active",
        )
        test_db_session.add(other_user)
        await test_db_session.commit()
        
        other_auth_cookies = {"session": create_session_token(str(other_user.id))}
        
        test_client.cookies.clear()
        test_client.cookies.update(other_auth_cookies)
        response = await test_client.delete(
            f"/api/files/{test_file.id}",
        )
        
        assert response.status_code == 404
    
    async def test_import_files_multiple(self, test_client, test_db_session, test_user_with_google, temp_storage_dir):
        """Test importing multiple files."""
        from backend.app.security import create_session_token
        auth_cookies = {"session": create_session_token(str(test_user_with_google.id))}
        
        with patch("backend.api.files._refresh_and_save_user_tokens"), \
             patch("backend.api.files.get_file_metadata") as mock_metadata, \
             patch("backend.api.files.download_drive_file") as mock_download:
            
            def metadata_side_effect(*args, **kwargs):
                file_id = kwargs.get("file_id", args[3] if len(args) > 3 else "drive_file_1")
                return {
                    "id": file_id,
                    "name": f"{file_id}.pdf",
                    "mimeType": "application/pdf",
                    "size": "1024",
                }
            
            mock_metadata.side_effect = metadata_side_effect
            mock_download.return_value = b"file content"
            
            test_client.cookies.update(auth_cookies)
            response = await test_client.post(
                "/api/files/import",
                json={"file_ids": ["drive_file_1", "drive_file_2", "drive_file_3"]},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["imported"]) == 3
    
    async def test_import_files_partial_failure(self, test_client, test_db_session, test_user_with_google, temp_storage_dir):
        """Test importing files with some failures."""
        from backend.app.security import create_session_token
        auth_cookies = {"session": create_session_token(str(test_user_with_google.id))}
        
        with patch("backend.api.files._refresh_and_save_user_tokens"), \
             patch("backend.api.files.get_file_metadata") as mock_metadata, \
             patch("backend.api.files.download_drive_file") as mock_download:
            
            def metadata_side_effect(*args, **kwargs):
                file_id = kwargs.get("file_id", args[3] if len(args) > 3 else "drive_file_1")
                return {
                    "id": file_id,
                    "name": f"{file_id}.pdf",
                    "mimeType": "application/pdf",
                }
            
            def download_side_effect(*args, **kwargs):
                file_id = kwargs.get("file_id", args[3] if len(args) > 3 else "drive_file_1")
                if file_id == "drive_file_2":
                    raise Exception("Download failed")
                return b"file content"
            
            mock_metadata.side_effect = metadata_side_effect
            mock_download.side_effect = download_side_effect
            
            test_client.cookies.update(auth_cookies)
            response = await test_client.post(
                "/api/files/import",
                json={"file_ids": ["drive_file_1", "drive_file_2", "drive_file_3"]},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["imported"]) == 2
            assert len(data["failed"]) == 1
            assert data["failed"][0]["file_id"] == "drive_file_2"

