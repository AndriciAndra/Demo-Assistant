from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional


# ============== User Schemas ==============

class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    name: Optional[str] = None
    jira_base_url: Optional[str] = None
    jira_email: Optional[str] = None
    jira_api_token: Optional[str] = None
    scheduler_enabled: Optional[bool] = None
    scheduler_day_of_week: Optional[str] = None
    scheduler_hour: Optional[int] = None
    scheduler_minute: Optional[int] = None
    sync_to_drive: Optional[bool] = None
    drive_folder_id: Optional[str] = None


class UserResponse(UserBase):
    id: int
    scheduler_enabled: bool
    scheduler_day_of_week: str
    scheduler_hour: int
    scheduler_minute: int
    sync_to_drive: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ============== Jira Schemas ==============

class JiraCredentials(BaseModel):
    base_url: str
    email: str
    api_token: str


class JiraProject(BaseModel):
    key: str
    name: str
    project_type: Optional[str] = None


class JiraSprint(BaseModel):
    id: int
    name: str
    state: str  # active, closed, future
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    goal: Optional[str] = None


class JiraIssue(BaseModel):
    key: str
    summary: str
    status: str
    issue_type: str
    assignee: Optional[str] = None
    assignee_email: Optional[str] = None  # Email for better matching
    story_points: Optional[float] = None
    priority: Optional[str] = None
    labels: list[str] = []
    created: datetime
    resolved: Optional[datetime] = None


# ============== Date Range Schema ==============

class DateRange(BaseModel):
    start: datetime
    end: datetime


# ============== Demo Schemas ==============

class DemoGenerateRequest(BaseModel):
    jira_project_key: str
    date_range: Optional[DateRange] = None
    sprint_id: Optional[int] = None
    template_id: Optional[int] = None
    title: Optional[str] = None


class DemoGenerateResponse(BaseModel):
    id: int
    google_slides_url: str
    firebase_url: Optional[str] = None
    drive_url: Optional[str] = None
    metrics: dict


# ============== Self Review Schemas ==============

class SelfReviewGenerateRequest(BaseModel):
    jira_project_key: str
    date_range: DateRange
    template: Optional[str] = None  # Custom template text
    template_id: Optional[int] = None  # Or use saved template


class SelfReviewRecommendRequest(BaseModel):
    jira_project_key: str
    date_range: DateRange


class SelfReviewRecommendResponse(BaseModel):
    recommended_template: str
    metrics_preview: dict


class SelfReviewGenerateResponse(BaseModel):
    id: int
    firebase_url: str
    drive_url: Optional[str] = None
    metrics: dict


# ============== Template Schemas ==============

class TemplateBase(BaseModel):
    name: str
    template_type: str  # 'demo' or 'self_review'
    content: str


class TemplateCreate(TemplateBase):
    pass


class TemplateResponse(TemplateBase):
    id: int
    user_id: Optional[int] = None
    is_default: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ============== Generated File Schemas ==============

class GeneratedFileResponse(BaseModel):
    id: int
    file_type: str
    filename: str
    firebase_url: Optional[str] = None
    drive_url: Optional[str] = None
    google_slides_id: Optional[str] = None
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None
    jira_project_key: Optional[str] = None
    metrics: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ============== Settings Schemas ==============

class SchedulerSettings(BaseModel):
    enabled: bool
    day_of_week: str
    hour: int
    minute: int


class StorageSettings(BaseModel):
    sync_to_drive: bool
    drive_folder_id: Optional[str] = None


class SettingsResponse(BaseModel):
    scheduler: SchedulerSettings
    storage: StorageSettings
    jira_connected: bool
    google_connected: bool