"""
Tests for commands/command.py's _SessionCommandLoggingMixin - the
per-command half of 2026-10-15's per-session logging feature (see
world/session_log.py's docstring for the "why"). Covers that it logs
for a real, logged-in Character, and - just as importantly - that it
stays silent for anything that isn't one, which is what keeps
pre-login/character-creation input (passwords) out of the log
without any special-casing.

Exercises `Command.at_pre_cmd()` directly, the same way cmdhandler
calls it, rather than going through a full command dispatch - cmdset
matching for a non-Character caller isn't the thing under test here.

Run with:
    evennia test commands
"""

from unittest.mock import patch

from django.test import TestCase
from evennia import create_account, create_object

from commands.command import Command

_PASSWORD = "zqv-prospect-test-9273"


class SessionCommandLoggingTests(TestCase):
    def setUp(self):
        self.room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=self.room
        )

    def _make_cmd(self, caller, raw_input="look"):
        cmd = Command()
        cmd.caller = caller
        cmd.raw_string = raw_input
        return cmd

    @patch("commands.command.log_command")
    def test_logs_a_command_for_a_character_with_a_session_id(self, mock_log_command):
        account = create_account("TesterAccount", "tester1@example.com", _PASSWORD)
        self.addCleanup(account.delete)
        account.ndb.session_id = "session-abc"
        self.actor.account = account

        self._make_cmd(self.actor, raw_input="look north").at_pre_cmd()

        mock_log_command.assert_called_once_with(
            session_id="session-abc",
            actor_key="Tester",
            actor_dbref=self.actor.dbref,
            location="Test Room",
            raw_input="look north",
        )

    @patch("commands.command.log_command")
    def test_does_not_log_without_an_account(self, mock_log_command):
        # No account puppeting this character at all - can't happen
        # for a real connected player, but confirms the guard doesn't
        # assume one is always present.
        self._make_cmd(self.actor).at_pre_cmd()

        mock_log_command.assert_not_called()

    @patch("commands.command.log_command")
    def test_does_not_log_without_a_session_id(self, mock_log_command):
        # An account exists but never logged in through our
        # at_post_login hook (so it never got a session_id) -
        # shouldn't crash or log.
        account = create_account("TesterAccount2", "tester2@example.com", _PASSWORD)
        self.addCleanup(account.delete)
        self.actor.account = account

        self._make_cmd(self.actor).at_pre_cmd()

        mock_log_command.assert_not_called()

    @patch("commands.command.log_command")
    def test_does_not_log_for_a_non_character_caller(self, mock_log_command):
        # Simulates the pre-login/character-creation shape: the
        # caller is a plain object, not a typeclasses.characters.
        # Character - this is what keeps password input out of the
        # log, with no special-casing of the login commands
        # themselves.
        account = create_account("TesterAccount3", "tester3@example.com", _PASSWORD)
        self.addCleanup(account.delete)
        account.ndb.session_id = "session-xyz"
        thing = create_object(
            "typeclasses.objects.Object", key="a non-character thing", location=self.room
        )
        thing.account = account

        self._make_cmd(thing).at_pre_cmd()

        mock_log_command.assert_not_called()

    @patch("commands.command.log_command")
    def test_does_not_abort_the_command(self, mock_log_command):
        # at_pre_cmd aborts the command if it returns anything truthy
        # - logging must never do that.
        account = create_account("TesterAccount4", "tester4@example.com", _PASSWORD)
        self.addCleanup(account.delete)
        account.ndb.session_id = "session-abc"
        self.actor.account = account

        result = self._make_cmd(self.actor).at_pre_cmd()

        self.assertFalse(result)
