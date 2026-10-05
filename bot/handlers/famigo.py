from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from database import (
    get_session, User, GroupConfig, GroupRole, GroupBan, UserRole,
    FamigoProfile, UserInterest, Connection, Favorite, CurrentlyInto,
    MoodStatus, SocialLink, Confession, Achievement, CommunityEvent,
    GroupJoinHistory, UserSettings, FamilyTreeNode, FamilyTreeRelation
)
from datetime import datetime
import logging
import random

logger = logging.getLogger(__name__)
router = Router()


# ----------------------------
# Helpers
# ----------------------------
def group_id(message: types.Message):
    return message.chat.id


def get_or_create_user(session, user_id, username, first_name):
    user = session.query(User).filter(User.user_id == user_id).first()
    if not user:
        user = User(user_id=user_id, username=username)
        session.add(user)
        session.flush()
    return user


def get_or_create_profile(session, user_id, gid, first_name):
    profile = session.query(FamigoProfile).filter(
        FamigoProfile.user_id == user_id,
        FamigoProfile.group_id == gid
    ).first()
    if not profile:
        profile = FamigoProfile(
            user_id=user_id,
            group_id=gid,
            display_name=first_name or "Member",
            reputation=0,
            level=1,
            visibility="public"
        )
        session.add(profile)
        session.flush()
    return profile


def ensure_group_config(session, gid, owner_id):
    cfg = session.query(GroupConfig).filter(GroupConfig.group_id == gid).first()
    if not cfg:
        cfg = GroupConfig(
            group_id=gid,
            owner_id=owner_id,
            group_name=f"Group {gid}",
            group_description="Famigo community"
        )
        session.add(cfg)
        session.flush()
    return cfg


def user_has_role(session, user_id, gid, *roles):
    role = session.query(GroupRole).filter(
        GroupRole.user_id == user_id,
        GroupRole.group_id == gid
    ).first()
    if not role:
        return False
    return role.role.value in [r.value if hasattr(r, 'value') else str(r) for r in roles]


# ----------------------------
# Famigo main menu
# ----------------------------
@router.message(Command("famigo"))
async def cmd_famigo(message: types.Message):
    await message.answer(
        "🤝 **Famigo Menu**",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 Profile", callback_data="menu_profile")],
            [InlineKeyboardButton(text="❤️ Interests", callback_data="menu_interests")],
            [InlineKeyboardButton(text="🤝 Connections", callback_data="menu_connections")],
            [InlineKeyboardButton(text="🌳 Family Tree", callback_data="menu_family")],
            [InlineKeyboardButton(text="🔍 Discover", callback_data="menu_discover")],
            [InlineKeyboardButton(text="💌 Confess", callback_data="menu_confess")],
            [InlineKeyboardButton(text="📊 Stats", callback_data="menu_stats")],
            [InlineKeyboardButton(text="⚙️ Settings", callback_data="menu_settings")],
        ])
    )


# ----------------------------
# Profile system
# ----------------------------
@router.message(Command("profile"))
@router.message(Command("me"))
@router.message(Command("myprofile"))
async def cmd_profile(message: types.Message):
    session = get_session()
    try:
        user = get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        profile = get_or_create_profile(session, user.user_id, group_id(message), message.from_user.first_name)

        interests = session.query(UserInterest).filter(
            UserInterest.user_id == user.user_id,
            UserInterest.group_id == group_id(message)
        ).all()
        connections = session.query(Connection).filter(
            Connection.user_id == user.user_id,
            Connection.group_id == group_id(message),
            Connection.status == "accepted"
        ).all()
        socials = session.query(SocialLink).filter(SocialLink.user_id == user.user_id).all()

        interest_text = " • ".join([i.interest for i in interests]) if interests else "No interests yet"
        social_text = " • ".join([s.platform for s in socials[:3]]) if socials else "No socials yet"

        text = (
            f"╭─────────────────╮\n"
            f"👤 {profile.display_name or message.from_user.first_name}\n"
            f"╰─────────────────╯\n\n"
            f"📍 {profile.city or 'Unknown city'}\n"
            f"💼 {profile.profession or 'Not shared'}\n\n"
            f"🎨 Hobbies\n{interest_text}\n\n"
            f"📝 About\n{profile.bio or 'No bio yet'}\n\n"
            f"✨ Fun fact\n{profile.fun_fact or 'Not shared'}\n\n"
            f"🏆 Level {profile.level} | ⭐ {profile.reputation} Reputation\n"
            f"🤝 {len(connections)} Connections\n\n"
            f"🔗 Socials\n{social_text}"
        )

        session.commit()
        await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Edit", callback_data="edit_profile")],
            [InlineKeyboardButton(text="❤️ Interests", callback_data="show_interests")],
            [InlineKeyboardButton(text="🔗 Socials", callback_data="show_socials")],
            [InlineKeyboardButton(text="🤝 Connections", callback_data="show_connections")],
            [InlineKeyboardButton(text="🏆 Achievements", callback_data="show_achievements")]
        ]))
    except Exception as e:
        logger.error(f"Error showing profile: {e}")
        await message.answer("❌ Error loading profile.")
    finally:
        session.close()


@router.message(Command("setprofile"))
@router.message(Command("editprofile"))
async def cmd_setprofile(message: types.Message):
    await message.answer(
        "👤 **Profile Setup**\n\n"
        "Reply in this format:\n"
        "city|profession|bio|fun_fact|languages\n\n"
        "Example:\n"
        "Delhi|Designer|I love meeting interesting people|I can draw with both hands|Hindi, English",
        parse_mode="Markdown"
    )


@router.message(Command("intro"))
async def cmd_intro(message: types.Message):
    session = get_session()
    try:
        user = get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        profile = session.query(FamigoProfile).filter(
            FamigoProfile.user_id == user.user_id,
            FamigoProfile.group_id == group_id(message)
        ).first()

        if not profile:
            await message.answer("👋 You don't have a profile yet. Use /setprofile first.")
            return

        text = (
            f"👋 **Meet {profile.display_name or message.from_user.first_name}**\n\n"
            f"📍 {profile.city or 'Unknown city'}\n"
            f"💼 {profile.profession or 'Not shared'}\n\n"
            f"📝 About:\n{profile.bio or 'No bio yet'}\n\n"
            f"✨ Fun fact:\n{profile.fun_fact or 'Not shared'}"
        )
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in /intro: {e}")
        await message.answer("❌ Error loading intro.")
    finally:
        session.close()


@router.message(Command("deleteprofile"))
async def cmd_deleteprofile(message: types.Message):
    session = get_session()
    try:
        profile = session.query(FamigoProfile).filter(
            FamigoProfile.user_id == message.from_user.id,
            FamigoProfile.group_id == group_id(message)
        ).first()
        if profile:
            session.delete(profile)
            session.commit()
        await message.answer("🗑 Your profile has been removed from this group.")
    except Exception as e:
        logger.error(f"Error deleting profile: {e}")
        await message.answer("❌ Error deleting profile.")
    finally:
        session.close()


# ----------------------------
# Interests system
# ----------------------------
@router.message(Command("interests"))
async def cmd_interests(message: types.Message):
    session = get_session()
    try:
        interests = session.query(UserInterest).filter(
            UserInterest.user_id == message.from_user.id,
            UserInterest.group_id == group_id(message)
        ).all()

        if not interests:
            await message.answer("❤️ You have no interests yet. Use /addinterest [interest] to add one!")
            return

        text = "❤️ **Your Interests**\n\n"
        for i in interests:
            emoji = i.interest_emoji or "•"
            text += f"{emoji} {i.interest}\n"
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error listing interests: {e}")
        await message.answer("❌ Error loading interests.")
    finally:
        session.close()


@router.message(Command("addinterest"))
async def cmd_addinterest(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❤️ Usage: /addinterest [interest name]")
        return
    session = get_session()
    try:
        user = get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        interest = UserInterest(
            user_id=user.user_id,
            group_id=group_id(message),
            interest=args[1],
            is_custom=True
        )
        session.add(interest)
        session.commit()
        await message.answer(f"❤️ Added interest: **{args[1]}**", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error adding interest: {e}")
        await message.answer("❌ Error adding interest.")
    finally:
        session.close()


@router.message(Command("similar"))
@router.message(Command("match"))
@router.message(Command("peoplelike"))
async def cmd_similar(message: types.Message):
    session = get_session()
    try:
        user = get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        my_interests = session.query(UserInterest).filter(
            UserInterest.user_id == user.user_id,
            UserInterest.group_id == group_id(message)
        ).all()

        if not my_interests:
            await message.answer("❤️ Add some interests first to find matches!")
            return

        my_interest_names = {i.interest.lower() for i in my_interests}
        matches = {}

        all_profiles = session.query(FamigoProfile).filter(FamigoProfile.group_id == group_id(message)).all()
        for profile in all_profiles:
            if profile.user_id == user.user_id:
                continue
            other_interests = session.query(UserInterest).filter(
                UserInterest.user_id == profile.user_id,
                UserInterest.group_id == group_id(message)
            ).all()
            common = [i.interest for i in other_interests if i.interest.lower() in my_interest_names]
            if common:
                matches[profile.display_name or f"User {profile.user_id}"] = common

        if not matches:
            await message.answer("❤️ No matches found yet. Keep exploring!")
            return

        text = "❤️ **People Who Share Your Interests**\n\n"
        for i, (name, common) in enumerate(list(matches.items())[:10], 1):
            text += f"{i}. {name}\n   {', '.join(common)}\n\n"
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error finding similar people: {e}")
        await message.answer("❌ Error finding similar people.")
    finally:
        session.close()


# ----------------------------
# Connection system
# ----------------------------
@router.message(Command("connections"))
@router.message(Command("relationships"))
async def cmd_relationships(message: types.Message):
    session = get_session()
    try:
        connections = session.query(Connection).filter(
            Connection.user_id == message.from_user.id,
            Connection.group_id == group_id(message),
            Connection.status == "accepted"
        ).all()

        if not connections:
            await message.answer("🤝 You have no approved connections yet.")
            return

        text = "🤝 **Your Connections**\n\n"
        for c in connections:
            rel_type = c.custom_relationship or c.relationship_type.value
            text += f"• {rel_type} (User {c.connected_user_id})\n"
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error listing relationships: {e}")
        await message.answer("❌ Error loading relationships.")
    finally:
        session.close()


@router.message(Command("connect"))
async def cmd_connect(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("🤝 Usage: /connect [user_id_or_username] [relationship]")
        return
    session = get_session()
    try:
        target = args[1]
        user = get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        await message.answer(
            f"🤝 Connection request sent to {target}.\nIt must be confirmed before approval."
        )
    except Exception as e:
        logger.error(f"Error creating connection: {e}")
        await message.answer("❌ Error creating connection request.")
    finally:
        session.close()


# ----------------------------
# Family tree system
# ----------------------------
@router.message(Command("family"))
@router.message(Command("familytree"))
async def cmd_familytree(message: types.Message):
    session = get_session()
    try:
        nodes = session.query(FamilyTreeNode).filter(
            FamilyTreeNode.group_id == group_id(message),
            FamilyTreeNode.is_visible == True
        ).all()

        if not nodes:
            await message.answer("🌳 No family tree data yet for this group. Add a relation with /addfamily [user_id] [relation].")
            return

        text = "🌳 **Family Tree**\n\n"
        for node in nodes[:10]:
            text += f"• User {node.user_id} -> Parent: {node.parent_id or 'None'}\n"
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error generating family tree: {e}")
        await message.answer("❌ Error loading family tree.")
    finally:
        session.close()


@router.message(Command("addfamily"))
async def cmd_addfamily(message: types.Message):
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("🌳 Usage: /addfamily [user_id] [relation_type]")
        return
    session = get_session()
    try:
        target_user_id = int(args[1])
        relation_type = args[2]

        family = FamilyTreeRelation(
            group_id=group_id(message),
            user1_id=message.from_user.id,
            user2_id=target_user_id,
            relation_type=relation_type,
            user1_confirmed=True,
            user2_confirmed=False,
            visibility="public"
        )
        session.add(family)
        session.commit()
        await message.answer(f"🌳 Family relation created: {relation_type} with user {target_user_id}.")
    except Exception as e:
        logger.error(f"Error adding family relation: {e}")
        await message.answer("❌ Error adding family relation.")
    finally:
        session.close()


# ----------------------------
# Social links
# ----------------------------
@router.message(Command("addsocial"))
async def cmd_addsocial(message: types.Message):
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("🔗 Usage: /addsocial [platform] [username_or_url]")
        return

    platform = args[1]
    value = args[2]
    session = get_session()
    try:
        user = get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        link = SocialLink(
            user_id=user.user_id,
            platform=platform,
            username_or_url=value,
            display_name=platform
        )
        session.add(link)
        session.commit()
        await message.answer(f"🔗 Social link added: {platform} -> {value}")
    except Exception as e:
        logger.error(f"Error adding social link: {e}")
        await message.answer("❌ Error adding social link.")
    finally:
        session.close()


@router.message(Command("socials"))
async def cmd_socials(message: types.Message):
    session = get_session()
    try:
        links = session.query(SocialLink).filter(SocialLink.user_id == message.from_user.id).all()
        if not links:
            await message.answer("🔗 You have not added any social links yet.")
            return
        text = "🔗 **Your Socials**\n\n"
        for link in links:
            text += f"• {link.platform}: {link.username_or_url}\n"
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error listing socials: {e}")
        await message.answer("❌ Error loading socials.")
    finally:
        session.close()


# ----------------------------
# Activities and favorites
# ----------------------------
@router.message(Command("watching"))
async def cmd_watching(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("🎬 Usage: /watching [title]")
        return
    session = get_session(); 
    try:
        user = get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        activity = CurrentlyInto(user_id=user.user_id, group_id=group_id(message), category="Watching", value=args[1])
        session.add(activity)
        session.commit()
        await message.answer(f"🎬 You are watching: **{args[1]}**", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error setting watching: {e}")
    finally:
        session.close()


@router.message(Command("listening"))
async def cmd_listening(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("🎵 Usage: /listening [artist or song]")
        return
    session = get_session(); 
    try:
        user = get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        activity = CurrentlyInto(user_id=user.user_id, group_id=group_id(message), category="Listening", value=args[1])
        session.add(activity)
        session.commit()
        await message.answer(f"🎵 You are listening to: **{args[1]}**", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error setting listening: {e}")
    finally:
        session.close()


@router.message(Command("reading"))
async def cmd_reading(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("📚 Usage: /reading [book]")
        return
    session = get_session(); 
    try:
        user = get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        activity = CurrentlyInto(user_id=user.user_id, group_id=group_id(message), category="Reading", value=args[1])
        session.add(activity)
        session.commit()
        await message.answer(f"📚 You are reading: **{args[1]}**", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error setting reading: {e}")
    finally:
        session.close()


@router.message(Command("playing"))
async def cmd_playing(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("🎮 Usage: /playing [game]")
        return
    session = get_session(); 
    try:
        user = get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        activity = CurrentlyInto(user_id=user.user_id, group_id=group_id(message), category="Playing", value=args[1])
        session.add(activity)
        session.commit()
        await message.answer(f"🎮 You are playing: **{args[1]}**", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error setting playing: {e}")
    finally:
        session.close()


@router.message(Command("addfavorite"))
async def cmd_addfavorite(message: types.Message):
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("⭐ Usage: /addfavorite [category] [value]")
        return
    session = get_session(); 
    try:
        user = get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        favorite = Favorite(user_id=user.user_id, group_id=group_id(message), category=args[1], value=args[2])
        session.add(favorite)
        session.commit()
        await message.answer(f"⭐ Favorite added: **{args[1]} = {args[2]}**", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error adding favorite: {e}")
    finally:
        session.close()


@router.message(Command("favorites"))
async def cmd_favorites(message: types.Message):
    session = get_session(); 
    try:
        favs = session.query(Favorite).filter(Favorite.user_id == message.from_user.id, Favorite.group_id == group_id(message)).all()
        if not favs:
            await message.answer("⭐ No favorites added yet.")
            return
        text = "⭐ **Your Favorites**\n\n"
        for f in favs:
            text += f"• {f.category}: {f.value}\n"
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error listing favorites: {e}")
    finally:
        session.close()


# ----------------------------
# Mood system
# ----------------------------
@router.message(Command("mood"))
async def cmd_mood(message: types.Message):
    args = message.text.split(maxsplit=1)
    mood_value = args[1].lower() if len(args) > 1 else "chill"
    session = get_session()
    try:
        user = get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        mood = MoodStatus(user_id=user.user_id, group_id=group_id(message), custom_mood=mood_value, set_at=datetime.utcnow())
        session.add(mood)
        session.commit()
        await message.answer(f"😌 You are feeling: **{mood_value}**", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error setting mood: {e}")
        await message.answer("❌ Error setting mood.")
    finally:
        session.close()


# ----------------------------
# Reputation and achievements
# ----------------------------
@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    session = get_session()
    try:
        user = get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        profile = session.query(FamigoProfile).filter(
            FamigoProfile.user_id == user.user_id,
            FamigoProfile.group_id == group_id(message)
        ).first()
        if not profile:
            await message.answer("📊 No profile yet. Create one with /setprofile!")
            return

        connections = session.query(Connection).filter(
            Connection.user_id == user.user_id,
            Connection.group_id == group_id(message),
            Connection.status == "accepted"
        ).count()

        achievements = session.query(Achievement).filter(
            Achievement.user_id == user.user_id,
            Achievement.group_id == group_id(message)
        ).count()

        text = (
            f"📊 **{profile.display_name or message.from_user.first_name}'s Community Stats**\n\n"
            f"⭐ Reputation: {profile.reputation}\n"
            f"🏅 Level: {profile.level}\n"
            f"🤝 Connections: {connections}\n"
            f"🏆 Achievements: {achievements}\n"
            f"📅 Member since: {profile.joined_at.strftime('%d %B %Y') if profile.joined_at else 'Unknown'}"
        )
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error loading stats: {e}")
        await message.answer("❌ Error loading stats.")
    finally:
        session.close()


@router.message(Command("achievements"))
async def cmd_achievements(message: types.Message):
    await message.answer(
        "🏆 **Achievements**\n\n"
        "• 👋 First Introduction\n"
        "• 🤝 First Connection\n"
        "• ❤️ 10 Connections\n"
        "• 🎨 Interest Explorer\n"
        "• 🎬 Movie Buff\n"
        "• 🎵 Music Lover",
        parse_mode="Markdown"
    )


# ----------------------------
# Confession system
# ----------------------------
@router.message(Command("confess"))
async def cmd_confess(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("💌 Usage: /confess [message]")
        return

    session = get_session()
    try:
        user = get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        confession = Confession(
            user_id=user.user_id,
            group_id=group_id(message),
            confession_text=args[1],
            is_anonymous=True,
            status="active"
        )
        session.add(confession)
        session.commit()
        await message.answer("💌 Your anonymous confession was submitted to the group!")
    except Exception as e:
        logger.error(f"Error creating confession: {e}")
        await message.answer("❌ Error creating confession.")
    finally:
        session.close()


# ----------------------------
# Search and random
# ----------------------------
@router.message(Command("random"))
@router.message(Command("randomperson"))
@router.message(Command("meet"))
async def cmd_random(message: types.Message):
    session = get_session()
    try:
        profiles = session.query(FamigoProfile).filter(
            FamigoProfile.group_id == group_id(message),
            FamigoProfile.visibility != "hidden"
        ).all()

        if not profiles:
            await message.answer("👋 No one has a profile yet in this group.")
            return

        profile = random.choice(profiles)
        interests = session.query(UserInterest).filter(
            UserInterest.user_id == profile.user_id,
            UserInterest.group_id == group_id(message)
        ).limit(5).all()
        interest_text = ", ".join([i.interest for i in interests]) if interests else "No interests shared"

        text = (
            f"👋 **Meet Someone From The Community**\n\n"
            f"👤 {profile.display_name or 'Member'}\n"
            f"📍 {profile.city or 'Unknown city'}\n"
            f"❤️ {interest_text}\n\n"
            f"📝 {profile.bio or 'New here'}"
        )
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error meeting random member: {e}")
        await message.answer("❌ Error selecting member.")
    finally:
        session.close()


@router.message(Command("search"))
async def cmd_search(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("🔎 Usage: /search [interest or term]")
        return

    term = args[1].lower()
    session = get_session()
    try:
        profiles = session.query(FamigoProfile).filter(
            FamigoProfile.group_id == group_id(message),
            FamigoProfile.visibility != "hidden"
        ).all()

        matches = []
        for profile in profiles:
            interests = session.query(UserInterest).filter(
                UserInterest.user_id == profile.user_id,
                UserInterest.group_id == group_id(message)
            ).all()
            if any(term in i.interest.lower() for i in interests):
                matches.append(profile)

        if not matches:
            await message.answer(f"🔎 No people found interested in '{term}'.")
            return

        text = f"🔎 **People interested in '{term}'**\n\n"
        for profile in matches[:10]:
            text += f"• {profile.display_name or 'Member'}\n"
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error searching: {e}")
        await message.answer("❌ Error searching.")
    finally:
        session.close()


# ----------------------------
# Settings and group owner/admin controls
# ----------------------------
@router.message(Command("settings"))
async def cmd_settings(message: types.Message):
    session = get_session()
    try:
        cfg = ensure_group_config(session, group_id(message), message.from_user.id)
        text = (
            "⚙️ **Group Settings**\n\n"
            f"Group: {cfg.group_name}\n"
            f"Owner: {cfg.owner_id}\n\n"
            "Permissions:\n"
            "• Profile visibility\n"
            "• Family tree visibility\n"
            "• Confessions\n"
            "• Group statistics\n"
            "• Connection approvals\n"
        )
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error opening settings: {e}")
        await message.answer("❌ Error opening settings.")
    finally:
        session.close()


@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    session = get_session()
    try:
        user = session.query(User).filter(User.user_id == message.from_user.id).first()
        if not user:
            user = get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.first_name)

        cfg = ensure_group_config(session, group_id(message), message.from_user.id)
        if cfg.owner_id == message.from_user.id:
            await message.answer(
                "👑 **Group Owner Controls**\n\n"
                "• /setgroupname [name]\n"
                "• /setgroupdesc [description]\n"
                "• /addadmin [user_id]\n"
                "• /removeadmin [user_id]\n"
                "• /toggleconfessions\n"
                "• /togglefamily\n"
                "• /viewgroupstats",
                parse_mode="Markdown"
            )
        else:
            await message.answer("⚠️ Only the group owner can manage group controls.")
    except Exception as e:
        logger.error(f"Error opening admin panel: {e}")
        await message.answer("❌ Error opening admin controls.")
    finally:
        session.close()


@router.message(Command("setgroupname"))
async def cmd_setgroupname(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("👑 Usage: /setgroupname [name]")
        return
    session = get_session()
    try:
        cfg = session.query(GroupConfig).filter(GroupConfig.group_id == group_id(message)).first()
        if not cfg:
            cfg = ensure_group_config(session, group_id(message), message.from_user.id)
        if cfg.owner_id != message.from_user.id:
            await message.answer("⚠️ Only the group owner can rename the group.")
            return
        cfg.group_name = args[1]
        session.commit()
        await message.answer(f"👑 Group name updated to: **{args[1]}**", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error renaming group: {e}")
        await message.answer("❌ Error updating group name.")
    finally:
        session.close()


@router.message(Command("setgroupdesc"))
async def cmd_setgroupdesc(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("👑 Usage: /setgroupdesc [description]")
        return
    session = get_session()
    try:
        cfg = session.query(GroupConfig).filter(GroupConfig.group_id == group_id(message)).first()
        if not cfg:
            cfg = ensure_group_config(session, group_id(message), message.from_user.id)
        if cfg.owner_id != message.from_user.id:
            await message.answer("⚠️ Only the group owner can change the group description.")
            return
        cfg.group_description = args[1]
        session.commit()
        await message.answer("👑 Group description updated.")
    except Exception as e:
        logger.error(f"Error setting description: {e}")
        await message.answer("❌ Error updating group description.")
    finally:
        session.close()


@router.message(Command("addadmin"))
async def cmd_addadmin(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("👑 Usage: /addadmin [user_id]")
        return
    session = get_session()
    try:
        cfg = session.query(GroupConfig).filter(GroupConfig.group_id == group_id(message)).first()
        if not cfg:
            cfg = ensure_group_config(session, group_id(message), message.from_user.id)
        if cfg.owner_id != message.from_user.id:
            await message.answer("⚠️ Only the group owner can add admins.")
            return

        target_user_id = int(args[1])
        role = session.query(GroupRole).filter(
            GroupRole.user_id == target_user_id,
            GroupRole.group_id == group_id(message)
        ).first()
        if not role:
            role = GroupRole(
                user_id=target_user_id,
                group_id=group_id(message),
                role="admin",
                assigned_by=message.from_user.id
            )
            session.add(role)
        else:
            role.role = "admin"
        session.commit()
        await message.answer(f"👑 User {target_user_id} is now an admin in this group.")
    except Exception as e:
        logger.error(f"Error adding admin: {e}")
        await message.answer("❌ Error adding admin.")
    finally:
        session.close()


@router.message(Command("removeadmin"))
async def cmd_removeadmin(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("👑 Usage: /removeadmin [user_id]")
        return
    session = get_session()
    try:
        cfg = session.query(GroupConfig).filter(GroupConfig.group_id == group_id(message)).first()
        if not cfg:
            cfg = ensure_group_config(session, group_id(message), message.from_user.id)
        if cfg.owner_id != message.from_user.id:
            await message.answer("⚠️ Only the group owner can remove admins.")
            return

        target_user_id = int(args[1])
        role = session.query(GroupRole).filter(
            GroupRole.user_id == target_user_id,
            GroupRole.group_id == group_id(message)
        ).first()
        if role:
            session.delete(role)
            session.commit()
            await message.answer(f"👑 User {target_user_id} is no longer an admin.")
        else:
            await message.answer("ℹ️ That user is not assigned as an admin.")
    except Exception as e:
        logger.error(f"Error removing admin: {e}")
        await message.answer("❌ Error removing admin.")
    finally:
        session.close()


@router.message(Command("toggleconfessions"))
async def cmd_toggleconfessions(message: types.Message):
    session = get_session()
    try:
        cfg = session.query(GroupConfig).filter(GroupConfig.group_id == group_id(message)).first()
        if not cfg:
            cfg = ensure_group_config(session, group_id(message), message.from_user.id)
        if cfg.owner_id != message.from_user.id:
            await message.answer("⚠️ Only the group owner can toggle confessions.")
            return
        cfg.confessions_enabled = not cfg.confessions_enabled
        session.commit()
        await message.answer(f"💌 Confessions: {'enabled' if cfg.confessions_enabled else 'disabled'}")
    except Exception as e:
        logger.error(f"Error toggling confessions: {e}")
        await message.answer("❌ Error toggling confessions.")
    finally:
        session.close()


@router.message(Command("togglefamily"))
async def cmd_togglefamily(message: types.Message):
    session = get_session()
    try:
        cfg = session.query(GroupConfig).filter(GroupConfig.group_id == group_id(message)).first()
        if not cfg:
            cfg = ensure_group_config(session, group_id(message), message.from_user.id)
        if cfg.owner_id != message.from_user.id:
            await message.answer("⚠️ Only the group owner can toggle the family tree.")
            return
        cfg.family_tree_enabled = not cfg.family_tree_enabled
        session.commit()
        await message.answer(f"🌳 Family tree: {'enabled' if cfg.family_tree_enabled else 'disabled'}")
    except Exception as e:
        logger.error(f"Error toggling family tree: {e}")
        await message.answer("❌ Error toggling family tree.")
    finally:
        session.close()


@router.message(Command("viewgroupstats"))
async def cmd_viewgroupstats(message: types.Message):
    session = get_session()
    try:
        cfg = session.query(GroupConfig).filter(GroupConfig.group_id == group_id(message)).first()
        if not cfg:
            cfg = ensure_group_config(session, group_id(message), message.from_user.id)
        if cfg.owner_id != message.from_user.id:
            await message.answer("⚠️ Only the group owner can view group stats.")
            return

        member_count = session.query(FamigoProfile).filter(FamigoProfile.group_id == group_id(message)).count()
        profiles_count = session.query(FamigoProfile).filter(FamigoProfile.group_id == group_id(message)).count()
        confessions_count = session.query(Confession).filter(Confession.group_id == group_id(message)).count()
        tree_count = session.query(FamilyTreeRelation).filter(FamilyTreeRelation.group_id == group_id(message)).count()

        text = (
            "📊 **Group Statistics**\n\n"
            f"Members: {member_count}\n"
            f"Profiles: {profiles_count}\n"
            f"Confessions: {confessions_count}\n"
            f"Family relations: {tree_count}"
        )
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error viewing group stats: {e}")
        await message.answer("❌ Error viewing group stats.")
    finally:
        session.close()


# ----------------------------
# Privacy and visibility controls
# ----------------------------
@router.message(Command("privacy"))
async def cmd_privacy(message: types.Message):
    await message.answer(
        "🔐 **Privacy Controls**\n\n"
        "• /setprofileprivacy public|group_only|hidden\n"
        "• /setconfessionprivacy on|off\n"
        "• /setconnectionprivacy public|friends_only|private",
        parse_mode="Markdown"
    )


@router.message(Command("setprofileprivacy"))
async def cmd_setprofileprivacy(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("🔐 Usage: /setprofileprivacy [public|group_only|hidden]")
        return
    session = get_session()
    try:
        profile = session.query(FamigoProfile).filter(
            FamigoProfile.user_id == message.from_user.id,
            FamigoProfile.group_id == group_id(message)
        ).first()
        if not profile:
            profile = get_or_create_profile(session, message.from_user.id, group_id(message), message.from_user.first_name)
        profile.visibility = args[1]
        session.commit()
        await message.answer(f"🔐 Profile visibility updated to: **{args[1]}**", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error updating privacy: {e}")
        await message.answer("❌ Error updating privacy.")
    finally:
        session.close()


# ----------------------------
# Simple command aliases
# ----------------------------
@router.message(Command("mygroups"))
async def cmd_mygroups(message: types.Message):
    session = get_session();
    try:
        profiles = session.query(FamigoProfile).filter(FamigoProfile.user_id == message.from_user.id).all()
        if not profiles:
            await message.answer("🏠 You have no groups yet.")
            return
        text = "🏠 **Your Communities**\n\n"
        for p in profiles:
            text += f"• Group {p.group_id} | Level {p.level} | ⭐ {p.reputation}\n"
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error loading groups: {e}")
    finally:
        session.close()


@router.message(Command("sayhi"))
async def cmd_sayhi(message: types.Message):
    await message.answer("👋 Hello! Nice to meet you. Want to say hi back?")


@router.message(Command("birthday"))
async def cmd_birthday(message: types.Message):
    await message.answer("🎂 Birthday settings: hidden|birthday_only|visible")


@router.message(Command("history"))
async def cmd_history(message: types.Message):
    await message.answer("📜 Community history is available when configured.")


@router.message(Command("trending"))
async def cmd_trending(message: types.Message):
    await message.answer("🔥 Popular interests\n\n🎬 Movies\n🎵 Music\n🎮 Gaming\n🎨 Art")


@router.message(Command("export"))
async def cmd_export(message: types.Message):
    await message.answer("📤 Export is available in your privacy settings panel.")
