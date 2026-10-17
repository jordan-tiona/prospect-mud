"""
Tests for the playtest channel (world/playtest_channel.py,
commands/playtest.py, typeclasses.channels.PlaytestChannel): on by
default at login, `off`/`on` sticking across logins, messages reaching
subscribers and the session log, and no channel nicks.

Run with:
    evennia test commands.test_playtest
"""

from unittest.mock import patch

from django.test import TestCase
from evennia import create_account, create_channel
from evennia.accounts.accounts import DefaultAccount

from commands.playtest import CmdPlaytest
from typeclasses.channels import PlaytestChannel
from world.playtest_channel import PLAYTEST_CHANNEL_KEY, ensure_subscribed


def _text(text):
    if isinstance(text, (tuple, list)):
        text = text[0]
    return text or ""


class PlaytestChannelTests(TestCase):
    def setUp(self):
        self.channel = create_channel(PLAYTEST_CHANNEL_KEY, typeclass="typeclasses.channels.PlaytestChannel")
        self.tester = create_account("Tester", "tester@example.com", "testpassword123")
        self.staff = create_account("Staff", "staff@example.com", "testpassword123", permissions=["Builder"])
        for account in (self.tester, self.staff):
            ensure_subscribed(account)

        self.received = {}
        for patcher in (
            patch.object(DefaultAccount, "msg", autospec=True, side_effect=self._record),
            # Not online in a test, but should still hear the channel.
            patch.object(PlaytestChannel, "send_to_online_only", False),
            # Keep test messages out of the real channel log file.
            patch("evennia.comms.comms.logger.log_file"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def _record(self, obj, text=None, **kwargs):
        self.received.setdefault(obj, []).append(_text(text))

    def _seen_by(self, account):
        return "\n".join(self.received.get(account, []))

    def _run(self, account, args, cmdstring="playtest"):
        cmd = CmdPlaytest()
        cmd.caller = account
        cmd.account = account
        cmd.session = None
        cmd.cmdstring = cmdstring
        cmd.args = args
        cmd.func()

    def test_login_subscribes_by_default(self):
        self.assertTrue(self.channel.has_connection(self.tester))

    def test_no_channel_nicks_so_pt_off_isnt_rewritten(self):
        self.assertFalse(self.tester.nicks.get(category="channel", return_obj=True))

    @patch("typeclasses.channels.log_channel_message")
    def test_message_reaches_every_subscriber_and_is_logged(self, mock_log):
        self._run(self.tester, " where is the workshop?", cmdstring="pt")
        self.assertIn("[Playtest] |cTester|n: where is the workshop?", self._seen_by(self.staff))
        self.assertIn("where is the workshop?", self._seen_by(self.tester))
        mock_log.assert_called_once()
        self.assertEqual(mock_log.call_args.kwargs["actor_key"], "Tester")
        self.assertFalse(mock_log.call_args.kwargs["staff"])
        self.assertEqual(mock_log.call_args.kwargs["message"], "where is the workshop?")

    @patch("typeclasses.channels.log_channel_message")
    def test_staff_messages_are_flagged_staff(self, mock_log):
        self._run(self.staff, " try the north exit")
        self.assertTrue(mock_log.call_args.kwargs["staff"])

    def test_off_stops_messages_and_survives_the_next_login(self):
        self._run(self.tester, " off")
        self.assertFalse(self.channel.has_connection(self.tester))
        ensure_subscribed(self.tester)
        self.assertFalse(self.channel.has_connection(self.tester))

        self._run(self.staff, " anyone there?")
        self.assertNotIn("anyone there?", self._seen_by(self.tester))

    def test_posting_while_off_is_refused(self):
        self._run(self.tester, " off")
        self._run(self.tester, " hello?")
        self.assertIn("You're not on the playtest channel", self._seen_by(self.tester))
        self.assertNotIn("hello?", self._seen_by(self.staff))

    def test_on_rejoins_and_clears_the_opt_out(self):
        self._run(self.tester, " off")
        self._run(self.tester, " on")
        self.assertTrue(self.channel.has_connection(self.tester))
        self.assertFalse(self.tester.db.playtest_opted_out)

    @patch("commands.playtest.tail_log_file", return_value=["12:00 Tester: hi\n", "12:01 Staff: hello\n"])
    def test_bare_command_shows_history(self, _mock_tail):
        self._run(self.tester, "")
        self.assertIn("Staff: hello", self._seen_by(self.tester))
