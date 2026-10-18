"""
Tests for world/gmcp.py's payloads and when characters send them.

Run with:
    evennia test world.test_gmcp
"""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from evennia import create_object

from world import gmcp
from world.entity_kinds import ROOM_KIND


class _FakeSession:
    def __init__(self):
        self.sent = []

    def msg(self, **kwargs):
        self.sent.append(kwargs)


def _with_sessions(*sessions):
    return SimpleNamespace(sessions=SimpleNamespace(all=lambda: list(sessions)))


class SendTests(TestCase):
    def test_package_name_becomes_evennia_cmdname(self):
        session = _FakeSession()
        gmcp._send(_with_sessions(session), "Room.Info", {"num": 1})
        # Evennia's gmcp_utils turns Room_Info back into "Room.Info".
        self.assertEqual(session.sent, [{"Room_Info": ((), {"num": 1})}])

    def test_every_session_gets_it(self):
        first, second = _FakeSession(), _FakeSession()
        gmcp._send(_with_sessions(first, second), "Char.Status", {"name": "Ravis"})
        self.assertEqual(len(first.sent), 1)
        self.assertEqual(len(second.sent), 1)

    def test_nothing_without_sessions(self):
        gmcp._send(SimpleNamespace(), "Room.Info", {})  # no error


class RoomInfoTests(TestCase):
    def setUp(self):
        self.square = create_object("typeclasses.rooms.Room", key="Square")
        self.cafe = create_object("typeclasses.rooms.Room", key="Cafe")
        self.attic = create_object("typeclasses.rooms.Room", key="Attic")
        create_object("typeclasses.exits.Exit", key="north", location=self.square, destination=self.cafe)
        create_object("typeclasses.exits.Exit", key="up", location=self.square, destination=self.attic)
        create_object("typeclasses.exits.Exit", key="hatch", location=self.square, destination=self.attic)
        self.looker = create_object("typeclasses.characters.Character", key="Ravis", location=self.square)

    def test_basic_fields(self):
        self.square.tags.add("old_quarter_square", category=ROOM_KIND["tag_category"])
        self.square.tags.add("elsewhere", category=gmcp.SECTOR_TAG_CATEGORY)
        info = gmcp.room_info(self.square, self.looker)
        self.assertEqual(info["num"], self.square.id)
        self.assertEqual(info["id"], "old_quarter_square")
        self.assertEqual(info["name"], "Square")
        self.assertEqual(info["area"], "elsewhere")
        self.assertEqual(info["environment"], "")

    def test_exits_use_short_directions_and_room_numbers(self):
        exits = gmcp.room_info(self.square, self.looker)["exits"]
        self.assertEqual(exits, {"n": self.cafe.id, "u": self.attic.id, "hatch": self.attic.id})

    def test_exits_the_looker_cannot_see_are_left_out(self):
        hidden = create_object("typeclasses.exits.Exit", key="west", location=self.square, destination=self.cafe)
        hidden.locks.add("view:false()")
        self.assertNotIn("w", gmcp.room_info(self.square, self.looker)["exits"])

    def test_untagged_room_sends_empty_ids(self):
        info = gmcp.room_info(self.cafe, self.looker)
        self.assertEqual(info["id"], "")
        self.assertEqual(info["area"], "")

    def test_coords_only_when_set(self):
        self.assertNotIn("coords", gmcp.room_info(self.square, self.looker))
        self.square.db.map_coords = {"x": 0, "y": "1", "z": -1}
        self.assertEqual(gmcp.room_info(self.square, self.looker)["coords"], {"x": 0, "y": 1, "z": -1})

    def test_malformed_coords_are_left_out(self):
        for bad in ({"x": 0, "y": 1}, {"x": "a", "y": 0, "z": 0}, [0, 0, 0]):
            self.square.db.map_coords = bad
            self.assertNotIn("coords", gmcp.room_info(self.square, self.looker), bad)


class CharStatusTests(TestCase):
    def test_species_left_out_until_chargen_sets_it(self):
        room = create_object("typeclasses.rooms.Room", key="Square")
        character = create_object("typeclasses.characters.Character", key="Ravis", location=room, home=room)
        self.assertEqual(gmcp.char_status(character), {"name": "Ravis"})
        character.db.species = "Kell"
        self.assertEqual(gmcp.char_status(character), {"name": "Ravis", "species": "Kell"})


class CharacterHookTests(TestCase):
    def setUp(self):
        self.square = create_object("typeclasses.rooms.Room", key="Square")
        self.cafe = create_object("typeclasses.rooms.Room", key="Cafe")
        self.mover = create_object("typeclasses.characters.Character", key="Ravis", location=self.square)

    def test_moving_sends_room_info(self):
        with patch("world.gmcp.send_room_info") as send:
            self.mover.move_to(self.cafe)
        send.assert_called_once_with(self.mover)

    def test_puppeting_sends_status_and_room_info(self):
        with patch("world.gmcp.send_room_info") as room, patch("world.gmcp.send_char_status") as status, \
                patch("world.tutorial.announce_tannoy"), patch("world.idle_emotes.start_room_emotes"):
            self.mover.at_post_puppet()
        status.assert_called_once_with(self.mover)
        room.assert_called_once_with(self.mover)
