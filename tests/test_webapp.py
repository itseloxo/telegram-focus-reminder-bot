import hashlib
import hmac
import json
import time
import unittest
from urllib.parse import urlencode
from unittest.mock import patch
from types import SimpleNamespace

from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database
from bot import webapp
from bot.webapp import create_web_app, validate_init_data


def signed_init_data(bot_token, user, auth_date):
    values = {
        "auth_date": str(auth_date),
        "user": json.dumps(user, separators=(",", ":")),
    }
    data_check_string = "\n".join(
        f"{key}={values[key]}" for key in sorted(values)
    )
    secret_key = hmac.new(
        b"WebAppData", bot_token.encode(), hashlib.sha256
    ).digest()
    values["hash"] = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    return urlencode(values)


class TelegramWebAppAuthTests(unittest.TestCase):
    def setUp(self):
        self.token = "123456:unit-test-token"
        self.now = 1_800_000_000
        self.init_data = signed_init_data(
            self.token,
            {"id": 12345, "first_name": "Famigo"},
            self.now,
        )

    def test_accepts_valid_telegram_init_data(self):
        auth = validate_init_data(self.init_data, self.token, now=self.now)
        self.assertEqual(12345, auth["user_id"])
        self.assertEqual("Famigo", auth["user"]["first_name"])

    def test_rejects_tampered_init_data(self):
        tampered = self.init_data.replace("12345", "54321")
        with self.assertRaises(web.HTTPUnauthorized):
            validate_init_data(tampered, self.token, now=self.now)

    def test_rejects_expired_init_data(self):
        with self.assertRaises(web.HTTPUnauthorized):
            validate_init_data(self.init_data, self.token, now=self.now + 86401)

    def test_rejects_duplicate_fields(self):
        duplicate = self.init_data + "&auth_date=" + str(self.now)
        with self.assertRaises(web.HTTPUnauthorized):
            validate_init_data(duplicate, self.token, now=self.now)


class MiniAppRouteTests(AioHTTPTestCase):
    async def get_application(self):
        return create_web_app(bot=object())

    async def test_health_and_static_app_are_served(self):
        health = await self.client.get("/health")
        self.assertEqual(200, health.status)
        self.assertEqual({"status": "ok"}, await health.json())

        page = await self.client.get("/")
        self.assertEqual(200, page.status)
        self.assertIn("Famigo", await page.text())

    async def test_api_rejects_requests_without_telegram_authentication(self):
        response = await self.client.get("/api/community?group_id=-1001")
        self.assertEqual(401, response.status)
        self.assertIn("Open Famigo from Telegram", (await response.json())["error"])


class MiniAppGroupScopeTests(AioHTTPTestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        database.Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        session = self.session_factory()
        session.add_all([
            database.User(user_id=1, username="viewer"),
            database.User(user_id=2, username="same_group"),
            database.User(user_id=3, username="other_group"),
        ])
        session.add_all([
            database.FamigoProfile(
                user_id=1, group_id=-100, display_name="Viewer",
                visibility=database.ProfileVisibility.GROUP_ONLY,
            ),
            database.FamigoProfile(
                user_id=2, group_id=-100, display_name="Same group member",
                visibility=database.ProfileVisibility.GROUP_ONLY,
            ),
            database.FamigoProfile(
                user_id=3, group_id=-200, display_name="Other group member",
                visibility=database.ProfileVisibility.GROUP_ONLY,
            ),
        ])
        session.add_all([
            database.UserInterest(user_id=2, group_id=-100, interest="Music"),
            database.UserInterest(user_id=3, group_id=-200, interest="Private hobby"),
        ])
        session.commit()
        session.close()
        self.db_patch = patch("bot.webapp.get_session", side_effect=self.session_factory)
        self.db_patch.start()
        self.bot = _FakeTelegramBot()
        self.init_data = signed_init_data(
            database.settings.bot_token,
            {"id": 1, "first_name": "Viewer"},
            int(time.time()),
        )
        super().setUp()

    def tearDown(self):
        self.db_patch.stop()
        self.engine.dispose()
        super().tearDown()

    async def get_application(self):
        return create_web_app(self.bot)

    async def test_directory_only_returns_profiles_for_the_selected_group(self):
        response = await self.client.get(
            "/api/community?group_id=-100",
            headers={"Authorization": f"tma {self.init_data}"},
        )
        self.assertEqual(200, response.status)
        data = await response.json()
        self.assertEqual([-100], [data["group"]["id"]])
        self.assertEqual([2], [profile["user_id"] for profile in data["profiles"]])
        self.assertEqual(["Music"], data["profiles"][0]["interests"])
        self.assertNotIn("Private hobby", await response.text())

    async def test_member_cannot_open_a_group_they_left(self):
        self.bot.membership[(1, -200)] = "left"
        response = await self.client.get(
            "/api/community?group_id=-200",
            headers={"Authorization": f"tma {self.init_data}"},
        )
        self.assertEqual(403, response.status)


class _FakeTelegramBot:
    def __init__(self):
        self.membership = {}

    async def get_chat(self, group_id):
        return SimpleNamespace(type="supergroup", title=f"Group {group_id}")

    async def get_chat_member(self, group_id, user_id):
        status = self.membership.get((user_id, group_id), "member")
        return SimpleNamespace(status=status, is_member=status != "left")


if __name__ == "__main__":
    unittest.main()
