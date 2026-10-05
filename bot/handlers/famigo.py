"""Telegram handlers for Famigo's group-scoped social features."""

import logging
import re
from datetime import datetime, timedelta

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from sqlalchemy import or_

from bot.services import famigo as service
from config import settings
from bot.webapp import normalize_webapp_url
from database import (
    Achievement,
    CommunityEvent,
    Confession,
    ConfessionReaction,
    Connection,
    CurrentlyInto,
    Favorite,
    FamigoProfile,
    FamilyTreeRelation,
    GroupJoinHistory,
    MoodStatus,
    ProfileVisibility,
    RelationshipType,
    SocialLink,
    UserInterest,
    get_session,
)

logger = logging.getLogger(__name__)
router = Router()
MAX_MESSAGE_LENGTH = 3500


def is_group_chat(message: types.Message) -> bool:
    return message.chat.type in {"group", "supergroup"}


async def require_group(message: types.Message) -> bool:
    if is_group_chat(message) and message.from_user is not None:
        return True
    await message.answer("Use Famigo commands in a group where the bot is installed.")
    return False


def format_profile(profile, interests, username=None) -> str:
    fields = [
        f"👤 {profile.display_name or 'Community member'}",
    ]
    if username:
        fields.append(f"Telegram: @{username}")
    for label, value in (
        ("📍 Location", ", ".join(part for part in (profile.city, profile.country) if part)),
        ("💼 Profession", profile.profession),
        ("📝 About", profile.bio),
        ("✨ Fun fact", profile.fun_fact),
    ):
        if value:
            fields.append(f"{label}: {value}")
    fields.append("❤️ Interests: " + (", ".join(interests) if interests else "Not shared"))
    fields.append(f"⭐ Reputation: {profile.reputation or 0} | Level {profile.level or 1}")
    return "\n".join(fields)


async def send_private_text(bot, user_id: int, lines: list[str]):
    chunks = []
    current = ""
    for line in lines:
        while len(line) > MAX_MESSAGE_LENGTH:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:MAX_MESSAGE_LENGTH])
            line = line[MAX_MESSAGE_LENGTH:]
        if current and len(current) + len(line) + 1 > MAX_MESSAGE_LENGTH:
            chunks.append(current)
            current = ""
        current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    for chunk in chunks:
        await bot.send_message(user_id, chunk)


@router.message(Command("famigo"))
async def cmd_famigo(message: types.Message):
    if await require_group(message):
        bot_user = await message.bot.get_me()
        webapp_url = normalize_webapp_url(settings.webapp_url)
        buttons = [[
            InlineKeyboardButton(
                text="Find members inline",
                switch_inline_query_current_chat=f"group:{message.chat.id} ",
            )
        ]]
        if webapp_url:
            buttons.append([InlineKeyboardButton(
                text="Open Mini App",
                url=f"https://t.me/{bot_user.username}?start=famigo_{message.chat.id}",
            )])
        await message.answer(
            "Famigo is your group's social space. Members who join can create a profile, browse other visible profiles in this group, discover shared interests, and request connections.\n\n"
            "Profiles are shown only in the group they belong to. Use the buttons below to browse or open the interactive Mini App.\n\n"
            "/profile - View your group profile\n"
            "/setprofile field | value - Add or edit a profile field\n"
            "/interests - View your interests\n"
            "/addinterest interest - Add an interest\n"
            "/currently category | activity - Share something you chose\n"
            "/mood [mood] - Set an optional mood that expires after 24 hours\n"
            "/discover - Find members with shared interests\n"
            "/connect @username [relationship] - Ask to connect\n"
            "/relationships - View your approved connections\n"
            "/stats - View your group-specific stats\n"
            "/socials - Privately view your saved links\n"
            "/privacy - Manage profile visibility\n"
            "/export - Export your data from this group\n"
            "/deleteprofile - Delete your Famigo data from this group",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )


@router.inline_query()
async def inline_group_directory(query: types.InlineQuery):
    match = re.fullmatch(r"group:(-?\d+)(?:\s+(.*))?", query.query.strip(), re.IGNORECASE)
    if not match or query.chat_type not in {"group", "supergroup"}:
        await query.answer(
            [],
            cache_time=0,
            is_personal=True,
            switch_pm_text="Open Famigo in a group",
            switch_pm_parameter="start",
        )
        return
    group_id = int(match.group(1))
    try:
        member = await query.bot.get_chat_member(group_id, query.from_user.id)
        if member.status in {"left", "kicked"} or (
            member.status == "restricted" and not member.is_member
        ):
            await query.answer([], cache_time=0, is_personal=True)
            return
        bot_user = await query.bot.get_me()
        await query.answer(
            [InlineQueryResultArticle(
                id="famigo-directory",
                title="Open your group's Famigo directory",
                description="Browse group profiles in the verified Telegram Mini App",
                input_message_content=InputTextMessageContent(
                    message_text="Open Famigo to browse your group's community."
                ),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text="Open group directory",
                        url=f"https://t.me/{bot_user.username}?start=famigo_{group_id}",
                    )
                ]]),
            )],
            cache_time=0,
            is_personal=True,
        )
    except Exception:
        logger.exception("Failed to serve the group-scoped Famigo inline launcher")
        await query.answer([], cache_time=0, is_personal=True)


@router.message(Command("profile", "me", "myprofile", "intro"))
async def cmd_profile(message: types.Message):
    if not await require_group(message):
        return

    args = (message.text or "").split(maxsplit=1)
    session = get_session()
    try:
        viewer_id = message.from_user.id
        target_id = viewer_id
        if len(args) > 1:
            username = args[1].lstrip("@").strip()
            target = session.query(service.User).filter(service.User.username.ilike(username)).first()
            if target is None:
                await message.answer("That member has not created a profile in this group.")
                return
            target_id = target.user_id

        profile = service.get_profile(session, target_id, message.chat.id)
        if profile is None:
            await message.answer(
                "No profile found in this group yet. Use /setprofile field | value to create yours."
            )
            return
        if target_id != viewer_id and profile.visibility == ProfileVisibility.HIDDEN:
            await message.answer("That member's profile is private.")
            return
        if target_id != viewer_id:
            try:
                member = await message.bot.get_chat_member(message.chat.id, target_id)
            except Exception:
                logger.exception("Could not verify profile owner's current group membership")
                await message.answer("I couldn't verify that member's current group membership.")
                return
            if member.status in {"left", "kicked"} or (
                member.status == "restricted" and not member.is_member
            ):
                await message.answer("That profile is no longer available because the member left this group.")
                return

        interests = session.query(UserInterest.interest).filter(
            UserInterest.user_id == target_id,
            UserInterest.group_id == message.chat.id,
        ).limit(20).all()
        user = session.query(service.User).filter(service.User.user_id == target_id).first()
        await message.answer(
            format_profile(profile, [row[0] for row in interests], user.username if user else None)
        )
    except Exception:
        logger.exception("Failed to display Famigo profile")
        await message.answer("I couldn't load that profile. Please try again.")
    finally:
        session.close()


@router.message(Command("setprofile", "editprofile"))
async def cmd_setprofile(message: types.Message):
    if not await require_group(message):
        return
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2 or "|" not in args[1]:
        fields = ", ".join(service.PROFILE_FIELDS)
        await message.answer(
            "Set one optional field at a time with:\n"
            "/setprofile field | value\n"
            f"Fields: {fields}\nExample: /setprofile bio | I enjoy hiking"
        )
        return
    field, value = (part.strip() for part in args[1].split("|", maxsplit=1))
    session = get_session()
    try:
        user = service.ensure_user(session, message.from_user.id, message.from_user.username)
        service.set_profile_field(
            session, user, message.chat.id, field, value, message.from_user.first_name
        )
        session.commit()
        await message.answer(f"Saved your {field.lower()} for this group.")
    except ValueError as exc:
        session.rollback()
        await message.answer(str(exc))
    except Exception:
        session.rollback()
        logger.exception("Failed to save Famigo profile")
        await message.answer("I couldn't save your profile. Please try again.")
    finally:
        session.close()


@router.message(Command("interests"))
async def cmd_interests(message: types.Message):
    if not await require_group(message):
        return
    session = get_session()
    try:
        interests = session.query(UserInterest.interest).filter(
            UserInterest.user_id == message.from_user.id,
            UserInterest.group_id == message.chat.id,
        ).order_by(UserInterest.interest).all()
        text = ", ".join(row[0] for row in interests) if interests else "No interests added yet."
        await message.answer(
            f"Your interests in this group: {text}\nAdd one with /addinterest photography."
        )
    except Exception:
        logger.exception("Failed to list Famigo interests")
        await message.answer("I couldn't load your interests. Please try again.")
    finally:
        session.close()


@router.message(Command("addinterest"))
async def cmd_addinterest(message: types.Message):
    if not await require_group(message):
        return
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2 or not args[1].strip() or len(args[1]) > 80:
        await message.answer("Use /addinterest followed by an interest (up to 80 characters).")
        return
    session = get_session()
    try:
        interest_name = args[1].strip()
        existing = session.query(UserInterest).filter(
            UserInterest.user_id == message.from_user.id,
            UserInterest.group_id == message.chat.id,
            UserInterest.interest.ilike(interest_name),
        ).first()
        if existing is not None:
            await message.answer("That interest is already on your profile.")
            return
        interest_count = session.query(UserInterest).filter(
            UserInterest.user_id == message.from_user.id,
            UserInterest.group_id == message.chat.id,
        ).count()
        if interest_count >= 20:
            await message.answer("You can add up to 20 interests to your profile in this group.")
            return
        user = service.ensure_user(session, message.from_user.id, message.from_user.username)
        if service.get_profile(session, user.user_id, message.chat.id) is None:
            session.add(FamigoProfile(
                user_id=user.user_id,
                group_id=message.chat.id,
                display_name=message.from_user.first_name or "Member",
                visibility=ProfileVisibility.GROUP_ONLY,
            ))
        session.add(UserInterest(
            user_id=user.user_id,
            group_id=message.chat.id,
            interest=interest_name,
            is_custom=True,
        ))
        session.commit()
        await message.answer("Added that interest to your profile in this group.")
    except Exception:
        session.rollback()
        logger.exception("Failed to save Famigo interest")
        await message.answer("I couldn't add that interest. Please try again.")
    finally:
        session.close()


@router.message(Command("removeinterest"))
async def cmd_removeinterest(message: types.Message):
    if not await require_group(message):
        return
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        await message.answer("Use /removeinterest followed by the interest to remove.")
        return
    session = get_session()
    try:
        interest = session.query(UserInterest).filter(
            UserInterest.user_id == message.from_user.id,
            UserInterest.group_id == message.chat.id,
            UserInterest.interest.ilike(args[1].strip()),
        ).first()
        if interest is None:
            await message.answer("That interest was not found on your profile in this group.")
            return
        session.delete(interest)
        session.commit()
        await message.answer("Removed that interest from your group profile.")
    except Exception:
        session.rollback()
        logger.exception("Failed to remove Famigo interest")
        await message.answer("I couldn't remove that interest. Please try again.")
    finally:
        session.close()


@router.message(Command("discover", "similar", "match", "peoplelike", "random", "meet"))
async def cmd_discover(message: types.Message):
    if not await require_group(message):
        return
    session = get_session()
    try:
        profiles = service.list_discoverable_profiles(
            session, message.chat.id, message.from_user.id
        )
        active_profiles = []
        for candidate in profiles:
            try:
                member = await message.bot.get_chat_member(message.chat.id, candidate.user_id)
            except Exception:
                logger.exception("Could not verify a Famigo discovery candidate")
                await message.answer(
                    "I couldn't verify group members. Ask an admin to make the bot an administrator, then try again."
                )
                return
            if member.status not in {"left", "kicked"} and not (
                member.status == "restricted" and not member.is_member
            ):
                active_profiles.append(candidate)
        profiles = active_profiles
        if not profiles:
            await message.answer("There are no discoverable profiles in this group yet.")
            return

        my_interests = {
            row[0].casefold() for row in session.query(UserInterest.interest).filter(
                UserInterest.user_id == message.from_user.id,
                UserInterest.group_id == message.chat.id,
            ).all()
        }
        candidates = []
        for profile in profiles:
            rows = session.query(UserInterest.interest).filter(
                UserInterest.user_id == profile.user_id,
                UserInterest.group_id == message.chat.id,
            ).all()
            interests = [row[0] for row in rows]
            shared = [item for item in interests if item.casefold() in my_interests]
            score = round(100 * len(shared) / max(len(interests), len(my_interests), 1))
            candidates.append((profile, interests, shared, score))

        if message.text and message.text.split(maxsplit=1)[0].split("@", 1)[0].lstrip("/") in {
            "random", "meet"
        }:
            service.ensure_user(session, message.from_user.id, message.from_user.username)
            profile = service.choose_random_profile(
                session, message.from_user.id, message.chat.id,
                [candidate[0] for candidate in candidates],
            )
            session.commit()
            interests, shared, score = next(
                (item[1], item[2], item[3])
                for item in candidates if item[0].user_id == profile.user_id
            )
        else:
            candidates = [candidate for candidate in candidates if candidate[2]]
            if not candidates:
                await message.answer("No one else in this group has shared interests with you yet.")
                return
            candidates.sort(key=lambda item: (-item[3], item[0].user_id))
            profile, interests, shared, score = candidates[0]

        user = session.query(service.User).filter(service.User.user_id == profile.user_id).first()
        card = format_profile(profile, interests, user.username if user else None)
        card += f"\nShared interests: {', '.join(shared) if shared else 'None yet'}"
        card += f"\nSimilarity for fun: {score}% (not a compatibility measure)"
        await message.answer(card)
    except Exception:
        logger.exception("Failed to discover Famigo members")
        await message.answer("I couldn't find members right now. Please try again.")
    finally:
        session.close()


@router.message(Command("connect"))
async def cmd_connect(message: types.Message):
    if not await require_group(message):
        return
    args = (message.text or "").split(maxsplit=2)
    target_user_id = None
    target_username = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user_id = message.reply_to_message.from_user.id
        relationship = args[1] if len(args) > 1 else RelationshipType.FRIEND.value
    elif len(args) > 1:
        target_username = args[1]
        relationship = args[2] if len(args) > 2 else RelationshipType.FRIEND.value
    else:
        await message.answer(
            "Use /connect @username [relationship], or reply to a member's message with /connect [relationship]."
        )
        return
    session = get_session()
    try:
        connection, target = service.request_connection(
            session,
            message.from_user.id,
            target_username,
            message.chat.id,
            relationship,
            target_user_id=target_user_id,
        )
        session.commit()
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="Accept",
                callback_data=f"famigo_accept_{connection.id}",
            ),
            InlineKeyboardButton(
                text="Decline",
                callback_data=f"famigo_decline_{connection.id}",
            ),
        ]])
        target_profile = service.get_profile(session, target.user_id, message.chat.id)
        target_label = (
            f"@{target.username}" if target.username
            else (target_profile.display_name if target_profile else "Community member")
        )
        await message.answer(
            f"{target_label}, {message.from_user.first_name} asked to connect "
            f"as {relationship}. Only you can accept or decline this request.",
            reply_markup=keyboard,
        )
    except ValueError as exc:
        session.rollback()
        await message.answer(str(exc))
    except Exception:
        session.rollback()
        logger.exception("Failed to create Famigo connection request")
        await message.answer("I couldn't send that request. Please try again.")
    finally:
        session.close()


@router.callback_query(F.data.startswith("famigo_accept_") | F.data.startswith("famigo_decline_"))
async def cb_connection_request(callback: types.CallbackQuery):
    if callback.message is None or callback.message.chat.type not in {"group", "supergroup"}:
        await callback.answer("Open this request in its original group.", show_alert=True)
        return
    action, connection_id_text = callback.data.removeprefix("famigo_").split("_", maxsplit=1)
    if not connection_id_text.isdigit():
        await callback.answer("This request is invalid.", show_alert=True)
        return

    session = get_session()
    try:
        connection = service.respond_to_connection(
            session,
            int(connection_id_text),
            callback.from_user.id,
            callback.message.chat.id,
            accept=action == "accept",
        )
        session.commit()
        await callback.answer("Connection accepted." if action == "accept" else "Request declined.")
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            logger.warning("Could not remove buttons from a handled connection request", exc_info=True)
        if action == "accept":
            try:
                await callback.message.reply("You are now connected in this group.")
            except Exception:
                logger.warning("Could not post connection acceptance notice", exc_info=True)
    except ValueError as exc:
        session.rollback()
        await callback.answer(str(exc), show_alert=True)
    except Exception:
        session.rollback()
        logger.exception("Failed to respond to Famigo connection request")
        await callback.answer("I couldn't update the request. Please try again.", show_alert=True)
    finally:
        session.close()


@router.message(Command("relationships", "connections"))
async def cmd_relationships(message: types.Message):
    if not await require_group(message):
        return
    session = get_session()
    try:
        connections = session.query(Connection).filter(
            Connection.group_id == message.chat.id,
            Connection.status == "accepted",
            or_(
                Connection.user_id == message.from_user.id,
                Connection.connected_user_id == message.from_user.id,
            ),
        ).all()
        if not connections:
            await message.answer("You have no confirmed connections in this group yet.")
            return

        lines = ["Your confirmed connections in this group:"]
        for connection in connections:
            other_id = (
                connection.connected_user_id
                if connection.user_id == message.from_user.id
                else connection.user_id
            )
            profile = service.get_profile(session, other_id, message.chat.id)
            if profile is None or profile.visibility == ProfileVisibility.HIDDEN:
                continue
            relationship = (
                connection.custom_relationship
                or connection.relationship_type.value
            )
            lines.append(f"• {profile.display_name or 'Community member'} - {relationship}")
        await message.answer("\n".join(lines))
    except Exception:
        logger.exception("Failed to list Famigo relationships")
        await message.answer("I couldn't load your connections. Please try again.")
    finally:
        session.close()


@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if not await require_group(message):
        return
    session = get_session()
    try:
        profile = service.get_profile(session, message.from_user.id, message.chat.id)
        if profile is None:
            await message.answer("Create your group profile with /setprofile first.")
            return
        connections = session.query(Connection).filter(
            Connection.group_id == message.chat.id,
            Connection.status == "accepted",
            or_(
                Connection.user_id == message.from_user.id,
                Connection.connected_user_id == message.from_user.id,
            ),
        ).count()
        interests = session.query(UserInterest).filter(
            UserInterest.user_id == message.from_user.id,
            UserInterest.group_id == message.chat.id,
        ).count()
        achievements = session.query(Achievement).filter(
            Achievement.user_id == message.from_user.id,
            Achievement.group_id == message.chat.id,
        ).count()
        joined = profile.joined_at.strftime("%Y-%m-%d") if profile.joined_at else "Unknown"
        await message.answer(
            f"Your stats in this group:\n"
            f"⭐ Reputation: {profile.reputation or 0}\n"
            f"Level: {profile.level or 1}\n"
            f"Confirmed connections: {connections}\n"
            f"Interests: {interests}\n"
            f"Achievements: {achievements}\n"
            f"Profile since: {joined}"
        )
    except Exception:
        logger.exception("Failed to load Famigo stats")
        await message.answer("I couldn't load your stats. Please try again.")
    finally:
        session.close()


@router.message(Command("privacy"))
async def cmd_privacy(message: types.Message):
    if await require_group(message):
        await message.answer(
            "Your profile is private to this group by default.\n"
            "Change this group's profile visibility with /setprofileprivacy public, group_only, or hidden.\n"
            "Control discoverability globally with /discoverability on|off.\n"
            "Control connection requests globally with /connectionrequests on|off."
        )


async def update_global_preference(message: types.Message, preference: str):
    args = (message.text or "").split(maxsplit=1)
    if len(args) != 2 or args[1].lower() not in {"on", "off"}:
        command = "discoverability" if preference == "discoverability" else "connectionrequests"
        await message.answer(f"Use /{command} on or /{command} off.")
        return
    session = get_session()
    try:
        user = service.ensure_user(session, message.from_user.id, message.from_user.username)
        service.set_user_preference(session, user, preference, args[1].lower() == "on")
        session.commit()
        setting = "enabled" if args[1].lower() == "on" else "disabled"
        await message.answer(f"Your {preference.replace('_', ' ')} is {setting} across groups.")
    except Exception:
        session.rollback()
        logger.exception("Failed to update Famigo privacy preference")
        await message.answer("I couldn't update that privacy preference. Please try again.")
    finally:
        session.close()


@router.message(Command("discoverability"))
async def cmd_discoverability(message: types.Message):
    if await require_group(message):
        await update_global_preference(message, "discoverability")


@router.message(Command("connectionrequests"))
async def cmd_connectionrequests(message: types.Message):
    if await require_group(message):
        await update_global_preference(message, "connection_requests")


@router.message(Command("setprofileprivacy"))
async def cmd_setprofileprivacy(message: types.Message):
    if not await require_group(message):
        return
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Use /setprofileprivacy public, group_only, or hidden.")
        return
    session = get_session()
    try:
        service.set_profile_visibility(
            session, message.from_user.id, message.chat.id, args[1]
        )
        session.commit()
        await message.answer("Your profile visibility was updated for this group.")
    except ValueError as exc:
        session.rollback()
        await message.answer(str(exc))
    except Exception:
        session.rollback()
        logger.exception("Failed to change Famigo profile privacy")
        await message.answer("I couldn't update your privacy setting. Please try again.")
    finally:
        session.close()


@router.message(Command("export"))
async def cmd_export(message: types.Message):
    if not await require_group(message):
        return
    session = get_session()
    try:
        profile = service.get_profile(session, message.from_user.id, message.chat.id)
        interests = session.query(UserInterest.interest).filter(
            UserInterest.user_id == message.from_user.id,
            UserInterest.group_id == message.chat.id,
        ).all()
        lines = ["Your Famigo data from this group:"]
        if profile is not None:
            lines.append(format_profile(profile, [row[0] for row in interests]))
            profile_fields = (
                ("Pronouns", profile.pronouns),
                ("Age range", profile.age_range),
                ("Education", profile.education),
                ("Languages", profile.languages),
                ("Introduction", profile.introduction),
                ("Favorite quote", profile.favorite_quote),
                ("Favorite emoji", profile.favorite_emoji),
            )
            lines.extend(f"{label}: {value}" for label, value in profile_fields if value)
        elif not interests:
            lines.append("No group profile or interest data.")

        favorites = session.query(Favorite).filter(
            Favorite.user_id == message.from_user.id,
            Favorite.group_id == message.chat.id,
        ).order_by(Favorite.category).limit(20).all()
        if favorites:
            lines.append("Favorites: " + "; ".join(
                f"{item.category}: {item.value}" for item in favorites
            ))

        activities = session.query(CurrentlyInto).filter(
            CurrentlyInto.user_id == message.from_user.id,
            CurrentlyInto.group_id == message.chat.id,
        ).order_by(CurrentlyInto.set_at.desc()).limit(10).all()
        if activities:
            lines.append("Current activities: " + "; ".join(
                f"{item.category}: {item.value}" for item in activities
            ))

        moods = session.query(MoodStatus).filter(
            MoodStatus.user_id == message.from_user.id,
            MoodStatus.group_id == message.chat.id,
        ).order_by(MoodStatus.set_at.desc()).limit(10).all()
        if moods:
            lines.append("Mood history: " + "; ".join(item.custom_mood or "" for item in moods))

        achievements = session.query(Achievement).filter(
            Achievement.user_id == message.from_user.id,
            Achievement.group_id == message.chat.id,
        ).all()
        if achievements:
            lines.append("Achievements: " + ", ".join(
                item.achievement_name for item in achievements
            ))

        membership = session.query(GroupJoinHistory).filter(
            GroupJoinHistory.user_id == message.from_user.id,
            GroupJoinHistory.group_id == message.chat.id,
        ).first()
        if membership:
            lines.append(
                f"Membership: first joined {membership.first_joined.isoformat()}, "
                f"most recent join {membership.last_joined.isoformat()}, "
                f"left {membership.left_count} times."
            )

        connections = session.query(Connection).filter(
            Connection.group_id == message.chat.id,
            or_(
                Connection.user_id == message.from_user.id,
                Connection.connected_user_id == message.from_user.id,
            ),
        ).all()
        if connections:
            lines.append("Connection requests and relationships:")
            for connection in connections:
                other_id = (
                    connection.connected_user_id
                    if connection.user_id == message.from_user.id
                    else connection.user_id
                )
                other = service.get_profile(session, other_id, message.chat.id)
                other_name = other.display_name if other else "Community member"
                lines.append(
                    f"• {other_name}: {connection.relationship_type.value} ({connection.status})"
                )

        confessions = session.query(Confession).filter(
            Confession.user_id == message.from_user.id,
            Confession.group_id == message.chat.id,
        ).order_by(Confession.created_at).all()
        if confessions:
            lines.append("Your submitted confessions:")
            lines.extend(f"• {item.confession_text}" for item in confessions)

        reactions = session.query(ConfessionReaction).join(
            Confession, Confession.id == ConfessionReaction.confession_id
        ).filter(
            ConfessionReaction.user_id == message.from_user.id,
            Confession.group_id == message.chat.id,
        ).all()
        if reactions:
            lines.append("Your anonymous confession reactions:")
            lines.extend(f"• Confession {item.confession_id}: {item.reaction_emoji}" for item in reactions)

        family_relations = session.query(FamilyTreeRelation).filter(
            FamilyTreeRelation.group_id == message.chat.id,
            or_(
                FamilyTreeRelation.user1_id == message.from_user.id,
                FamilyTreeRelation.user2_id == message.from_user.id,
            ),
        ).all()
        if family_relations:
            lines.append("Your confirmed or pending group relationship records:")
            lines.extend(
                f"• {item.relation_type} with user "
                f"{item.user2_id if item.user1_id == message.from_user.id else item.user1_id} "
                f"(confirmed by both: {item.user1_confirmed and item.user2_confirmed})"
                for item in family_relations
            )

        events = session.query(CommunityEvent).filter(
            CommunityEvent.group_id == message.chat.id,
            or_(
                CommunityEvent.user_id == message.from_user.id,
                CommunityEvent.related_user_id == message.from_user.id,
            ),
        ).all()
        if events:
            lines.append("Related community timeline records:")
            lines.extend(f"• {item.event_type}: {item.event_data or ''}" for item in events)

        social_links = session.query(SocialLink).filter(
            SocialLink.user_id == message.from_user.id
        ).order_by(SocialLink.platform).limit(20).all()
        if social_links:
            lines.append("Your separately stored, user-level social links:")
            lines.extend(f"• {link.platform}: {link.username_or_url}" for link in social_links)
        try:
            await send_private_text(message.bot, message.from_user.id, lines)
        except Exception:
            logger.info("Could not privately deliver Famigo export for user %s", message.from_user.id)
            await message.answer(
                "I couldn't message you. Start a private chat with me, then run /export again here."
            )
    except Exception:
        logger.exception("Failed to export Famigo data")
        await message.answer("I couldn't export your data. Please try again.")
    finally:
        session.close()


@router.message(Command("deleteprofile"))
async def cmd_deleteprofile(message: types.Message):
    if not await require_group(message):
        return
    await message.answer(
        "Delete your Famigo profile and associated data from this group? This cannot be undone. "
        "Your separately saved social links will not be changed.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="Delete my group data",
                callback_data=f"famigo_delete_{message.from_user.id}_{message.chat.id}",
            ),
            InlineKeyboardButton(
                text="Cancel",
                callback_data=f"famigo_delete_cancel_{message.from_user.id}_{message.chat.id}",
            ),
        ]]),
    )


@router.callback_query(F.data.startswith("famigo_delete_"))
async def cb_delete_profile(callback: types.CallbackQuery):
    if callback.message is None:
        await callback.answer("This confirmation is no longer available.", show_alert=True)
        return
    prefix = "famigo_delete_"
    is_cancel = callback.data.startswith(prefix + "cancel_")
    payload = callback.data[len(prefix + "cancel_"):] if is_cancel else callback.data[len(prefix):]
    try:
        owner_id_text, group_id_text = payload.split("_", maxsplit=1)
        owner_id = int(owner_id_text)
        group_id = int(group_id_text)
    except ValueError:
        await callback.answer("This confirmation is invalid.", show_alert=True)
        return

    if callback.from_user.id != owner_id or callback.message.chat.id != group_id:
        await callback.answer("Only the person who requested this action can confirm it.", show_alert=True)
        return
    if is_cancel:
        await callback.message.edit_text("Profile deletion cancelled.")
        await callback.answer()
        return

    session = get_session()
    try:
        deleted = service.delete_group_profile(session, owner_id, group_id)
        session.commit()
        await callback.answer()
        try:
            await callback.message.edit_text(
                "Your Famigo profile and group-specific data were deleted."
                if deleted else "You have no Famigo profile in this group to delete."
            )
        except Exception:
            logger.warning("Could not update group message after profile deletion", exc_info=True)
    except Exception:
        session.rollback()
        logger.exception("Failed to delete Famigo profile")
        await callback.answer("I couldn't delete your profile. Please try again.", show_alert=True)
    finally:
        session.close()


@router.message(Command("mygroups"))
async def cmd_mygroups(message: types.Message):
    session = get_session()
    try:
        profiles = session.query(FamigoProfile).filter(
            FamigoProfile.user_id == message.from_user.id
        ).order_by(FamigoProfile.group_id).all()
        if not profiles:
            await message.answer("You have no Famigo profiles yet.")
            return
        await message.bot.send_message(
            message.from_user.id,
            "Your group-specific Famigo profiles:\n" + "\n".join(
                f"• Group {profile.group_id}: Level {profile.level or 1}, "
                f"{profile.reputation or 0} Reputation"
                for profile in profiles
            )
        )
    except Exception:
        logger.exception("Failed to list Famigo groups")
        await message.answer("I couldn't privately send your group list. Start a private chat with me first.")
    finally:
        session.close()


ACTIVITY_COMMANDS = {
    "watching": "Watching",
    "listening": "Listening",
    "reading": "Reading",
    "playing": "Playing",
}
MOOD_OPTIONS = {
    "happy", "chill", "energetic", "tired", "sad", "thinking", "vibing",
    "romantic", "overwhelmed", "excited",
}


@router.message(Command("currently", "watching", "listening", "reading", "playing"))
async def cmd_currently(message: types.Message):
    if not await require_group(message):
        return
    args = (message.text or "").split(maxsplit=1)
    command_name = (args[0].split("@", 1)[0].lstrip("/").lower() if args else "currently")
    if len(args) < 2:
        await message.answer(
            "Use /currently category | activity, or for example /watching a movie. "
            "Use /currently off to clear your activities."
        )
        return
    if command_name == "currently" and args[1].strip().lower() == "off":
        session = get_session()
        try:
            session.query(CurrentlyInto).filter(
                CurrentlyInto.user_id == message.from_user.id,
                CurrentlyInto.group_id == message.chat.id,
            ).delete(synchronize_session=False)
            session.commit()
            await message.answer("Your activities were cleared from this group.")
        except Exception:
            session.rollback()
            logger.exception("Failed to clear Famigo activities")
            await message.answer("I couldn't clear your activities. Please try again.")
        finally:
            session.close()
        return
    if command_name in ACTIVITY_COMMANDS:
        category, value = ACTIVITY_COMMANDS[command_name], args[1].strip()
    elif "|" in args[1]:
        category, value = (part.strip() for part in args[1].split("|", maxsplit=1))
    else:
        await message.answer("Use /currently category | activity.")
        return
    if not category or len(category) > 40 or not value or len(value) > 150:
        await message.answer("Category must be 1-40 characters and activity 1-150 characters.")
        return
    if command_name in ACTIVITY_COMMANDS and value.lower() == "off":
        session = get_session()
        try:
            session.query(CurrentlyInto).filter(
                CurrentlyInto.user_id == message.from_user.id,
                CurrentlyInto.group_id == message.chat.id,
                CurrentlyInto.category.ilike(category),
            ).delete(synchronize_session=False)
            session.commit()
            await message.answer(f"Your {category} activity was cleared.")
        except Exception:
            session.rollback()
            logger.exception("Failed to clear Famigo activity")
            await message.answer("I couldn't clear that activity. Please try again.")
        finally:
            session.close()
        return

    session = get_session()
    try:
        activities = session.query(CurrentlyInto).filter(
            CurrentlyInto.user_id == message.from_user.id,
            CurrentlyInto.group_id == message.chat.id,
            CurrentlyInto.category.ilike(category),
        ).order_by(CurrentlyInto.set_at.desc()).all()
        if activities:
            activities[0].value = value
            activities[0].set_at = datetime.utcnow()
            for duplicate in activities[1:]:
                session.delete(duplicate)
        else:
            session.add(CurrentlyInto(
                user_id=message.from_user.id,
                group_id=message.chat.id,
                category=category,
                value=value,
            ))
        session.commit()
        await message.answer(f"Saved your {category} activity in this group.")
    except Exception:
        session.rollback()
        logger.exception("Failed to save Famigo activity")
        await message.answer("I couldn't save that activity. Please try again.")
    finally:
        session.close()


@router.message(Command("addfavorite"))
async def cmd_addfavorite(message: types.Message):
    if not await require_group(message):
        return
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2 or "|" not in args[1]:
        await message.answer("Use /addfavorite category | item. Example: /addfavorite book | Dune")
        return
    category, value = (part.strip() for part in args[1].split("|", maxsplit=1))
    if not category or len(category) > 40 or not value or len(value) > 150:
        await message.answer("Category must be 1-40 characters and item 1-150 characters.")
        return
    session = get_session()
    try:
        count = session.query(Favorite).filter(
            Favorite.user_id == message.from_user.id,
            Favorite.group_id == message.chat.id,
        ).count()
        if count >= 20:
            await message.answer("You can save up to 20 favorites in this group.")
            return
        service.ensure_user(session, message.from_user.id, message.from_user.username)
        session.add(Favorite(
            user_id=message.from_user.id,
            group_id=message.chat.id,
            category=category,
            value=value,
        ))
        session.commit()
        await message.answer("Saved that favorite to this group profile.")
    except Exception:
        session.rollback()
        logger.exception("Failed to save Famigo favorite")
        await message.answer("I couldn't save that favorite. Please try again.")
    finally:
        session.close()


@router.message(Command("removefavorite"))
async def cmd_removefavorite(message: types.Message):
    if not await require_group(message):
        return
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2 or "|" not in args[1]:
        await message.answer("Use /removefavorite category | item.")
        return
    category, value = (part.strip() for part in args[1].split("|", maxsplit=1))
    session = get_session()
    try:
        favorite = session.query(Favorite).filter(
            Favorite.user_id == message.from_user.id,
            Favorite.group_id == message.chat.id,
            Favorite.category.ilike(category),
            Favorite.value.ilike(value),
        ).first()
        if favorite is None:
            await message.answer("That favorite was not found in this group.")
            return
        session.delete(favorite)
        session.commit()
        await message.answer("Removed that favorite from this group.")
    except Exception:
        session.rollback()
        logger.exception("Failed to remove Famigo favorite")
        await message.answer("I couldn't remove that favorite. Please try again.")
    finally:
        session.close()


@router.message(Command("favorites"))
async def cmd_favorites(message: types.Message):
    if not await require_group(message):
        return
    session = get_session()
    try:
        favorites = session.query(Favorite).filter(
            Favorite.user_id == message.from_user.id,
            Favorite.group_id == message.chat.id,
        ).order_by(Favorite.category).limit(20).all()
        if not favorites:
            await message.answer("You have no favorites saved in this group yet.")
            return
        await message.answer("Your favorites in this group:\n" + "\n".join(
            f"• {item.category}: {item.value}" for item in favorites
        ))
    except Exception:
        logger.exception("Failed to list Famigo favorites")
        await message.answer("I couldn't load your favorites. Please try again.")
    finally:
        session.close()


@router.message(Command("mood"))
async def cmd_mood(message: types.Message):
    if not await require_group(message):
        return
    args = (message.text or "").split(maxsplit=1)
    session = get_session()
    try:
        if len(args) < 2:
            mood = session.query(MoodStatus).filter(
                MoodStatus.user_id == message.from_user.id,
                MoodStatus.group_id == message.chat.id,
                or_(MoodStatus.expires_at.is_(None), MoodStatus.expires_at > datetime.utcnow()),
            ).order_by(MoodStatus.set_at.desc()).first()
            current = f"Your current mood here is {mood.custom_mood}." if mood else "You have not set a mood here."
            await message.answer(
                f"{current}\nSet one with /mood [mood], or clear it with /mood off.\n"
                f"Options: {', '.join(sorted(MOOD_OPTIONS))}"
            )
            return
        mood_value = args[1].strip().lower()
        previous = session.query(MoodStatus).filter(
            MoodStatus.user_id == message.from_user.id,
            MoodStatus.group_id == message.chat.id,
        ).all()
        for item in previous:
            session.delete(item)
        if mood_value == "off":
            session.commit()
            await message.answer("Your mood was cleared from this group.")
            return
        if mood_value not in MOOD_OPTIONS:
            session.rollback()
            await message.answer(f"Choose one of: {', '.join(sorted(MOOD_OPTIONS))}.")
            return
        service.ensure_user(session, message.from_user.id, message.from_user.username)
        session.add(MoodStatus(
            user_id=message.from_user.id,
            group_id=message.chat.id,
            custom_mood=mood_value,
            set_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24),
        ))
        session.commit()
        await message.answer("Saved your mood in this group for 24 hours.")
    except Exception:
        session.rollback()
        logger.exception("Failed to update Famigo mood")
        await message.answer("I couldn't update your mood. Please try again.")
    finally:
        session.close()


SOCIAL_PLATFORMS = {
    "instagram", "x", "facebook", "youtube", "tiktok", "reddit", "github",
    "discord", "spotify", "letterboxd", "linkedin", "website", "telegram", "custom",
}


@router.message(Command("addsocial"))
async def cmd_addsocial(message: types.Message):
    args = (message.text or "").split(maxsplit=2)
    if len(args) < 3:
        await message.answer("Use /addsocial platform username-or-https-url.")
        return
    platform, value = args[1].lower(), args[2].strip()
    if platform not in SOCIAL_PLATFORMS or not value or len(value) > 200:
        await message.answer("Choose a supported platform and provide a value up to 200 characters.")
        return
    if any(ord(character) < 32 for character in value):
        await message.answer("That link value contains unsupported characters.")
        return
    if value.lower().startswith(("http://", "https://")):
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            await message.answer("Links must use HTTPS and must not contain embedded credentials.")
            return
    elif "://" in value or value.startswith("//") or not re.fullmatch(r"[\w.@+-]+", value):
        await message.answer("Enter a username or a valid HTTPS link.")
        return

    session = get_session()
    try:
        service.ensure_user(session, message.from_user.id, message.from_user.username)
        existing = session.query(SocialLink).filter(
            SocialLink.user_id == message.from_user.id,
            SocialLink.platform == platform,
        ).first()
        if existing is None:
            existing = SocialLink(user_id=message.from_user.id, platform=platform, username_or_url=value)
            session.add(existing)
        else:
            existing.username_or_url = value
        session.commit()
        await message.answer("Saved your link privately. It is not shown in group profiles.")
    except Exception:
        session.rollback()
        logger.exception("Failed to save Famigo social link")
        await message.answer("I couldn't save that link. Please try again.")
    finally:
        session.close()


@router.message(Command("socials"))
async def cmd_socials(message: types.Message):
    session = get_session()
    try:
        links = session.query(SocialLink).filter(
            SocialLink.user_id == message.from_user.id,
        ).order_by(SocialLink.platform).all()
        if not links:
            await message.answer("You have no saved social links.")
            return
        text = "Your saved social links:\n" + "\n".join(
            f"• {link.platform}: {link.username_or_url}" for link in links
        )
        await message.bot.send_message(message.from_user.id, text)
    except Exception:
        logger.info("Could not privately deliver social links for user %s", message.from_user.id)
        await message.answer("Start a private chat with me to view your saved social links.")
    finally:
        session.close()


@router.message(Command("deletesocial"))
async def cmd_deletesocial(message: types.Message):
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Use /deletesocial followed by the platform name.")
        return
    session = get_session()
    try:
        link = session.query(SocialLink).filter(
            SocialLink.user_id == message.from_user.id,
            SocialLink.platform == args[1].lower(),
        ).first()
        if link is None:
            await message.answer("No saved link for that platform was found.")
            return
        session.delete(link)
        session.commit()
        await message.answer("Deleted your saved link.")
    except Exception:
        session.rollback()
        logger.exception("Failed to delete Famigo social link")
        await message.answer("I couldn't delete that link. Please try again.")
    finally:
        session.close()
