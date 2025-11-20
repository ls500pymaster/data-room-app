from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, AsyncMock
import pytest

from backend.app.services.google_drive import (
    create_credentials_from_tokens,
    refresh_access_token,
    get_authorization_url,
    list_drive_files,
    download_drive_file,
    get_file_metadata,
)


class TestCreateCredentialsFromTokens:
    def test_create_credentials_with_expiry(self):
        """Test creating credentials with expiry time."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        with patch("backend.app.services.google_drive.settings") as mock_settings:
            mock_settings.GOOGLE_CLIENT_ID = "test_client_id"
            mock_settings.GOOGLE_CLIENT_SECRET = "test_secret"
            mock_settings.GOOGLE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
            
            creds = create_credentials_from_tokens(
                access_token="test_token",
                refresh_token="test_refresh",
                expires_at=expires_at,
            )
            
            assert creds.token == "test_token"
            assert creds.refresh_token == "test_refresh"
            assert creds.expiry is not None
            assert creds.expiry.tzinfo == timezone.utc
    
    def test_create_credentials_without_expiry(self):
        """Test creating credentials without expiry time."""
        with patch("backend.app.services.google_drive.settings") as mock_settings:
            mock_settings.GOOGLE_CLIENT_ID = "test_client_id"
            mock_settings.GOOGLE_CLIENT_SECRET = "test_secret"
            mock_settings.GOOGLE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
            
            creds = create_credentials_from_tokens(
                access_token="test_token",
                refresh_token="test_refresh",
                expires_at=None,
            )
            
            assert creds.token == "test_token"
            assert creds.refresh_token == "test_refresh"


class TestRefreshAccessToken:
    def test_refresh_when_not_expired(self):
        """Test refresh when token is not expired."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
        
        with patch("backend.app.services.google_drive.settings") as mock_settings:
            mock_settings.GOOGLE_CLIENT_ID = "test_client_id"
            mock_settings.GOOGLE_CLIENT_SECRET = "test_secret"
            mock_settings.GOOGLE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
            
            creds = create_credentials_from_tokens(
                access_token="test_token",
                refresh_token="test_refresh",
                expires_at=expires_at,
            )
            
            refreshed = refresh_access_token(creds)
            # Should return same credentials without refreshing
            assert refreshed.token == creds.token
    
    def test_refresh_when_expired(self):
        """Test refresh when token is expired."""
        expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        
        with patch("backend.app.services.google_drive.settings") as mock_settings:
            mock_settings.GOOGLE_CLIENT_ID = "test_client_id"
            mock_settings.GOOGLE_CLIENT_SECRET = "test_secret"
            mock_settings.GOOGLE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
            
            creds = create_credentials_from_tokens(
                access_token="test_token",
                refresh_token="test_refresh",
                expires_at=expires_at,
            )
            
            # Mock the refresh method at the class level to intercept the call
            from google.oauth2.credentials import Credentials
            original_refresh = Credentials.refresh
            
            def mock_refresh(self, request):
                # Simulate what refresh() does - updates token and expiry in place
                self.token = "new_token"
                self.expiry = datetime.now(timezone.utc) + timedelta(hours=1)
            
            with patch.object(Credentials, "refresh", mock_refresh):
                refreshed = refresh_access_token(creds)
                # Verify the credentials were updated
                assert refreshed.expiry.tzinfo == timezone.utc
                assert refreshed.token == "new_token"
                assert refreshed.expiry > datetime.now(timezone.utc)


class TestGetAuthorizationUrl:
    def test_get_authorization_url(self):
        """Test getting authorization URL."""
        with patch("backend.app.services.google_drive.create_oauth_flow") as mock_flow:
            mock_flow_instance = Mock()
            mock_flow_instance.authorization_url.return_value = (
                "https://accounts.google.com/o/oauth2/auth?state=test",
                "test_state"
            )
            mock_flow.return_value = mock_flow_instance
            
            url = get_authorization_url(state="test_state")
            
            assert url is not None
            assert isinstance(url, str)
            mock_flow_instance.authorization_url.assert_called_once()


@pytest.mark.asyncio
class TestListDriveFiles:
    async def test_list_drive_files_success(self):
        """Test listing drive files successfully."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        with patch("backend.app.services.google_drive.create_credentials_from_tokens") as mock_create, \
             patch("backend.app.services.google_drive.refresh_access_token") as mock_refresh, \
             patch("backend.app.services.google_drive.get_drive_service") as mock_service:
            
            mock_creds = Mock()
            mock_create.return_value = mock_creds
            mock_refresh.return_value = mock_creds
            
            mock_service_instance = Mock()
            mock_files_list = Mock()
            mock_files_list.execute.return_value = {
                "files": [
                    {
                        "id": "file1",
                        "name": "test1.pdf",
                        "mimeType": "application/pdf",
                        "size": "1024",
                        "modifiedTime": "2024-01-01T00:00:00Z",
                        "webViewLink": "https://drive.google.com/file1",
                    }
                ],
                "nextPageToken": None,
            }
            mock_service_instance.files.return_value.list.return_value = mock_files_list
            mock_service.return_value = mock_service_instance
            
            result = await list_drive_files(
                access_token="test_token",
                refresh_token="test_refresh",
                expires_at=expires_at,
                page_size=10,
            )
            
            assert "files" in result
            assert len(result["files"]) == 1
            assert result["files"][0]["id"] == "file1"
    
    async def test_list_drive_files_with_pagination(self):
        """Test listing drive files with pagination."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        with patch("backend.app.services.google_drive.create_credentials_from_tokens") as mock_create, \
             patch("backend.app.services.google_drive.refresh_access_token") as mock_refresh, \
             patch("backend.app.services.google_drive.get_drive_service") as mock_service:
            
            mock_creds = Mock()
            mock_create.return_value = mock_creds
            mock_refresh.return_value = mock_creds
            
            mock_service_instance = Mock()
            mock_files_list = Mock()
            mock_files_list.execute.return_value = {
                "files": [],
                "nextPageToken": "next_page_token_123",
            }
            mock_service_instance.files.return_value.list.return_value = mock_files_list
            mock_service.return_value = mock_service_instance
            
            result = await list_drive_files(
                access_token="test_token",
                refresh_token="test_refresh",
                expires_at=expires_at,
                page_size=10,
                page_token="prev_token",
            )
            
            assert result["next_page_token"] == "next_page_token_123"


@pytest.mark.asyncio
class TestDownloadDriveFile:
    async def test_download_drive_file_success(self):
        """Test downloading a file successfully."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        with patch("backend.app.services.google_drive.create_credentials_from_tokens") as mock_create, \
             patch("backend.app.services.google_drive.refresh_access_token") as mock_refresh, \
             patch("backend.app.services.google_drive.get_drive_service") as mock_service:
            
            mock_creds = Mock()
            mock_create.return_value = mock_creds
            mock_refresh.return_value = mock_creds
            
            mock_service_instance = Mock()
            mock_get_media = Mock()
            mock_get_media.execute.return_value = b"file content"
            mock_service_instance.files.return_value.get_media.return_value = mock_get_media
            mock_service.return_value = mock_service_instance
            
            content = await download_drive_file(
                access_token="test_token",
                refresh_token="test_refresh",
                expires_at=expires_at,
                file_id="file123",
            )
            
            assert content == b"file content"
    
    async def test_download_drive_file_error(self):
        """Test downloading a file with error."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        with patch("backend.app.services.google_drive.create_credentials_from_tokens") as mock_create, \
             patch("backend.app.services.google_drive.refresh_access_token") as mock_refresh, \
             patch("backend.app.services.google_drive.get_drive_service") as mock_service:
            
            from googleapiclient.errors import HttpError
            
            mock_creds = Mock()
            mock_create.return_value = mock_creds
            mock_refresh.return_value = mock_creds
            
            mock_service_instance = Mock()
            mock_get_media = Mock()
            mock_resp = Mock()
            mock_resp.status = 404
            mock_error = HttpError(mock_resp, b"Not found")
            mock_get_media.execute.side_effect = mock_error
            mock_service_instance.files.return_value.get_media.return_value = mock_get_media
            mock_service.return_value = mock_service_instance
            
            with pytest.raises(Exception) as exc_info:
                await download_drive_file(
                    access_token="test_token",
                    refresh_token="test_refresh",
                    expires_at=expires_at,
                    file_id="file123",
                )
            
            assert "Error downloading file from Google Drive" in str(exc_info.value)


@pytest.mark.asyncio
class TestGetFileMetadata:
    async def test_get_file_metadata_success(self):
        """Test getting file metadata successfully."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        with patch("backend.app.services.google_drive.create_credentials_from_tokens") as mock_create, \
             patch("backend.app.services.google_drive.refresh_access_token") as mock_refresh, \
             patch("backend.app.services.google_drive.get_drive_service") as mock_service:
            
            mock_creds = Mock()
            mock_create.return_value = mock_creds
            mock_refresh.return_value = mock_creds
            
            mock_service_instance = Mock()
            mock_get = Mock()
            mock_get.execute.return_value = {
                "id": "file123",
                "name": "test.pdf",
                "mimeType": "application/pdf",
                "size": "1024",
                "modifiedTime": "2024-01-01T00:00:00Z",
            }
            mock_service_instance.files.return_value.get.return_value = mock_get
            mock_service.return_value = mock_service_instance
            
            metadata = await get_file_metadata(
                access_token="test_token",
                refresh_token="test_refresh",
                expires_at=expires_at,
                file_id="file123",
            )
            
            assert metadata["id"] == "file123"
            assert metadata["name"] == "test.pdf"

