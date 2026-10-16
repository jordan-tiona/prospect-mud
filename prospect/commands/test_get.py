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

    def test_take_picks_up_an_object(self):
        rock = create_object("typeclasses.objects.Object", key="a rock", location=self.room)
        self.actor.execute_cmd("take rock")
        self.assertEqual(rock.location, self.actor)
