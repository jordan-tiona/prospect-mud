"""
Tests for the project's first per-player, per-NPC reputation state
(world/reputation.py), docs/phase2e-word-gets-around-design.md.

Run with:
    evennia test world
"""

from django.test import TestCase
from evennia import create_object

from world.reputation import adjust_reputation, get_reputation, reputation_context_for, reset_reputation


class ReputationTests(TestCase):
    def setUp(self):
        room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.actor = create_object("typeclasses.characters.Character", key="Tester", location=room)

    def test_defaults_to_zero(self):
        self.assertEqual(get_reputation(self.actor, "mara_voss"), 0)

    def test_adjust_increases_and_returns_new_value(self):
        new_value = adjust_reputation(self.actor, "mara_voss", 1)
        self.assertEqual(new_value, 1)
        self.assertEqual(get_reputation(self.actor, "mara_voss"), 1)

    def test_adjust_accumulates(self):
        adjust_reputation(self.actor, "mara_voss", 1)
        adjust_reputation(self.actor, "mara_voss", 1)
        self.assertEqual(get_reputation(self.actor, "mara_voss"), 2)

    def test_per_npc(self):
        adjust_reputation(self.actor, "mara_voss", 1)
        self.assertEqual(get_reputation(self.actor, "tarin_os"), 0)

    def test_per_player(self):
        other = create_object("typeclasses.characters.Character", key="Other", location=self.actor.location)
        adjust_reputation(self.actor, "mara_voss", 1)
        self.assertEqual(get_reputation(other, "mara_voss"), 0)

    def test_reset_clears_and_returns_previous_value(self):
        adjust_reputation(self.actor, "mara_voss", 1)
        previous = reset_reputation(self.actor, "mara_voss")
        self.assertEqual(previous, 1)
        self.assertEqual(get_reputation(self.actor, "mara_voss"), 0)

    def test_reset_with_nothing_set_returns_zero(self):
        self.assertEqual(reset_reputation(self.actor, "mara_voss"), 0)


class ReputationContextForTests(TestCase):
    def setUp(self):
        room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.actor = create_object("typeclasses.characters.Character", key="Tester", location=room)

    def test_none_when_reputation_is_zero(self):
        self.assertIsNone(reputation_context_for("mara_voss", self.actor))

    def test_includes_the_value_once_nonzero(self):
        adjust_reputation(self.actor, "mara_voss", 1)
        context = reputation_context_for("mara_voss", self.actor)
        self.assertIsNotNone(context)
        self.assertIn("1", context)

    def test_scoped_to_the_right_npc(self):
        adjust_reputation(self.actor, "mara_voss", 1)
        self.assertIsNone(reputation_context_for("tarin_os", self.actor))
