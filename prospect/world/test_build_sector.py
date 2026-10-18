"""
Tests for world/build_sector.py (docs/build-sector-proposal.md, Step A):
building from a small fixture manifest, idempotency, dry runs, typeclass
swaps, exit adoption and re-keying, managed-value removal, held items,
orphans and the prune safety rules - plus a check that the per-kind
world/build_*.py wrappers together leave nothing for a full build to do.

Run with:
    evennia test world.test_build_sector
"""

import copy
from unittest import mock

from django.test import TestCase
from evennia import create_object, search_tag
from evennia.objects.models import ObjectDB

from world import build_sector
from world.build_sector import EXIT_TAG_CATEGORY, MANAGED_ATTRIBUTE, SECTOR_TAG_CATEGORY, SectorBuildError

ROOMS = "phase1_neighborhood"
AMBIENT = "phase1_ambient"

BASE = {
    "format_version": 1,
    "sector_id": "testsector",
    "rooms": {
        "t_room_a": {"title": "Room A", "typeclass": "typeclasses.rooms.Room", "tag_category": ROOMS,
                     "desc": "Room A.", "glance": None},
        "t_room_b": {"title": "Room B", "typeclass": "typeclasses.rooms.Room", "tag_category": ROOMS,
                     "desc": "Room B.", "glance": "B, briefly."},
    },
    "exits": [
        {"id": "t_room_a__north", "from": "t_room_a", "to": "t_room_b", "key": "north", "aliases": ["n"]},
        {"id": "t_room_b__south", "from": "t_room_b", "to": "t_room_a", "key": "south", "aliases": ["s"]},
    ],
    "entities": {
        "t_thing": {"kind": "ambient_object", "typeclass": "typeclasses.objects.RoomObject",
                    "tag_category": AMBIENT, "room": "t_room_a", "key": "a thing", "aliases": ["thing"],
                    "attributes": {"room_line": "A thing is here.", "desc": "It is a thing."}},
        "t_kit": {"kind": "gardening_kit", "typeclass": "typeclasses.objects.GardeningKit",
                  "tag_category": "garden_prop", "room": "t_room_a", "key": "a kit", "aliases": [],
                  "attributes": {"desc": "A kit."}},
    },
}


def one(tag, category):
    matches = search_tag(key=tag, category=category)
    assert len(matches) == 1, f"{tag}/{category}: {len(matches)} matches"
    return matches[0]


class BuildSectorTests(TestCase):
    def setUp(self):
        patcher = mock.patch.object(build_sector, "_server_is_running", return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        print_patcher = mock.patch("builtins.print")
        print_patcher.start()
        self.addCleanup(print_patcher.stop)
        self.manifest = copy.deepcopy(BASE)
        # Objects created without a home get settings.DEFAULT_HOME ("#2", Limbo
        # in a real database). In the empty test DB #2 would be one of the
        # fixture rooms, making it everything's home - so give the test a Limbo.
        limbo = create_object("typeclasses.rooms.Room", key="Limbo", nohome=True)
        override = self.settings(DEFAULT_HOME=limbo.dbref)
        override.enable()
        self.addCleanup(override.disable)

    def build(self, **kwargs):
        return build_sector.build("testsector", manifest=self.manifest, **kwargs)

    def room(self, room_id):
        return one(room_id, ROOMS)

    def test_builds_everything_from_empty(self):
        report = self.build()
        self.assertEqual(len(report.created), 6)
        a, b = self.room("t_room_a"), self.room("t_room_b")
        self.assertEqual((a.key, a.db.desc, b.db.glance), ("Room A", "Room A.", "B, briefly."))
        north = one("t_room_a__north", EXIT_TAG_CATEGORY)
        self.assertEqual((north.location, north.destination, north.key), (a, b, "north"))
        self.assertEqual(north.aliases.all(), ["n"])
        thing = one("t_thing", AMBIENT)
        self.assertEqual((thing.location, thing.db.room_line), (a, "A thing is here."))
        self.assertEqual(thing.aliases.all(), ["thing"])
        for obj in (a, b, north, thing):
            self.assertTrue(obj.tags.get("testsector", category=SECTOR_TAG_CATEGORY))

    def test_second_run_changes_nothing(self):
        self.build()
        report = self.build()
        self.assertEqual((report.created, report.updated, report.orphans), ([], {}, []))
        self.assertEqual(len(report.unchanged), 6)

    def test_dry_run_writes_nothing_and_reports_what_a_real_run_does(self):
        before = ObjectDB.objects.count()
        dry = self.build(dry_run=True)
        self.assertEqual(ObjectDB.objects.count(), before)
        real = self.build()
        self.assertEqual(dry.created, real.created)
        self.manifest["rooms"]["t_room_a"]["title"] = "Room A, renamed"
        dry = self.build(dry_run=True)
        self.assertEqual(self.room("t_room_a").key, "Room A")
        self.assertEqual(dry.updated, self.build().updated)
        self.assertEqual(self.room("t_room_a").key, "Room A, renamed")

    def test_typeclass_swap_keeps_attributes(self):
        self.build()
        self.manifest["entities"]["t_thing"]["typeclass"] = "typeclasses.objects.Object"
        report = self.build()
        self.assertIn("typeclass", report.updated["ambient_object t_thing"])
        thing = one("t_thing", AMBIENT)
        self.assertEqual(thing.typeclass_path, "typeclasses.objects.Object")
        self.assertEqual(thing.db.room_line, "A thing is here.")

    def test_changing_an_exits_direction_updates_the_same_exit(self):
        self.build()
        north = one("t_room_a__north", EXIT_TAG_CATEGORY)
        self.manifest["exits"][0].update(id="t_room_a__up", key="up", aliases=["u"])
        report = self.build()
        self.assertEqual(report.created, [])
        self.assertEqual(report.orphans, [])
        up = one("t_room_a__up", EXIT_TAG_CATEGORY)
        self.assertEqual(up.id, north.id)
        self.assertEqual((up.key, up.aliases.all()), ("up", ["u"]))
        self.assertEqual(len(self.room("t_room_a").exits), 1)

    def test_adopts_an_untagged_exit_built_by_the_old_scripts(self):
        exits = self.manifest["exits"]
        self.manifest["exits"] = []
        self.build()
        legacy = create_object("typeclasses.exits.Exit", key="north", location=self.room("t_room_a"),
                               destination=self.room("t_room_b"))
        self.manifest["exits"] = exits
        report = self.build()
        self.assertEqual(report.created, ["exit t_room_b__south"])
        self.assertIn("tag", report.updated["exit t_room_a__north"])
        self.assertEqual(one("t_room_a__north", EXIT_TAG_CATEGORY).id, legacy.id)

    def test_two_adoptable_exits_are_a_conflict_and_block_pruning(self):
        exits = self.manifest["exits"]
        self.manifest["exits"] = []
        self.build()
        for key in ("north", "door"):
            create_object("typeclasses.exits.Exit", key=key, location=self.room("t_room_a"),
                          destination=self.room("t_room_b"))
        self.manifest["exits"] = exits
        report = self.build(prune=True)
        self.assertEqual(len(report.conflicts), 1)
        self.assertNotIn("exit t_room_a__north", report.created)
        self.assertEqual(len(self.room("t_room_a").exits), 2)
        self.assertEqual(report.pruned, [])
        self.assertEqual(len(report.blocked), 2)

    def test_room_with_a_duplicate_tag_skips_everything_in_it_without_writing_any_of_it(self):
        # Dev review (docs/build-sector-proposal.md Section 9): this used to
        # raise KeyError partway through a real build.
        for _ in range(2):
            create_object("typeclasses.rooms.Room", key="Room A?").tags.add("t_room_a", category=ROOMS)
        report = self.build()
        self.assertEqual(sorted(report.created), ["room t_room_b"])
        self.assertEqual(len(report.conflicts), 5)  # the room, both exits, both entities in it
        self.assertEqual(len(search_tag(key="t_thing", category=AMBIENT)), 0)
        self.assertEqual(self.room("t_room_b").exits, [])

    def test_unresolvable_room_refuses_before_writing(self):
        del self.manifest["rooms"]["t_room_a"]  # an export would never allow this; build_sector must not crash on it
        before = ObjectDB.objects.count()
        with self.assertRaises(SectorBuildError):
            self.build()
        self.assertEqual(ObjectDB.objects.count(), before)

    def test_probe_text_is_set_and_removed_with_the_manifest(self):
        self.manifest["entities"]["t_thing"]["attributes"]["probe_desc"] = "Up close, still a thing."
        self.build()
        thing = one("t_thing", AMBIENT)
        self.assertEqual(thing.db.probe_desc, "Up close, still a thing.")
        del self.manifest["entities"]["t_thing"]["attributes"]["probe_desc"]
        self.build()
        self.assertFalse(thing.attributes.has("probe_desc"))

    def test_map_coordinates_are_set_and_removed_with_the_manifest(self):
        self.manifest["rooms"]["t_room_a"]["map"] = {"x": -2, "y": 0, "z": 1}
        self.build()
        room = one("t_room_a", ROOMS)
        self.assertEqual(room.db.map_coords, {"x": -2, "y": 0, "z": 1})
        del self.manifest["rooms"]["t_room_a"]["map"]  # off the grid: GMCP then sends no coords
        self.build()
        self.assertFalse(room.attributes.has("map_coords"))

    def test_values_the_manifest_drops_are_removed(self):
        self.build()
        entity = self.manifest["entities"]["t_thing"]
        entity["aliases"] = []
        del entity["attributes"]["room_line"]
        self.build()
        thing = one("t_thing", AMBIENT)
        self.assertEqual(thing.aliases.all(), [])
        self.assertFalse(thing.attributes.has("room_line"))
        self.assertEqual(thing.db.desc, "It is a thing.")

    def test_first_run_on_an_old_script_object_only_records(self):
        self.manifest["entities"] = {}
        self.build()
        legacy = create_object("typeclasses.objects.RoomObject", key="a thing", location=self.room("t_room_a"))
        legacy.tags.add("t_thing", category=AMBIENT)
        legacy.aliases.add("oldname")
        legacy.db.note = "set by hand"
        self.manifest["entities"]["t_thing"] = copy.deepcopy(BASE["entities"]["t_thing"])
        for _ in range(2):
            self.build()
            self.assertEqual(sorted(legacy.aliases.all()), ["oldname", "thing"])
            self.assertEqual(legacy.db.note, "set by hand")
        self.assertEqual(legacy.attributes.get(MANAGED_ATTRIBUTE)["aliases"], ["thing"])

    def test_held_entity_is_left_with_its_holder(self):
        self.build()
        carrier = create_object("typeclasses.objects.Object", key="carrier", location=self.room("t_room_b"))
        kit = one("t_kit", "garden_prop")
        kit.move_to(carrier, quiet=True)
        report = self.build()
        self.assertEqual(kit.location, carrier)
        self.assertEqual(len(report.held), 1)
        self.assertNotIn("gardening_kit t_kit", report.updated)

    def test_entity_held_by_an_offline_character_is_left_with_them(self):
        # With the server stopped, an offline character's location is None
        # (seen live 2026-10-17: the gardening kit was taken from a player).
        self.build()
        character = create_object("evennia.objects.objects.DefaultCharacter", key="Someone",
                                  location=self.room("t_room_b"))
        kit = one("t_kit", "garden_prop")
        kit.move_to(character, quiet=True)
        character.location = None
        report = self.build()
        self.assertEqual(kit.location, character)
        self.assertEqual(len(report.held), 1)
        self.assertNotIn("gardening_kit t_kit", report.updated)

    def test_removed_entity_is_an_orphan_until_pruned(self):
        self.build()
        del self.manifest["entities"]["t_thing"]
        report = self.build()
        self.assertEqual(len(report.orphans), 1)
        self.assertEqual(len(search_tag(key="t_thing", category=AMBIENT)), 1)
        report = self.build(prune=True)
        self.assertEqual(len(report.pruned), 1)
        self.assertEqual(len(search_tag(key="t_thing", category=AMBIENT)), 0)

    def test_renamed_ambient_npc_id_prunes_the_old_object(self):
        # An NPC is a DefaultObject, not a character, so the character
        # guard doesn't keep the old-id one (LR-LORE-0001's id rename).
        npc = {"kind": "ambient_npc", "typeclass": "typeclasses.npcs.NPC", "tag_category": AMBIENT,
               "room": "t_room_a", "key": "a neighbor", "aliases": [], "attributes": {"desc": "A neighbor."}}
        self.manifest["entities"]["t_old_neighbor"] = copy.deepcopy(npc)
        self.build()
        del self.manifest["entities"]["t_old_neighbor"]
        self.manifest["entities"]["t_new_neighbor"] = copy.deepcopy(npc)
        report = self.build(prune=True)
        self.assertEqual(len(report.pruned), 1)
        self.assertEqual(len(search_tag(key="t_old_neighbor", category=AMBIENT)), 0)
        self.assertEqual(one("t_new_neighbor", AMBIENT).location, self.room("t_room_a"))

    def test_untagged_old_script_object_not_in_manifest_is_an_orphan(self):
        self.build()
        stray = create_object("typeclasses.objects.RoomObject", key="stray", location=self.room("t_room_a"))
        stray.tags.add("stray", category=AMBIENT)
        self.assertEqual(len(self.build().orphans), 1)

    def _remove_room_b(self):
        del self.manifest["rooms"]["t_room_b"]
        self.manifest["exits"] = []

    def test_room_with_anything_left_in_it_is_not_pruned(self):
        self.build()
        self._remove_room_b()
        visitor = create_object("typeclasses.objects.Object", key="a dropped item", location=self.room("t_room_b"))
        report = self.build(prune=True)
        self.assertIn("not empty", dict(report.blocked).values())
        self.assertEqual(len(search_tag(key="t_room_b", category=ROOMS)), 1)
        visitor.delete()
        report = self.build(prune=True)
        self.assertEqual(report.blocked, [])
        self.assertEqual(len(search_tag(key="t_room_b", category=ROOMS)), 0)
        self.assertEqual(len(self.room("t_room_a").exits), 0)  # the orphaned exit into it went too

    def test_room_used_as_home_is_not_pruned(self):
        self.build()
        self._remove_room_b()
        create_object("typeclasses.objects.Object", key="lives elsewhere", location=self.room("t_room_a"),
                      home=self.room("t_room_b"))
        report = self.build(prune=True)
        self.assertIn("something uses it as home", dict(report.blocked).values())

    def test_required_room_is_never_pruned(self):
        self.build()
        self._remove_room_b()
        with mock.patch.dict(build_sector.REQUIRED_ROOM_IDS, {"testsector": ["t_room_b"]}):
            report = self.build(prune=True)
        self.assertIn("required by game code (REQUIRED_ROOM_IDS)", dict(report.blocked).values())

    def test_characters_are_never_pruned(self):
        self.build()
        character = create_object("evennia.objects.objects.DefaultCharacter", key="Someone",
                                  location=self.room("t_room_a"))
        character.tags.add("someone", category=AMBIENT)
        report = self.build(prune=True)
        self.assertIn("a character - never pruned", dict(report.blocked).values())
        self.assertTrue(ObjectDB.objects.filter(id=character.id).exists())

    def test_kinds_filter_leaves_other_kinds_alone(self):
        report = self.build(kinds={"ambient_object"})
        self.assertNotIn("gardening_kit t_kit", report.created)
        self.assertIn("room t_room_a", report.created)
        self.build()
        self.assertEqual(self.build(kinds={"ambient_object"}).orphans, [])

    def test_refuses_to_write_under_a_live_server(self):
        with mock.patch.object(build_sector, "_server_is_running", return_value=True):
            with self.assertRaises(SectorBuildError):
                self.build()
            self.build(dry_run=True)
            self.build(force_live=True)

    def test_rejects_unknown_format_or_wrong_sector(self):
        self.manifest["format_version"] = 2
        with self.assertRaises(SectorBuildError):
            self.build()
        self.manifest["format_version"] = 1
        with self.assertRaises(SectorBuildError):
            build_sector.build("elsewhere", manifest=self.manifest)


class ElsewhereWrappersVsFullBuildTests(TestCase):
    """The per-kind wrappers (world/build_*.py) together leave nothing for a
    full build to do: no creates, no updates, no orphans. Before Step C this
    compared the old hand-written scripts the same way, and passed."""

    @classmethod
    def setUpTestData(cls):
        from world.test_sector_manifest import build_with_wrappers

        build_with_wrappers()

    def setUp(self):
        patcher = mock.patch.object(build_sector, "_server_is_running", return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        print_patcher = mock.patch("builtins.print")
        print_patcher.start()
        self.addCleanup(print_patcher.stop)

    def test_full_build_after_the_wrappers_changes_nothing(self):
        report = build_sector.build("elsewhere")
        self.assertEqual((report.created, report.updated, report.orphans, report.conflicts), ([], {}, [], []))
