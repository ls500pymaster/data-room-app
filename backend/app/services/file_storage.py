from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Tuple

from backend.core.config import settings


def _ensure_storage_root() -> Path:
    root = Path(settings.STORAGE_PATH)
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_imported_file(
    user_id: uuid.UUID,
    file_id: uuid.UUID,
    extension: str | None,
    content: bytes,
) -> Tuple[str, str]:
    """
    Persists imported file content on disk and returns storage metadata.

    Args:
        user_id: Owner of the file.
        file_id: Internal file UUID.
        extension: File extension (with or without leading dot) or None.
        content: Raw file bytes.

    Returns:
        Tuple of (storage_key, sha256_checksum).
    """
    root = _ensure_storage_root()
    user_dir = root / "users" / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)

    ext = ""
    if extension:
        ext = extension if extension.startswith(".") else f".{extension.lstrip('.')}"

    file_name = f"{file_id}{ext}"
    file_path = user_dir / file_name
    file_path.write_bytes(content)

    checksum = hashlib.sha256(content).hexdigest()
    storage_key = file_path.relative_to(root).as_posix()
    return storage_key, checksum


def get_file_path(storage_key: str) -> Path:
    """
    Gets full file path by storage_key.
    
    Args:
        storage_key: Relative file path (e.g., "users/{user_id}/{file_id}.ext")
    
    Returns:
        Path object with full file path
    """
    root = _ensure_storage_root()
    return root / storage_key


def read_file_content(storage_key: str) -> bytes:
    """
    Reads file content from disk.
    
    Args:
        storage_key: Relative file path
    
    Returns:
        File content as bytes
    
    Raises:
        FileNotFoundError: If file not found
    """
    file_path = get_file_path(storage_key)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {storage_key}")
    return file_path.read_bytes()


def delete_file(storage_key: str) -> None:
    """
    Deletes file from disk.
    
    Args:
        storage_key: Relative file path
    
    Raises:
        FileNotFoundError: If file not found
        OSError: If file deletion failed
    """
    file_path = get_file_path(storage_key)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {storage_key}")
    file_path.unlink()

