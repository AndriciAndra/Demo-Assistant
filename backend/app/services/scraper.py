"""
Scraper service for scheduled Jira data caching.
Runs on schedule to fetch and cache Jira data for faster demo/review generation.
Now uses MongoDB Atlas for persistent cache storage.
Uses Agile API to fetch sprint-based data (more reliable than deprecated search API).
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.database import User
from app.services.jira_client import JiraClient
from app.services.mongo_storage import get_mongo_storage
import logging
import asyncio

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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


async def scrape_jira_data_for_user(user_id: int):
    """
    Scrape Jira data for a specific user and cache it in MongoDB.
    Called by the scheduler.

    Uses Agile API to fetch sprint-based data since the search API has been deprecated.
    """
    db: Session = SessionLocal()

    try:
        # Get user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"User {user_id} not found")
            return

        if not user.jira_api_token:
            logger.warning(f"User {user_id} has no Jira credentials configured")
            return

        logger.info(f"Starting Jira scrape for user {user_id} ({user.email})")

        # Create Jira client
        jira_client = JiraClient(
            base_url=user.jira_base_url,
            email=user.jira_email,
            api_token=user.jira_api_token
        )

        # Test connection
        if not await jira_client.test_connection():
            logger.error(f"Failed to connect to Jira for user {user_id}")
            return

        # Get all projects
        projects = await jira_client.get_projects()
        logger.info(f"Found {len(projects)} projects for user {user_id}")

        # Get MongoDB storage
        mongo_storage = get_mongo_storage()

        for project in projects:
            try:
                logger.info(f"Scraping project {project.key} for user {user_id}")

                # Get board ID for this project
                board_id = await jira_client.get_board_id(project.key)
                if not board_id:
                    logger.warning(f"No board found for project {project.key}, skipping")
                    continue

                # Get all sprints (closed + active)
                all_sprints = await jira_client.get_sprints(board_id)
                relevant_sprints = [s for s in all_sprints if s.state in ['closed', 'active']]

                logger.info(f"Found {len(relevant_sprints)} relevant sprints for project {project.key}")

                # Cache data for each sprint
                for sprint in relevant_sprints:
                    try:
                        logger.info(f"Caching sprint {sprint.name} (ID: {sprint.id})")

                        # Get metrics using Agile API (this works!)
                        metrics = await jira_client.get_project_metrics_by_sprint(
                            project.key,
                            sprint.id
                        )

                        # Serialize metrics for JSON storage
                        serialized_metrics = serialize_for_json(metrics)

                        # Save to MongoDB cache with sprint_id and dates
                        await mongo_storage.save_cached_data(
                            user_id=user_id,
                            project_key=project.key,
                            data=serialized_metrics,
                            sprint_id=str(sprint.id),
                            sprint_name=sprint.name,
                            sprint_start_date=sprint.start_date,
                            sprint_end_date=sprint.end_date
                        )

                        logger.info(f"Cached sprint {sprint.name}: {metrics.get('total_issues', 0)} issues")

                    except Exception as e:
                        logger.error(f"Failed to cache sprint {sprint.name}: {e}")
                        continue

            except Exception as e:
                logger.error(f"Failed to scrape project {project.key}: {e}")
                continue

        logger.info(f"Completed Jira scrape for user {user_id}")

    except Exception as e:
        logger.error(f"Error during Jira scrape for user {user_id}: {e}")
    finally:
        db.close()


def scrape_jira_data_sync(user_id: int):
    """
    Synchronous wrapper for the async scrape function.
    Used by APScheduler which doesn't support async directly.
    """
    # Create new event loop for the scheduled job
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(scrape_jira_data_for_user(user_id))
    finally:
        loop.close()


async def get_cached_data(user_id: int, project_key: str, sprint_id: str = None, max_age_hours: int = 24):
    """
    Get cached Jira data from MongoDB if it exists and is not too old.

    Args:
        user_id: User ID
        project_key: Jira project key
        sprint_id: Optional sprint ID to get specific sprint cache
        max_age_hours: Maximum age of cache in hours (default 24)

    Returns:
        Cached data dict or None if not found/expired
    """
    mongo_storage = get_mongo_storage()
    return await mongo_storage.get_cached_data(user_id, project_key, sprint_id, max_age_hours)


async def delete_user_cache(user_id: int):
    """Delete all cached data for a user from MongoDB."""
    mongo_storage = get_mongo_storage()
    await mongo_storage.delete_cached_data(user_id)
    logger.info(f"Deleted all cached data for user {user_id}")