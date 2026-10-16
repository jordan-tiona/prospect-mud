"""
Tests for Quest 2's world object builder (world/build_garden_props.py):
idempotency, and that the planting bed carries the aliases/room_line
fields caught missing during playtesting (2026-10-14) - "beds" didn't
match the object, and the room's inline listing fell back to the full
look-desc as a sentence fragment instead of a "Name is here" line.

Run with:
    evennia test world
"""

from django.test import TestCase

from world.build_garden_props import GARDEN_PROP_TAG_CATEGORY, build
from world.build_rooms import build as build_rooms


class BuildGardenPropsTests(TestCase):
    def setUp(self):
        build_rooms()

    def test_planting_bed_has_a_room_line_distinct_from_its_look_desc(self):
        props = build()
        bed = props["planting_bed"]
        self.assertTrue(bed.db.room_line)
        self.assertNotEqual(bed.db.room_line, bed.db.desc)

    def test_planting_bed_matches_plural_aliases(self):
        props = build()
        bed = props["planting_bed"]
        self.assertTrue(bed.aliases.get("beds"))
        self.assertTrue(bed.aliases.get("planting beds"))

    def test_rerunning_build_does_not_duplicate_props(self):
        build()
        build()
        from evennia import search_tag

        matches = search_tag(key="planting_bed", category=GARDEN_PROP_TAG_CATEGORY)
        self.assertEqual(len(matches), 1)
