"""
Tests for per-player NPC memory (world/npc_memory.py), design-bible
16.6. CLAUDE.md hard rule 6 applies directly: these are always stored
and injected as a player's claim, never promoted to fact.

Run with:
    evennia test world
"""

from django.test import SimpleTestCase, TestCase
from evennia import create_object

from world.npc_memory import (
    MAX_FACT_LENGTH,
    MAX_FACTS_PER_NPC,
    known_npc_ids_with_memory_for,
    memory_context_for,
    check_player_words,
    remember_fact,
    reset_memory,
)

NPC_ID = "mara_voss"


class RememberFactTests(TestCase):
    def setUp(self):
        room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.actor = create_object("typeclasses.characters.Character", key="Tester", location=room)

    def test_remembers_a_fact(self):
        result = remember_fact(self.actor, NPC_ID, "grew up near the Docks")
        self.assertTrue(result.ok)
        context = memory_context_for(NPC_ID, self.actor)
        self.assertIn("grew up near the Docks", context)

    def test_empty_fact_dropped(self):
        result = remember_fact(self.actor, NPC_ID, "   ")
        self.assertFalse(result.ok)

    def test_too_long_fact_dropped_not_truncated(self):
        long_fact = "x" * (MAX_FACT_LENGTH + 1)
        result = remember_fact(self.actor, NPC_ID, long_fact)
        self.assertFalse(result.ok)
        self.assertIsNone(memory_context_for(NPC_ID, self.actor))

    def test_flagged_fact_dropped(self):
        result = remember_fact(self.actor, NPC_ID, "As an AI, I don't have personal experiences.")
        self.assertFalse(result.ok)
        self.assertIn("flagged", result.reason)

    def test_cap_prunes_oldest_first(self):
        for i in range(MAX_FACTS_PER_NPC + 2):
            remember_fact(self.actor, NPC_ID, f"fact number {i}")
        context = memory_context_for(NPC_ID, self.actor)
        self.assertNotIn("fact number 0", context)
        self.assertNotIn("fact number 1", context)
        self.assertIn(f"fact number {MAX_FACTS_PER_NPC + 1}", context)

    def test_memory_is_per_npc(self):
        remember_fact(self.actor, "mara_voss", "likes cold drinks")
        self.assertIsNone(memory_context_for("tarin_os", self.actor))

    def test_memory_is_per_player(self):
        other = create_object("typeclasses.characters.Character", key="Other", location=self.actor.location)
        remember_fact(self.actor, NPC_ID, "likes cold drinks")
        self.assertIsNone(memory_context_for(NPC_ID, other))

    def test_context_labels_facts_as_unverified_claims(self):
        remember_fact(self.actor, NPC_ID, "used to work in maintenance")
        context = memory_context_for(NPC_ID, self.actor)
        self.assertIn("no way to verify", context)
        self.assertIn("claims, not settled fact", context)

    def test_context_none_with_nothing_remembered(self):
        self.assertIsNone(memory_context_for(NPC_ID, self.actor))


class ResetMemoryTests(TestCase):
    def setUp(self):
        room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.actor = create_object("typeclasses.characters.Character", key="Tester", location=room)

    def test_reset_clears_facts(self):
        remember_fact(self.actor, NPC_ID, "likes cold drinks")
        snapshot = reset_memory(self.actor, NPC_ID)
        self.assertEqual(len(snapshot["previous_facts"]), 1)
        self.assertIsNone(memory_context_for(NPC_ID, self.actor))

    def test_reset_snapshot_is_actually_json_serializable(self):
        # Confirmed live, 2026-10-14: Evennia wraps a stored dict/list
        # attribute in _SaverDict/_SaverList proxies on read -
        # list(...) on the outer container isn't enough, since each
        # fact underneath is still a _SaverDict, which crashed
        # resetcommand's log_memory_reset call the moment there was
        # actually something to report. A length-only assertion here
        # previously passed despite the bug; this exercises the same
        # json.dumps() call the real crash happened in.
        import json

        remember_fact(self.actor, NPC_ID, "likes cold drinks")
        snapshot = reset_memory(self.actor, NPC_ID)
        json.dumps(snapshot["previous_facts"])  # must not raise

    def test_reset_with_nothing_stored_reports_empty(self):
        snapshot = reset_memory(self.actor, NPC_ID)
        self.assertEqual(snapshot["previous_facts"], [])

    def test_known_npc_ids_with_memory_for(self):
        remember_fact(self.actor, "mara_voss", "likes cold drinks")
        remember_fact(self.actor, "tarin_os", "grew up near the Docks")
        self.assertEqual(known_npc_ids_with_memory_for(self.actor), {"mara_voss", "tarin_os"})

    def test_known_npc_ids_empty_when_nothing_stored(self):
        self.assertEqual(known_npc_ids_with_memory_for(self.actor), set())


class CheckPlayerWordsTests(SimpleTestCase):
    """PF-0004: remember_fact's quote must be the player's own
    statement about themselves, from their latest message."""

    def test_accepts_a_statement_from_the_message(self):
        self.assertEqual(check_player_words("I grew up near the Docks", "I grew up near the Docks, actually."), "")

    def test_ignores_case_spacing_and_curly_apostrophes(self):
        self.assertEqual(check_player_words("i’m  new here", "I'm new here."), "")

    def test_accepts_a_statement_before_a_question(self):
        self.assertEqual(check_player_words("I'm from the Docks", "I'm from the Docks, what about you?"), "")

    def test_rejects_words_not_in_the_message(self):
        self.assertTrue(check_player_words("I'm Drask", "What race am I? I can't remember."))

    def test_rejects_a_question(self):
        self.assertTrue(check_player_words("What race am I", "What race am I? I can't remember."))
        self.assertTrue(check_player_words("am I Drask?", "am I Drask?"))

    def test_rejects_words_not_about_the_player(self):
        self.assertTrue(check_player_words("Drask", "Drask, right."))

    def test_rejects_a_missing_quote_or_message(self):
        self.assertTrue(check_player_words("", "I grew up near the Docks."))
        self.assertTrue(check_player_words("I grew up near the Docks", None))

