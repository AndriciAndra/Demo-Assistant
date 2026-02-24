"""
Self Review API routes.
Uses MongoDB GridFS for PDF storage.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app.models import (
    User, GeneratedFile,
    SelfReviewGenerateRequest, SelfReviewRecommendRequest,
    SelfReviewRecommendResponse, SelfReviewGenerateResponse
)
from app.services import GeminiService, PDFService
from app.services.mongo_storage import get_mongo_storage
from app.api.deps import get_current_user
from app.api.routes.jira import get_jira_client
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/self-review", tags=["self-review"])


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
    """Calculate cache expiry based on user's scheduler settings."""
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
        jira_client,
        start_date: datetime,
        end_date: datetime
) -> dict:
    """
    Get metrics from cache if available, otherwise fetch from Jira.
    Uses sprint-based cache and combines sprints that overlap with date range.
    """
    mongo_storage = get_mongo_storage()

    max_cache_age_hours = calculate_cache_expiry_hours(user)
    logger.info(f"Cache expiry for user {user.id}: {max_cache_age_hours} hours")

    # Get all cached sprints for this project
    all_cached = await mongo_storage.get_all_sprint_caches(
        user_id=user.id,
        project_key=project_key,
        max_age_hours=max_cache_age_hours
    )

    if all_cached:
        logger.info(f"Found {len(all_cached)} cached sprints, filtering by date range")

        # Make start/end dates timezone-naive for comparison
        start_naive = start_date.replace(tzinfo=None) if start_date.tzinfo else start_date
        end_naive = end_date.replace(tzinfo=None) if end_date.tzinfo else end_date

        # Combine issues from sprints that overlap with the date range
        combined_issues = []
        seen_keys = set()
        sprints_included = 0

        for cache in all_cached:
            sprint_name = cache.get('sprint_name', 'Unknown')
            sprint_start = cache.get('sprint_start_date')
            sprint_end = cache.get('sprint_end_date')

            # Check if sprint overlaps with date range
            sprint_in_range = False

            if sprint_start and sprint_end:
                # Make timezone-naive
                if hasattr(sprint_start, 'tzinfo') and sprint_start.tzinfo:
                    sprint_start = sprint_start.replace(tzinfo=None)
                if hasattr(sprint_end, 'tzinfo') and sprint_end.tzinfo:
                    sprint_end = sprint_end.replace(tzinfo=None)

                # Sprint overlaps if: sprint_start <= end_naive AND sprint_end >= start_naive
                if sprint_start <= end_naive and sprint_end >= start_naive:
                    sprint_in_range = True
                    logger.info(f"Sprint {sprint_name} overlaps with date range")
            else:
                # No sprint dates - include anyway
                sprint_in_range = True

            if sprint_in_range:
                sprints_included += 1
                issues = cache.get('data', {}).get('issues', [])
                logger.info(f"Including {len(issues)} issues from sprint {sprint_name}")

                for issue in issues:
                    issue_key = issue.get('key')
                    if issue_key and issue_key not in seen_keys:
                        seen_keys.add(issue_key)
                        combined_issues.append(issue)

        logger.info(f"Included {sprints_included} sprints, {len(combined_issues)} unique issues")

        if combined_issues:
            # Calculate metrics from combined issues
            total_issues = len(combined_issues)
            completed = [i for i in combined_issues if i.get('status', '').lower() in ['done', 'closed', 'resolved']]
            in_progress = [i for i in combined_issues if i.get('status', '').lower() in ['in progress', 'in review']]

            total_points = sum(i.get('story_points') or 0 for i in combined_issues)
            completed_points = sum(i.get('story_points') or 0 for i in completed)

            by_type = {}
            for issue in combined_issues:
                t = issue.get('issue_type', 'Task')
                by_type[t] = by_type.get(t, 0) + 1

            by_assignee = {}
            for issue in combined_issues:
                a = issue.get('assignee') or 'Unassigned'
                by_assignee[a] = by_assignee.get(a, 0) + 1

            metrics = {
                "total_issues": total_issues,
                "completed_issues": len(completed),
                "in_progress_issues": len(in_progress),
                "completion_rate": round(len(completed) / total_issues * 100, 1) if total_issues > 0 else 0,
                "total_story_points": total_points,
                "completed_story_points": completed_points,
                "by_type": by_type,
                "by_assignee": by_assignee,
                "issues": combined_issues,
                "from_cache": True,
                "sprints_combined": sprints_included
            }

            logger.info(f"Returning {total_issues} issues from cache")
            return metrics

    # No cache - this will likely fail with 410 Gone error
    # In production, you should run the scraper first
    logger.warning(f"No cache available for project {project_key}. Please run the scraper first.")

    # Return empty metrics rather than calling deprecated API
    return {
        "total_issues": 0,
        "completed_issues": 0,
        "in_progress_issues": 0,
        "completion_rate": 0,
        "total_story_points": 0,
        "completed_story_points": 0,
        "by_type": {},
        "by_assignee": {},
        "issues": [],
        "from_cache": False,
        "error": "No cached data available. Please run the data scraper in Settings."
    }


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
        from app.models.database import Template
        db_template = db.query(Template).filter(
            Template.id == request.template_id
        ).first()
        if db_template:
            template = db_template.content

    # Generate content with Gemini (with user_name for personalization)
    gemini = GeminiService()
    user_name = current_user.name or current_user.email.split('@')[0]
    content = await gemini.generate_self_review(metrics, user_name=user_name, template=template)

    # Generate PDF
    pdf_service = PDFService()
    pdf_data = await pdf_service.generate_self_review_pdf(
        content=content,
        metrics=metrics,
        user_name=current_user.name or current_user.email,
        date_range_start=request.date_range.start,
        date_range_end=request.date_range.end
    )

    # Build filename with date range + timestamp
    date_format = "%d%b%Y"
    start_str = request.date_range.start.strftime(date_format)
    end_str = request.date_range.end.strftime(date_format)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"self_review_{request.jira_project_key}_{start_str}-{end_str}_{timestamp}.pdf"

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

    # Sync to Google Drive if enabled
    drive_url = None
    drive_file_id = None
    if current_user.sync_to_drive:
        try:
            from app.services.drive import DriveService
            from app.services.google_auth import GoogleAuthService

            # Get Google credentials
            google_auth = GoogleAuthService()
            credentials = google_auth.get_credentials(
                access_token=current_user.google_access_token,
                refresh_token=current_user.google_refresh_token,
                token_expiry=current_user.google_token_expiry
            )

            # Refresh if needed
            if google_auth.is_token_expired(current_user.google_token_expiry):
                credentials = await google_auth.refresh_credentials(credentials)
                current_user.google_access_token = credentials.token
                if credentials.expiry:
                    current_user.google_token_expiry = credentials.expiry
                db.commit()

            # Upload to Drive
            drive_service = DriveService(credentials)

            # Get or create app folder
            app_folder_id = await drive_service.get_or_create_app_folder(
                base_folder_id=current_user.drive_folder_id
            )

            # Upload PDF
            drive_result = await drive_service.upload_pdf(
                pdf_data=pdf_data,
                filename=filename,
                folder_id=app_folder_id
            )

            drive_url = drive_result.get('url')
            drive_file_id = drive_result.get('id')
            logger.info(f"Synced self-review to Drive: {drive_url}")

        except Exception as e:
            logger.error(f"Failed to sync to Google Drive: {e}")

    # Serialize metrics for JSON storage
    serialized_metrics = serialize_for_json(metrics)

    # Save to database
    generated_file = GeneratedFile(
        user_id=current_user.id,
        file_type="self_review",
        filename=filename,
        mongo_file_id=mongo_file_id,
        drive_file_id=drive_file_id,
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

    result = []
    for f in files:
        file_dict = {
            "id": f.id,
            "file_type": f.file_type,
            "filename": f.filename,
            "download_url": f"/api/files/{f.mongo_file_id}" if f.mongo_file_id else None,
            "drive_file_id": f.drive_file_id,
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

    # Delete from Google Drive
    if file.drive_file_id:
        try:
            from app.services.drive import DriveService
            from app.services.google_auth import GoogleAuthService

            google_auth = GoogleAuthService()
            credentials = google_auth.get_credentials(
                access_token=current_user.google_access_token,
                refresh_token=current_user.google_refresh_token,
                token_expiry=current_user.google_token_expiry
            )

            drive_service = DriveService(credentials)
            await drive_service.delete_file(file.drive_file_id)
            logger.info(f"Deleted file from Drive: {file.drive_file_id}")
        except Exception as e:
            logger.error(f"Failed to delete from Drive: {e}")

    db.delete(file)
    db.commit()

    return {"message": "Self-review deleted successfully"}