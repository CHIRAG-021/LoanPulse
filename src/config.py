"""Configuration module for LoanPulse application."""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env if present
load_dotenv(BASE_DIR / ".env")


def normalize_database_url(raw_url: str | None = None) -> str:
    """Normalize database URL for SQLite relative paths and PostgreSQL drivers."""
    if not raw_url:
        raw_url = os.getenv("DATABASE_URL", "sqlite:///loanpulse.db")
    if raw_url.startswith("postgres://"):
        raw_url = raw_url.replace("postgres://", "postgresql://", 1)
    if raw_url.startswith("sqlite:///") and not raw_url.startswith("sqlite:////") and not raw_url.startswith("sqlite:///:memory:"):
        db_rel = raw_url.replace("sqlite:///", "")
        if not os.path.isabs(db_rel):
            return f"sqlite:///{BASE_DIR / db_rel}"
    return raw_url


class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-for-local-development")
    SQLALCHEMY_DATABASE_URI = normalize_database_url()

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TESTING = False
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "uploads" / "documents"))
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB maximum request size

    # Session cookie security settings (Phase 9 & 10)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "False").lower() in ("true", "1")
    BEHIND_PROXY = os.getenv("BEHIND_PROXY", "False").lower() in ("true", "1")
    PERMANENT_SESSION_LIFETIME = int(os.getenv("SESSION_LIFETIME_SECONDS", "86400"))


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class TestingConfig(Config):
    """Testing configuration with in-memory database."""
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    UPLOAD_FOLDER = str(BASE_DIR / "uploads" / "test_documents")


class ProductionConfig(Config):
    """Production configuration (Phase 9 & 10)."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "True").lower() in ("true", "1")
    BEHIND_PROXY = os.getenv("BEHIND_PROXY", "True").lower() in ("true", "1")
    PERMANENT_SESSION_LIFETIME = int(os.getenv("SESSION_LIFETIME_SECONDS", "86400"))


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
