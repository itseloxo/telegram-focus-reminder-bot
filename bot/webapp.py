"""Telegram Mini App HTTP endpoints and group-scoped profile API."""

import hashlib
import hmac
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiohttp import web
from sqlalchemy import or_

from bot.services import famigo as service
from config import settings
from database import (
    CurrentlyInto,
    FamigoProfile,
    MoodStatus,
    ProfileVisibility,
    UserInterest,
    UserSettings,
    get_session,
)

logger = logging.getLogger(__name__)
WEBAPP_DIRECTORY = Path(__file__).resolve().parent.parent / "webapp"
BOT_KEY = web.AppKey("bot", Bot)
PROFILE_TEXT_FIELDS = {
    "display_name": 60,
    "bio": 500,
    "city": 80,
    "country": 80,
    "pronouns": 60,
    "profession": 100,
    "languages": 120,
    "fun_fact": 180,
}


def connection_keyboard(connection_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Accept", callback_data=f"famigo_accept_{connection_id}"),
        InlineKeyboardButton(text="Decline", callback_data=f"famigo_decline_{connection_id}"),
    ]])


def normalize_webapp_url(value: str) -> str:
    value = value.strip().rstrip("/")
    if not value:
        return ""
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        return ""
    return value


def validate_init_data(init_data: str, bot_token: str, now: int | None = None) -> dict:
    if not init_data or len(init_data) > 8192:
        raise web.HTTPUnauthorized(text="Missing or invalid Telegram Web App data")
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise web.HTTPUnauthorized(text="Invalid Telegram Web App data") from exc
    data = {}
    for key, value in pairs:
        if key in data:
            raise web.HTTPUnauthorized(text="Invalid Telegram Web App data")
        data[key] = value

    supplied_hash = data.pop("hash", "")
    if not re.fullmatch(r"[a-fA-F0-9]{64}", supplied_hash):
        raise web.HTTPUnauthorized(text="Invalid Telegram Web App signature")
    check_string = "\n".join(f"{key}={data[key]}" for key in sorted(data))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, supplied_hash.lower()):
        raise web.HTTPUnauthorized(text="Invalid Telegram Web App signature")

    try:
        auth_date = int(data["auth_date"])
        telegram_user = json.loads(data["user"])
        user_id = int(telegram_user["id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise web.HTTPUnauthorized(text="Invalid Telegram Web App user data") from exc
    current_time = int(time.time()) if now is None else now
    if auth_date > current_time + 60 or current_time - auth_date > 86400 or user_id <= 0:
        raise web.HTTPUnauthorized(text="Telegram session expired; reopen the Mini App")
    return {"user": telegram_user, "user_id": user_id}


async def authenticate(request: web.Request) -> dict:
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("tma "):
        raise web.HTTPUnauthorized(text="Open Famigo from Telegram to continue")
    return validate_init_data(
        authorization[4:],
        settings.bot_token,
    )


async def verify_group_member(bot, user_id: int, group_id: int):
    try:
        chat = await bot.get_chat(group_id)
        if chat.type not in {"group", "supergroup"}:
            raise web.HTTPForbidden(text="Famigo data is only available in Telegram groups")
        member = await bot.get_chat_member(group_id, user_id)
    except web.HTTPException:
        raise
    except Exception as exc:
        logger.info("Could not verify group %s membership for user %s", group_id, user_id, exc_info=True)
        raise web.HTTPForbidden(
            text="I couldn't verify your group membership. Check that the bot is an admin in the group."
        ) from exc
    if member.status in {"left", "kicked"} or (
        member.status == "restricted" and not member.is_member
    ):
        raise web.HTTPForbidden(text="You must be a current member of this group")
    return chat


@web.middleware
async def json_errors(request, handler):
    try:
        return await handler(request)
    except web.HTTPException as exc:
        if request.path.startswith("/api/"):
            return web.json_response({"error": exc.text}, status=exc.status)
        raise
    except Exception:
        logger.exception("Mini App request failed")
        return web.json_response({"error": "Something went wrong. Please try again."}, status=500)


def get_group_id(request: web.Request) -> int:
    raw_group_id = request.query.get("group_id")
    if raw_group_id is None or not re.fullmatch(r"-?\d{1,20}", raw_group_id):
        raise web.HTTPBadRequest(text="Choose a valid Telegram group")
    return int(raw_group_id)


def profile_json(session, profile: FamigoProfile, group_id: int) -> dict:
    user = session.query(service.User).filter(service.User.user_id == profile.user_id).first()
    interests = [
        row[0] for row in session.query(UserInterest.interest).filter(
            UserInterest.user_id == profile.user_id,
            UserInterest.group_id == group_id,
        ).order_by(UserInterest.interest).limit(20).all()
    ]
    activities = [
        {"category": item.category, "value": item.value}
        for item in session.query(CurrentlyInto).filter(
            CurrentlyInto.user_id == profile.user_id,
            CurrentlyInto.group_id == group_id,
            or_(CurrentlyInto.expires_at.is_(None), CurrentlyInto.expires_at > datetime.utcnow()),
        ).order_by(CurrentlyInto.set_at.desc()).limit(5).all()
    ]
    mood = session.query(MoodStatus).filter(
        MoodStatus.user_id == profile.user_id,
        MoodStatus.group_id == group_id,
        or_(MoodStatus.expires_at.is_(None), MoodStatus.expires_at > datetime.utcnow()),
    ).order_by(MoodStatus.set_at.desc()).first()
    return {
        "user_id": profile.user_id,
        "username": user.username if user else None,
        "display_name": profile.display_name or "Community member",
        "bio": profile.bio or "",
        "city": profile.city or "",
        "country": profile.country or "",
        "pronouns": profile.pronouns or "",
        "profession": profile.profession or "",
        "languages": profile.languages or "",
        "fun_fact": profile.fun_fact or "",
        "interests": interests,
        "activities": activities,
        "mood": mood.custom_mood if mood else None,
        "reputation": profile.reputation or 0,
        "level": profile.level or 1,
        "visibility": profile.visibility.value if profile.visibility else "group_only",
    }


async def groups(request: web.Request):
    auth = await authenticate(request)
    bot = request.app[BOT_KEY]
    session = get_session()
    try:
        group_ids = [
            row[0] for row in session.query(FamigoProfile.group_id).filter(
                FamigoProfile.user_id == auth["user_id"]
            ).distinct().all()
        ]
    finally:
        session.close()

    available = []
    for group_id in group_ids:
        try:
            chat = await verify_group_member(bot, auth["user_id"], group_id)
        except web.HTTPException as exc:
            if "couldn't verify" in exc.text:
                raise
            continue
        available.append({"id": group_id, "title": chat.title or "Telegram group"})
    return web.json_response({"groups": available})


async def community(request: web.Request):
    auth = await authenticate(request)
    group_id = get_group_id(request)
    chat = await verify_group_member(request.app[BOT_KEY], auth["user_id"], group_id)
    session = get_session()
    try:
        own_profile = service.get_profile(session, auth["user_id"], group_id)
        profiles = service.list_discoverable_profiles(session, group_id, auth["user_id"])
        settings_by_user = {
            item.user_id: item for item in session.query(UserSettings).filter(
                UserSettings.user_id.in_([profile.user_id for profile in profiles])
            ).all()
        } if profiles else {}
        profiles = [
            profile for profile in profiles
            if settings_by_user.get(profile.user_id) is None
            or settings_by_user[profile.user_id].allow_discoveries
        ]
        directory = []
        for profile in profiles[:100]:
            try:
                member = await request.app[BOT_KEY].get_chat_member(group_id, profile.user_id)
            except Exception as exc:
                logger.info("Could not verify profile owner %s in group %s", profile.user_id, group_id, exc_info=True)
                raise web.HTTPForbidden(
                    text="I couldn't verify group members. Make the bot an admin and try again."
                ) from exc
            if member.status in {"left", "kicked"} or (
                member.status == "restricted" and not member.is_member
            ):
                continue
            directory.append(profile_json(session, profile, group_id))
        own = profile_json(session, own_profile, group_id) if own_profile else None
        return web.json_response({
            "group": {"id": group_id, "title": chat.title or "Telegram group"},
            "self": {"user_id": auth["user_id"], "first_name": auth["user"].get("first_name", "Member")},
            "profile": own,
            "profiles": directory,
        })
    finally:
        session.close()


async def save_profile(request: web.Request):
    auth = await authenticate(request)
    group_id = get_group_id(request)
    await verify_group_member(request.app[BOT_KEY], auth["user_id"], group_id)
    try:
        payload = await request.json()
    except (json.JSONDecodeError, web.HTTPBadRequest) as exc:
        raise web.HTTPBadRequest(text="Send valid profile data") from exc
    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(text="Send valid profile data")

    session = get_session()
    try:
        user = service.ensure_user(session, auth["user_id"], auth["user"].get("username"))
        profile = service.get_profile(session, auth["user_id"], group_id)
        if profile is None:
            profile = FamigoProfile(
                user_id=auth["user_id"],
                group_id=group_id,
                display_name=auth["user"].get("first_name") or "Member",
                visibility=ProfileVisibility.GROUP_ONLY,
            )
            session.add(profile)
            session.flush()

        for field, maximum in PROFILE_TEXT_FIELDS.items():
            value = payload.get(field, getattr(profile, field) or "")
            if not isinstance(value, str) or len(value.strip()) > maximum:
                raise web.HTTPBadRequest(text=f"{field.replace('_', ' ').title()} is too long or invalid")
            if field == "display_name" and not value.strip():
                value = auth["user"].get("first_name") or "Member"
            setattr(profile, field, value.strip() or None)

        if "visibility" in payload:
            try:
                visibility = ProfileVisibility(payload["visibility"])
            except (ValueError, TypeError) as exc:
                raise web.HTTPBadRequest(
                    text="Choose group_only or hidden for this group's profile"
                ) from exc
            if visibility not in {ProfileVisibility.GROUP_ONLY, ProfileVisibility.HIDDEN}:
                raise web.HTTPBadRequest(
                    text="Choose group_only or hidden for this group's profile"
                )
            profile.visibility = visibility

        if "interests" in payload:
            interests = payload["interests"]
            if (
                not isinstance(interests, list)
                or len(interests) > 20
                or any(not isinstance(value, str) or not value.strip() or len(value.strip()) > 80 for value in interests)
            ):
                raise web.HTTPBadRequest(text="Add up to 20 interests, each no longer than 80 characters")
            clean_interests = list(dict.fromkeys(value.strip() for value in interests))
            session.query(UserInterest).filter(
                UserInterest.user_id == auth["user_id"],
                UserInterest.group_id == group_id,
            ).delete(synchronize_session=False)
            session.add_all([
                UserInterest(
                    user_id=auth["user_id"],
                    group_id=group_id,
                    interest=value,
                    is_custom=True,
                )
                for value in clean_interests
            ])
        session.commit()
        return web.json_response({"ok": True})
    except web.HTTPException:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def connect(request: web.Request):
    auth = await authenticate(request)
    group_id = get_group_id(request)
    await verify_group_member(request.app[BOT_KEY], auth["user_id"], group_id)
    try:
        payload = await request.json()
        target_id = int(payload["target_user_id"])
    except (json.JSONDecodeError, web.HTTPBadRequest, KeyError, TypeError, ValueError) as exc:
        raise web.HTTPBadRequest(text="Choose a valid group profile") from exc
    if target_id <= 0 or target_id == auth["user_id"]:
        raise web.HTTPBadRequest(text="Choose another group member")
    await verify_group_member(request.app["bot"], target_id, group_id)

    session = get_session()
    try:
        connection, target = service.request_connection(
            session,
            auth["user_id"],
            None,
            group_id,
            "friend",
            target_user_id=target_id,
        )
        session.commit()
        keyboard = connection_keyboard(connection.id)
        chat = await request.app[BOT_KEY].get_chat(group_id)
        sender = auth["user"].get("first_name") or "A group member"
        target_profile = service.get_profile(session, target.user_id, group_id)
        target_name = target_profile.display_name if target_profile else "Member"
        try:
            await request.app[BOT_KEY].send_message(
                group_id,
                f"{target_name}, {sender} would like to connect with you in {chat.title or 'this group'}. "
                "Only you can accept or decline.",
                reply_markup=keyboard,
            )
        except Exception as exc:
            connection.status = "cancelled"
            session.commit()
            logger.exception("Could not deliver group connection request")
            raise web.HTTPServiceUnavailable(
                text="The request could not be delivered in the group. Please try again later."
            ) from exc
        return web.json_response({"ok": True})
    except ValueError as exc:
        session.rollback()
        raise web.HTTPBadRequest(text=str(exc)) from exc
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def index(_request: web.Request):
    return web.FileResponse(WEBAPP_DIRECTORY / "index.html")


async def health(_request: web.Request):
    return web.json_response({"status": "ok"})


def create_web_app(bot) -> web.Application:
    app = web.Application(middlewares=[json_errors], client_max_size=16 * 1024)
    app[BOT_KEY] = bot
    app.router.add_get("/health", health)
    app.router.add_get("/", index)
    app.router.add_get("/api/groups", groups)
    app.router.add_get("/api/community", community)
    app.router.add_post("/api/profile", save_profile)
    app.router.add_post("/api/connect", connect)
    return app
