"""
Command-level tests for commands/chargen.py's CmdScriptedCreate - the
full narrated "First Awakening" generator, not just the pure logic in
world/chargen.py (already covered by world/test_chargen.py).

CmdScriptedCreate.func() only ever touches `self.caller` (treated as
the Session, per the module's own docstring) via `.msg()`,
`.address`, and `.sessionhandler.login()`. That's narrow enough to
drive directly with a lightweight fake session, without needing
Evennia's full command-dispatch/Twisted-deferred plumbing
(`_progressive_cmd_run`) that normally runs a generator Command -
`_drive()` below plays that role synchronously: it resumes every
numeric (pause) yield immediately (there's no real reactor running in
a synchronous test) and feeds one scripted response per string
(input) yield, in order.

Run with:
    evennia test commands
"""

import itertools
from unittest.mock import Mock

from django.test import TestCase

from commands.chargen import CmdScriptedCreate
from world.build_rooms import build as build_rooms

# Account.create() checks Evennia's module-level CREATION_THROTTLE,
# keyed by IP and not reset between test methods (it isn't DB-backed,
# so Django's per-test transaction rollback doesn't touch it) - reuse
# the same fake address across every test here and the 4th-or-later
# account creation in a run gets silently throttled. A distinct,
# never-repeated address per test sidesteps that entirely.
_next_fake_ip = itertools.count(1)


class _FakeSession:
    def __init__(self):
        self.msgs = []
        self.address = f"10.0.0.{next(_next_fake_ip)}"
        self.sessionhandler = Mock()

    def msg(self, text="", **kwargs):
        self.msgs.append(text)

    @property
    def transcript(self):
        return "\n".join(self.msgs)


def _drive(gen, responses):
    """Run a chargen generator to completion: every numeric yield is
    resumed right away, every string yield gets the next item from
    `responses`. Raises StopIteration when the generator finishes,
    same as a real `for`/`next()` exhaustion - callers catch it."""
    responses = list(responses)
    value = gen.send(None)
    while True:
        if isinstance(value, (int, float)):
            value = gen.send(None)
        else:
            value = gen.send(responses.pop(0))


def _character_from(account):
    return account.db._last_puppet or account.characters.all()[0]


class ScriptedCreateTests(TestCase):
    def setUp(self):
        self.rooms = build_rooms()
        self.session = _FakeSession()
        self.cmd = CmdScriptedCreate()
        self.cmd.caller = self.session

    def test_happy_path_creates_account_and_places_character_in_medical_bay(self):
        gen = self.cmd.func()
        try:
            _drive(
                gen,
                [
                    "Tester1",
                    "female",
                    "Kethari",
                    "confirm",
                    "ScriptedPass123!",
                    "ScriptedPass123!",
                ],
            )
        except StopIteration:
            pass

        self.session.sessionhandler.login.assert_called_once()
        account = self.session.sessionhandler.login.call_args[0][1]
        character = _character_from(account)
        self.assertEqual(character.key, "Tester1")
        self.assertEqual(character.db.sex, "female")
        self.assertEqual(character.db.species, "Kethari")
        self.assertEqual(character.location, self.rooms["medical_bay"])

    def test_password_never_appears_in_any_displayed_line(self):
        gen = self.cmd.func()
        try:
            _drive(
                gen,
                [
                    "Tester2",
                    "male",
                    "Sylari",
                    "confirm",
                    "SuperSecret99!",
                    "SuperSecret99!",
                ],
            )
        except StopIteration:
            pass

        self.assertNotIn("SuperSecret99!", self.session.transcript)

    def test_correction_loop_only_redoes_the_chosen_field(self):
        gen = self.cmd.func()
        try:
            _drive(
                gen,
                [
                    "Tester3",
                    "male",
                    "Sylari",
                    "correct",  # decline the identity summary
                    "species",  # only species was wrong
                    "Voldren",  # corrected species
                    "confirm",  # accept this time
                    "SomePass123!",
                    "SomePass123!",
                ],
            )
        except StopIteration:
            pass

        account = self.session.sessionhandler.login.call_args[0][1]
        character = _character_from(account)
        # Name and sex from the first pass survived unchanged - only
        # the field the player chose to correct was redone.
        self.assertEqual(character.key, "Tester3")
        self.assertEqual(character.db.sex, "male")
        self.assertEqual(character.db.species, "Voldren")

    def test_invalid_species_reprompts_without_losing_name_and_sex(self):
        gen = self.cmd.func()
        try:
            _drive(
                gen,
                [
                    "Tester4",
                    "female",
                    "Not A Species",  # invalid - reprompted
                    "Naevari",
                    "confirm",
                    "AnotherPass123!",
                    "AnotherPass123!",
                ],
            )
        except StopIteration:
            pass

        account = self.session.sessionhandler.login.call_args[0][1]
        character = _character_from(account)
        self.assertEqual(character.db.sex, "female")
        self.assertEqual(character.db.species, "Naevari")
