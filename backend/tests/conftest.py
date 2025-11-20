from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import AsyncGenerator

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import event
from sqlalchemy.dialects.sqlite.base import SQLiteDialect
from sqlalchemy.dialects.postgresql import CITEXT, ENUM, JSONB, INET
from sqlalchemy.types import String, JSON

from backend.app.db import get_session
from backend.app.main import app
from backend.app.models.base import Base
from backend.app.models.user import User
from backend.app.models.file import File
from backend.app.security import create_session_token, hash_password


# Test database URL (in-memory SQLite for tests)
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# Map PostgreSQL-specific types to SQLite-compatible types for tests
@event.listens_for(Base.metadata, "before_create")
def receive_before_create(target, connection, **kw):
    """Convert PostgreSQL-specific types to SQLite-compatible types."""
    if isinstance(connection.dialect, SQLiteDialect):
        # Map PostgreSQL-specific types to SQLite-compatible types
        for table in target.tables.values():
            for column in table.columns:
                if isinstance(column.type, CITEXT):
                    column.type = String()
                elif isinstance(column.type, ENUM):
                    # Convert ENUM to String for SQLite
                    column.type = String()
                elif isinstance(column.type, JSONB):
                    # Convert JSONB to JSON for SQLite
                    column.type = JSON()
                elif isinstance(column.type, INET):
                    # Convert INET to String for SQLite
                    column.type = String()
                # UUID is handled by SQLAlchemy automatically in SQLite


@pytest.fixture(scope="function")
async def test_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    engine = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture(scope="function")
async def test_client(test_db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with overridden database session."""
    async def override_get_session():
        yield test_db_session
    
    app.dependency_overrides[get_session] = override_get_session
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest.fixture
def temp_storage_dir(monkeypatch) -> Path:
    """Create a temporary storage directory for file tests."""
    temp_dir = tempfile.mkdtemp()
    storage_path = Path(temp_dir)
    # Patch settings.STORAGE_PATH directly since it's cached at import time
    from backend.core.config import settings
    monkeypatch.setattr(settings, "STORAGE_PATH", str(storage_path))
    yield storage_path
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
async def test_user(test_db_session: AsyncSession) -> User:
    """Create a test user."""
    import uuid
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        password_hash=hash_password("testpassword123"),
        status="active",
        full_name="Test User",
    )
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)
    return user


@pytest.fixture
async def test_user_with_google(test_db_session: AsyncSession) -> User:
    """Create a test user with Google OAuth tokens."""
    import uuid
    from datetime import datetime, timedelta, timezone
    
    user = User(
        id=uuid.uuid4(),
        email="google@example.com",
        status="active",
        full_name="Google User",
        google_id="google123",
        google_access_token="test_access_token",
        google_refresh_token="test_refresh_token",
        google_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)
    return user


@pytest.fixture
async def auth_cookies(test_user: User) -> dict:
    """Create auth cookies for a test user."""
    session_token = create_session_token(str(test_user.id))
    return {"session": session_token}


@pytest.fixture
async def test_file(test_db_session: AsyncSession, test_user: User) -> File:
    """Create a test file."""
    import uuid
    file = File(
        id=uuid.uuid4(),
        uploader_id=test_user.id,
        storage_key="users/test/file.pdf",
        original_name="test.pdf",
        extension="pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        status="ready",
    )
    test_db_session.add(file)
    await test_db_session.commit()
    await test_db_session.refresh(file)
    return file

