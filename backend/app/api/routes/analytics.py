"""
Analytics API routes for personal performance dashboard.
Shows user's own Jira data across sprints.
Uses cached data from MongoDB (per sprint), filters by current user.
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

    # By status (NEW)
    by_status = {}
    for issue in issues:
        status = issue.get('status', 'Unknown')
        by_status[status] = by_status.get(status, 0) + 1

    return {
        "total_issues": total,
        "completed_issues": len(completed),
        "in_progress_issues": len(in_progress),
        "completion_rate": round(len(completed) / total * 100, 1) if total > 0 else 0,
        "total_story_points": total_points,
        "completed_story_points": completed_points,
        "velocity": completed_points,
        "by_type": by_type,
        "by_priority": by_priority,
        "by_status": by_status
    }


def calculate_avg_time_to_complete(issues: list) -> float:
    """
    Calculate average time from created to resolved in days.
    Only considers completed issues with both dates.
    """
    times = []
    for issue in issues:
        status = issue.get('status', '').lower()
        if status not in ['done', 'closed', 'resolved']:
            continue

        created_str = issue.get('created')
        resolved_str = issue.get('resolved')

        if not created_str or not resolved_str:
            continue

        try:
            # Parse dates
            if 'T' in str(created_str):
                created = datetime.fromisoformat(str(created_str).replace('Z', '+00:00'))
            else:
                created = datetime.strptime(str(created_str)[:10], '%Y-%m-%d')

            if 'T' in str(resolved_str):
                resolved = datetime.fromisoformat(str(resolved_str).replace('Z', '+00:00'))
            else:
                resolved = datetime.strptime(str(resolved_str)[:10], '%Y-%m-%d')

            # Make timezone-naive
            if created.tzinfo:
                created = created.replace(tzinfo=None)
            if resolved.tzinfo:
                resolved = resolved.replace(tzinfo=None)

            days = (resolved - created).days
            if days >= 0:
                times.append(days)
        except (ValueError, TypeError):
            continue

    if times:
        return round(sum(times) / len(times), 1)
    return 0


def calculate_completion_streak(issues: list) -> int:
    """
    Calculate the current streak of consecutive days with at least 1 completed issue.
    Counts backwards from today.
    """
    # Get all resolved dates
    resolved_dates = set()

    for issue in issues:
        status = issue.get('status', '').lower()
        if status not in ['done', 'closed', 'resolved']:
            continue

        resolved_str = issue.get('resolved')
        if not resolved_str:
            continue

        try:
            if 'T' in str(resolved_str):
                resolved = datetime.fromisoformat(str(resolved_str).replace('Z', '+00:00'))
            else:
                resolved = datetime.strptime(str(resolved_str)[:10], '%Y-%m-%d')

            if resolved.tzinfo:
                resolved = resolved.replace(tzinfo=None)

            resolved_dates.add(resolved.date())
        except (ValueError, TypeError):
            continue

    if not resolved_dates:
        return 0

    # Count streak backwards from today
    today = datetime.now().date()
    streak = 0
    current_date = today

    # Check if today or yesterday has completions (allow 1 day gap for weekends)
    if current_date not in resolved_dates:
        current_date = today - timedelta(days=1)
        if current_date not in resolved_dates:
            return 0

    # Count consecutive days
    while current_date in resolved_dates:
        streak += 1
        current_date -= timedelta(days=1)

    return streak


async def get_sprint_data_with_cache(
        user_id: int,
        project_key: str,
        sprint_id: int,
        sprint_info: dict,
        user_email: str,
        jira_client,
        max_cache_hours: int = 168
) -> dict:
    """
    Get sprint data from cache if available, otherwise fetch from Jira.
    Filters issues by user.
    """
    mongo = get_mongo_storage()

    # Try cache first (keyed by sprint_id)
    cached = await mongo.get_cached_data(
        user_id=user_id,
        project_key=project_key,
        sprint_id=str(sprint_id),
        max_age_hours=max_cache_hours
    )

    if cached:
        logger.info(f"Using cache for sprint {sprint_id}")
        all_issues = cached.get('issues', [])
        user_issues = filter_issues_by_user(all_issues, user_email)
        source = "cache"
    else:
        logger.info(f"No cache for sprint {sprint_id}, fetching from Jira")
        # Fetch from Jira and filter
        all_issues_raw = await jira_client.get_sprint_issues(sprint_id)
        all_issues = [i.model_dump() for i in all_issues_raw]
        user_issues = filter_issues_by_user(all_issues, user_email)
        source = "jira"

    # Calculate metrics for user's issues
    metrics = calculate_metrics_from_issues(user_issues)

    return {
        "sprint_id": sprint_info.get('id') or sprint_id,
        "sprint_name": sprint_info.get('name', f'Sprint {sprint_id}'),
        "sprint_state": sprint_info.get('state', 'unknown'),
        "start_date": sprint_info.get('start_date'),
        "end_date": sprint_info.get('end_date'),
        "metrics": metrics,
        "by_type": metrics.get('by_type', {}),
        "by_priority": metrics.get('by_priority', {}),
        "by_status": metrics.get('by_status', {}),  # NEW
        "issues": user_issues,
        "source": source
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
    Uses cached data from MongoDB (per sprint), filters by current user.
    """
    user_email = current_user.jira_email or current_user.email
    jira_client = await get_jira_client(current_user)

    # Get board and sprints info
    board_id = await jira_client.get_board_id(project_key)
    if not board_id:
        raise HTTPException(status_code=404, detail="No board found for project")

    all_sprints = await jira_client.get_sprints(board_id)

    # Filter closed + active, sort by date, take num_sprints
    sorted_sprints = sorted(
        [s for s in all_sprints if s.state in ['closed', 'active']],
        key=lambda x: x.start_date or datetime.min,
        reverse=True
    )[:num_sprints]
    sorted_sprints = list(reversed(sorted_sprints))  # Oldest first for charts

    # Get data for each sprint (from cache or Jira)
    sprint_data = []
    all_user_issues = []  # Collect all issues for aggregate calculations
    cache_hits = 0

    for sprint in sorted_sprints:
        sprint_info = {
            'id': sprint.id,
            'name': sprint.name,
            'state': sprint.state,
            'start_date': sprint.start_date.isoformat() if sprint.start_date else None,
            'end_date': sprint.end_date.isoformat() if sprint.end_date else None
        }

        data = await get_sprint_data_with_cache(
            user_id=current_user.id,
            project_key=project_key,
            sprint_id=sprint.id,
            sprint_info=sprint_info,
            user_email=user_email,
            jira_client=jira_client
        )

        if data.get('source') == 'cache':
            cache_hits += 1

        # Keep issues for aggregate calculations before removing
        all_user_issues.extend(data.get('issues', []))

        sprint_data.append(data)

    # Calculate summary
    velocities = [s["metrics"]["velocity"] for s in sprint_data if s["metrics"]["velocity"] > 0]
    completion_rates = [s["metrics"]["completion_rate"] for s in sprint_data if s["metrics"]["total_issues"] > 0]

    # Calculate average time to complete (days from created to resolved)
    avg_time_to_complete = calculate_avg_time_to_complete(all_user_issues)

    # Calculate streak (consecutive days with at least 1 completed issue)
    streak = calculate_completion_streak(all_user_issues)

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
            "avg_time_to_complete_days": avg_time_to_complete,
            "current_streak": streak
        },
        "cache_stats": {
            "hits": cache_hits,
            "misses": len(sprint_data) - cache_hits
        }
    }


@router.get("/my-current-sprint")
async def get_my_current_sprint(
        project_key: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Get user's issues in the current active sprint.
    Uses cache if available.
    """
    jira_client = await get_jira_client(current_user)
    user_email = current_user.jira_email or current_user.email

    # Get board and active sprint
    board_id = await jira_client.get_board_id(project_key)
    if not board_id:
        raise HTTPException(status_code=404, detail="No board found for project")

    sprints = await jira_client.get_sprints(board_id, state='active')
    if not sprints:
        return {"message": "No active sprint", "sprint": None, "issues": []}

    active_sprint = sprints[0]

    sprint_info = {
        'id': active_sprint.id,
        'name': active_sprint.name,
        'state': active_sprint.state,
        'start_date': active_sprint.start_date.isoformat() if active_sprint.start_date else None,
        'end_date': active_sprint.end_date.isoformat() if active_sprint.end_date else None,
        'goal': active_sprint.goal
    }

    # Get data from cache or Jira
    data = await get_sprint_data_with_cache(
        user_id=current_user.id,
        project_key=project_key,
        sprint_id=active_sprint.id,
        sprint_info=sprint_info,
        user_email=user_email,
        jira_client=jira_client
    )

    issues = data.get('issues', [])

    # Group by status
    by_status = {}
    for issue in issues:
        status = issue.get('status', 'Unknown')
        if status not in by_status:
            by_status[status] = []
        by_status[status].append({
            "key": issue.get('key'),
            "summary": issue.get('summary'),
            "issue_type": issue.get('issue_type'),
            "story_points": issue.get('story_points'),
            "priority": issue.get('priority')
        })

    return {
        "sprint": {
            "id": active_sprint.id,
            "name": active_sprint.name,
            "start_date": sprint_info['start_date'],
            "end_date": sprint_info['end_date'],
            "goal": active_sprint.goal
        },
        "my_stats": data['metrics'],
        "by_status": by_status,
        "issues": [
            {
                "key": i.get('key'),
                "summary": i.get('summary'),
                "status": i.get('status'),
                "issue_type": i.get('issue_type'),
                "story_points": i.get('story_points'),
                "priority": i.get('priority')
            }
            for i in issues
        ],
        "from_cache": data.get('source') == 'cache'
    }


@router.get("/my-overview")
async def get_my_overview(
        project_key: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Get overall statistics for the user across recent sprints.
    Aggregates data from multiple sprint caches.
    """
    user_email = current_user.jira_email or current_user.email
    jira_client = await get_jira_client(current_user)

    # Get board and recent sprints
    board_id = await jira_client.get_board_id(project_key)
    if not board_id:
        raise HTTPException(status_code=404, detail="No board found for project")

    all_sprints = await jira_client.get_sprints(board_id)
    recent_sprints = sorted(
        [s for s in all_sprints if s.state in ['closed', 'active']],
        key=lambda x: x.start_date or datetime.min,
        reverse=True
    )[:10]  # Last 10 sprints

    # Aggregate user issues from all sprint caches
    all_user_issues = []
    cache_hits = 0

    for sprint in recent_sprints:
        sprint_info = {
            'id': sprint.id,
            'name': sprint.name,
            'state': sprint.state
        }

        data = await get_sprint_data_with_cache(
            user_id=current_user.id,
            project_key=project_key,
            sprint_id=sprint.id,
            sprint_info=sprint_info,
            user_email=user_email,
            jira_client=jira_client
        )

        if data.get('source') == 'cache':
            cache_hits += 1

        all_user_issues.extend(data.get('issues', []))

    # Deduplicate issues (same issue might appear in multiple sprints)
    seen_keys = set()
    unique_issues = []
    for issue in all_user_issues:
        key = issue.get('key')
        if key and key not in seen_keys:
            seen_keys.add(key)
            unique_issues.append(issue)

    # Calculate stats
    total = len(unique_issues)
    completed = [i for i in unique_issues if i.get('status', '').lower() in ['done', 'closed', 'resolved']]

    by_type = {}
    for issue in unique_issues:
        t = issue.get('issue_type', 'Task')
        by_type[t] = by_type.get(t, 0) + 1

    by_status = {}
    for issue in unique_issues:
        s = issue.get('status', 'Unknown')
        by_status[s] = by_status.get(s, 0) + 1

    by_priority = {}
    for issue in unique_issues:
        p = issue.get('priority') or 'None'
        by_priority[p] = by_priority.get(p, 0) + 1

    # Recent completed
    recent_completed = sorted(
        [i for i in completed if i.get('resolved')],
        key=lambda x: x.get('resolved', ''),
        reverse=True
    )[:10]

    return {
        "period": {
            "sprints_analyzed": len(recent_sprints),
            "cache_hits": cache_hits,
            "cache_misses": len(recent_sprints) - cache_hits
        },
        "totals": {
            "total_issues": total,
            "completed_issues": len(completed),
            "completion_rate": round(len(completed) / total * 100, 1) if total > 0 else 0,
            "total_story_points": sum(i.get('story_points') or 0 for i in unique_issues),
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