"""
Tests for the `say`-addressing rule (world/npc_addressing.py), per
design-bible 16.5 (adopted 2026-10-11). This is where a silent bug
would call the model for ambient chatter never meant for an NPC, or
fail to resolve a message a player clearly meant for one - see
CLAUDE.md's call-out of the tool validator and prompt builder for the
same reason.

Needs real DB-backed rooms/NPCs, so these use TestCase (not
SimpleTestCase) and build the phase 1 neighborhood in setUp.

Run with:
    evennia test world
"""

from django.test import TestCase
from evennia import create_object

from world.build_npcs import build as build_npcs
from world.build_rooms import build as build_rooms
from world.npc_addressing import resolve_addressee


class NpcAddressingTests(TestCase):
    def setUp(self):
        rooms = build_rooms()
        npcs = build_npcs()
        self.cafe = rooms["corner_cafe"]
        self.mara = npcs["mara_voss"]
        self.tarin = npcs["tarin_os"]
        self.iri = npcs["iri_vael"]
        self.actor = create_object("typeclasses.characters.Character", key="Tester", location=self.cafe)

    def _add_other_player(self):
        return create_object("typeclasses.characters.Character", key="Other", location=self.cafe)

    # -- lone player, lone NPC: implicit addressing ----------------------

    def test_lone_player_lone_npc_implicitly_addressed(self):
        npc, message = resolve_addressee("hello there", self.cafe)
        self.assertIs(npc, self.mara)
        self.assertEqual(message, "hello there")

    def test_no_npc_present_is_ambient(self):
        self.mara.location = None
        npc, message = resolve_addressee("hello there", self.cafe)
        self.assertIsNone(npc)
        self.assertEqual(message, "hello there")

    # -- multiple players: name required ---------------------------------

    def test_multiple_players_no_name_is_ambient(self):
        self._add_other_player()
        npc, message = resolve_addressee("hello there", self.cafe)
        self.assertIsNone(npc)

    def test_multiple_players_name_mention_resolves_and_keeps_text(self):
        self._add_other_player()
        npc, message = resolve_addressee("hey, how are you, Mara?", self.cafe)
        self.assertIs(npc, self.mara)
        self.assertEqual(message, "hey, how are you, Mara?")

    # -- a name opening the line is addressing, like "to <name>" ----------

    def test_leading_name_with_comma_strips_name(self):
        self._add_other_player()
        npc, message = resolve_addressee("Mara, how are you?", self.cafe)
        self.assertIs(npc, self.mara)
        self.assertEqual(message, "how are you?")

    def test_leading_name_without_comma_strips_name(self):
        # Live 2026-10-20: "say Iri hello" reached Iri as "Iri hello."
        # and she repeated it back.
        self._add_other_player()
        npc, message = resolve_addressee("Mara hello", self.cafe)
        self.assertIs(npc, self.mara)
        self.assertEqual(message, "hello")

    def test_leading_full_name_strips_whole_name(self):
        self.tarin.move_to(self.cafe, quiet=True)
        npc, message = resolve_addressee("Mara Voss, hello there", self.cafe)
        self.assertIs(npc, self.mara)
        self.assertEqual(message, "hello there")

    def test_leading_possessive_is_not_stripped(self):
        self._add_other_player()
        npc, message = resolve_addressee("Mara's coffee is good", self.cafe)
        self.assertIs(npc, self.mara)
        self.assertEqual(message, "Mara's coffee is good")

    def test_leading_name_alone_leaves_nothing_to_say(self):
        self._add_other_player()
        npc, message = resolve_addressee("Mara", self.cafe)
        self.assertIs(npc, self.mara)
        self.assertEqual(message, "")

    def test_leading_name_of_absent_npc_is_kept_for_the_npc_present(self):
        # In the café, "Iri hello" isn't addressing Iri (she isn't
        # here) - Mara, alone with the player, hears the whole line.
        npc, message = resolve_addressee("Iri hello", self.cafe)
        self.assertIs(npc, self.mara)
        self.assertEqual(message, "Iri hello")

    def test_whole_word_match_rejects_substring(self):
        self._add_other_player()
        npc, _ = resolve_addressee("Maranatha is not her name", self.cafe)
        self.assertIsNone(npc)

    def test_alias_first_name_matches(self):
        self._add_other_player()
        npc, _ = resolve_addressee("hey Mara, got a sec?", self.cafe)
        self.assertIs(npc, self.mara)

    # -- explicit "to <name>" syntax --------------------------------------

    def test_explicit_to_with_comma_strips_prefix(self):
        self._add_other_player()
        npc, message = resolve_addressee("to Mara Voss, hello there", self.cafe)
        self.assertIs(npc, self.mara)
        self.assertEqual(message, "hello there")

    def test_explicit_to_without_comma_strips_prefix(self):
        self._add_other_player()
        npc, message = resolve_addressee("to Mara Voss hello there", self.cafe)
        self.assertIs(npc, self.mara)
        self.assertEqual(message, "hello there")

    def test_explicit_to_with_alias_strips_only_the_alias(self):
        self._add_other_player()
        npc, message = resolve_addressee("to Mara, hello there", self.cafe)
        self.assertIs(npc, self.mara)
        self.assertEqual(message, "hello there")

    def test_explicit_to_naming_absent_npc_is_ambient(self):
        self._add_other_player()
        npc, message = resolve_addressee("to Tarin, hello there", self.cafe)
        self.assertIsNone(npc)
        self.assertEqual(message, "to Tarin, hello there")

    def test_to_prefix_that_isnt_addressing_falls_through_to_mention_scan(self):
        # "to be honest" isn't "to <NPC name>" - should fall through to
        # a plain name-mention scan over the whole message instead of
        # being swallowed as unrecognized addressing syntax.
        self._add_other_player()
        npc, message = resolve_addressee("to be honest, Mara is great", self.cafe)
        self.assertIs(npc, self.mara)
        self.assertEqual(message, "to be honest, Mara is great")

    # -- multiple NPCs present: name required even for a lone player -----

    def test_multiple_npcs_present_requires_name_even_for_lone_player(self):
        self.tarin.move_to(self.cafe, quiet=True)
        npc, _ = resolve_addressee("hello there", self.cafe)
        self.assertIsNone(npc)

    def test_multiple_npcs_present_with_name_resolves_the_named_one(self):
        self.tarin.move_to(self.cafe, quiet=True)
        npc, _ = resolve_addressee("Tarin, got a minute?", self.cafe)
        self.assertIs(npc, self.tarin)

    def test_longest_name_wins_over_shorter_alias(self):
        self.tarin.move_to(self.cafe, quiet=True)
        npc, message = resolve_addressee("to Mara Voss, hello there", self.cafe)
        self.assertIs(npc, self.mara)
        self.assertEqual(message, "hello there")

    # -- conversational focus: unaddressed follow-up continues it ---------

    def test_unaddressed_followup_continues_focused_npc(self):
        self.tarin.move_to(self.cafe, quiet=True)
        npc, message = resolve_addressee("how's that going", self.cafe, focus=self.tarin)
        self.assertIs(npc, self.tarin)
        self.assertEqual(message, "how's that going")

    def test_explicit_different_name_overrides_focus(self):
        self.tarin.move_to(self.cafe, quiet=True)
        npc, _ = resolve_addressee("to Mara, hello there", self.cafe, focus=self.tarin)
        self.assertIs(npc, self.mara)

    def test_focus_on_an_absent_npc_is_ignored(self):
        self.tarin.move_to(self.cafe, quiet=True)
        npc, _ = resolve_addressee("hello there", self.cafe, focus=self.iri)
        self.assertIsNone(npc)

    def test_no_focus_with_multiple_npcs_is_still_ambient(self):
        self.tarin.move_to(self.cafe, quiet=True)
        npc, _ = resolve_addressee("hello there", self.cafe, focus=None)
        self.assertIsNone(npc)

    def test_focus_does_not_override_lone_npc_rule(self):
        # Only one NPC present (Mara) and focus points at a different,
        # absent one - the lone-NPC implicit rule still wins since
        # Mara is the only one who could possibly be meant.
        npc, _ = resolve_addressee("hello there", self.cafe, focus=self.tarin)
        self.assertIs(npc, self.mara)
