from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from database import get_session, User, Reminder, ReminderStatus, ReminderRecurrence
from datetime import datetime, timedelta
import re
import logging

logger = logging.getLogger(__name__)

router = Router()


def parse_time_offset(time_str: str):
    """Parse time offset like '2h', '30m', '1d'."""
    match = re.match(r'(\d+)([mhd])', time_str.lower())
    if not match:
        return None
    
    amount, unit = int(match.group(1)), match.group(2)
    
    if unit == 'm':
        return timedelta(minutes=amount)
    elif unit == 'h':
        return timedelta(hours=amount)
    elif unit == 'd':
        return timedelta(days=amount)
    
    return None


@router.message(Command("remind"))
async def cmd_remind(message: types.Message):
    """Handle /remind command - Set a reminder."""
    
    # Parse command: /remind [time] [task]
    args = message.text.split(maxsplit=2)
    
    if len(args) < 3:
        await message.answer(
            "⏰ Usage: /remind [time] [task]\n\n"
            "Examples:\n"
            "/remind 2h study\n"
            "/remind 30m drink water\n"
            "/remind 8pm call mom\n"
            "/remind tomorrow 7pm assignment"
        )
        return
    
    time_str = args[1]
    task = args[2]
    
    # Parse time
    time_offset = parse_time_offset(time_str)
    if not time_offset:
        await message.answer("⏰ Invalid time format. Use: 30m, 2h, 1d")
        return
    
    scheduled_at = datetime.utcnow() + time_offset
    
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
        
        # Create reminder
        reminder = Reminder(
            user_id=message.from_user.id,
            group_id=message.chat.id if message.chat.type != "private" else None,
            text=task,
            scheduled_at=scheduled_at,
            recurrence=ReminderRecurrence.ONCE,
            status=ReminderStatus.ACTIVE
        )
        session.add(reminder)
        session.commit()
        
        # Calculate display time
        time_delta = scheduled_at - datetime.utcnow()
        hours = time_delta.seconds // 3600
        minutes = (time_delta.seconds % 3600) // 60
        
        time_display = f"in {hours}h {minutes}m" if hours > 0 else f"in {minutes}m"
        
        await message.answer(
            f"⏰ Reminder set!\n\n"
            f"📝 {task}\n"
            f"⏱️ {time_display}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✏️ Edit", callback_data=f"edit_reminder_{reminder.id}")],
                [InlineKeyboardButton(text="🗑 Delete", callback_data=f"del_reminder_{reminder.id}")]
            ])
        )
        
        logger.info(f"Reminder created for user {message.from_user.id}: {task} at {scheduled_at}")
        
    except Exception as e:
        logger.error(f"Error creating reminder: {e}")
        await message.answer("❌ Error creating reminder. Please try again.")
    finally:
        session.close()


@router.message(Command("reminders"))
async def cmd_reminders(message: types.Message):
    """Handle /reminders command - List user's reminders."""
    
    session = get_session()
    
    try:
        reminders = session.query(Reminder).filter(
            Reminder.user_id == message.from_user.id,
            Reminder.status == ReminderStatus.ACTIVE
        ).order_by(Reminder.scheduled_at).all()
        
        if not reminders:
            await message.answer("ℹ️ You have no active reminders.")
            return
        
        text = "⏰ **YOUR REMINDERS**\n\n"
        
        for i, reminder in enumerate(reminders, 1):
            time_delta = reminder.scheduled_at - datetime.utcnow()
            if time_delta.total_seconds() > 0:
                hours = int(time_delta.total_seconds() // 3600)
                minutes = int((time_delta.total_seconds() % 3600) // 60)
                if hours > 0:
                    time_str = f"{hours}h {minutes}m"
                else:
                    time_str = f"{minutes}m"
            else:
                time_str = "Now"
            
            text += f"{i}. 📝 {reminder.text}\n"
            text += f"   ⏱️ {time_str}\n\n"
        
        await message.answer(text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error fetching reminders: {e}")
        await message.answer("❌ Error fetching reminders.")
    finally:
        session.close()


@router.message(Command("timezone"))
async def cmd_timezone(message: types.Message):
    """Handle /timezone command - Set user's timezone."""
    
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer(
            "🌍 Usage: /timezone [timezone]\n\n"
            "Examples: UTC, US/Eastern, Europe/London, Asia/Tokyo"
        )
        return
    
    timezone = args[1]
    
    session = get_session()
    
    try:
        user = session.query(User).filter(User.user_id == message.from_user.id).first()
        if not user:
            user = User(
                user_id=message.from_user.id,
                username=message.from_user.username,
                timezone=timezone
            )
            session.add(user)
        else:
            user.timezone = timezone
        
        session.commit()
        await message.answer(f"✅ Timezone set to {timezone}")
        
    except Exception as e:
        logger.error(f"Error setting timezone: {e}")
        await message.answer("❌ Error setting timezone. Please check the timezone format.")
    finally:
        session.close()
