from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from database import (
    get_session, User, FocusSession, FocusStatistics, FocusStatus, 
    FocusWarningStyle, FocusVisibility
)
from datetime import datetime, timedelta
import re
import logging

logger = logging.getLogger(__name__)

router = Router()


def parse_duration(duration_str: str):
    """Parse duration like '4h', '30m', '1d'."""
    match = re.match(r'(\d+)([mhd])', duration_str.lower())
    if not match:
        return None
    
    amount, unit = int(match.group(1)), match.group(2)
    
    if unit == 'm':
        return amount
    elif unit == 'h':
        return amount * 60
    elif unit == 'd':
        return amount * 60 * 24
    
    return None


@router.message(Command("focus"))
async def cmd_focus(message: types.Message):
    """Handle /focus command - Start a focus session."""
    
    # Parse command: /focus [duration] [goal]
    args = message.text.split(maxsplit=2)
    
    if len(args) < 2:
        await message.answer(
            "📚 Usage: /focus [duration] [goal]\n\n"
            "Examples:\n"
            "/focus 4h studying\n"
            "/focus 2h work\n"
            "/focus 90m assignment"
        )
        return
    
    duration_str = args[1]
    goal = args[2] if len(args) > 2 else "Focus"
    
    # Parse duration
    duration_minutes = parse_duration(duration_str)
    if not duration_minutes:
        await message.answer("⏰ Invalid duration format. Use: 30m, 2h, 1d")
        return
    
    session = get_session()
    
    try:
        # Get or create user
        user = session.query(User).filter(User.user_id == message.from_user.id).first()
        if not user:
            user = User(
                user_id=message.from_user.id,
                username=message.from_user.username
            )
            session.add(user)
            session.flush()
        
        # Check for existing focus session
        existing = session.query(FocusSession).filter(
            FocusSession.user_id == message.from_user.id,
            FocusSession.status == FocusStatus.ACTIVE
        ).first()
        
        if existing:
            await message.answer(
                "⚠️ You already have an active focus session.\n"
                "Use /focusoff to end it first."
            )
            return
        
        # Create focus session with default settings (PRIVATE mode)
        ends_at = datetime.utcnow() + timedelta(minutes=duration_minutes)
        
        focus_session = FocusSession(
            user_id=message.from_user.id,
            group_id=message.chat.id if message.chat.type != "private" else None,
            ends_at=ends_at,
            duration_minutes=duration_minutes,
            mode=goal,
            status=FocusStatus.ACTIVE,
            warning_style=FocusWarningStyle.GENTLE,
            visibility=FocusVisibility.PRIVATE,
            warning_cooldown_minutes=10,
            max_warnings=3
        )
        session.add(focus_session)
        session.commit()
        
        # Show intensity level selection
        await message.answer(
            f"📚 **Focus Mode**\n\n"
            f"You're committing to {duration_minutes // 60}h {duration_minutes % 60}m\n"
            f"Goal: {goal}\n\n"
            f"How strict should I be?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="😌 Gentle", callback_data=f"focus_style_gentle_{focus_session.id}"),
                    InlineKeyboardButton(text="😤 Strict", callback_data=f"focus_style_strict_{focus_session.id}")
                ],
                [
                    InlineKeyboardButton(text="💀 Brutal", callback_data=f"focus_style_brutal_{focus_session.id}")
                ],
                [
                    InlineKeyboardButton(text="🛑 Cancel", callback_data=f"focus_cancel_{focus_session.id}")
                ]
            ])
        )
        
        logger.info(f"Focus session created for user {message.from_user.id}: {goal} for {duration_minutes}m")
        
    except Exception as e:
        logger.error(f"Error creating focus session: {e}")
        await message.answer("❌ Error creating focus session. Please try again.")
    finally:
        session.close()


@router.callback_query(F.data.startswith("focus_style_"))
async def cb_focus_style(callback: types.CallbackQuery):
    """Handle focus intensity selection."""
    
    parts = callback.data.split("_")
    style = parts[2]
    session_id = int(parts[3])
    
    session = get_session()
    
    try:
        focus_session = session.query(FocusSession).filter(FocusSession.id == session_id).first()
        
        if not focus_session:
            await callback.answer("❌ Focus session not found")
            return
        
        focus_session.warning_style = FocusWarningStyle(style)
        session.commit()
        
        style_emoji = {"gentle": "😌", "strict": "😤", "brutal": "💀"}[style]
        
        await callback.message.edit_text(
            f"📚 **Focus Mode Activated**\n\n"
            f"Goal: {focus_session.mode}\n"
            f"Duration: {focus_session.duration_minutes // 60}h {focus_session.duration_minutes % 60}m\n"
            f"Style: {style_emoji} {style.capitalize()}\n"
            f"Visibility: 🔒 Private\n\n"
            f"⏳ Ends at: {focus_session.ends_at.strftime('%I:%M %p')}\n\n"
            f"Good luck! 📚",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="⏸ Pause", callback_data=f"focus_pause_{focus_session.id}"),
                    InlineKeyboardButton(text="🛑 End", callback_data=f"focus_end_{focus_session.id}")
                ]
            ])
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error updating focus style: {e}")
        await callback.answer("❌ Error updating focus style")
    finally:
        session.close()


@router.callback_query(F.data.startswith("focus_end_"))
async def cb_focus_end(callback: types.CallbackQuery):
    """Handle focus session end."""
    
    session_id = int(callback.data.split("_")[2])
    session = get_session()
    
    try:
        focus_session = session.query(FocusSession).filter(FocusSession.id == session_id).first()
        
        if not focus_session:
            await callback.answer("❌ Focus session not found")
            return
        
        focus_session.status = FocusStatus.CANCELLED
        focus_session.completed_at = datetime.utcnow()
        session.commit()
        
        await callback.message.edit_text("🛑 Focus session ended.")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error ending focus session: {e}")
        await callback.answer("❌ Error ending focus session")
    finally:
        session.close()


@router.message(Command("focusoff"))
async def cmd_focusoff(message: types.Message):
    """Handle /focusoff command - End focus session."""
    
    session = get_session()
    
    try:
        focus_session = session.query(FocusSession).filter(
            FocusSession.user_id == message.from_user.id,
            FocusSession.status == FocusStatus.ACTIVE
        ).first()
        
        if not focus_session:
            await message.answer("ℹ️ You don't have an active focus session.")
            return
        
        focus_session.status = FocusStatus.CANCELLED
        focus_session.completed_at = datetime.utcnow()
        session.commit()
        
        await message.answer("🛑 Focus session ended.")
        
    except Exception as e:
        logger.error(f"Error ending focus session: {e}")
        await message.answer("❌ Error ending focus session.")
    finally:
        session.close()


@router.message(Command("focusstats"))
async def cmd_focusstats(message: types.Message):
    """Handle /focusstats command - Show focus statistics."""
    
    session = get_session()
    
    try:
        stats = session.query(FocusStatistics).filter(
            FocusStatistics.user_id == message.from_user.id
        ).first()
        
        if not stats:
            await message.answer("📚 You haven't started any focus sessions yet.\n\nUse /focus to begin!")
            return
        
        hours = stats.total_focus_minutes // 60
        minutes = stats.total_focus_minutes % 60
        
        longest_hours = stats.longest_session_minutes // 60
        longest_minutes = stats.longest_session_minutes % 60
        
        text = (
            f"📚 **YOUR FOCUS STATS**\n\n"
            f"Sessions: {stats.total_sessions}\n"
            f"Completed: {stats.completed_sessions}\n"
            f"Cancelled: {stats.cancelled_sessions}\n\n"
            f"Total focus time: {hours}h {minutes}m\n"
            f"🔥 Longest session: {longest_hours}h {longest_minutes}m\n"
            f"🔥 Current streak: {stats.current_streak} days"
        )
        
        await message.answer(text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error fetching focus stats: {e}")
        await message.answer("❌ Error fetching statistics.")
    finally:
        session.close()
