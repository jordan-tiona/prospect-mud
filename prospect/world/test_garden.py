"""
Tests for the per-player planting-bed completion fact (world/garden.py),
Quest 2 ("A Little Community Work" - docs/prospect-initial-playtest-
design-spec.md §6). The actual fact is set only by commands/use.py's
world action - Iri's confirm_bed_tended (world/actions.py) only ever
reads it.

Run with:
    evennia test world
"""

from django.test import TestCase
from evennia import create_object

from world.garden import is_bed_tended, mark_bed_tended, reset_bed_tended


class GardenBedTendedTests(TestCase):
    def setUp(self):
        room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.actor = create_object("typeclasses.characters.Character", key="Tester", location=room)

    def test_starts_untended(self):
        self.assertFalse(is_bed_tended(self.actor))

    def test_marking_sets_it(self):
        mark_bed_tended(self.actor)
        self.assertTrue(is_bed_tended(self.actor))

    def test_per_player(self):
        other = create_object("typeclasses.characters.Character", key="Other", location=self.actor.location)
        mark_bed_tended(self.actor)
        self.assertTrue(is_bed_tended(self.actor))
        self.assertFalse(is_bed_tended(other))

    def test_reset_clears_it_and_returns_previous_value(self):
        mark_bed_tended(self.actor)
        previous = reset_bed_tended(self.actor)
        self.assertTrue(previous)
        self.assertFalse(is_bed_tended(self.actor))

    def test_reset_with_nothing_tended_returns_false(self):
        previous = reset_bed_tended(self.actor)
        self.assertFalse(previous)
