from aiogram import Router, types
from aiogram.filters import Command
import logging

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    """Handle /start command."""
    await message.answer(
        "🤖 Welcome to Focus Reminder Bot!\n\n"
        "I help you with three things:\n\n"
        "💤 **AFK** - Mark yourself as unavailable\n"
        "⏰ **Reminders** - Set reminders for later\n"
        "📚 **Focus Mode** - Self-discipline study sessions\n\n"
        "Commands:\n"
        "/afk [reason] - Set AFK status\n"
        "/remind [time] [task] - Set a reminder\n"
        "/focus [duration] [goal] - Start focus mode\n"
        "/help - Show all commands",
        parse_mode="Markdown"
    )


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Handle /help command."""
    help_text = """🤖 **Focus Reminder Bot - Complete Guide**

💤 **AFK SYSTEM**
/afk [reason] - Mark yourself as AFK
/unafk - Remove AFK status
Example: /afk sleeping

⏰ **REMINDER SYSTEM**
/remind [time] [task] - Set a reminder
/reminders - List all reminders
/timezone - Set your timezone
Examples:
  /remind 2h study
  /remind 30m drink water
  /remind 8pm call mom

📚 **FOCUS MODE**
/focus [duration] [goal] - Start a focus session
/focusstats - View your focus statistics
/focusoff - End current focus session
/focuspause - Pause focus session
/focusresume - Resume focus session
Examples:
  /focus 4h studying
  /focus 2h work
    """
    await message.answer(help_text, parse_mode="Markdown")
