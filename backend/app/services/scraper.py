"""
Scraper service for scheduled Jira data caching.
Runs on schedule to fetch and cache Jira data for faster demo/review generation.
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.database import User, ScrapedData
from app.services.jira_client import JiraClient
import logging

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
    Scrape Jira data for a specific user and cache it.
    Called by the scheduler.
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

        # For each project, scrape recent data (last 30 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        for project in projects:
            try:
                logger.info(f"Scraping project {project.key} for user {user_id}")

                # Get metrics for the project
                metrics = await jira_client.get_project_metrics(
                    project.key,
                    start_date,
                    end_date
                )

                # Serialize metrics for JSON storage
                serialized_metrics = serialize_for_json(metrics)

                # Check if we already have cached data for this project
                existing = db.query(ScrapedData).filter(
                    ScrapedData.user_id == user_id,
                    ScrapedData.jira_project_key == project.key
                ).first()

                if existing:
                    # Update existing cache
                    existing.data = serialized_metrics
                    existing.scraped_at = datetime.now()
                    existing.date_range_start = start_date
                    existing.date_range_end = end_date
                    logger.info(f"Updated cache for project {project.key}")
                else:
                    # Create new cache entry
                    scraped_data = ScrapedData(
                        user_id=user_id,
                        jira_project_key=project.key,
                        data=serialized_metrics,
                        date_range_start=start_date,
                        date_range_end=end_date
                    )
                    db.add(scraped_data)
                    logger.info(f"Created cache for project {project.key}")

                db.commit()

            except Exception as e:
                logger.error(f"Failed to scrape project {project.key}: {e}")
                continue

        logger.info(f"Completed Jira scrape for user {user_id}")

    except Exception as e:
        logger.error(f"Error during Jira scrape for user {user_id}: {e}")
        db.rollback()
    finally:
        db.close()


def scrape_jira_data_sync(user_id: int):
    """
    Synchronous wrapper for the async scrape function.
    Used by APScheduler which doesn't support async directly.
    """
    import asyncio

    # Create new event loop for the scheduled job
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(scrape_jira_data_for_user(user_id))
    finally:
        loop.close()


def get_cached_data(db: Session, user_id: int, project_key: str, max_age_hours: int = 24):
    """
    Get cached Jira data if it exists and is not too old.

    Args:
        db: Database session
        user_id: User ID
        project_key: Jira project key
        max_age_hours: Maximum age of cache in hours (default 24)

    Returns:
        Cached data dict or None if not found/expired
    """
    cached = db.query(ScrapedData).filter(
        ScrapedData.user_id == user_id,
        ScrapedData.jira_project_key == project_key
    ).first()

    if not cached:
        return None

    # Check if cache is too old
    age = datetime.now() - cached.scraped_at
    if age > timedelta(hours=max_age_hours):
        logger.info(f"Cache for {project_key} is {age.total_seconds() / 3600:.1f} hours old, considered stale")
        return None

    logger.info(f"Using cached data for {project_key} (age: {age.total_seconds() / 60:.0f} minutes)")
    return cached.data


def delete_user_cache(db: Session, user_id: int):
    """Delete all cached data for a user."""
    db.query(ScrapedData).filter(ScrapedData.user_id == user_id).delete()
    db.commit()
    logger.info(f"Deleted all cached data for user {user_id}")