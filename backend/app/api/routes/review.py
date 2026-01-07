from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app.models import (
    User, GeneratedFile,
    SelfReviewGenerateRequest, SelfReviewGenerateResponse,
    SelfReviewRecommendRequest, SelfReviewRecommendResponse
)
from app.services import JiraClient, GeminiService, FirebaseService, PDFService
from app.api.deps import get_current_user
from app.api.routes.jira import get_jira_client

router = APIRouter(prefix="/self-review", tags=["self-review"])


@router.post("/recommend", response_model=SelfReviewRecommendResponse)
async def recommend_template(
        request: SelfReviewRecommendRequest,
        current_user: User = Depends(get_current_user)
):
    """Get AI-recommended template based on work data."""
    jira_client = await get_jira_client(current_user)

    # Get metrics
    metrics = await jira_client.get_project_metrics(
        request.jira_project_key,
        request.date_range.start,
        request.date_range.end
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

    # Get metrics
    metrics = await jira_client.get_project_metrics(
        request.jira_project_key,
        request.date_range.start,
        request.date_range.end
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

    # Upload to Firebase
    filename = f"self_review_{request.jira_project_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    firebase = FirebaseService()
    firebase_url = await firebase.upload_pdf(pdf_data, filename, current_user.id)

    # Optionally sync to Google Drive
    drive_url = None
    if current_user.sync_to_drive and current_user.drive_folder_id:
        # TODO: Implement Drive sync
        pass

    # Save to database
    generated_file = GeneratedFile(
        user_id=current_user.id,
        file_type="self_review",
        filename=filename,
        firebase_url=firebase_url,
        drive_url=drive_url,
        date_range_start=request.date_range.start,
        date_range_end=request.date_range.end,
        jira_project_key=request.jira_project_key,
        metrics=metrics
    )
    db.add(generated_file)
    db.commit()
    db.refresh(generated_file)

    return SelfReviewGenerateResponse(
        id=generated_file.id,
        firebase_url=firebase_url,
        drive_url=drive_url,
        metrics=metrics
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

    return files


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

    # Delete from Firebase
    if file.firebase_url:
        firebase = FirebaseService()
        # Extract path and delete
        path = f"users/{current_user.id}/self-reviews/{file.filename}"
        await firebase.delete_file(path)

    db.delete(file)
    db.commit()

    return {"message": "Self-review deleted successfully"}