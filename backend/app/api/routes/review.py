from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app.models import (
    User, GeneratedFile,
    SelfReviewGenerateRequest, SelfReviewGenerateResponse,
    SelfReviewRecommendRequest, SelfReviewRecommendResponse
)
from app.services import JiraClient, GeminiService, PDFService
from app.services.mongo_storage import get_mongo_storage
from app.api.deps import get_current_user
from app.api.routes.jira import get_jira_client
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/self-review", tags=["self-review"])


def serialize_for_json(obj):
    """Recursively convert datetime objects to ISO strings for JSON serialization."""
    if isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    else:
        return obj


def calculate_cache_expiry_hours(user: User) -> int:
    """
    Calculate cache expiry based on user's scheduler settings.
    """
    if not user.scheduler_enabled:
        return 168  # 7 days default

    frequency = getattr(user, 'scheduler_frequency', 'weekly') or 'weekly'
    days_str = getattr(user, 'scheduler_days', 'thu') or 'thu'
    days = days_str.split(",") if days_str else ['thu']

    if frequency == "daily":
        return 36
    elif frequency == "weekly":
        return 192
    elif frequency == "custom":
        num_days = len(days)
        if num_days >= 5:
            return 36
        elif num_days >= 3:
            return 72
        elif num_days >= 2:
            return 96
        else:
            return 192
    else:
        return 168


async def get_metrics_with_cache(
        user: User,
        project_key: str,
        jira_client: JiraClient,
        start_date: datetime,
        end_date: datetime
) -> dict:
    """
    Get metrics from cache if available, otherwise fetch from Jira.
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

    metrics = await jira_client.get_project_metrics(project_key, start_date, end_date)

    # Save to cache for future use
    try:
        await mongo_storage.save_cached_data(
            user_id=user.id,
            project_key=project_key,
            data=serialize_for_json(metrics),
            date_range_start=start_date,
            date_range_end=end_date
        )
        logger.info(f"Cached metrics for project {project_key}")
    except Exception as e:
        logger.warning(f"Failed to cache metrics: {e}")

    return metrics


@router.post("/recommend", response_model=SelfReviewRecommendResponse)
async def recommend_template(
        request: SelfReviewRecommendRequest,
        current_user: User = Depends(get_current_user)
):
    """Get AI-recommended template based on work data."""
    jira_client = await get_jira_client(current_user)

    # Get metrics (with cache)
    metrics = await get_metrics_with_cache(
        user=current_user,
        project_key=request.jira_project_key,
        jira_client=jira_client,
        start_date=request.date_range.start,
        end_date=request.date_range.end
    )

    # Generate template recommendation
    gemini = GeminiService()
    template = await gemini.recommend_template(metrics)

    return SelfReviewRecommendResponse(
        recommended_template=template,
        metrics_preview={
            "total_issues": metrics.get("total_issues", 0),
            "completed_issues": metrics.get("completed_issues", 0),
            "completion_rate": metrics.get("completion_rate", 0),
            "by_type": metrics.get("by_type", {})
        }
    )


@router.post("/generate", response_model=SelfReviewGenerateResponse)
async def generate_self_review(
        request: SelfReviewGenerateRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Generate a self-review PDF."""
    jira_client = await get_jira_client(current_user)

    # Get metrics (with cache)
    metrics = await get_metrics_with_cache(
        user=current_user,
        project_key=request.jira_project_key,
        jira_client=jira_client,
        start_date=request.date_range.start,
        end_date=request.date_range.end
    )

    # Get template
    template = request.template
    if request.template_id:
        # Load template from database
        from app.models.database import Template
        db_template = db.query(Template).filter(
            Template.id == request.template_id
        ).first()
        if db_template:
            template = db_template.content

    # Generate content with Gemini
    gemini = GeminiService()
    content = await gemini.generate_self_review(metrics, template)

    # Generate PDF
    pdf_service = PDFService()
    pdf_data = await pdf_service.generate_self_review_pdf(
        content=content,
        metrics=metrics,
        user_name=current_user.name or current_user.email,
        date_range_start=request.date_range.start,
        date_range_end=request.date_range.end
    )

    # Upload to MongoDB Atlas (replaces Firebase)
    filename = f"self_review_{request.jira_project_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    mongo_storage = get_mongo_storage()
    mongo_file_id = await mongo_storage.upload_pdf(
        pdf_data,
        filename,
        current_user.id,
        metadata={
            "file_type": "self_review",
            "project_key": request.jira_project_key
        }
    )

    # Optionally sync to Google Drive
    drive_url = None
    if current_user.sync_to_drive and current_user.drive_folder_id:
        # TODO: Implement Drive sync
        pass

    # Serialize metrics for JSON storage
    serialized_metrics = serialize_for_json(metrics)

    # Save to database
    generated_file = GeneratedFile(
        user_id=current_user.id,
        file_type="self_review",
        filename=filename,
        mongo_file_id=mongo_file_id,  # MongoDB GridFS ObjectId
        drive_url=drive_url,
        date_range_start=request.date_range.start,
        date_range_end=request.date_range.end,
        jira_project_key=request.jira_project_key,
        metrics=serialized_metrics
    )
    db.add(generated_file)
    db.commit()
    db.refresh(generated_file)

    return SelfReviewGenerateResponse(
        id=generated_file.id,
        download_url=f"/api/files/{mongo_file_id}",
        drive_url=drive_url,
        metrics=serialized_metrics
    )


@router.get("/history")
async def get_self_review_history(
        current_user: User = Depends(get_current_user),
        limit: int = 10,
        db: Session = Depends(get_db)
):
    """Get history of generated self-reviews."""
    files = db.query(GeneratedFile).filter(
        GeneratedFile.user_id == current_user.id,
        GeneratedFile.file_type == "self_review"
    ).order_by(GeneratedFile.created_at.desc()).limit(limit).all()

    # Convert mongo_file_id to download URL
    result = []
    for f in files:
        file_dict = {
            "id": f.id,
            "file_type": f.file_type,
            "filename": f.filename,
            "download_url": f"/api/files/{f.mongo_file_id}" if f.mongo_file_id else None,
            "drive_url": f.drive_url,
            "google_slides_id": f.google_slides_id,
            "date_range_start": f.date_range_start,
            "date_range_end": f.date_range_end,
            "jira_project_key": f.jira_project_key,
            "metrics": f.metrics,
            "created_at": f.created_at
        }
        result.append(file_dict)

    return result


@router.delete("/{review_id}")
async def delete_self_review(
        review_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Delete a generated self-review."""
    file = db.query(GeneratedFile).filter(
        GeneratedFile.id == review_id,
        GeneratedFile.user_id == current_user.id
    ).first()

    if not file:
        raise HTTPException(status_code=404, detail="Self-review not found")

    # Delete from MongoDB
    if file.mongo_file_id:
        mongo_storage = get_mongo_storage()
        await mongo_storage.delete_file(file.mongo_file_id)

    db.delete(file)
    db.commit()

    return {"message": "Self-review deleted successfully"}