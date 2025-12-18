from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import (
    User, UserUpdate,
    SchedulerSettings, StorageSettings, SettingsResponse
)
from app.services import scheduler_service
from app.api.deps import get_current_user

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings(
        current_user: User = Depends(get_current_user)
):
    """Get user settings."""
    return SettingsResponse(
        scheduler=SchedulerSettings(
            enabled=current_user.scheduler_enabled,
            day_of_week=current_user.scheduler_day_of_week,
            hour=current_user.scheduler_hour,
            minute=current_user.scheduler_minute
        ),
        storage=StorageSettings(
            sync_to_drive=current_user.sync_to_drive,
            drive_folder_id=current_user.drive_folder_id
        ),
        jira_connected=bool(current_user.jira_api_token),
        google_connected=bool(current_user.google_access_token)
    )


@router.put("/scheduler")
async def update_scheduler_settings(
        settings: SchedulerSettings,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Update scheduler settings."""
    current_user.scheduler_enabled = settings.enabled
    current_user.scheduler_day_of_week = settings.day_of_week
    current_user.scheduler_hour = settings.hour
    current_user.scheduler_minute = settings.minute

    db.commit()

    # Update scheduler jobs
    if settings.enabled:
        # TODO: Add actual job functions
        scheduler_service.add_user_job(
            user_id=current_user.id,
            job_type="scrape",
            func=lambda **kwargs: None,  # Placeholder
            day_of_week=settings.day_of_week,
            hour=settings.hour,
            minute=settings.minute
        )
    else:
        scheduler_service.remove_user_jobs(current_user.id)

    return {"message": "Scheduler settings updated"}


@router.put("/storage")
async def update_storage_settings(
        settings: StorageSettings,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Update storage settings."""
    current_user.sync_to_drive = settings.sync_to_drive
    current_user.drive_folder_id = settings.drive_folder_id

    db.commit()

    return {"message": "Storage settings updated"}


@router.put("/profile")
async def update_profile(
        update: UserUpdate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Update user profile."""
    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)

    db.commit()

    return {"message": "Profile updated"}


@router.get("/scheduled-jobs")
async def get_scheduled_jobs(
        current_user: User = Depends(get_current_user)
):
    """Get user's scheduled jobs."""
    jobs = scheduler_service.get_user_jobs(current_user.id)
    return {"jobs": jobs}


@router.delete("/jira")
async def disconnect_jira(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Disconnect Jira account."""
    current_user.jira_base_url = None
    current_user.jira_email = None
    current_user.jira_api_token = None

    db.commit()

    return {"message": "Jira disconnected"}