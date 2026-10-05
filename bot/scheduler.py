from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
import logging

logger = logging.getLogger(__name__)


def init_scheduler():
    """Initialize APScheduler for background jobs."""
    
    jobstores = {
        'default': MemoryJobStore()
    }
    
    executors = {
        'default': AsyncIOExecutor()
    }
    
    job_defaults = {
        'coalesce': False,
        'max_instances': 1
    }
    
    scheduler = AsyncIOScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults
    )
    
    scheduler.start()
    logger.info("Scheduler initialized and started")
    
    return scheduler
