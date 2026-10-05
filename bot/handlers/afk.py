from aiogram import Router, types
from aiogram.filters import Command
from database import get_session, User, AFK
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("afk"))
async def cmd_afk(message: types.Message):
    """Handle /afk command - Set user as AFK."""
    
    # Get reason from command
    args = message.text.split(maxsplit=1)
    reason = args[1] if len(args) > 1 else None
    
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
        
        # Set AFK status
        afk_status = session.query(AFK).filter(AFK.user_id == message.from_user.id).first()
        if not afk_status:
            afk_status = AFK(user_id=message.from_user.id)
            session.add(afk_status)
        
        afk_status.reason = reason
        afk_status.set_at = datetime.utcnow()
        
        session.commit()
        
        # Confirm to user
        response = f"💤 You're now AFK"
        if reason:
            response += f"\nReason: {reason}"
        
        await message.answer(response)
        logger.info(f"User {message.from_user.id} set AFK with reason: {reason}")
        
    except Exception as e:
        logger.error(f"Error setting AFK: {e}")
        await message.answer("❌ Error setting AFK status. Please try again.")
    finally:
        session.close()


@router.message(Command("unafk"))
async def cmd_unafk(message: types.Message):
    """Handle /unafk command - Remove AFK status."""
    
    session = get_session()
    
    try:
        afk_status = session.query(AFK).filter(AFK.user_id == message.from_user.id).first()
        
        if afk_status:
            session.delete(afk_status)
            session.commit()
            await message.answer("✅ You're no longer AFK")
            logger.info(f"User {message.from_user.id} removed AFK status")
        else:
            await message.answer("ℹ️ You're not currently AFK")
            
    except Exception as e:
        logger.error(f"Error removing AFK: {e}")
        await message.answer("❌ Error removing AFK status. Please try again.")
    finally:
        session.close()
