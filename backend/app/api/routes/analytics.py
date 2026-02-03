"""
Analytics API routes for personal performance dashboard.
Shows user's own Jira data across sprints.
Uses cached data from MongoDB when available, filters by current user.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
from app.database import get_db
from app.models import User
from app.services.mongo_storage import get_mongo_storage
from app.api.deps import get_current_user
from app.api.routes.jira import get_jira_client
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])


def filter_issues_by_user(issues: list, user_email: str) -> list:
    """Filter issues to only those assigned to the user."""
    if not issues:
        return []

    user_issues = []
    user_email_lower = user_email.lower()

    for issue in issues:
        # Check assignee_email first (most accurate)
        assignee_email = issue.get('assignee_email') or ''
        if assignee_email and assignee_email.lower() == user_email_lower:
            user_issues.append(issue)
            continue

        # Fallback: partial match on displayName
        assignee = issue.get('assignee') or ''
        if assignee and (
                user_email_lower in assignee.lower() or
                assignee.lower() in user_email_lower
        ):
            user_issues.append(issue)

    return user_issues


def calculate_metrics_from_issues(issues: list) -> dict:
    """Calculate metrics from a list of issues."""
    total = len(issues)
    completed = [i for i in issues if i.get('status', '').lower() in ['done', 'closed', 'resolved']]
    in_progress = [i for i in issues if i.get('status', '').lower() in ['in progress', 'in review']]

    total_points = sum(i.get('story_points') or 0 for i in issues)
    completed_points = sum(i.get('story_points') or 0 for i in completed)

    # By type
    by_type = {}
    for issue in issues:
        issue_type = issue.get('issue_type', 'Task')
        by_type[issue_type] = by_type.get(issue_type, 0) + 1

    # By priority
    by_priority = {}
    for issue in issues:
        priority = issue.get('priority') or 'None'
        by_priority[priority] = by_priority.get(priority, 0) + 1

    return {
        "total_issues": total,
        "completed_issues": len(completed),
        "in_progress_issues": len(in_progress),
        "completion_rate": round(len(completed) / total * 100, 1) if total > 0 else 0,
        "total_story_points": total_points,
        "completed_story_points": completed_points,
        "velocity": completed_points,
        "by_type": by_type,
        "by_priority": by_priority
    }


@router.get("/my-sprints")
async def get_my_sprint_performance(
        project_key: str,
        num_sprints: int = 5,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Get user's personal performance across multiple sprints.
    Uses cached data from MongoDB when available, filters by current user.
    """
    user_email = current_user.jira_email or current_user.email
    jira_client = await get_jira_client(current_user)

    # Try to get cached data from MongoDB first
    mongo = get_mongo_storage()
    cached = await mongo.get_cached_data(current_user.id, project_key, max_age_hours=24)

    # Get board and sprints (always need this for sprint info)
    board_id = await jira_client.get_board_id(project_key)
    if not board_id:
        raise HTTPException(status_code=404, detail="No board found for project")

    all_sprints = await jira_client.get_sprints(board_id)
    sorted_sprints = sorted(
        [s for s in all_sprints if s.state in ['closed', 'active']],
        key=lambda x: x.start_date or datetime.min,
        reverse=True
    )[:num_sprints]
    sorted_sprints = list(reversed(sorted_sprints))  # Oldest first for charts

    sprint_data = []

    if cached:
        logger.info(f"Using MongoDB cache for analytics - project {project_key}")
        all_issues = cached.get('issues', [])

        # For each sprint, we still need to fetch per-sprint issues
        # because cache has all issues, not per-sprint breakdown
        for sprint in sorted_sprints:
            sprint_issues = await jira_client.get_sprint_issues_for_user(sprint.id, user_email)
            sprint_data.append(build_sprint_data(sprint, sprint_issues))
    else:
        # No cache - fetch from Jira directly
        logger.info(f"No MongoDB cache, fetching from Jira - project {project_key}")

        for sprint in sorted_sprints:
            sprint_issues = await jira_client.get_sprint_issues_for_user(sprint.id, user_email)
            sprint_data.append(build_sprint_data(sprint, sprint_issues))

    # Calculate summary
    velocities = [s["metrics"]["velocity"] for s in sprint_data if s["metrics"]["velocity"] > 0]
    completion_rates = [s["metrics"]["completion_rate"] for s in sprint_data if s["metrics"]["total_issues"] > 0]

    return {
        "user_email": user_email,
        "project_key": project_key,
        "sprints": sprint_data,
        "summary": {
            "total_sprints": len(sprint_data),
            "avg_velocity": round(sum(velocities) / len(velocities), 1) if velocities else 0,
            "avg_completion_rate": round(sum(completion_rates) / len(completion_rates), 1) if completion_rates else 0,
            "total_issues_all_sprints": sum(s["metrics"]["total_issues"] for s in sprint_data),
            "total_points_all_sprints": sum(s["metrics"]["completed_story_points"] for s in sprint_data),
        },
        "cache_used": cached is not None
    }


def build_sprint_data(sprint, issues) -> dict:
    """Build sprint data dict from sprint and issues."""
    total_issues = len(issues)
    completed = [i for i in issues if i.status.lower() in ['done', 'closed', 'resolved']]
    in_progress = [i for i in issues if i.status.lower() in ['in progress', 'in review']]

    total_points = sum(i.story_points or 0 for i in issues)
    completed_points = sum(i.story_points or 0 for i in completed)

    by_type = {}
    for issue in issues:
        by_type[issue.issue_type] = by_type.get(issue.issue_type, 0) + 1

    by_priority = {}
    for issue in issues:
        priority = issue.priority or 'None'
        by_priority[priority] = by_priority.get(priority, 0) + 1

    return {
        "sprint_id": sprint.id,
        "sprint_name": sprint.name,
        "sprint_state": sprint.state,
        "start_date": sprint.start_date.isoformat() if sprint.start_date else None,
        "end_date": sprint.end_date.isoformat() if sprint.end_date else None,
        "metrics": {
            "total_issues": total_issues,
            "completed_issues": len(completed),
            "in_progress_issues": len(in_progress),
            "completion_rate": round(len(completed) / total_issues * 100, 1) if total_issues > 0 else 0,
            "total_story_points": total_points,
            "completed_story_points": completed_points,
            "velocity": completed_points,
        },
        "by_type": by_type,
        "by_priority": by_priority,
        "issues": [
            {
                "key": i.key,
                "summary": i.summary,
                "status": i.status,
                "issue_type": i.issue_type,
                "story_points": i.story_points,
                "priority": i.priority
            }
            for i in issues
        ]
    }


@router.get("/my-current-sprint")
async def get_my_current_sprint(
        project_key: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Get user's issues in the current active sprint.
    """
    jira_client = await get_jira_client(current_user)

    # Get board and active sprint
    board_id = await jira_client.get_board_id(project_key)
    if not board_id:
        raise HTTPException(status_code=404, detail="No board found for project")

    sprints = await jira_client.get_sprints(board_id, state='active')
    if not sprints:
        return {"message": "No active sprint", "sprint": None, "issues": []}

    active_sprint = sprints[0]
    user_email = current_user.jira_email or current_user.email

    # Get user's issues
    issues = await jira_client.get_sprint_issues_for_user(
        active_sprint.id,
        user_email
    )

    # Group by status
    by_status = {}
    for issue in issues:
        status = issue.status
        if status not in by_status:
            by_status[status] = []
        by_status[status].append({
            "key": issue.key,
            "summary": issue.summary,
            "issue_type": issue.issue_type,
            "story_points": issue.story_points,
            "priority": issue.priority
        })

    total_points = sum(i.story_points or 0 for i in issues)
    completed = [i for i in issues if i.status.lower() in ['done', 'closed', 'resolved']]
    completed_points = sum(i.story_points or 0 for i in completed)

    return {
        "sprint": {
            "id": active_sprint.id,
            "name": active_sprint.name,
            "start_date": active_sprint.start_date.isoformat() if active_sprint.start_date else None,
            "end_date": active_sprint.end_date.isoformat() if active_sprint.end_date else None,
            "goal": active_sprint.goal
        },
        "my_stats": {
            "total_issues": len(issues),
            "completed_issues": len(completed),
            "total_points": total_points,
            "completed_points": completed_points,
            "progress_percent": round(completed_points / total_points * 100, 1) if total_points > 0 else 0
        },
        "by_status": by_status,
        "issues": [
            {
                "key": i.key,
                "summary": i.summary,
                "status": i.status,
                "issue_type": i.issue_type,
                "story_points": i.story_points,
                "priority": i.priority
            }
            for i in issues
        ]
    }


@router.get("/my-overview")
async def get_my_overview(
        project_key: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Get overall statistics for the user across all time.
    Uses cached data from MongoDB when available.
    """
    user_email = current_user.jira_email or current_user.email

    # Try MongoDB cache first
    mongo = get_mongo_storage()
    cached = await mongo.get_cached_data(current_user.id, project_key, max_age_hours=24)

    if cached:
        logger.info(f"Using MongoDB cache for my-overview - project {project_key}")
        all_issues = cached.get('issues', [])
        user_issues = filter_issues_by_user(all_issues, user_email)

        # Calculate stats from filtered issues
        total = len(user_issues)
        completed = [i for i in user_issues if i.get('status', '').lower() in ['done', 'closed', 'resolved']]

        by_type = {}
        for issue in user_issues:
            t = issue.get('issue_type', 'Task')
            by_type[t] = by_type.get(t, 0) + 1

        by_status = {}
        for issue in user_issues:
            s = issue.get('status', 'Unknown')
            by_status[s] = by_status.get(s, 0) + 1

        by_priority = {}
        for issue in user_issues:
            p = issue.get('priority') or 'None'
            by_priority[p] = by_priority.get(p, 0) + 1

        # Recent completed (sort by resolved date)
        recent_completed = sorted(
            [i for i in completed if i.get('resolved')],
            key=lambda x: x.get('resolved', ''),
            reverse=True
        )[:10]

        return {
            "period": {
                "source": "mongodb_cache"
            },
            "totals": {
                "total_issues": total,
                "completed_issues": len(completed),
                "completion_rate": round(len(completed) / total * 100, 1) if total > 0 else 0,
                "total_story_points": sum(i.get('story_points') or 0 for i in user_issues),
                "completed_story_points": sum(i.get('story_points') or 0 for i in completed)
            },
            "by_type": by_type,
            "by_status": by_status,
            "by_priority": by_priority,
            "recent_completed": [
                {
                    "key": i.get('key'),
                    "summary": i.get('summary'),
                    "issue_type": i.get('issue_type'),
                    "resolved": i.get('resolved')
                }
                for i in recent_completed
            ]
        }

    # No cache - fetch from Jira
    logger.info(f"No MongoDB cache for my-overview, fetching from Jira - project {project_key}")
    jira_client = await get_jira_client(current_user)

    # Get issues from last 90 days assigned to user
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)

    issues = await jira_client.get_issues_for_user(
        project_key,
        user_email,
        start_date,
        end_date
    )

    # Calculate stats
    total = len(issues)
    completed = [i for i in issues if i.status.lower() in ['done', 'closed', 'resolved']]

    by_type = {}
    for issue in issues:
        by_type[issue.issue_type] = by_type.get(issue.issue_type, 0) + 1

    by_status = {}
    for issue in issues:
        by_status[issue.status] = by_status.get(issue.status, 0) + 1

    by_priority = {}
    for issue in issues:
        priority = issue.priority or 'None'
        by_priority[priority] = by_priority.get(priority, 0) + 1

    recent_completed = sorted(
        [i for i in completed if i.resolved],
        key=lambda x: x.resolved,
        reverse=True
    )[:10]

    return {
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "days": 90,
            "source": "jira_api"
        },
        "totals": {
            "total_issues": total,
            "completed_issues": len(completed),
            "completion_rate": round(len(completed) / total * 100, 1) if total > 0 else 0,
            "total_story_points": sum(i.story_points or 0 for i in issues),
            "completed_story_points": sum(i.story_points or 0 for i in completed)
        },
        "by_type": by_type,
        "by_status": by_status,
        "by_priority": by_priority,
        "recent_completed": [
            {
                "key": i.key,
                "summary": i.summary,
                "issue_type": i.issue_type,
                "resolved": i.resolved.isoformat() if i.resolved else None
            }
            for i in recent_completed
        ]
    }