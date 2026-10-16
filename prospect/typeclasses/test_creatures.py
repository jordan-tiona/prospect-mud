"""
Tests for typeclasses/creatures.py's generic Creature base and its
first subclass, Skitter (docs/playtest-quest3-skitters-design.md).

Run with:
    evennia test typeclasses
"""

from django.test import TestCase
from evennia import create_object

from world.build_rooms import build as build_rooms
from world.commitments import accept_commitment, propose_commitment


class CreatureTakeDamageTests(TestCase):
    def setUp(self):
        self.room = create_object("typeclasses.rooms.Room", key="Test Room")

    def test_damage_below_threshold_does_not_defeat(self):
        creature = create_object("typeclasses.creatures.Creature", key="a thing", location=self.room)
        creature.max_hp = 3
        creature.db.hp = 3
        defeated = creature.take_damage(1)
        self.assertFalse(defeated)
        self.assertEqual(creature.db.hp, 2)

    def test_damage_at_threshold_defeats_and_deletes(self):
        creature = create_object("typeclasses.creatures.Creature", key="a thing", location=self.room)
        creature.db.hp = 1
        defeated = creature.take_damage(1)
        self.assertTrue(defeated)
        self.assertIsNone(creature.pk)

    def test_access_forces_no_superuser_bypass_for_view_and_search(self):
        creature = create_object("typeclasses.creatures.Creature", key="a thing", location=self.room)
        # A lock that always denies, so a correct no_superuser_bypass
        # override is the only thing that could make this False for a
        # superuser-ish accessor - confirmed the same way
        # CommitmentHintObject's own test would (docs/engineering-
        # pitfalls.md #2).
        creature.locks.add("view:false()")
        looker = create_object("typeclasses.characters.Character", key="Looker", location=self.room)
        self.assertFalse(creature.access(looker, "view"))

    def test_health_descriptor_none_when_no_descriptors_defined(self):
        creature = create_object("typeclasses.creatures.Creature", key="a thing", location=self.room)
        self.assertIsNone(creature.health_descriptor())


class HealthDescriptorTests(TestCase):
    """
    Materia Magica-style threshold health feedback (project owner,
    2026-10-16, found while playtesting) - never a number, just an
    ordered, most-severe-first sequence of flavor descriptors.
    """

    def setUp(self):
        self.room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.skitter = create_object(
            "typeclasses.creatures.Skitter", key="a skitter", location=self.room
        )

    def test_full_health_has_no_descriptor(self):
        self.assertIsNone(self.skitter.health_descriptor())

    def test_light_scratches_after_one_hit(self):
        self.skitter.take_damage(1)
        self.assertEqual(self.skitter.health_descriptor(), "has a few light scratches")

    def test_badly_hurt_after_two_hits(self):
        self.skitter.take_damage(1)
        self.skitter.take_damage(1)
        self.assertEqual(self.skitter.health_descriptor(), "looks badly hurt")

    def test_more_severe_threshold_wins_on_overlap(self):
        # hp=1 (fraction .33) satisfies both the "scratches" (<=.67)
        # and "badly hurt" (<=.34) thresholds - the more severe one,
        # checked first, must win.
        self.skitter.db.hp = 1
        self.assertEqual(self.skitter.health_descriptor(), "looks badly hurt")


class SkitterDefeatTests(TestCase):
    def setUp(self):
        self.rooms = build_rooms()
        self.room = self.rooms["old_quarter_square"]
        self.other_room = self.rooms["corner_cafe"]
        self.actor = create_object(
            "typeclasses.characters.Character", key="Hunter", location=self.room
        )
        propose_commitment(self.actor, "hunt_skitters")
        accept_commitment(self.actor, "hunt_skitters")

    def test_defeat_records_a_kill_for_the_attacker(self):
        from world.skitters import kills_for

        skitter = create_object("typeclasses.creatures.Skitter", key="a skitter", location=self.room)
        skitter.db.hp = 1
        skitter.take_damage(1, attacker=self.actor)
        self.assertEqual(kills_for(self.actor), 1)

    def test_defeat_tops_the_population_back_up(self):
        from world.skitters import _live_skitters

        skitter = create_object("typeclasses.creatures.Skitter", key="a skitter", location=self.room)
        skitter.db.hp = 1
        skitter.take_damage(1, attacker=self.actor)
        self.assertEqual(len(_live_skitters()), 2)

    def test_defeat_with_no_attacker_still_deletes_and_respawns(self):
        from world.skitters import _live_skitters

        skitter = create_object("typeclasses.creatures.Skitter", key="a skitter", location=self.room)
        skitter.db.hp = 1
        skitter.take_damage(1)
        self.assertIsNone(skitter.pk)
        self.assertEqual(len(_live_skitters()), 2)

