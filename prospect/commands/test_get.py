"""
Tests for commands/get.py's "take" alias on the stock CmdGet - caught
live during Quest 2 playtesting (2026-10-14): "take kit" silently
failed because stock Evennia only aliases "grab", not "take".

Run with:
    evennia test commands
"""

from django.test import TestCase
from evennia import create_object


class TakeAliasTests(TestCase):
    def setUp(self):
        self.room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=self.room
        )

    def test_get_from_a_container(self):
        box = create_object("typeclasses.objects.Container", key="a box", location=self.room, aliases=["box"])
        rock = create_object("typeclasses.objects.Object", key="a rock", location=box)
        self.actor.execute_cmd("get rock from box")
        self.assertEqual(rock.location, self.actor)

    def test_plain_get_reaches_into_a_container_when_nothing_loose_matches(self):
        box = create_object("typeclasses.objects.Container", key="a box", location=self.room)
        rock = create_object("typeclasses.objects.Object", key="a rock", location=box)
        self.actor.execute_cmd("get rock")
        self.assertEqual(rock.location, self.actor)

    def test_loose_item_wins_over_one_in_a_container(self):
        box = create_object("typeclasses.objects.Container", key="a box", location=self.room)
        inside = create_object("typeclasses.objects.Object", key="a rock", location=box)
        loose = create_object("typeclasses.objects.Object", key="a rock", location=self.room)
        self.actor.execute_cmd("get rock")
        self.assertEqual(loose.location, self.actor)
        self.assertEqual(inside.location, box)

    def test_from_something_that_is_not_a_container_looks_in_the_room(self):
        rock = create_object("typeclasses.objects.Object", key="a rock", location=self.room)
        self.actor.execute_cmd("get rock from shelf")
        self.assertEqual(rock.location, self.actor)

    def test_container_cannot_be_picked_up(self):
        box = create_object("typeclasses.objects.Container", key="a box", location=self.room)
        self.actor.execute_cmd("get box")
        self.assertEqual(box.location, self.room)

    def test_take_picks_up_an_object(self):
        rock = create_object("typeclasses.objects.Object", key="a rock", location=self.room)
        self.actor.execute_cmd("take rock")
        self.assertEqual(rock.location, self.actor)
