from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import (
    User, UserUpdate,
    SchedulerSettings, StorageSettings, SettingsResponse
)
from app.services import scheduler_service
from app.services.mongo_storage import get_mongo_storage
from app.api.deps import get_current_user

router = APIRouter(prefix="/settings", tags=["settings"])


def calculate_cache_expiry_hours(frequency: str, days: list[str]) -> int:
    """
    Calculate cache expiry based on scheduler frequency.

    Cache should be valid until next scheduled run + buffer.
    """
    if frequency == "daily":
        # Runs every day → cache valid 36 hours (1.5 days buffer)
        return 36
    elif frequency == "weekly":
        # Runs once per week → cache valid 192 hours (8 days)
        return 192
    elif frequency == "custom":
        # Based on number of days selected
        num_days = len(days) if days else 1
        if num_days >= 5:  # Almost daily
            return 36
        elif num_days >= 3:  # 3-4 times per week
            return 72  # 3 days
        elif num_days >= 2:  # Twice per week
            return 96  # 4 days
        else:  # Once per week
            return 192  # 8 days
    else:
        # Default fallback
        return 168  # 7 days


@router.get("", response_model=SettingsResponse)
async def get_settings(
        current_user: User = Depends(get_current_user)
):
    """Get user settings."""
    # Parse days from comma-separated string to list
    days_list = current_user.scheduler_days.split(",") if current_user.scheduler_days else ["thu"]

    return SettingsResponse(
        scheduler=SchedulerSettings(
            enabled=current_user.scheduler_enabled,
            frequency=current_user.scheduler_frequency or "weekly",
            days=days_list,
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
    # Convert days list to comma-separated string
    days_str = ",".join(settings.days) if settings.days else "thu"

    current_user.scheduler_enabled = settings.enabled
    current_user.scheduler_frequency = settings.frequency
    current_user.scheduler_days = days_str
    current_user.scheduler_hour = settings.hour
    current_user.scheduler_minute = settings.minute

    db.commit()

    # Update scheduler jobs
    if settings.enabled:
        # Remove old jobs first
        scheduler_service.remove_user_jobs(current_user.id)

        # Determine which days to schedule
        if settings.frequency == "daily":
            # Schedule for all days
            schedule_days = "mon,tue,wed,thu,fri,sat,sun"
        elif settings.frequency == "weekly":
            # Use first day from the list
            schedule_days = settings.days[0] if settings.days else "thu"
        else:  # custom
            schedule_days = days_str

        # Add job(s) for each day
        scheduler_service.add_user_job(
            user_id=current_user.id,
            job_type="scrape",
            day_of_week=schedule_days,
            hour=settings.hour,
            minute=settings.minute
        )
    else:
        scheduler_service.remove_user_jobs(current_user.id)

    # Calculate and return cache expiry info
    cache_hours = calculate_cache_expiry_hours(settings.frequency, settings.days)

    return {
        "message": "Scheduler settings updated",
        "cache_expiry_hours": cache_hours,
        "next_runs": scheduler_service.get_user_jobs(current_user.id)
    }


@router.post("/scheduler/run-now")
async def run_scheduler_now(
        current_user: User = Depends(get_current_user)
):
    """Manually trigger the Jira scraper to run immediately."""
    if not current_user.jira_api_token:
        raise HTTPException(
            status_code=400,
            detail="Jira not configured. Please connect Jira first."
        )

    # Run the scraper directly (async)
    from app.services.scraper import scrape_jira_data_for_user

    try:
        await scrape_jira_data_for_user(current_user.id)
        return {"message": "Scraper completed successfully. Data has been cached in MongoDB."}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to run scraper: {str(e)}"
        )


@router.get("/cache")
async def get_cached_data(
        current_user: User = Depends(get_current_user)
):
    """Get all cached Jira data for the current user from MongoDB."""
    mongo_storage = get_mongo_storage()
    cached = await mongo_storage.get_all_cached_data(current_user.id)
    return cached


@router.delete("/cache")
async def clear_cached_data(
        current_user: User = Depends(get_current_user)
):
    """Clear all cached Jira data for the current user from MongoDB."""
    mongo_storage = get_mongo_storage()
    await mongo_storage.delete_cached_data(current_user.id)
    return {"message": "Cache cleared successfully"}


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

    # Remove scheduled jobs
    scheduler_service.remove_user_jobs(current_user.id)

    # Clear MongoDB cache
    mongo_storage = get_mongo_storage()
    await mongo_storage.delete_cached_data(current_user.id)

    db.commit()

    return {"message": "Jira disconnected"}