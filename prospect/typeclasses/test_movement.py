"""
Tests for Character's movement lines (owner, 2026-10-17): "Ravis leaves
to the northwest." / "Ravis arrives from the south." instead of
Evennia's "Ravis is leaving <room>, heading for <room>."

Run with:
    evennia test typeclasses
"""

from django.test import TestCase
from evennia import create_object

from typeclasses.characters import arrive_message, leave_message


class MovementMessageTextTests(TestCase):
    def test_compass_directions(self):
        self.assertEqual(leave_message("northwest"), "{object} leaves to the northwest.")
        self.assertEqual(arrive_message("south"), "{object} arrives from the south.")

    def test_up_and_down(self):
        self.assertEqual(leave_message("down"), "{object} heads down.")
        self.assertEqual(arrive_message("up"), "{object} arrives from above.")
        self.assertEqual(arrive_message("down"), "{object} arrives from below.")

    def test_unknown_exit_names_fall_back(self):
        self.assertEqual(leave_message("hatch"), "{object} leaves.")
        self.assertEqual(arrive_message(""), "{object} arrives.")


class MovementAnnouncementTests(TestCase):
    def setUp(self):
        self.south_room = create_object("typeclasses.rooms.Room", key="South Room")
        self.north_room = create_object("typeclasses.rooms.Room", key="North Room")
        create_object("typeclasses.exits.Exit", key="north", location=self.south_room, destination=self.north_room)
        create_object("typeclasses.exits.Exit", key="south", location=self.north_room, destination=self.south_room)
        self.mover = create_object("typeclasses.characters.Character", key="Ravis", location=self.south_room)

    def _watcher(self, room):
        watcher = create_object("typeclasses.characters.Character", key="Watcher", location=room)
        heard = []
        watcher.msg = lambda text=None, **kw: heard.append(text[0] if isinstance(text, tuple) else text)
        return heard

    def test_people_left_behind_see_the_direction(self):
        heard = self._watcher(self.south_room)
        self.mover.move_to(self.north_room)
        self.assertIn("Ravis leaves to the north.", heard)
        self.assertFalse(any("heading for" in str(line) for line in heard))

    def test_people_arrived_at_see_where_from(self):
        heard = self._watcher(self.north_room)
        self.mover.move_to(self.north_room)
        self.assertIn("Ravis arrives from the south.", heard)

    def test_quiet_moves_say_nothing(self):
        heard = self._watcher(self.north_room)
        self.mover.move_to(self.north_room, quiet=True)
        self.assertFalse(any("Ravis" in str(line) for line in heard))
