"""
Tests for Room's Achaea-style appearance overrides (return_appearance's
display hooks) - per the project owner's preference over Evennia's
default "You see: X and Y." / "Characters: ..." / "Exits: ..." lines.

Run with:
    evennia test typeclasses
"""

from django.test import TestCase
from evennia import create_object

from world.commitments import propose_commitment


class RoomAppearanceTests(TestCase):
    def setUp(self):
        self.room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.looker = create_object(
            "typeclasses.characters.Character", key="Tester", location=self.room
        )

    # -- leading blank line before the whole appearance block --------------

    def test_return_appearance_leads_with_a_blank_line(self):
        self.room.db.desc = "A plain room."
        output = self.room.return_appearance(self.looker)
        self.assertTrue(output.startswith("\n"))

    # -- exits -------------------------------------------------------------

    def test_no_exits_is_blank(self):
        self.assertEqual(self.room.get_display_exits(self.looker), "")

    def test_single_exit_phrasing(self):
        other = create_object("typeclasses.rooms.Room", key="Other Room")
        create_object(
            "typeclasses.exits.Exit", key="north", location=self.room, destination=other
        )
        self.assertEqual(
            self.room.get_display_exits(self.looker),
            "|YYou see a single exit leading north.|n",
        )

    def test_two_exit_phrasing_uses_compass_order(self):
        other = create_object("typeclasses.rooms.Room", key="Other Room")
        # created in reverse compass order - output should still read
        # north before east, not alphabetically or creation order
        create_object("typeclasses.exits.Exit", key="east", location=self.room, destination=other)
        create_object(
            "typeclasses.exits.Exit", key="north", location=self.room, destination=other
        )
        self.assertEqual(
            self.room.get_display_exits(self.looker),
            "|YYou see two exits leading north and east.|n",
        )

    def test_three_or_more_exits_drop_the_count_phrasing(self):
        other = create_object("typeclasses.rooms.Room", key="Other Room")
        for direction in ("west", "south", "north"):
            create_object(
                "typeclasses.exits.Exit", key=direction, location=self.room, destination=other
            )
        self.assertEqual(
            self.room.get_display_exits(self.looker),
            "|YYou see exits leading north, south, and west.|n",
        )

    def test_four_exits_use_compass_order_not_alphabetical(self):
        other = create_object("typeclasses.rooms.Room", key="Other Room")
        for direction in ("west", "east", "south", "north"):
            create_object(
                "typeclasses.exits.Exit", key=direction, location=self.room, destination=other
            )
        self.assertEqual(
            self.room.get_display_exits(self.looker),
            "|YYou see exits leading north, south, east, and west.|n",
        )

    # -- NPC presence lines --------------------------------------------------
    # Ambient (non-LLM) NPCs are dark cyan (|C); talk-capable NPCs are
    # bright cyan (|c), same as real players - project owner's color
    # scheme.

    def test_ambient_npc_with_no_pose(self):
        npc = create_object("typeclasses.npcs.NPC", key="Mara Voss", location=self.room)
        self.assertEqual(
            self.room.get_display_things(self.looker), "    |CMara Voss is here.|n"
        )

    def test_ambient_npc_with_pose(self):
        npc = create_object("typeclasses.npcs.NPC", key="Mara Voss", location=self.room)
        npc.db.ambient_pose = "idly drying a glass"
        self.assertEqual(
            self.room.get_display_things(self.looker),
            "    |CMara Voss is here, idly drying a glass.|n",
        )

    def test_talkative_npc_is_bright_cyan_not_dark(self):
        npc = create_object(
            "typeclasses.npcs.TalkativeNPC", key="Tarin Os", location=self.room
        )
        self.assertEqual(
            self.room.get_display_things(self.looker), "    |cTarin Os is here.|n"
        )

    # -- phase 2B discoverability hint pose ------------------------------

    def test_commitment_holder_shows_hint_pose_before_any_offer(self):
        npc = create_object(
            "typeclasses.npcs.TalkativeNPC", key="Tarin Os", location=self.room
        )
        npc.db.npc_id = "tarin_os"
        self.assertEqual(
            self.room.get_display_things(self.looker),
            "    |cTarin Os is here, frowning over a shipment manifest.|n",
        )

    def test_commitment_holder_hint_pose_gone_once_offered(self):
        npc = create_object(
            "typeclasses.npcs.TalkativeNPC", key="Tarin Os", location=self.room
        )
        npc.db.npc_id = "tarin_os"
        propose_commitment(self.looker, "discrepancy_report")
        self.assertEqual(
            self.room.get_display_things(self.looker), "    |cTarin Os is here.|n"
        )

    def test_hint_pose_is_per_looker(self):
        npc = create_object(
            "typeclasses.npcs.TalkativeNPC", key="Tarin Os", location=self.room
        )
        npc.db.npc_id = "tarin_os"
        propose_commitment(self.looker, "discrepancy_report")
        other = create_object(
            "typeclasses.characters.Character", key="Other", location=self.room
        )
        # self.looker has already been offered; a different player
        # hasn't, and still sees the hint.
        self.assertEqual(
            self.room.get_display_things(other),
            "    |cTarin Os is here, frowning over a shipment manifest.|n",
        )

    def test_static_ambient_pose_still_wins_for_non_commitment_npcs(self):
        npc = create_object(
            "typeclasses.npcs.TalkativeNPC", key="Iri Vael", location=self.room
        )
        npc.db.npc_id = "iri_vael"
        npc.db.ambient_pose = "flipping through a thick ledger"
        self.assertEqual(
            self.room.get_display_things(self.looker),
            "    |cIri Vael is here, flipping through a thick ledger.|n",
        )

    # -- room objects (fixtures) ----------------------------------------------
    # Dark cyan (|C), same as ambient NPCs.

    def test_room_object_uses_room_line(self):
        create_object(
            "typeclasses.objects.RoomObject",
            key="a symbol",
            location=self.room,
            attributes=[("room_line", "A symbol is gouged into the wall.")],
        )
        self.assertEqual(
            self.room.get_display_things(self.looker),
            "    |CA symbol is gouged into the wall.|n",
        )

    def test_room_object_falls_back_to_desc(self):
        create_object(
            "typeclasses.objects.RoomObject",
            key="a corpse",
            location=self.room,
            attributes=[("desc", "A mangled corpse lies in the far corner of the cell.")],
        )
        self.assertEqual(
            self.room.get_display_things(self.looker),
            "    |CA mangled corpse lies in the far corner of the cell.|n",
        )

    def test_room_object_falls_back_to_generic_line(self):
        create_object("typeclasses.objects.RoomObject", key="a crate", location=self.room)
        self.assertEqual(
            self.room.get_display_things(self.looker), "    |CThere is a crate here.|n"
        )

    def test_room_object_is_not_pickupable(self):
        obj = create_object("typeclasses.objects.RoomObject", key="a sign", location=self.room)
        self.assertFalse(obj.access(self.looker, "get"))

    def test_multiple_things_join_in_order_created(self):
        create_object(
            "typeclasses.objects.RoomObject",
            key="a symbol",
            location=self.room,
            attributes=[("room_line", "A symbol is gouged into the wall.")],
        )
        create_object("typeclasses.npcs.NPC", key="An old man", location=self.room)
        self.assertEqual(
            self.room.get_display_things(self.looker),
            "    |CA symbol is gouged into the wall.|n |CAn old man is here.|n",
        )

    # -- other player characters -------------------------------------------

    def test_other_character_presence_line(self):
        other = create_object(
            "typeclasses.characters.Character", key="Someone", location=self.room
        )
        self.assertIn("Someone is here.", self.room.get_display_characters(self.looker))
        self.assertTrue(self.room.get_display_characters(self.looker).startswith("    "))

    def test_other_character_with_pose(self):
        other = create_object(
            "typeclasses.characters.Character", key="Someone", location=self.room
        )
        other.db.ambient_pose = "resting against the wall"
        self.assertIn(
            "Someone is here, resting against the wall.",
            self.room.get_display_characters(self.looker),
        )

    def test_looker_itself_not_listed(self):
        # filter_visible excludes the looker from its own view of the room
        self.assertEqual(self.room.get_display_characters(self.looker), "")

    # -- two-tier description (glance vs full look) -------------------------

    def test_look_shows_full_desc(self):
        self.room.db.desc = "The full description."
        self.room.db.glance = "The short blurb."
        self.assertEqual(
            self.room.get_display_desc(self.looker), "    The full description."
        )

    def test_glance_shows_short_blurb(self):
        self.room.db.desc = "The full description."
        self.room.db.glance = "The short blurb."
        self.assertEqual(
            self.room.get_display_desc(self.looker, glance=True), "    The short blurb."
        )

    def test_glance_falls_back_to_full_desc_if_unset(self):
        self.room.db.desc = "The full description."
        self.assertEqual(
            self.room.get_display_desc(self.looker, glance=True), "    The full description."
        )

    # -- room title tag -------------------------------------------------------

    def test_room_type_tag_appended_to_name(self):
        self.room.db.room_type = "indoors"
        self.assertIn("(indoors)", self.room.get_display_name(self.looker))

    def test_no_room_type_means_no_tag(self):
        self.assertNotIn("(", self.room.get_display_name(self.looker))
