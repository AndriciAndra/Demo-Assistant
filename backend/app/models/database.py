from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, JSON
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255))

    # Google OAuth tokens
    google_access_token = Column(Text, nullable=True)
    google_refresh_token = Column(Text, nullable=True)
    google_token_expiry = Column(DateTime, nullable=True)

    # Jira credentials (stored per user for flexibility)
    jira_base_url = Column(String(500), nullable=True)
    jira_email = Column(String(255), nullable=True)
    jira_api_token = Column(Text, nullable=True)

    # Scheduler preferences (flexible)
    scheduler_enabled = Column(Boolean, default=False)
    # Frequency: 'daily', 'weekly', 'custom'
    scheduler_frequency = Column(String(20), default="weekly")
    # For 'custom': comma-separated days e.g. "mon,wed,fri"
    # For 'weekly': single day e.g. "thu"
    # For 'daily': ignored (runs every day)
    scheduler_days = Column(String(50), default="thu")
    scheduler_hour = Column(Integer, default=18)
    scheduler_minute = Column(Integer, default=0)

    # Storage preferences
    sync_to_drive = Column(Boolean, default=False)
    drive_folder_id = Column(String(255), nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class GeneratedFile(Base):
    __tablename__ = "generated_files"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)

    # File type: 'demo' or 'self_review'
    file_type = Column(String(50), nullable=False)

    # File info
    filename = Column(String(500), nullable=False)
    mongo_file_id = Column(String(100), nullable=True)  # MongoDB GridFS ObjectId
    drive_url = Column(Text, nullable=True)
    google_slides_id = Column(String(255), nullable=True)

    # Metadata
    date_range_start = Column(DateTime, nullable=True)
    date_range_end = Column(DateTime, nullable=True)
    jira_project_key = Column(String(50), nullable=True)

    # Metrics snapshot (stored as JSON)
    metrics = Column(JSON, nullable=True)

    created_at = Column(DateTime, server_default=func.now())


class Template(Base):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=True)  # null = system template

    name = Column(String(255), nullable=False)
    template_type = Column(String(50), nullable=False)  # 'demo' or 'self_review'
    content = Column(Text, nullable=False)
    is_default = Column(Boolean, default=False)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

# NOTE: ScrapedData table removed - cache is now stored in MongoDB Atlas