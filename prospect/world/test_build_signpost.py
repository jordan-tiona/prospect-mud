"""
Tests for Old Quarter Square's signpost builder (world/build_signpost.py)
and its dynamically computed route (typeclasses.objects.SignpostObject).

Run with:
    evennia test world
"""

from django.test import TestCase
from evennia import search_tag

from world.build_signpost import SIGNPOST_TAG_CATEGORY, build
from world.build_rooms import build as build_rooms


class BuildSignpostTests(TestCase):
    def setUp(self):
        self.rooms = build_rooms()

    def test_builds_the_signpost_in_the_square(self):
        signpost = build()
        self.assertEqual(signpost.location, self.rooms["old_quarter_square"])
        self.assertTrue(signpost.is_typeclass("typeclasses.objects.SignpostObject", exact=True))

    def test_rerun_does_not_duplicate(self):
        build()
        build()
        matches = search_tag(key="old_quarter_square_signpost", category=SIGNPOST_TAG_CATEGORY)
        self.assertEqual(len(matches), 1)

    def test_not_pickable(self):
        signpost = build()
        self.assertFalse(signpost.access(None, "get"))

    def test_room_line_has_no_route_in_it(self):
        signpost = build()
        self.assertNotIn("Daven", signpost.db.room_line)

    def test_examined_desc_names_the_real_route_to_davens_office(self):
        signpost = build()
        desc = signpost.get_display_desc(None)
        self.assertIn("Daven's office", desc)
        # square -> street (southwest) -> office (south), per world.build_rooms
        self.assertIn("southwest, then south", desc)

    def test_route_breaks_if_the_real_exits_change(self):
        # Prove the route is computed from live exits, not hardcoded:
        # sever the path and confirm the signpost stops claiming one.
        signpost = build()
        for exi in list(self.rooms["old_quarter_street"].exits):
            if exi.destination == self.rooms["daven_office"]:
                exi.delete()
        desc = signpost.get_display_desc(None)
        self.assertNotIn("Daven's office:", desc)
