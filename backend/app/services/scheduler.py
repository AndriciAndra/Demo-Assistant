from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Callable, Optional
from app.config import get_settings

settings = get_settings()


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
        
        self.scheduler = AsyncIOScheduler()
        self._jobs = {}
        self._initialized = True
    
    def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
    
    def shutdown(self):
        """Shutdown the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
    
    def add_user_job(
        self,
        user_id: int,
        job_type: str,  # 'demo' or 'self_review'
        func: Callable,
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
        
        trigger = CronTrigger(
            day_of_week=day_of_week,
            hour=hour,
            minute=minute
        )
        
        job = self.scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            kwargs={"user_id": user_id, **kwargs},
            replace_existing=True
        )
        
        self._jobs[job_id] = job
        return job_id
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job."""
        try:
            self.scheduler.remove_job(job_id)
            if job_id in self._jobs:
                del self._jobs[job_id]
            return True
        except Exception:
            return False
    
    def remove_user_jobs(self, user_id: int) -> None:
        """Remove all jobs for a user."""
        job_ids_to_remove = [
            job_id for job_id in self._jobs.keys()
            if job_id.startswith(f"user_{user_id}_")
        ]
        for job_id in job_ids_to_remove:
            self.remove_job(job_id)
    
    def get_user_jobs(self, user_id: int) -> list:
        """Get all scheduled jobs for a user."""
        user_jobs = []
        for job_id, job in self._jobs.items():
            if job_id.startswith(f"user_{user_id}_"):
                user_jobs.append({
                    "job_id": job_id,
                    "next_run": job.next_run_time,
                    "trigger": str(job.trigger)
                })
        return user_jobs
    
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
