from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Application
    app_name: str = "Demo Generator"
    debug: bool = True
    secret_key: str = "change-me-in-production"

    # Database
    database_url: str = "sqlite:///./app.db"

    # MongoDB (for PDF storage)
    mongodb_url: str = ""

    # Jira
    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""

    # Google Gemini
    gemini_api_key: str = ""

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"

    # Firebase
    firebase_credentials_path: str = "./firebase-credentials.json"
    firebase_storage_bucket: str = ""

    # Scheduler defaults
    scheduler_day_of_week: str = "thu"
    scheduler_hour: int = 18
    scheduler_minute: int = 0


@lru_cache()
def get_settings() -> Settings:
    return Settings()