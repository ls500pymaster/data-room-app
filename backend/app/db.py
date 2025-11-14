from __future__ import annotations

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.engine import URL

from backend.core.config import settings

logger = logging.getLogger(__name__)

# Log DB URL without password for debugging
_db_url_for_log = settings.DB_URL
if "@" in _db_url_for_log:
    # Mask password in log
    parts = _db_url_for_log.split("@")
    if len(parts) == 2:
        user_pass = parts[0].split("//")[-1]
        if ":" in user_pass:
            user, _ = user_pass.split(":", 1)
            _db_url_for_log = _db_url_for_log.replace(f":{user_pass.split(':')[1]}", ":****", 1)
logger.info(f"Connecting to database: {_db_url_for_log}")

engine = create_async_engine(
    settings.DB_URL,
    future=True,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,  # Recycle connections after 1 hour
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


