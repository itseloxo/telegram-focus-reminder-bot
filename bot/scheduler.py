from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from aiogram import Bot
from datetime import datetime, timedelta, timezone
from database import get_session, Reminder, ReminderStatus
import logging

logger = logging.getLogger(__name__)


async def deliver_reminder(bot: Bot, scheduler: AsyncIOScheduler, reminder_id: int):
    """Send an active reminder and retry after transient delivery failures."""
    session = get_session()
    try:
        reminder = session.query(Reminder).filter(
            Reminder.id == reminder_id,
            Reminder.status == ReminderStatus.ACTIVE,
        ).first()
        if reminder is None:
            return

        chat_id = reminder.group_id or reminder.user_id
        text = reminder.text
    finally:
        session.close()

    try:
        await bot.send_message(chat_id, f"⏰ Reminder: {text}")
    except Exception:
        logger.exception("Failed to deliver reminder %s; retrying in one minute", reminder_id)
        scheduler.add_job(
            deliver_reminder,
            trigger="date",
            run_date=datetime.now(timezone.utc) + timedelta(minutes=1),
            args=[bot, scheduler, reminder_id],
            id=f"reminder_{reminder_id}",
            replace_existing=True,
            misfire_grace_time=None,
        )
        return

    session = get_session()
    try:
        reminder = session.query(Reminder).filter(
            Reminder.id == reminder_id,
            Reminder.status == ReminderStatus.ACTIVE,
        ).first()
        if reminder is not None:
            reminder.status = ReminderStatus.COMPLETED
            reminder.completed_at = datetime.utcnow()
            session.commit()
    finally:
        session.close()


def schedule_reminder(bot: Bot, scheduler: AsyncIOScheduler, reminder_id: int, scheduled_at: datetime):
    """Schedule one reminder for delivery."""
    scheduler.add_job(
        deliver_reminder,
        trigger="date",
        run_date=scheduled_at.replace(tzinfo=timezone.utc),
        args=[bot, scheduler, reminder_id],
        id=f"reminder_{reminder_id}",
        replace_existing=True,
        misfire_grace_time=None,
    )


def schedule_pending_reminders(bot: Bot, scheduler: AsyncIOScheduler):
    """Restore active reminders from the database after startup."""
    session = get_session()
    try:
        reminders = session.query(Reminder).filter(
            Reminder.status == ReminderStatus.ACTIVE,
        ).all()
        for reminder in reminders:
            schedule_reminder(bot, scheduler, reminder.id, reminder.scheduled_at)
        logger.info("Restored %d pending reminders", len(reminders))
    finally:
        session.close()


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
        'max_instances': 1,
        'misfire_grace_time': None,
    }
    
    scheduler = AsyncIOScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults
    )
    
    scheduler.start()
    logger.info("Scheduler initialized and started")
    
    return scheduler
