from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # Application
    app_name: str = "Demo Assistant"
    debug: bool = False
    secret_key: str = "change-me-in-production"
    frontend_url: str = "http://localhost:5173"

    # Database - SQLite (for Railway Volume use: sqlite:////data/demo_assistant.db)
    database_url: str = "sqlite:///./app.db"

    # MongoDB Atlas - for cache and file storage
    mongodb_url: Optional[str] = None

    # Jira OAuth 2.0
    jira_client_id: str = ""
    jira_client_secret: str = ""
    jira_redirect_uri: str = "http://localhost:8000/auth/jira/callback"

    # Google Gemini
    gemini_api_key: str = ""

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"

    # Google Drive (optional - for PDF sync)
    google_drive_folder_id: Optional[str] = None

    # Scheduler defaults
    scheduler_enabled: bool = True
    scheduler_day_of_week: str = "thu"
    scheduler_hour: int = 18
    scheduler_minute: int = 0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Allow extra fields for flexibility
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()