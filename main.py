import logging
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import settings
from database import init_db
from bot.scheduler import init_scheduler
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
    
    # Start polling
    logger.info("Bot started. Polling for updates...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
