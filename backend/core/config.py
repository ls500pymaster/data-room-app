import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME = "MVP Data Room"
    API_PREFIX = "/api"

    # Database
    DB_URL = os.getenv("DB_URL", "postgresql+asyncpg://user:pass@db:5432/dataroom").replace(
        "postgresql://", "postgresql+asyncpg://", 1
    )

    # CORS
    _cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001")
    if _cors_origins and _cors_origins.strip():
        CORS_ORIGINS = [origin.strip() for origin in _cors_origins.split(",") if origin.strip()]
        if not CORS_ORIGINS:
            CORS_ORIGINS = ["*"]
    else:
        CORS_ORIGINS = ["*"]

    # Security
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    SESSION_TTL_MINUTES = int(os.getenv("SESSION_TTL_MINUTES", "60"))

    # Google OAuth 2.0
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/callback")
    GOOGLE_AUTH_URI = os.getenv("GOOGLE_AUTH_URI", "https://accounts.google.com/o/oauth2/auth")
    GOOGLE_TOKEN_URI = os.getenv("GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token")
    GOOGLE_SCOPES = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/drive.readonly",
    ]

    # Storage
    STORAGE_PATH = os.getenv("STORAGE_PATH", "/app/storage")

    # Environment
    IS_PRODUCTION = os.getenv("ENVIRONMENT", "").lower() == "production" or any(
        origin.startswith("https://") for origin in CORS_ORIGINS if origin != "*"
    )


settings = Settings()