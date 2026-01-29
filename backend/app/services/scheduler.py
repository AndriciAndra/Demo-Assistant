from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Callable, Optional
from app.config import get_settings
import logging

settings = get_settings()
logger = logging.getLogger(__name__)


class SchedulerService:
    """Service for scheduling automated tasks."""

    _instance: Optional['SchedulerService'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Use BackgroundScheduler instead of AsyncIOScheduler for better compatibility
        self.scheduler = BackgroundScheduler()
        self._jobs = {}
        self._initialized = True

    def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")

    def shutdown(self):
        """Shutdown the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler shutdown")

    def add_user_job(
            self,
            user_id: int,
            job_type: str,  # 'scrape', 'demo', 'self_review'
            func: Callable = None,
            day_of_week: str = None,
            hour: int = None,
            minute: int = None,
            **kwargs
    ) -> str:
        """Add a scheduled job for a user."""
        job_id = f"user_{user_id}_{job_type}"

        # Remove existing job if any
        self.remove_job(job_id)

        # Use defaults if not specified
        day_of_week = day_of_week or settings.scheduler_day_of_week
        hour = hour if hour is not None else settings.scheduler_hour
        minute = minute if minute is not None else settings.scheduler_minute

        # If no function provided, use the default scraper
        if func is None and job_type == "scrape":
            from app.services.scraper import scrape_jira_data_sync
            func = scrape_jira_data_sync

        if func is None:
            logger.warning(f"No function provided for job {job_id}")
            return job_id

        trigger = CronTrigger(
            day_of_week=day_of_week,
            hour=hour,
            minute=minute
        )

        job = self.scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            args=[user_id],  # Pass user_id as argument
            replace_existing=True
        )

        self._jobs[job_id] = job
        logger.info(f"Added job {job_id}: {day_of_week} at {hour:02d}:{minute:02d}")

        return job_id

    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job."""
        try:
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            if job_id in self._jobs:
                del self._jobs[job_id]
            return True
        except Exception as e:
            logger.error(f"Failed to remove job {job_id}: {e}")
            return False

    def remove_user_jobs(self, user_id: int) -> None:
        """Remove all jobs for a user."""
        job_ids_to_remove = [
            job_id for job_id in self._jobs.keys()
            if job_id.startswith(f"user_{user_id}_")
        ]
        for job_id in job_ids_to_remove:
            self.remove_job(job_id)
        logger.info(f"Removed {len(job_ids_to_remove)} jobs for user {user_id}")

    def get_user_jobs(self, user_id: int) -> list:
        """Get all scheduled jobs for a user."""
        user_jobs = []
        for job_id in self._jobs.keys():
            if job_id.startswith(f"user_{user_id}_"):
                job = self.scheduler.get_job(job_id)
                if job:
                    user_jobs.append({
                        "job_id": job_id,
                        "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                        "trigger": str(job.trigger)
                    })
        return user_jobs

    def run_job_now(self, user_id: int, job_type: str = "scrape") -> bool:
        """Manually trigger a job to run immediately."""
        job_id = f"user_{user_id}_{job_type}"
        job = self.scheduler.get_job(job_id)

        if job:
            # Run the job function directly
            try:
                job.func(*job.args, **job.kwargs)
                logger.info(f"Manually triggered job {job_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to run job {job_id}: {e}")
                return False
        else:
            # If no scheduled job, run scraper directly
            if job_type == "scrape":
                from app.services.scraper import scrape_jira_data_sync
                try:
                    scrape_jira_data_sync(user_id)
                    logger.info(f"Manually ran scraper for user {user_id}")
                    return True
                except Exception as e:
                    logger.error(f"Failed to run scraper for user {user_id}: {e}")
                    return False

        return False

    def update_user_schedule(
            self,
            user_id: int,
            job_type: str,
            func: Callable,
            day_of_week: str,
            hour: int,
            minute: int,
            **kwargs
    ) -> str:
        """Update schedule for an existing user job."""
        return self.add_user_job(
            user_id=user_id,
            job_type=job_type,
            func=func,
            day_of_week=day_of_week,
            hour=hour,
            minute=minute,
            **kwargs
        )


# Singleton instance
scheduler_service = SchedulerService()