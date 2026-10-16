"""
Tests for typeclasses/characters.py's Character.at_post_move - just
the structured `room_changed` gameplay event (world/session_log.py,
game-plan.md 6.2) it logs, not the glance-on-arrival/tutorial-nudge
behavior already covered elsewhere (world/test_tutorial.py).

Run with:
    evennia test typeclasses
"""

from unittest.mock import patch

from django.test import TestCase
from evennia import create_account, create_object

_PASSWORD = "zqv-prospect-test-9273"


class RoomChangedEventTests(TestCase):
    def setUp(self):
        self.room_a = create_object("typeclasses.rooms.Room", key="Room A")
        self.room_b = create_object("typeclasses.rooms.Room", key="Room B")
        self.character = create_object(
            "typeclasses.characters.Character", key="Tester", location=self.room_a
        )
        self.character.msg = lambda text="", **kw: None

    @patch("typeclasses.characters.log_room_changed")
    def test_logs_room_changed_for_a_character_with_a_session_id(self, mock_log):
        account = create_account("RoomTesterAccount", "roomtester@example.com", _PASSWORD)
        self.addCleanup(account.delete)
        account.ndb.session_id = "session-abc"
        self.character.account = account

        self.character.move_to(self.room_b, quiet=True)

        mock_log.assert_called_once_with(
            session_id="session-abc",
            actor_key="Tester",
            actor_dbref=self.character.dbref,
            from_location="Room A",
            to_location="Room B",
        )

    @patch("typeclasses.characters.log_room_changed")
    def test_does_not_log_without_a_session_id(self, mock_log):
        self.character.move_to(self.room_b, quiet=True)

        mock_log.assert_not_called()
