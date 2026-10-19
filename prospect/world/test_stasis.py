"""
Tests for stasis on logout and login (world/stasis.py,
Character.at_post_unpuppet/at_post_puppet, commands/quit.py).
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase
from evennia import create_object
from evennia.objects.objects import DefaultObject

from commands.quit import CmdQuit
from world.stasis import GOING_LINES, QUIT_DELAY_SECONDS, QUIT_SELF_LINE, RETURN_SELF_LINE, RETURNING_LINES


def _text(text):
    if isinstance(text, (tuple, list)):
        text = text[0]
    return text if isinstance(text, str) else ""


def _lines(template_set, name):
    return [t.format(name=name) for t in template_set]


class StasisTests(TestCase):
    def setUp(self):
        self.room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.ana = create_object("typeclasses.characters.Character", key="Ana Pell", location=self.room)
        self.ravis = create_object("typeclasses.characters.Character", key="Ravis Vardur", location=self.room)
        self.received = {}
        patcher = patch.object(DefaultObject, "msg", autospec=True, side_effect=self._record)
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in ("world.tutorial.announce_tannoy", "world.idle_emotes.start_room_emotes",
                     "world.gmcp.send_char_status", "world.gmcp.send_room_info"):
            p = patch(name)
            p.start()
            self.addCleanup(p.stop)

    def _record(self, obj, text=None, **kwargs):
        self.received.setdefault(obj, []).append(_text(text))

    def _seen_by(self, char):
        return "\n".join(self.received.get(char, []))

    def _saw_one_of(self, char, lines):
        return any(line in self._seen_by(char) for line in lines)

    # -- going into stasis ----------------------------------------------

    def test_logout_shows_the_room_and_leaves_the_listing(self):
        self.ana.at_post_unpuppet()
        self.assertTrue(self._saw_one_of(self.ravis, _lines(GOING_LINES, "Ana Pell")))
        self.assertNotIn("has left the game", self._seen_by(self.ravis))
        self.assertIsNone(self.ana.location)
        self.assertEqual(self.ana.db.prelogout_location, self.room)

    def test_a_line_already_shown_by_quit_isnt_repeated(self):
        self.ana.ndb.stasis_announced = True
        self.ana.at_post_unpuppet()
        self.assertFalse(self._saw_one_of(self.ravis, _lines(GOING_LINES, "Ana Pell")))
        self.assertIsNone(self.ana.location)
        self.assertFalse(self.ana.ndb.stasis_announced)

    def test_a_takeover_shows_nothing(self):
        account = MagicMock()
        account.ndb.stasis_takeover = True
        self.ana.at_post_unpuppet(account=account)
        self.assertEqual(self._seen_by(self.ravis), "")

    # -- coming out of stasis -------------------------------------------

    def test_a_returning_character_comes_out_of_stasis(self):
        self.ana.db.prelogout_location = self.room
        self.ana.at_post_puppet()
        self.assertIn(RETURN_SELF_LINE, self._seen_by(self.ana))
        self.assertTrue(self._saw_one_of(self.ravis, _lines(RETURNING_LINES, "Ana Pell")))
        self.assertNotIn("has entered the game", self._seen_by(self.ravis))

    def test_a_new_character_gets_no_stasis_lines(self):
        self.ana.at_post_puppet()
        self.assertNotIn(RETURN_SELF_LINE, self._seen_by(self.ana))
        self.assertEqual(self._seen_by(self.ravis), "")

    def test_a_takeover_login_gets_no_stasis_lines(self):
        self.ana.db.prelogout_location = self.room
        account = MagicMock()
        account.ndb.stasis_takeover = True
        with patch.object(type(self.ana), "account", new=account):
            self.ana.at_post_puppet()
        self.assertNotIn(RETURN_SELF_LINE, self._seen_by(self.ana))
        self.assertEqual(self._seen_by(self.ravis), "")


class QuitTests(TestCase):
    def setUp(self):
        self.room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.ana = create_object("typeclasses.characters.Character", key="Ana Pell", location=self.room)
        self.ravis = create_object("typeclasses.characters.Character", key="Ravis Vardur", location=self.room)
        self.received = {}
        patcher = patch.object(DefaultObject, "msg", autospec=True, side_effect=self._record)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.session = MagicMock(puppet=self.ana, sessid=42)
        self.account = MagicMock()
        self.account.sessions.all.return_value = [self.session]
        self.cmd = CmdQuit()
        self.cmd.session = self.session
        self.cmd.account = self.account
        self.cmd.caller = self.account
        self.cmd.switches = []

    def _record(self, obj, text=None, **kwargs):
        self.received.setdefault(obj, []).append(_text(text))

    def _seen_by(self, char):
        return "\n".join(self.received.get(char, []))

    @patch("commands.quit.delay")
    def test_quit_shows_both_lines_then_waits(self, mock_delay):
        self.cmd.func()
        self.assertIn(QUIT_SELF_LINE, self._seen_by(self.ana))
        self.assertTrue(any(line in self._seen_by(self.ravis) for line in _lines(GOING_LINES, "Ana Pell")))
        self.assertEqual(mock_delay.call_args.args[0], QUIT_DELAY_SECONDS)
        self.account.disconnect_session_from_account.assert_not_called()
        self.assertTrue(self.ana.ndb.stasis_announced)

    @patch("commands.quit.delay")
    def test_the_delay_ends_in_a_disconnect(self, mock_delay):
        self.cmd.func()
        with patch("commands.quit.SESSION_HANDLER", {42: self.session}):
            mock_delay.call_args.args[1]()
        self.account.disconnect_session_from_account.assert_called_once_with(self.session, "quit")

    @patch("commands.quit.delay")
    def test_a_connection_gone_during_the_delay_isnt_disconnected_twice(self, mock_delay):
        self.cmd.func()
        with patch("commands.quit.SESSION_HANDLER", {}):
            mock_delay.call_args.args[1]()
        self.account.disconnect_session_from_account.assert_not_called()

    @patch("commands.quit.delay")
    def test_quitting_again_during_the_delay_does_nothing(self, mock_delay):
        self.cmd.func()
        self.cmd.func()
        self.assertEqual(mock_delay.call_count, 1)
        self.assertEqual(self._seen_by(self.ana).count(QUIT_SELF_LINE), 1)

    @patch("commands.quit.delay")
    def test_quit_all_disconnects_at_once(self, mock_delay):
        self.cmd.switches = ["all"]
        self.cmd.func()
        mock_delay.assert_not_called()
        self.account.disconnect_session_from_account.assert_called_once_with(self.session, "quit/all")
