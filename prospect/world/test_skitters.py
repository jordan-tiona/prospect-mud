"""
Tests for world/skitters.py (docs/playtest-quest3-skitters-design.md):
per-player kill tracking/eligibility and the shared global population.

Run with:
    evennia test world
"""

from django.test import TestCase
from evennia import create_object

from world.build_rooms import build as build_rooms
from world.commitments import accept_commitment, propose_commitment
from world.skitters import (
    ELIGIBLE_ROOM_TAGS,
    SKITTER_TAG,
    SKITTER_TAG_CATEGORY,
    _live_skitters,
    ensure_population,
    is_hunting,
    kills_for,
    record_kill,
    reset_kills,
    spawn_one,
)


class KillCounterTests(TestCase):
    def setUp(self):
        self.room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.actor = create_object(
            "typeclasses.characters.Character", key="Hunter", location=self.room
        )

    def test_starts_at_zero(self):
        self.assertEqual(kills_for(self.actor), 0)

    def test_record_kill_increments(self):
        record_kill(self.actor)
        record_kill(self.actor)
        self.assertEqual(kills_for(self.actor), 2)

    def test_is_per_player(self):
        other = create_object(
            "typeclasses.characters.Character", key="Other", location=self.room
        )
        record_kill(self.actor)
        self.assertEqual(kills_for(other), 0)

    def test_reset_clears_it_and_returns_previous_count(self):
        record_kill(self.actor)
        record_kill(self.actor)
        previous = reset_kills(self.actor)
        self.assertEqual(previous, 2)
        self.assertEqual(kills_for(self.actor), 0)

    def test_reset_with_no_kills_returns_zero(self):
        previous = reset_kills(self.actor)
        self.assertEqual(previous, 0)


class IsHuntingTests(TestCase):
    def setUp(self):
        self.rooms = build_rooms()
        self.actor = create_object(
            "typeclasses.characters.Character", key="Hunter", location=self.rooms["old_quarter_square"]
        )

    def test_not_hunting_before_any_commitment(self):
        self.assertFalse(is_hunting(self.actor))

    def test_not_hunting_while_only_offered(self):
        propose_commitment(self.actor, "hunt_skitters")
        self.assertFalse(is_hunting(self.actor))

    def test_hunting_once_accepted(self):
        propose_commitment(self.actor, "hunt_skitters")
        accept_commitment(self.actor, "hunt_skitters")
        self.assertTrue(is_hunting(self.actor))


class PopulationTests(TestCase):
    def setUp(self):
        self.rooms = build_rooms()

    def test_spawn_one_lands_in_an_eligible_room(self):
        skitter = spawn_one()
        tags = [self.rooms[tag] for tag in ELIGIBLE_ROOM_TAGS]
        self.assertIn(skitter.location, tags)
        self.assertIn(SKITTER_TAG, skitter.tags.get(category=SKITTER_TAG_CATEGORY, return_list=True))

    def test_spawn_one_sets_a_room_line(self):
        # Same bug class PlantingBed hit before it - without a
        # room_line, typeclasses.rooms.Room's get_display_things falls
        # back to showing the full db.desc in the room listing
        # (confirmed live during playtesting, 2026-10-16).
        skitter = spawn_one()
        self.assertTrue(skitter.db.room_line)
        self.assertNotEqual(skitter.db.room_line, skitter.db.desc)

    def test_spawn_one_excludes_given_room_when_possible(self):
        exclude = self.rooms["corner_cafe"]
        for _ in range(10):
            skitter = spawn_one(exclude_room=exclude)
            self.assertNotEqual(skitter.location, exclude)

    def test_ensure_population_spawns_up_to_the_target_count(self):
        ensure_population()
        self.assertEqual(len(_live_skitters()), 2)

    def test_ensure_population_does_not_over_spawn(self):
        ensure_population()
        ensure_population()
        self.assertEqual(len(_live_skitters()), 2)

    def test_ensure_population_tops_up_a_partial_deficit(self):
        spawn_one()
        ensure_population()
        self.assertEqual(len(_live_skitters()), 2)
