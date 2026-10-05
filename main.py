import logging
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage
from config import settings
from database import init_db
from bot.scheduler import init_scheduler, schedule_pending_reminders
from bot.handlers import afk, reminder, focus, common, famigo

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
    dp.include_router(common.router)
    dp.include_router(afk.router)
    dp.include_router(reminder.router)
    dp.include_router(focus.router)
    dp.include_router(famigo.router)

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
        BotCommand(command="famigo", description="Open Famigo social features"),
        BotCommand(command="profile", description="View your group profile"),
        BotCommand(command="setprofile", description="Edit your group profile"),
        BotCommand(command="interests", description="View your interests"),
        BotCommand(command="addinterest", description="Add a group interest"),
        BotCommand(command="removeinterest", description="Remove a group interest"),
        BotCommand(command="currently", description="Share your current activity"),
        BotCommand(command="watching", description="Share what you are watching"),
        BotCommand(command="listening", description="Share what you are listening to"),
        BotCommand(command="reading", description="Share what you are reading"),
        BotCommand(command="playing", description="Share what you are playing"),
        BotCommand(command="addfavorite", description="Add a group favorite"),
        BotCommand(command="favorites", description="View your group favorites"),
        BotCommand(command="removefavorite", description="Remove a group favorite"),
        BotCommand(command="mood", description="Set or clear your group mood"),
        BotCommand(command="discover", description="Discover group members"),
        BotCommand(command="random", description="Meet a random group member"),
        BotCommand(command="connect", description="Request a connection"),
        BotCommand(command="relationships", description="View confirmed connections"),
        BotCommand(command="stats", description="View your group stats"),
        BotCommand(command="addsocial", description="Save a private social link"),
        BotCommand(command="socials", description="Privately view your social links"),
        BotCommand(command="deletesocial", description="Delete a saved social link"),
        BotCommand(command="privacy", description="View profile privacy options"),
        BotCommand(command="setprofileprivacy", description="Change profile visibility"),
        BotCommand(command="discoverability", description="Manage global profile discovery"),
        BotCommand(command="connectionrequests", description="Manage global connection requests"),
        BotCommand(command="export", description="Privately export group data"),
        BotCommand(command="deleteprofile", description="Delete your group profile"),
        BotCommand(command="mygroups", description="Privately list your group profiles"),
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
