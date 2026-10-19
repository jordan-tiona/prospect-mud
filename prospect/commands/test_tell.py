"""
Tests for commands/tell.py: finding the recipient by displayed name,
replying with no name, the message format, online-only delivery, the
comms lead-in timing, and tells staying out of the session log.

Run with:
    evennia test commands.test_tell
"""

from unittest.mock import patch

from django.test import TestCase
from evennia import create_object
from evennia.objects.objects import DefaultObject

from commands import tell
from commands.tell import match_recipient


def _text(text):
    if isinstance(text, (tuple, list)):
        text = text[0]
    return text or ""


class TellTests(TestCase):
    def setUp(self):
        self.room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.ravis = create_object("typeclasses.characters.Character", key="Ravis Vardur", location=self.room)
        self.ana = create_object("typeclasses.characters.Character", key="Ana Pell", location=self.room)
        self.offline = create_object("typeclasses.characters.Character", key="Oren Hale", location=self.room)
        self.online = [self.ravis, self.ana]

        self.received = {}
        for patcher in (
            patch.object(DefaultObject, "msg", autospec=True, side_effect=self._record),
            patch("commands.tell.online_characters", side_effect=lambda: list(self.online)),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def _record(self, obj, text=None, **kwargs):
        self.received.setdefault(obj, []).append(_text(text))

    def _seen_by(self, char):
        return "\n".join(self.received.get(char, []))

    def test_full_name(self):
        self.ana.execute_cmd("tell Ravis Vardur meet me at the cafe")
        self.assertIn('Ana Pell tells you, |Y"Meet me at the cafe."|n', self._seen_by(self.ravis))
        self.assertIn('You tell Ravis Vardur, |Y"Meet me at the cafe."|n', self._seen_by(self.ana))

    def test_profanity_is_masked(self):
        self.ana.execute_cmd("tell Ravis this is shit")
        self.assertIn('Ana Pell tells you, |Y"This is ****."|n', self._seen_by(self.ravis))

    def test_first_name_and_case(self):
        self.ana.execute_cmd("tell ravis hi")
        self.assertIn("tells you", self._seen_by(self.ravis))

    def test_equals_form(self):
        self.ana.execute_cmd("tell Ravis = hi there")
        self.assertIn('|Y"Hi there."|n', self._seen_by(self.ravis))

    def test_no_name_replies_to_last_sender(self):
        self.ana.execute_cmd("tell Ravis hi")
        self.ravis.execute_cmd("tell on my way")
        self.assertIn('Ravis Vardur tells you, |Y"On my way."|n', self._seen_by(self.ana))

    def test_no_name_and_no_one_to_reply_to(self):
        self.ana.execute_cmd("tell hello")
        self.assertIn("Usage", self._seen_by(self.ana))
        self.assertNotIn("tells you", self._seen_by(self.ravis))

    def test_offline_player_isnt_found(self):
        self.ana.execute_cmd("tell Oren = hello")
        self.assertIn("No one by that name is in the game", self._seen_by(self.ana))
        self.assertFalse(self.received.get(self.offline))

    def test_reply_to_someone_who_logged_off(self):
        self.ravis.execute_cmd("tell Ana hi")
        self.online.remove(self.ravis)
        self.ana.execute_cmd("tell still there?")
        self.assertIn("isn't in the game right now", self._seen_by(self.ana))

    def test_ambiguous_first_name_is_an_error_not_a_reply(self):
        other = create_object("typeclasses.characters.Character", key="Ravis Toll", location=self.room)
        self.online.append(other)
        self.ravis.execute_cmd("tell Ana hi")
        self.ana.execute_cmd("tell Ravis hello")
        self.assertIn("More than one Ravis", self._seen_by(self.ana))
        self.assertNotIn("Hello.", self._seen_by(self.ravis))

    def test_cannot_tell_yourself(self):
        self.ana.execute_cmd("tell Ana hi")
        self.assertNotIn("tells you", self._seen_by(self.ana))

    def test_longest_name_wins(self):
        target, message, _ = match_recipient("Ravis Vardur hi", [self.ravis])
        self.assertEqual((target, message), (self.ravis, "hi"))

    def test_lead_in_on_first_tell_and_after_a_gap_only(self):
        with patch("commands.tell.time.time") as clock:
            clock.return_value = 1000
            self.ana.execute_cmd("tell Ravis one")
            clock.return_value = 1000 + 60
            self.ana.execute_cmd("tell Ravis two")
            clock.return_value = 1060 + tell.LEAD_IN_GAP_SECONDS + 1
            self.ana.execute_cmd("tell Ravis three")
        self.assertEqual(self._seen_by(self.ravis).count("you hear the voice of Ana Pell"), 2)
        self.assertEqual(self._seen_by(self.ana).count("a line opens to Ravis Vardur"), 2)

    def test_lead_in_comes_before_the_tell(self):
        self.ana.execute_cmd("tell Ravis one")
        self.assertEqual(
            self.received[self.ravis],
            ["Your comms crackle, and you hear the voice of Ana Pell.", 'Ana Pell tells you, |Y"One."|n'],
        )

    @patch("commands.command.log_command")
    @patch("commands.command.session_id_for", return_value="sid")
    def test_tells_arent_logged(self, _sid, mock_log):
        self.ana.execute_cmd("tell Ravis my secret")
        logged = mock_log.call_args.kwargs["raw_input"]
        self.assertEqual(logged, "tell")

    def test_stock_page_is_gone(self):
        from commands.default_cmdsets import AccountCmdSet

        cmdset = AccountCmdSet()
        cmdset.at_cmdset_creation()
        self.assertFalse(any(cmd.key == "page" for cmd in cmdset.commands))
