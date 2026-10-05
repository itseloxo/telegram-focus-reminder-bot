import os
import unittest
from datetime import datetime

os.environ.setdefault("BOT_TOKEN", "123456:test")

from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers, sessionmaker

import database
from bot.services import famigo


class FamigoServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_mappers()

    def setUp(self):
        self.engine = create_engine("sqlite://")
        database.Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine, expire_on_commit=False)()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def add_profile(self, user_id, username, group_id, visibility=database.ProfileVisibility.GROUP_ONLY):
        if self.session.query(database.User).filter_by(user_id=user_id).first() is None:
            self.session.add(database.User(user_id=user_id, username=username))
            self.session.flush()
        profile = database.FamigoProfile(
            user_id=user_id,
            group_id=group_id,
            display_name=username,
            visibility=visibility,
        )
        self.session.add(profile)
        self.session.flush()
        return profile

    def test_discovery_is_group_scoped_and_respects_hidden_profiles(self):
        self.add_profile(1, "one", -100, database.ProfileVisibility.GROUP_ONLY)
        visible = self.add_profile(2, "two", -100, database.ProfileVisibility.GROUP_ONLY)
        hidden = self.add_profile(3, "three", -100, database.ProfileVisibility.HIDDEN)
        self.add_profile(4, "four", -200, database.ProfileVisibility.PUBLIC)
        user = famigo.ensure_user(self.session, 2, "two")
        famigo.set_user_preference(self.session, user, "discoverability", False)
        self.session.commit()

        profiles = famigo.list_discoverable_profiles(self.session, -100, 1)

        self.assertEqual([], profiles)
        self.assertNotIn(hidden, profiles)
        self.assertEqual(2, visible.user_id)

    def test_profile_creation_uses_group_only_privacy(self):
        user = famigo.ensure_user(self.session, 5, "fifth")
        profile = famigo.set_profile_field(
            self.session, user, -100, "bio", "Hiking fan", "Fifth"
        )
        self.session.commit()

        self.assertEqual(database.ProfileVisibility.GROUP_ONLY, profile.visibility)

    def test_random_discovery_avoids_immediate_repeat(self):
        self.add_profile(1, "one", -100)
        first = self.add_profile(2, "two", -100)
        second = self.add_profile(3, "three", -100)
        selected_first = famigo.choose_random_profile(
            self.session, 1, -100, [first, second]
        )
        self.session.commit()
        selected_next = famigo.choose_random_profile(
            self.session, 1, -100, [first, second]
        )

        self.assertNotEqual(selected_first.user_id, selected_next.user_id)

    def test_connection_requires_recipient_confirmation_and_checks_callback_owner(self):
        self.add_profile(1, "oneuser", -100)
        self.add_profile(2, "twouser", -100)
        connection, _ = famigo.request_connection(
            self.session, 1, "@twouser", -100, "friend"
        )
        self.session.commit()

        with self.assertRaisesRegex(ValueError, "no longer available"):
            famigo.respond_to_connection(self.session, connection.id, 1, -100, True)
        with self.assertRaisesRegex(ValueError, "no longer available"):
            famigo.respond_to_connection(self.session, connection.id, 2, -200, True)

        famigo.respond_to_connection(self.session, connection.id, 2, -100, True)
        self.session.commit()
        self.assertEqual("accepted", connection.status)
        self.assertIsNotNone(connection.accepted_at)

    def test_connection_requests_are_rate_limited_per_group(self):
        self.add_profile(1, "requester", -100)
        target_ids = range(2, 8)
        for user_id in target_ids:
            self.add_profile(user_id, f"user{user_id}", -100)
        for user_id in range(2, 7):
            famigo.request_connection(
                self.session, 1, None, -100, "friend", target_user_id=user_id
            )
            self.session.commit()

        with self.assertRaisesRegex(ValueError, "maximum number"):
            famigo.request_connection(
                self.session, 1, None, -100, "friend", target_user_id=7
            )

    def test_group_profile_deletion_preserves_other_groups(self):
        self.add_profile(1, "one", -100)
        other_group_profile = self.add_profile(1, "one", -200)
        self.session.add(database.UserInterest(user_id=1, group_id=-100, interest="Books"))
        self.session.add(database.UserInterest(user_id=1, group_id=-200, interest="Music"))
        self.session.add(database.Favorite(
            user_id=1, group_id=-100, category="book", value="Dune"
        ))
        self.session.add(database.MoodStatus(
            user_id=1, group_id=-100, custom_mood="chill", set_at=datetime.utcnow()
        ))
        self.session.commit()

        self.assertTrue(famigo.delete_group_profile(self.session, 1, -100))
        self.session.commit()

        self.assertIsNone(famigo.get_profile(self.session, 1, -100))
        self.assertIsNotNone(famigo.get_profile(self.session, 1, -200))
        self.assertEqual(1, self.session.query(database.UserInterest).filter_by(group_id=-200).count())
        self.assertEqual(0, self.session.query(database.UserInterest).filter_by(group_id=-100).count())
        self.assertEqual(0, self.session.query(database.Favorite).filter_by(group_id=-100).count())
        self.assertEqual(0, self.session.query(database.MoodStatus).filter_by(group_id=-100).count())
        self.assertEqual(-200, other_group_profile.group_id)

    def test_group_data_can_be_deleted_even_without_a_profile(self):
        self.session.add(database.User(user_id=10, username="tenuser"))
        self.session.add(database.Favorite(
            user_id=10, group_id=-100, category="book", value="Dune"
        ))
        self.session.add(database.CurrentlyInto(
            user_id=10, group_id=-100, category="Reading", value="Dune"
        ))
        self.session.commit()

        self.assertTrue(famigo.delete_group_profile(self.session, 10, -100))
        self.session.commit()

        self.assertEqual(0, self.session.query(database.Favorite).filter_by(user_id=10).count())
        self.assertEqual(0, self.session.query(database.CurrentlyInto).filter_by(user_id=10).count())


if __name__ == "__main__":
    unittest.main()
