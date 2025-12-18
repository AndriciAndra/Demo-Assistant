from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app.models import (
    User, GeneratedFile,
    DemoGenerateRequest, DemoGenerateResponse
)
from app.services import JiraClient, GeminiService, SlidesService, FirebaseService
from app.api.deps import get_current_user
from app.api.routes.jira import get_jira_client

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/generate", response_model=DemoGenerateResponse)
async def generate_demo(
        request: DemoGenerateRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Generate a demo presentation from Jira data."""
    # Get Jira client
    jira_client = await get_jira_client(current_user)

    # Determine date range
    if request.date_range:
        start_date = request.date_range.start
        end_date = request.date_range.end
    elif request.sprint_id:
        # Get sprint dates
        board_id = await jira_client.get_board_id(request.jira_project_key)
        sprints = await jira_client.get_sprints(board_id)
        sprint = next((s for s in sprints if s.id == request.sprint_id), None)
        if not sprint:
            raise HTTPException(status_code=404, detail="Sprint not found")
        start_date = sprint.start_date or datetime.now()
        end_date = sprint.end_date or datetime.now()
    else:
        raise HTTPException(
            status_code=400,
            detail="Either date_range or sprint_id is required"
        )

    # Get metrics from Jira
    metrics = await jira_client.get_project_metrics(
        request.jira_project_key,
        start_date,
        end_date
    )

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
    # TODO: Get user's Google credentials
    # For now, we'll return a placeholder

    # Save to database
    generated_file = GeneratedFile(
        user_id=current_user.id,
        file_type="demo",
        filename=f"demo_{request.jira_project_key}_{datetime.now().strftime('%Y%m%d')}.pptx",
        date_range_start=start_date,
        date_range_end=end_date,
        jira_project_key=request.jira_project_key,
        metrics=metrics
    )
    db.add(generated_file)
    db.commit()
    db.refresh(generated_file)

    return DemoGenerateResponse(
        id=generated_file.id,
        google_slides_url="https://docs.google.com/presentation/d/placeholder",
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
    """Preview demo content without generating slides."""
    jira_client = await get_jira_client(current_user)

    # Get metrics
    metrics = await jira_client.get_project_metrics(
        jira_project_key,
        start_date,
        end_date
    )

    # Generate content preview
    gemini = GeminiService()
    content = await gemini.generate_demo_content(metrics, jira_project_key)

    return {
        "metrics": metrics,
        "content": content
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