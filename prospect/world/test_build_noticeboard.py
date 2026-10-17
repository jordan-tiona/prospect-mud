"""
Tests for the civic information display's builder
(world/build_noticeboard.py) and its per-looker dynamic description
(typeclasses.objects.RevisionDisplayObject).

Run with:
    evennia test world
"""

from django.test import TestCase
from evennia import create_object, search_tag

from world.build_noticeboard import NOTICEBOARD_TAG_CATEGORY, build
from world.build_rooms import build as build_rooms
from world.noticeboard import get_or_create_expected_revision


class BuildNoticeboardTests(TestCase):
    def setUp(self):
        self.rooms = build_rooms()
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=self.rooms["corner_cafe"]
        )

    def test_builds_the_display_in_davens_office(self):
        display = build()
        self.assertEqual(display.location, self.rooms["daven_office"])
        self.assertTrue(display.is_typeclass("typeclasses.objects.RevisionDisplayObject", exact=True))

    def test_rerun_does_not_duplicate(self):
        build()
        build()
        matches = search_tag(key="civic_information_display", category=NOTICEBOARD_TAG_CATEGORY)
        self.assertEqual(len(matches), 1)

    def test_not_pickable(self):
        display = build()
        self.assertFalse(display.access(self.actor, "get"))

    def test_room_line_does_not_contain_a_revision_number(self):
        display = build()
        self.assertNotIn(get_or_create_expected_revision(self.actor), display.db.room_line)

    def test_examined_desc_contains_this_players_own_revision(self):
        display = build()
        revision = get_or_create_expected_revision(self.actor)
        self.assertIn(revision, display.get_display_desc(self.actor))

    def test_different_players_see_their_own_revision(self):
        display = build()
        other = create_object(
            "typeclasses.characters.Character", key="Other", location=self.rooms["corner_cafe"]
        )
        mine = get_or_create_expected_revision(self.actor)
        theirs = get_or_create_expected_revision(other)
        self.assertIn(mine, display.get_display_desc(self.actor))
        self.assertIn(theirs, display.get_display_desc(other))

    def test_upgrades_a_display_created_as_plain_room_object(self):
        stale = create_object(
            "typeclasses.objects.RoomObject", key="a civic information display", location=self.rooms["corner_cafe"]
        )
        stale.tags.add("civic_information_display", category=NOTICEBOARD_TAG_CATEGORY)

        display = build()

        matches = search_tag(key="civic_information_display", category=NOTICEBOARD_TAG_CATEGORY)
        self.assertEqual(len(matches), 1)
        self.assertTrue(display.is_typeclass("typeclasses.objects.RevisionDisplayObject", exact=True))
        # The stale one sat in the café, its pre-2026-10-16 room: moved, not orphaned.
        self.assertEqual(display.location, self.rooms["daven_office"])
