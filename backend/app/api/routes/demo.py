from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.database import get_db
from app.models import (
    User, GeneratedFile,
    DemoGenerateRequest, DemoGenerateResponse
)
from app.services import JiraClient, GeminiService, SlidesService, FirebaseService, GoogleAuthService
from app.api.deps import get_current_user
from app.api.routes.jira import get_jira_client

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
        # Use sprint API directly - more reliable
        print(f"DEBUG: Using sprint_id = {request.sprint_id}")
        metrics = await jira_client.get_project_metrics_by_sprint(request.jira_project_key, request.sprint_id)

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

    elif request.date_range:
        print(f"DEBUG: Using date_range = {request.date_range.start} to {request.date_range.end}")
        start_date = request.date_range.start
        end_date = request.date_range.end
        metrics = await jira_client.get_project_metrics(
            request.jira_project_key,
            start_date,
            end_date
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="Either date_range or sprint_id is required"
        )

    print(f"DEBUG: Got metrics - total_issues={metrics.get('total_issues', 0)}")

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
    print("DEBUG: Creating Google Slides presentation...")
    try:
        credentials = await get_user_google_credentials(current_user)
        slides_service = SlidesService(credentials)
        slides_result = await slides_service.create_demo_presentation(content)
        google_slides_url = slides_result["url"]
        google_slides_id = slides_result["presentation_id"]
        print(f"DEBUG: Created presentation: {google_slides_id}")
    except Exception as e:
        print(f"DEBUG: Failed to create slides: {e}")
        # Fall back to placeholder if slides creation fails
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

    # Get metrics
    metrics = await jira_client.get_project_metrics(
        jira_project_key,
        start_date,
        end_date
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

    # Get metrics by sprint
    metrics = await jira_client.get_project_metrics_by_sprint(
        jira_project_key,
        sprint_id
    )

    return {
        "metrics": metrics,
        "content": None  # Don't generate AI content for preview, just metrics
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

    # Delete from Firebase if exists
    if file.firebase_url:
        firebase = FirebaseService()
        # Extract path from URL and delete
        # await firebase.delete_file(path)

    db.delete(file)
    db.commit()

    return {"message": "Demo deleted successfully"}