"""
Tests for commands/scripted_login.py's CmdScriptedLogin - the splash
screen plus "Who are you? / Password:" flow that replaces Evennia's
stock plain-text connect screen. Same lightweight-fake-session
approach as commands/test_chargen.py's `_drive()`, for the same
reason: `func()` only ever touches `self.caller` (the Session) via
`.msg()`, `.address`, and `.sessionhandler.login()`.

Run with:
    evennia test commands
"""

import itertools
from unittest.mock import Mock

from django.conf import settings
from django.test import TestCase, override_settings
from evennia.utils import class_from_module

from commands.scripted_login import CmdScriptedLogin
from world.build_rooms import build as build_rooms
from world.invites import generate_codes

_next_fake_ip = itertools.count(1)


class _FakeSession:
    def __init__(self):
        self.msgs = []
        self.msg_options = []
        self.address = f"10.0.1.{next(_next_fake_ip)}"
        self.sessionhandler = Mock()

    def msg(self, text="", **kwargs):
        self.msgs.append(text)
        self.msg_options.append(kwargs.get("options"))

    @property
    def transcript(self):
        return "\n".join(self.msgs)


def _drive(gen, responses):
    responses = list(responses)
    value = gen.send(None)
    while True:
        if isinstance(value, (int, float)):
            value = gen.send(None)
        else:
            value = gen.send(responses.pop(0))


class ScriptedLoginTests(TestCase):
    def setUp(self):
        # Account.create() points a new character's default home at
        # dbref #2 (settings.DEFAULT_HOME). Nothing else in this test
        # file creates any object, so without this, that dbref is
        # dangling in the full suite (where no other test's rollback
        # leaves a real #2 behind) - same reasoning as
        # commands/test_chargen.py's identical build_rooms() call.
        build_rooms()
        self.session = _FakeSession()
        self.cmd = CmdScriptedLogin()
        self.cmd.caller = self.session

    def test_shows_the_splash_art_before_prompting(self):
        gen = self.cmd.func()
        prompt = gen.send(None)
        self.assertIn("Who are you?", prompt)
        # The splash is the first thing sent, before the prompt itself.
        self.assertIn("\x1b[", self.session.msgs[0])

    def test_splash_is_sent_raw_so_it_is_not_reprocessed_as_evennia_markup(self):
        gen = self.cmd.func()
        gen.send(None)
        self.assertEqual(self.session.msg_options[0], {"raw": True})

    def test_old_style_connect_line_logs_in_without_a_second_password_prompt(self):
        Account = class_from_module(settings.BASE_ACCOUNT_TYPECLASS)
        account, errors = Account.create(
            username="OldStyle1", password="CorrectPass123!", ip=self.session.address
        )
        self.assertTrue(account, errors)

        gen = self.cmd.func()
        try:
            # A single answer to "Who are you?" in the old one-line
            # shape - e.g. a client's pre-configured auto-login string
            # (project owner, 2026-10-14: Mudlet sends exactly this
            # automatically on connect) - must work the same as typing
            # just the name and then the password separately.
            _drive(gen, ["connect OldStyle1 CorrectPass123!"])
        except StopIteration:
            pass

        self.session.sessionhandler.login.assert_called_once_with(self.session, account)
        self.assertNotIn("Password:", self.session.transcript)

    def test_old_style_connect_line_with_only_a_name_still_prompts_for_password(self):
        Account = class_from_module(settings.BASE_ACCOUNT_TYPECLASS)
        account, errors = Account.create(
            username="OldStyle2", password="CorrectPass123!", ip=self.session.address
        )
        self.assertTrue(account, errors)

        gen = self.cmd.func()
        try:
            _drive(gen, ["connect OldStyle2", "CorrectPass123!"])
        except StopIteration:
            pass

        self.session.sessionhandler.login.assert_called_once_with(self.session, account)

    def test_blank_name_creates_a_new_character(self):
        # INVITE_ONLY_REGISTRATION is on by default (world/invites.py)
        # - this hand-off into CmdScriptedCreate goes through its gate
        # too, same as creating directly (commands/test_chargen.py's
        # own dedicated InviteGateTests covers the gate itself).
        code = generate_codes(1)[0]
        gen = self.cmd.func()
        try:
            _drive(
                gen,
                [
                    "",  # blank -> hands off into character creation
                    code,
                    "NewPlayer1",
                    "female",
                    "Kethari",
                    "yes",
                    "confirm",
                    "LoginFlowPass123!",
                    "LoginFlowPass123!",
                ],
            )
        except StopIteration:
            pass

        self.session.sessionhandler.login.assert_called_once()
        account = self.session.sessionhandler.login.call_args[0][1]
        self.assertEqual(account.db._last_puppet.key, "NewPlayer1")

    @override_settings(NEW_ACCOUNT_REGISTRATION_ENABLED=False)
    def test_blank_name_with_registration_disabled_reprompts_instead_of_creating(self):
        gen = self.cmd.func()
        gen.send(None)  # splash + first prompt
        gen.send("")  # blank name, registration disabled
        self.assertIn("Registration is currently disabled.", self.session.transcript)
        self.session.sessionhandler.login.assert_not_called()

    def test_existing_account_logs_in_with_correct_password(self):
        Account = class_from_module(settings.BASE_ACCOUNT_TYPECLASS)
        account, errors = Account.create(
            username="Returning1", password="CorrectPass123!", ip=self.session.address
        )
        self.assertTrue(account, errors)

        gen = self.cmd.func()
        try:
            _drive(gen, ["Returning1", "CorrectPass123!"])
        except StopIteration:
            pass

        self.session.sessionhandler.login.assert_called_once_with(self.session, account)

    def test_wrong_password_reprompts_rather_than_logging_in(self):
        Account = class_from_module(settings.BASE_ACCOUNT_TYPECLASS)
        account, errors = Account.create(
            username="Returning2", password="CorrectPass123!", ip=self.session.address
        )
        self.assertTrue(account, errors)

        gen = self.cmd.func()
        try:
            _drive(
                gen,
                [
                    "Returning2",
                    "WrongPassword!",
                    "Returning2",
                    "CorrectPass123!",
                ],
            )
        except StopIteration:
            pass

        self.session.sessionhandler.login.assert_called_once_with(self.session, account)
