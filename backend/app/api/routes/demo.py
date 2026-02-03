from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.database import get_db
from app.models import (
    User, GeneratedFile,
    DemoGenerateRequest, DemoGenerateResponse
)
from app.services import JiraClient, GeminiService, SlidesService, GoogleAuthService
from app.services.mongo_storage import get_mongo_storage
from app.api.deps import get_current_user
from app.api.routes.jira import get_jira_client
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/demo", tags=["demo"])


def serialize_for_json(obj):
    """Recursively convert datetime objects to ISO strings for JSON serialization."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    return obj


def calculate_cache_expiry_hours(user: User) -> int:
    """
    Calculate cache expiry based on user's scheduler settings.

    Cache should be valid until next scheduled run + buffer.
    """
    if not user.scheduler_enabled:
        # No scheduler - use 7 days default
        return 168

    frequency = getattr(user, 'scheduler_frequency', 'weekly') or 'weekly'
    days_str = getattr(user, 'scheduler_days', 'thu') or 'thu'
    days = days_str.split(",") if days_str else ['thu']

    if frequency == "daily":
        # Runs every day → cache valid 36 hours (1.5 days buffer)
        return 36
    elif frequency == "weekly":
        # Runs once per week → cache valid 192 hours (8 days)
        return 192
    elif frequency == "custom":
        # Based on number of days selected
        num_days = len(days)
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


def serialize_for_json(obj):
    """Recursively convert datetime objects to ISO strings for JSON serialization."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    return obj


async def get_user_google_credentials(user: User):
    """Get Google credentials for a user, refreshing if needed."""
    if not user.google_access_token:
        raise HTTPException(
            status_code=400,
            detail="Google account not connected. Please reconnect via Settings."
        )

    google_auth = GoogleAuthService()
    credentials = google_auth.get_credentials(
        access_token=user.google_access_token,
        refresh_token=user.google_refresh_token,
        token_expiry=user.google_token_expiry
    )

    # Refresh if expired
    if google_auth.is_token_expired(user.google_token_expiry):
        credentials = await google_auth.refresh_credentials(credentials)

    return credentials


async def get_metrics_with_cache(
        user: User,
        project_key: str,
        jira_client: JiraClient,
        start_date: datetime = None,
        end_date: datetime = None,
        sprint_id: int = None
) -> dict:
    """
    Get metrics from cache if available, otherwise fetch from Jira.

    Cache expiry is calculated based on user's scheduler settings.
    """
    mongo_storage = get_mongo_storage()

    # Calculate cache expiry based on user's scheduler settings
    max_cache_age_hours = calculate_cache_expiry_hours(user)
    logger.info(f"Cache expiry for user {user.id}: {max_cache_age_hours} hours")

    # Try to get cached data first
    cached_data = await mongo_storage.get_cached_data(
        user_id=user.id,
        project_key=project_key,
        max_age_hours=max_cache_age_hours
    )

    if cached_data:
        logger.info(f"Using cached metrics for project {project_key}")
        return cached_data

    # No valid cache - fetch from Jira
    logger.info(f"Fetching fresh metrics from Jira for project {project_key}")

    if sprint_id:
        metrics = await jira_client.get_project_metrics_by_sprint(project_key, sprint_id)
    else:
        metrics = await jira_client.get_project_metrics(project_key, start_date, end_date)

    # Save to cache for future use
    try:
        await mongo_storage.save_cached_data(
            user_id=user.id,
            project_key=project_key,
            data=serialize_for_json(metrics),
            date_range_start=start_date,
            date_range_end=end_date,
            sprint_id=str(sprint_id) if sprint_id else None
        )
        logger.info(f"Cached metrics for project {project_key}")
    except Exception as e:
        logger.warning(f"Failed to cache metrics: {e}")

    return metrics


@router.post("/generate", response_model=DemoGenerateResponse)
async def generate_demo(
        request: DemoGenerateRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Generate a demo presentation from Jira data."""
    # Get Jira client
    jira_client = await get_jira_client(current_user)

    # Determine how to get metrics
    if request.sprint_id:
        logger.info(f"Generating demo using sprint_id = {request.sprint_id}")

        # Get sprint info for date range
        board_id = await jira_client.get_board_id(request.jira_project_key)
        sprints = await jira_client.get_sprints(board_id)
        sprint = next((s for s in sprints if s.id == request.sprint_id), None)

        if sprint and sprint.start_date:
            start_date = datetime.fromisoformat(str(sprint.start_date).replace('Z', '+00:00')) if isinstance(
                sprint.start_date, str) else sprint.start_date
        else:
            start_date = datetime.now() - timedelta(days=14)

        if sprint and sprint.end_date:
            end_date = datetime.fromisoformat(str(sprint.end_date).replace('Z', '+00:00')) if isinstance(
                sprint.end_date, str) else sprint.end_date
        else:
            end_date = datetime.now()

        # Get metrics (with cache)
        metrics = await get_metrics_with_cache(
            user=current_user,
            project_key=request.jira_project_key,
            jira_client=jira_client,
            start_date=start_date,
            end_date=end_date,
            sprint_id=request.sprint_id
        )

    elif request.date_range:
        logger.info(f"Generating demo using date_range = {request.date_range.start} to {request.date_range.end}")
        start_date = request.date_range.start
        end_date = request.date_range.end

        # Get metrics (with cache)
        metrics = await get_metrics_with_cache(
            user=current_user,
            project_key=request.jira_project_key,
            jira_client=jira_client,
            start_date=start_date,
            end_date=end_date
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="Either date_range or sprint_id is required"
        )

    logger.info(f"Got metrics - total_issues={metrics.get('total_issues', 0)}")

    # Generate content with Gemini
    gemini = GeminiService()
    content = await gemini.generate_demo_content(
        metrics,
        request.jira_project_key
    )

    # Override title if provided
    if request.title:
        content["title"] = request.title

    # Create Google Slides presentation
    logger.info("Creating Google Slides presentation...")
    try:
        credentials = await get_user_google_credentials(current_user)
        slides_service = SlidesService(credentials)
        slides_result = await slides_service.create_demo_presentation(content)
        google_slides_url = slides_result["url"]
        google_slides_id = slides_result["presentation_id"]
        logger.info(f"Created presentation: {google_slides_id}")
    except Exception as e:
        logger.error(f"Failed to create slides: {e}")
        google_slides_url = None
        google_slides_id = None

    # Save to database
    serialized_metrics = serialize_for_json(metrics)
    generated_file = GeneratedFile(
        user_id=current_user.id,
        file_type="demo",
        filename=f"demo_{request.jira_project_key}_{datetime.now().strftime('%Y%m%d')}.pptx",
        date_range_start=start_date,
        date_range_end=end_date,
        jira_project_key=request.jira_project_key,
        metrics=serialized_metrics,
        google_slides_id=google_slides_id
    )
    db.add(generated_file)
    db.commit()
    db.refresh(generated_file)

    if not google_slides_url:
        raise HTTPException(
            status_code=500,
            detail="Failed to create Google Slides presentation. Please check your Google connection."
        )

    return DemoGenerateResponse(
        id=generated_file.id,
        google_slides_url=google_slides_url,
        firebase_url=None,
        drive_url=None,
        metrics=metrics
    )


@router.get("/preview")
async def preview_demo(
        jira_project_key: str,
        start_date: datetime,
        end_date: datetime,
        current_user: User = Depends(get_current_user)
):
    """Preview demo content without generating slides (by date range)."""
    jira_client = await get_jira_client(current_user)

    # Get metrics (with cache)
    metrics = await get_metrics_with_cache(
        user=current_user,
        project_key=jira_project_key,
        jira_client=jira_client,
        start_date=start_date,
        end_date=end_date
    )

    return {
        "metrics": metrics,
        "content": None  # Don't generate AI content for preview, just metrics
    }


@router.get("/preview/sprint")
async def preview_demo_by_sprint(
        jira_project_key: str,
        sprint_id: int,
        current_user: User = Depends(get_current_user)
):
    """Preview demo content without generating slides (by sprint)."""
    jira_client = await get_jira_client(current_user)

    # Get metrics (with cache)
    metrics = await get_metrics_with_cache(
        user=current_user,
        project_key=jira_project_key,
        jira_client=jira_client,
        sprint_id=sprint_id
    )

    return {
        "metrics": metrics,
        "content": None
    }


@router.get("/history")
async def get_demo_history(
        current_user: User = Depends(get_current_user),
        limit: int = 10,
        db: Session = Depends(get_db)
):
    """Get history of generated demos."""
    files = db.query(GeneratedFile).filter(
        GeneratedFile.user_id == current_user.id,
        GeneratedFile.file_type == "demo"
    ).order_by(GeneratedFile.created_at.desc()).limit(limit).all()

    return files


@router.delete("/{demo_id}")
async def delete_demo(
        demo_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Delete a generated demo."""
    file = db.query(GeneratedFile).filter(
        GeneratedFile.id == demo_id,
        GeneratedFile.user_id == current_user.id
    ).first()

    if not file:
        raise HTTPException(status_code=404, detail="Demo not found")

    db.delete(file)
    db.commit()

    return {"message": "Demo deleted successfully"}