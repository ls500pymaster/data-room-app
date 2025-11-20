from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
import pytest

from backend.app.services.file_storage import (
    save_imported_file,
    get_file_path,
    read_file_content,
    delete_file,
)


def test_save_imported_file(temp_storage_dir):
    """Test saving an imported file."""
    user_id = uuid.uuid4()
    file_id = uuid.uuid4()
    extension = "pdf"
    content = b"test file content"
    
    storage_key, checksum = save_imported_file(
        user_id=user_id,
        file_id=file_id,
        extension=extension,
        content=content,
    )
    
    assert storage_key is not None
    assert isinstance(storage_key, str)
    assert checksum is not None
    assert isinstance(checksum, str)
    assert len(checksum) == 64  # SHA256 hex digest length
    
    # Verify checksum
    expected_checksum = hashlib.sha256(content).hexdigest()
    assert checksum == expected_checksum
    
    # Verify file exists
    file_path = get_file_path(storage_key)
    assert file_path.exists()
    assert file_path.read_bytes() == content


def test_save_imported_file_with_dot_extension(temp_storage_dir):
    """Test saving file with extension that already has a dot."""
    user_id = uuid.uuid4()
    file_id = uuid.uuid4()
    extension = ".pdf"
    content = b"test content"
    
    storage_key, checksum = save_imported_file(
        user_id=user_id,
        file_id=file_id,
        extension=extension,
        content=content,
    )
    
    file_path = get_file_path(storage_key)
    assert file_path.suffix == ".pdf"


def test_save_imported_file_no_extension(temp_storage_dir):
    """Test saving file without extension."""
    user_id = uuid.uuid4()
    file_id = uuid.uuid4()
    content = b"test content"
    
    storage_key, checksum = save_imported_file(
        user_id=user_id,
        file_id=file_id,
        extension=None,
        content=content,
    )
    
    file_path = get_file_path(storage_key)
    assert file_path.suffix == ""
    assert file_path.exists()


def test_get_file_path(temp_storage_dir):
    """Test getting file path from storage key."""
    user_id = uuid.uuid4()
    file_id = uuid.uuid4()
    content = b"test content"
    
    storage_key, _ = save_imported_file(
        user_id=user_id,
        file_id=file_id,
        extension="txt",
        content=content,
    )
    
    file_path = get_file_path(storage_key)
    assert file_path.exists()
    assert file_path.is_absolute()
    assert storage_key in str(file_path)


def test_read_file_content(temp_storage_dir):
    """Test reading file content."""
    user_id = uuid.uuid4()
    file_id = uuid.uuid4()
    content = b"test file content for reading"
    
    storage_key, _ = save_imported_file(
        user_id=user_id,
        file_id=file_id,
        extension="txt",
        content=content,
    )
    
    read_content = read_file_content(storage_key)
    assert read_content == content


def test_read_file_content_not_found(temp_storage_dir):
    """Test reading non-existent file."""
    storage_key = "users/nonexistent/file.txt"
    
    with pytest.raises(FileNotFoundError):
        read_file_content(storage_key)


def test_delete_file(temp_storage_dir):
    """Test deleting a file."""
    user_id = uuid.uuid4()
    file_id = uuid.uuid4()
    content = b"test content to delete"
    
    storage_key, _ = save_imported_file(
        user_id=user_id,
        file_id=file_id,
        extension="txt",
        content=content,
    )
    
    file_path = get_file_path(storage_key)
    assert file_path.exists()
    
    delete_file(storage_key)
    assert not file_path.exists()


def test_delete_file_not_found(temp_storage_dir):
    """Test deleting non-existent file."""
    storage_key = "users/nonexistent/file.txt"
    
    with pytest.raises(FileNotFoundError):
        delete_file(storage_key)


def test_storage_key_format(temp_storage_dir):
    """Test that storage key has correct format."""
    user_id = uuid.uuid4()
    file_id = uuid.uuid4()
    content = b"test"
    
    storage_key, _ = save_imported_file(
        user_id=user_id,
        file_id=file_id,
        extension="pdf",
        content=content,
    )
    
    # Storage key should be relative path
    assert not Path(storage_key).is_absolute()
    assert storage_key.startswith("users/")
    assert str(user_id) in storage_key
    assert str(file_id) in storage_key
    assert storage_key.endswith(".pdf")

