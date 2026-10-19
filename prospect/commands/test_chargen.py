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
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from evennia import create_object

from commands.chargen import CmdScriptedCreate, species_menu
from typeclasses.objects import indent_paragraphs
from world.chargen import SPECIES_CHOICES, load_species_entries, load_species_groups
from world.build_rooms import build as build_rooms
from world.disclosure import AGREE_PROMPT, DISCLOSURE_VERSION
from world.invites import generate_codes

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
    same as a real `for`/`next()` exhaustion - callers catch it.
    The data disclosure is answered "agree" without taking a response;
    DisclosureTests drives that prompt itself."""
    responses = list(responses)
    value = gen.send(None)
    while True:
        if isinstance(value, (int, float)):
            value = gen.send(None)
        elif value == AGREE_PROMPT:
            value = gen.send("agree")
        else:
            value = gen.send(responses.pop(0))


def _character_from(account):
    return account.db._last_puppet or account.characters.all()[0]


@override_settings(INVITE_ONLY_REGISTRATION=False)
class ScriptedCreateTests(TestCase):
    """
    INVITE_ONLY_REGISTRATION is forced off for this whole class: these
    tests exercise the "First Awakening" script itself, not the
    invite-code gate in front of it (that gate has its own dedicated
    tests in InviteGateTests below).
    """

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
                    "Testera",
                    "female",
                    "Kell",
                    "yes",
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
        self.assertEqual(character.key, "Testera")
        self.assertEqual(character.db.sex, "female")
        self.assertEqual(character.db.species, "Kell")
        self.assertEqual(character.location, self.rooms["medical_bay"])

    def _create(self, responses):
        try:
            _drive(self.cmd.func(), responses)
        except StopIteration:
            pass

    def test_name_with_a_space_makes_an_underscore_account_and_a_spaced_character(self):
        self._create(["jordan tiona", "female", "Kell", "yes", "confirm", "ScriptedPass123!", "ScriptedPass123!"])
        account = self.session.sessionhandler.login.call_args[0][1]
        self.assertEqual(account.username, "Jordan_Tiona")
        self.assertEqual(_character_from(account).key, "Jordan Tiona")
        self.assertIn("(Your account will be created as Jordan_Tiona. Use that name to log in.)", self.session.msgs)

    def test_single_name_shows_no_account_notice(self):
        self._create(["Jordan", "female", "Kell", "yes", "confirm", "ScriptedPass123!", "ScriptedPass123!"])
        self.assertFalse(any("account will be created" in m for m in self.session.msgs))

    def test_digits_and_symbols_reprompt_for_the_name(self):
        self._create(["Jordan2", "J@ck", "Jordan", "female", "Kell", "yes", "confirm",
                      "ScriptedPass123!", "ScriptedPass123!"])
        rejections = [m for m in self.session.msgs if "letters only" in m]
        self.assertEqual(len(rejections), 2)
        account = self.session.sessionhandler.login.call_args[0][1]
        self.assertEqual(_character_from(account).key, "Jordan")

    def test_a_taken_character_name_reprompts(self):
        create_object("typeclasses.characters.Character", key="Jordan Tiona",
                      location=self.rooms["medical_bay"], home=self.rooms["medical_bay"])
        self._create(["Jordan Tiona", "Jordan", "female", "Kell", "yes", "confirm",
                      "ScriptedPass123!", "ScriptedPass123!"])
        self.assertTrue(any("already a character with that name" in m for m in self.session.msgs))
        account = self.session.sessionhandler.login.call_args[0][1]
        self.assertEqual(_character_from(account).key, "Jordan")

    def test_a_profane_name_reprompts(self):
        self._create(["Fuckface", "Jordan", "female", "Kell", "yes", "confirm",
                      "ScriptedPass123!", "ScriptedPass123!"])
        self.assertTrue(any("can't record that name" in m for m in self.session.msgs))
        account = self.session.sessionhandler.login.call_args[0][1]
        self.assertEqual(_character_from(account).key, "Jordan")

    def test_password_never_appears_in_any_displayed_line(self):
        gen = self.cmd.func()
        try:
            _drive(
                gen,
                [
                    "Testerb",
                    "male",
                    "Drask",
                    "yes",
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
                    "Testerc",
                    "male",
                    "Drask",
                    "yes",
                    "correct",  # decline the identity summary
                    "species",  # only species was wrong
                    "Voldren",  # corrected species
                    "yes",
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
        self.assertEqual(character.key, "Testerc")
        self.assertEqual(character.db.sex, "male")
        self.assertEqual(character.db.species, "Voldren")

    def test_invalid_species_reprompts_without_losing_name_and_sex(self):
        gen = self.cmd.func()
        try:
            _drive(
                gen,
                [
                    "Testerd",
                    "female",
                    "Not A Species",  # invalid - reprompted
                    "Revari",
                    "yes",
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
        self.assertEqual(character.db.species, "Revari")

    # -- species entries (content/species.md) --------------------------------

    def _run(self, responses):
        try:
            _drive(self.cmd.func(), responses)
        except StopIteration:
            pass

    def test_declining_an_entry_returns_to_the_list(self):
        self._run(["Testerg", "male", "Drask", "no", "3", "yes", "confirm", "SomePass123!", "SomePass123!"])

        account = self.session.sessionhandler.login.call_args[0][1]
        self.assertEqual(_character_from(account).db.species, "Lirra")
        # Both entries were shown: the declined one, then the chosen one.
        self.assertIn("|YDrask|n", self.session.transcript)
        self.assertIn("|YLirra|n", self.session.transcript)

    def test_entry_is_laid_out_like_a_room(self):
        _preface, entries = load_species_entries()
        self._run(["Testerh", "male", "Kell", "yes", "confirm", "SomePass123!", "SomePass123!"])

        expected = f"|YKell|n\n\n|W{indent_paragraphs(entries['Kell'])}|n\n"
        self.assertIn(expected, self.session.msgs)

    def test_unclear_answer_to_select_reprompts(self):
        self._run(["Testeri", "male", "Kell", "maybe", "yes", "confirm", "SomePass123!", "SomePass123!"])

        self.assertIn("Please answer 'yes' or 'no'", self.session.transcript)
        account = self.session.sessionhandler.login.call_args[0][1]
        self.assertEqual(_character_from(account).db.species, "Kell")

    def test_preface_is_shown_once_even_after_a_species_correction(self):
        preface, _entries = load_species_entries()
        self._run([
            "Testerj", "male", "Drask", "yes",
            "correct", "species", "Voldren", "yes",
            "confirm", "SomePass123!", "SomePass123!",
        ])

        shown = [m for m in self.session.msgs if indent_paragraphs(preface) in m]
        self.assertEqual(len(shown), 1)

    def test_no_comment_text_reaches_the_player(self):
        # species.md's HTML comments hold Provisional anatomy notes.
        self._run(["Testerk", "male", "Selk", "yes", "confirm", "SomePass123!", "SomePass123!"])

        self.assertNotIn("<!--", self.session.transcript)
        self.assertNotIn("Provisional", self.session.transcript)
        self.assertNotIn("sharklike", self.session.transcript)

    def test_creation_still_works_without_species_entries(self):
        with patch("commands.chargen.load_species_entries", return_value=("", {})):
            self._run(["Testerl", "male", "Astrel", "yes", "confirm", "SomePass123!", "SomePass123!"])

        account = self.session.sessionhandler.login.call_args[0][1]
        self.assertEqual(_character_from(account).db.species, "Astrel")
        self.assertIn("|YAstrel|n\n", self.session.msgs)

    def _menus_shown(self, responses):
        """Like _run, but returns every species menu the command yielded
        (prompts don't go through session.msg, so they're not in msgs)."""
        menus = []
        gen = self.cmd.func()
        responses = list(responses)
        try:
            value = gen.send(None)
            while True:
                if isinstance(value, (int, float)):
                    value = gen.send(None)
                    continue
                if value == AGREE_PROMPT:
                    value = gen.send("agree")
                    continue
                if "1. " in value and "7. " in value:
                    menus.append(value)
                value = gen.send(responses.pop(0))
        except StopIteration:
            pass
        return menus

    def test_group_notes_show_on_the_first_menu_only(self):
        groups = load_species_groups()
        menus = self._menus_shown(
            ["Testerm", "male", "Drask", "no", "Revari", "yes", "confirm", "SomePass123!", "SomePass123!"]
        )
        self.assertEqual(len(menus), 2)
        self.assertEqual(menus[0], species_menu(groups, with_notes=True))
        self.assertEqual(menus[1], species_menu(groups, with_notes=False))
        for title, note, _names in groups:
            self.assertIn(note, menus[0])
            self.assertNotIn(note, menus[1])
            self.assertIn(f"|Y{title}|n", menus[1])

    def test_ungrouped_content_gives_the_flat_list(self):
        with patch("commands.chargen.load_species_groups", return_value=[]):
            menus = self._menus_shown(["Testern", "male", "1", "yes", "confirm", "SomePass123!", "SomePass123!"])
        self.assertEqual(menus[0], "\n".join(f"  {i}. {name}" for i, name in enumerate(SPECIES_CHOICES, start=1)))


class SpeciesMenuTests(TestCase):
    GROUPS = [("Group A", "Note A.", SPECIES_CHOICES[:3]), ("Group B", "Note B.", SPECIES_CHOICES[3:])]

    def test_numbers_follow_species_choices_across_groups(self):
        menu = species_menu(self.GROUPS, with_notes=False)
        for i, name in enumerate(SPECIES_CHOICES, start=1):
            self.assertIn(f"    {i}. {name}", menu)

    def test_layout_with_and_without_notes(self):
        first, rest = SPECIES_CHOICES[:3], SPECIES_CHOICES[3:]
        self.assertEqual(
            species_menu(self.GROUPS, with_notes=True),
            "  |YGroup A|n\n  |WNote A.|n\n"
            + "\n".join(f"    {i}. {n}" for i, n in enumerate(first, start=1))
            + "\n\n  |YGroup B|n\n  |WNote B.|n\n"
            + "\n".join(f"    {i}. {n}" for i, n in enumerate(rest, start=4)),
        )
        self.assertNotIn("Note A.", species_menu(self.GROUPS, with_notes=False))


@override_settings(INVITE_ONLY_REGISTRATION=True)
class InviteGateTests(TestCase):
    def setUp(self):
        self.rooms = build_rooms()
        self.session = _FakeSession()
        self.cmd = CmdScriptedCreate()
        self.cmd.caller = self.session

    def _finish_with(self, *, invite_code, name="Testere"):
        gen = self.cmd.func()
        try:
            _drive(
                gen,
                [
                    invite_code,
                    name,
                    "female",
                    "Kell",
                    "yes",
                    "confirm",
                    "ScriptedPass123!",
                    "ScriptedPass123!",
                ],
            )
        except StopIteration:
            pass

    def test_valid_unused_code_lets_creation_proceed(self):
        code = generate_codes(1)[0]

        self._finish_with(invite_code=code)

        self.session.sessionhandler.login.assert_called_once()

    def test_invalid_code_blocks_creation_and_reprompts(self):
        gen = self.cmd.func()
        value = gen.send(None)  # the invite-code prompt
        value = gen.send("not-a-real-code")

        self.assertIn("isn't valid", self.session.transcript)
        # Still waiting on the same prompt, not past the gate -
        # confirmed by the next yield being another string prompt
        # rather than the cinematic's first (numeric, pause) yield.
        self.assertIsInstance(value, str)

    def test_code_is_single_use(self):
        code = generate_codes(1)[0]
        self._finish_with(invite_code=code, name="Testerf")

        second_cmd = CmdScriptedCreate()
        second_cmd.caller = _FakeSession()
        gen = second_cmd.func()
        value = gen.send(None)
        value = gen.send(code)

        self.assertIn("isn't valid", second_cmd.caller.transcript)

    def test_code_check_is_case_and_whitespace_insensitive(self):
        code = generate_codes(1)[0]

        self._finish_with(invite_code=f"  {code.lower()}  ")

        self.session.sessionhandler.login.assert_called_once()


@override_settings(INVITE_ONLY_REGISTRATION=True)
class DisclosureTests(TestCase):
    """world/disclosure.py: after the invite code, before chargen."""

    def setUp(self):
        self.rooms = build_rooms()
        self.session = _FakeSession()
        self.cmd = CmdScriptedCreate()
        self.cmd.caller = self.session
        self.code = generate_codes(1)[0]

    def _to_disclosure(self):
        gen = self.cmd.func()
        gen.send(None)  # invite prompt
        value = gen.send(self.code)
        self.assertEqual(value, AGREE_PROMPT)
        self.assertIn("OpenRouter", self.session.transcript)
        return gen

    def test_welcome_comes_first_and_names_bug_and_feedback(self):
        # LR-DEV-0010: before the agreement, in the same message.
        self._to_disclosure()
        transcript = self.session.transcript
        self.assertLess(transcript.index("Welcome to the Prospect: Elsewhere playtest"), transcript.index("OpenRouter"))
        self.assertIn("type BUG", transcript)
        self.assertIn("type FEEDBACK", transcript)

    def test_quit_ends_registration_and_keeps_the_code(self):
        gen = self._to_disclosure()
        with self.assertRaises(StopIteration):
            gen.send("quit")
        self.assertIn("still unused", self.session.transcript)
        self.session.sessionhandler.login.assert_not_called()

        again = CmdScriptedCreate()
        again.caller = _FakeSession()
        gen = again.func()
        gen.send(None)
        self.assertEqual(gen.send(self.code), AGREE_PROMPT)

    def test_anything_else_asks_again(self):
        gen = self._to_disclosure()
        self.assertEqual(gen.send("sure"), AGREE_PROMPT)

    def test_agreeing_uses_the_code_and_is_recorded_on_the_account(self):
        gen = self._to_disclosure()
        value = gen.send("AGREE")
        try:
            responses = ["Testert", "female", "Kell", "yes", "confirm", "ScriptedPass123!", "ScriptedPass123!"]
            while True:
                if isinstance(value, (int, float)):
                    value = gen.send(None)
                else:
                    value = gen.send(responses.pop(0))
        except StopIteration:
            pass

        account = self.session.sessionhandler.login.call_args[0][1]
        self.assertEqual(account.db.disclosure_agreed["version"], DISCLOSURE_VERSION)

        second = CmdScriptedCreate()
        second.caller = _FakeSession()
        gen = second.func()
        gen.send(None)
        gen.send(self.code)
        self.assertIn("isn't valid", second.caller.transcript)

