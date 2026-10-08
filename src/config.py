"""Configuration module for LoanPulse application."""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env if present
load_dotenv(BASE_DIR / ".env")


class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-for-local-development")
    
    # Resolve SQLite database URL relative to project root if relative
    raw_db_url = os.getenv("DATABASE_URL", "sqlite:///loanpulse.db")
    if raw_db_url.startswith("sqlite:///") and not raw_db_url.startswith("sqlite:////") and not raw_db_url.startswith("sqlite:///:memory:"):
        db_rel = raw_db_url.replace("sqlite:///", "")
        if not os.path.isabs(db_rel):
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / db_rel}"
        else:
            SQLALCHEMY_DATABASE_URI = raw_db_url
    else:
        SQLALCHEMY_DATABASE_URI = raw_db_url

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TESTING = False


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class TestingConfig(Config):
    """Testing configuration with in-memory database."""
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
