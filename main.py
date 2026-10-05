import logging
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage
from config import settings
from database import init_db
from bot.scheduler import init_scheduler, schedule_pending_reminders
from bot.handlers import afk, reminder, focus, common

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Initialize and run the bot."""
    
    # Initialize database
    logger.info("Initializing database...")
    init_db()
    
    # Initialize Telegram bot
    logger.info("Initializing Telegram bot...")
    bot = Bot(token=settings.bot_token)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Initialize scheduler for reminders and focus timers
    logger.info("Initializing scheduler...")
    scheduler = init_scheduler()
    dp["scheduler"] = scheduler
    
    # Register handlers
    logger.info("Registering handlers...")
    
    # Common handlers
    dp.include_router(common.router)
    
    # AFK handlers
    dp.include_router(afk.router)
    
    # Reminder handlers
    dp.include_router(reminder.router)
    
    # Focus handlers
    dp.include_router(focus.router)

    await bot.set_my_commands([
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="help", description="Show available commands"),
        BotCommand(command="afk", description="Set your AFK status"),
        BotCommand(command="unafk", description="Remove your AFK status"),
        BotCommand(command="remind", description="Set a reminder"),
        BotCommand(command="reminders", description="List your reminders"),
        BotCommand(command="timezone", description="Set your timezone"),
        BotCommand(command="focus", description="Start a focus session"),
        BotCommand(command="focusoff", description="End your focus session"),
        BotCommand(command="focusstats", description="Show your focus statistics"),
    ])

    # Restore active reminders from the database after every bot restart.
    try:
        schedule_pending_reminders(bot, scheduler)
    except Exception:
        await bot.session.close()
        scheduler.shutdown()
        raise

    # Start polling
    logger.info("Bot started. Polling for updates...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
