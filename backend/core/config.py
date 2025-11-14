import os
from dotenv import load_dotenv


load_dotenv()


class Settings:
    PROJECT_NAME = "MVP Data Room"
    API_PREFIX = "/api"
    # Get DB_URL from environment
    # Render provides postgres:// or postgresql://, but we need postgresql+asyncpg:// for asyncpg
    _db_url = os.getenv("DB_URL", "postgresql+asyncpg://user:pass@db:5432/dataroom")
    
    # Convert to asyncpg format if needed
    if _db_url.startswith("postgresql://"):
        DB_URL = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif _db_url.startswith("postgres://"):
        DB_URL = _db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif not _db_url.startswith("postgresql+asyncpg://"):
        # If it's already in correct format or something else, use as-is
        DB_URL = _db_url
    else:
        DB_URL = _db_url
    
    # Log DB URL format for debugging (without password)
    if not DB_URL.startswith("postgresql+asyncpg://"):
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"DB_URL format may be incorrect: {DB_URL.split('@')[0]}@...")
    # CORS origins - allow all in development, specific origins in production
    _cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001")
    if _cors_origins and _cors_origins.strip():
        CORS_ORIGINS = [origin.strip() for origin in _cors_origins.split(",") if origin.strip()]
        # If empty list after processing, allow all
        if not CORS_ORIGINS:
            CORS_ORIGINS = ["*"]
    else:
        # If not set, allow all origins (development mode)
        CORS_ORIGINS = ["*"]
    
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    SESSION_TTL_MINUTES = int(os.getenv("SESSION_TTL_MINUTES", "60"))
    
    # Google OAuth 2.0 credentials
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/callback")
    GOOGLE_SCOPES = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    STORAGE_PATH = os.getenv("STORAGE_PATH", "/app/storage")
    
    # Determine if running in production (HTTPS)
    # Check if any CORS origin is HTTPS or if explicitly set
    IS_PRODUCTION = os.getenv("ENVIRONMENT", "").lower() == "production" or any(
        origin.startswith("https://") for origin in CORS_ORIGINS if origin != "*"
    )


settings = Settings()