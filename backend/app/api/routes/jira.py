from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, JiraCredentials, JiraProject, JiraSprint
from app.services import JiraClient
from app.api.deps import get_current_user

router = APIRouter(prefix="/jira", tags=["jira"])


async def get_jira_client(user: User) -> JiraClient:
    """Get Jira client for a user."""
    if not user.jira_api_token:
        raise HTTPException(status_code=400, detail="Jira not configured")

    return JiraClient(
        base_url=user.jira_base_url,
        email=user.jira_email,
        api_token=user.jira_api_token
    )


@router.post("/connect")
async def connect_jira(
        credentials: JiraCredentials,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Connect Jira account."""
    client = JiraClient(
        base_url=credentials.base_url,
        email=credentials.email,
        api_token=credentials.api_token
    )

    # Test connection
    if not await client.test_connection():
        raise HTTPException(status_code=400, detail="Invalid Jira credentials")

    # Save to user
    current_user.jira_base_url = credentials.base_url
    current_user.jira_email = credentials.email
    current_user.jira_api_token = credentials.api_token
    db.commit()

    return {"message": "Jira connected successfully"}


@router.get("/projects", response_model=list[JiraProject])
async def get_projects(
        current_user: User = Depends(get_current_user)
):
    """Get all accessible Jira projects."""
    client = await get_jira_client(current_user)
    return await client.get_projects()


@router.get("/projects/{project_key}/sprints", response_model=list[JiraSprint])
async def get_sprints(
        project_key: str,
        state: str = None,
        current_user: User = Depends(get_current_user)
):
    """Get sprints for a project."""
    client = await get_jira_client(current_user)

    board_id = await client.get_board_id(project_key)
    if not board_id:
        raise HTTPException(status_code=404, detail="No board found for project")

    return await client.get_sprints(board_id, state=state)


@router.get("/projects/{project_key}/velocity")
async def get_velocity(
        project_key: str,
        sprints: int = 5,
        current_user: User = Depends(get_current_user)
):
    """Get velocity data for a project."""
    client = await get_jira_client(current_user)

    board_id = await client.get_board_id(project_key)
    if not board_id:
        raise HTTPException(status_code=404, detail="No board found for project")

    return await client.get_velocity(board_id, sprints)


@router.get("/test")
async def test_connection(
        current_user: User = Depends(get_current_user)
):
    """Test Jira connection."""
    try:
        client = await get_jira_client(current_user)
        connected = await client.test_connection()
        return {"connected": connected}
    except HTTPException:
        return {"connected": False}