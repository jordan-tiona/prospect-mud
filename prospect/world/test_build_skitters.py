"""
Tests for world/build_skitters.py.

Run with:
    evennia test world
"""

from django.test import TestCase

from world.build_rooms import build as build_rooms
from world.build_skitters import build
from world.skitters import ELIGIBLE_ROOM_TAGS, _live_skitters


class BuildSkittersTests(TestCase):
    def setUp(self):
        self.rooms = build_rooms()

    def test_build_produces_the_configured_count(self):
        build()
        self.assertEqual(len(_live_skitters()), 2)

    def test_build_only_uses_eligible_rooms(self):
        build()
        eligible = {self.rooms[tag] for tag in ELIGIBLE_ROOM_TAGS}
        for skitter in _live_skitters():
            self.assertIn(skitter.location, eligible)

    def test_build_is_idempotent(self):
        build()
        build()
        self.assertEqual(len(_live_skitters()), 2)
