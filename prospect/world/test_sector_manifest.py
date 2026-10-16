"""
MUD editor migration guarantee (docs/mud-editor-sector-format.md
Section 7): the Elsewhere sector's export manifest must describe exactly
what today's world/build_*.py scripts build - every room, exit and
placed entity, with the same typeclass, tag, key, aliases, location,
attributes and locks, and nothing extra on either side.

The manifest is resolved with ops/editor/export.py's build_manifest(),
which skips the approval gate (export itself refuses while content is
still Draft) - this test is about structure and text, not approval.

Once world.build_sector replaces the old scripts, this becomes the
"old vs new builder" comparison; until then it compares the manifest
against the old scripts' actual database output.

Run with:
    evennia test world.test_sector_manifest
"""

import sys
from pathlib import Path

from django.test import TestCase
from evennia import search_tag
from evennia.objects.models import ObjectDB

from world import (build_ambient, build_garden_props, build_noticeboard, build_npcs, build_quest_props,
                   build_rooms, build_signpost, build_skitter_ledger)

_EDITOR_DIR = Path(__file__).resolve().parents[2] / "ops" / "editor"
if str(_EDITOR_DIR) not in sys.path:
    sys.path.insert(0, str(_EDITOR_DIR))

import export as sector_export  # noqa: E402  (ops/editor/export.py)
from world_model import ROOT  # noqa: E402

ATTRIBUTES = ("desc", "glance", "room_line", "spoke_lines", "npc_id")


def _one(tag, category):
    matches = search_tag(key=tag, category=category)
    if len(matches) != 1:
        raise AssertionError(f"expected one object tagged {tag!r}/{category!r}, found {len(matches)}")
    return matches[0]


class SectorManifestMatchesLegacyBuildTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        build_rooms.build()
        build_npcs.build()
        build_ambient.apply_all_room_content()
        build_ambient.build_ambient_entities()
        build_quest_props.build()
        build_noticeboard.build()
        build_signpost.build()
        build_garden_props.build()
        build_skitter_ledger.build()

    def setUp(self):
        self.manifest = sector_export.build_manifest(ROOT, "elsewhere")
        self.rooms = self.manifest["rooms"]
        self.room_tag_category = next(iter(self.rooms.values()))["tag_category"]

    def _room_tag(self, obj):
        return obj.tags.get(category=self.room_tag_category, return_list=True)[0]

    def test_rooms(self):
        built = ObjectDB.objects.filter(db_tags__db_category=self.room_tag_category).distinct()
        self.assertEqual(sorted(self._room_tag(r) for r in built), sorted(self.rooms))
        for room_id, expected in self.rooms.items():
            with self.subTest(room_id):
                room = _one(room_id, expected["tag_category"])
                self.assertEqual(room.typeclass_path, expected["typeclass"])
                self.assertEqual(room.key, expected["title"])
                self.assertEqual(room.db.desc, expected["desc"])
                self.assertEqual(room.db.glance, expected["glance"])

    def test_exits(self):
        built = set()
        for room_id, expected in self.rooms.items():
            for exi in _one(room_id, expected["tag_category"]).exits:
                built.add((room_id, self._room_tag(exi.destination), exi.key,
                           tuple(sorted(exi.aliases.all())), exi.typeclass_path))
        manifest = {(e["from"], e["to"], e["key"], tuple(sorted(a.lower() for a in e["aliases"])), "typeclasses.exits.Exit")
                    for e in self.manifest["exits"]}
        self.assertEqual(built, manifest)
        self.assertEqual(len(manifest), len(self.manifest["exits"]), "duplicate exits in manifest")

    def test_entities(self):
        for entity_id, expected in self.manifest["entities"].items():
            with self.subTest(entity_id):
                obj = _one(entity_id, expected["tag_category"])
                self.assertEqual(obj.typeclass_path, expected["typeclass"])
                self.assertEqual(self._room_tag(obj.location), expected["room"])
                self.assertEqual(obj.key, expected["key"])
                self.assertEqual(sorted(obj.aliases.all()), sorted(a.lower() for a in expected["aliases"]))  # Evennia lowercases aliases
                for name in ATTRIBUTES:
                    self.assertEqual(obj.attributes.get(name), expected["attributes"].get(name), name)
                self.assertEqual(obj.db.ambient_poses, expected.get("poses"))
                if "locks" in expected:
                    for part in expected["locks"].split(";"):
                        access_type = part.split(":", 1)[0]
                        self.assertEqual(obj.locks.get(access_type), part)

    def test_no_built_entity_missing_from_manifest(self):
        categories = {e["tag_category"] for e in self.manifest["entities"].values()}
        for category in sorted(categories):
            with self.subTest(category):
                built = {tag for obj in ObjectDB.objects.filter(db_tags__db_category=category).distinct()
                         for tag in obj.tags.get(category=category, return_list=True)}
                expected = {i for i, e in self.manifest["entities"].items() if e["tag_category"] == category}
                self.assertEqual(built, expected)
