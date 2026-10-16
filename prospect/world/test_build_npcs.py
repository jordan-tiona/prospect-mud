"""
Tests for world/build_npcs.py: specifically the `desc` field it reads
off each NPC's persona file (world/npc_profile.py) and applies to
`db.desc`, so `look <npc>` shows the project owner's authored
description instead of Evennia's default "You see nothing special."

Run with:
    evennia test world
"""

from django.test import TestCase

from world.build_npcs import build
from world.build_rooms import build as build_rooms


class BuildNpcsDescTests(TestCase):
    def setUp(self):
        build_rooms()
        self.npcs = build()

    def test_given_and_daven_get_their_authored_desc(self):
        self.assertIn("Given Marr is a Neshyr medical technician", self.npcs["given_marr"].db.desc)
        self.assertIn("Daven Varek is a Kethari", self.npcs["daven_varek"].db.desc)

    def test_npc_with_no_authored_desc_is_left_alone(self):
        # mara_voss.md has no `desc` metadata field yet - build() must
        # not overwrite whatever (or nothing) is already there with a
        # blank string.
        self.assertIsNone(self.npcs["mara_voss"].db.desc)

    def test_rerun_does_not_duplicate_npcs_and_keeps_desc(self):
        from evennia import search_tag

        from world.build_npcs import NPC_TAG_CATEGORY

        build()
        self.assertEqual(len(search_tag(key="given_marr", category=NPC_TAG_CATEGORY)), 1)
        self.assertIn("Given Marr is a Neshyr medical technician", self.npcs["given_marr"].db.desc)
