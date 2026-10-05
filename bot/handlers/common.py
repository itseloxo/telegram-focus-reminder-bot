from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
import logging
import re

from config import settings
from bot.webapp import normalize_webapp_url
logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    """Handle /start command."""
    payload = (message.text or "").split(maxsplit=1)
    if (
        len(payload) == 2
        and message.chat.type == "private"
        and (match := re.fullmatch(r"famigo_(-?\d+)", payload[1]))
    ):
        group_id = int(match.group(1))
        try:
            member = await message.bot.get_chat_member(group_id, message.from_user.id)
            if member.status in {"left", "kicked"} or (
                member.status == "restricted" and not member.is_member
            ):
                await message.answer("You need to be a current member of that group to open its Famigo community.")
                return
        except Exception:
            logger.exception("Could not verify group membership for Mini App deep link")
            await message.answer("I couldn't verify your membership. Make sure Famigo is installed in that group and try again.")
            return

        webapp_url = normalize_webapp_url(settings.webapp_url)
        if not webapp_url:
            await message.answer("Famigo's Mini App is not configured yet. Ask the bot admin to set WEBAPP_URL in Railway.")
            return
        await message.answer(
            "Open your group's Famigo community. Profiles and activity here are only for this group.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="Open Famigo",
                    web_app=WebAppInfo(url=f"{webapp_url}?group_id={group_id}"),
                )
            ]]),
        )
        return

    await message.answer(
        "🤖 Welcome to Focus Reminder Bot!\n\n"
        "I can help with:\n\n"
        "🤝 **Famigo** - Build voluntary connections in your group\n"
        "💤 **AFK** - Mark yourself as unavailable\n"
        "⏰ **Reminders** - Set reminders for later\n"
        "📚 **Focus Mode** - Self-discipline study sessions\n\n"
        "Commands:\n"
        "/famigo - Show social features\n"
        "/profile - View your group profile\n"
        "/discover - Find people with shared interests\n"
        "/connect - Request a connection\n"
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
  /remind 1d submit assignment

📚 **FOCUS MODE**
/focus [duration] [goal] - Start a focus session
/focusstats - View your focus statistics
/focusoff - End current focus session
Examples:
  /focus 4h studying
  /focus 2h work
    """
    await message.answer(help_text, parse_mode="Markdown")
