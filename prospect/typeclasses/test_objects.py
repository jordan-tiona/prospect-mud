"""
Tests for ObjectParent's leading-blank-line appearance override (see
typeclasses/rooms.py's RoomAppearanceTests for the room-specific case;
this covers that every entity - not just rooms - gets it, since it
lives on the shared ObjectParent mixin).

Run with:
    evennia test typeclasses
"""

from django.test import TestCase
from evennia import create_object


class LeadingBlankLineTests(TestCase):
    def setUp(self):
        self.room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.looker = create_object(
            "typeclasses.characters.Character", key="Tester", location=self.room
        )

    def test_room_object_examine_leads_with_a_blank_line(self):
        obj = create_object(
            "typeclasses.objects.RoomObject",
            key="a sign",
            location=self.room,
            attributes=[("desc", "A plain sign.")],
        )
        self.assertTrue(obj.return_appearance(self.looker).startswith("\n"))

    def test_npc_examine_leads_with_a_blank_line(self):
        npc = create_object(
            "typeclasses.npcs.NPC",
            key="A dockhand",
            location=self.room,
            attributes=[("desc", "A plain dockhand.")],
        )
        self.assertTrue(npc.return_appearance(self.looker).startswith("\n"))

    def test_character_examine_leads_with_a_blank_line(self):
        other = create_object(
            "typeclasses.characters.Character",
            key="Someone",
            location=self.room,
            attributes=[("desc", "A plain person.")],
        )
        self.assertTrue(other.return_appearance(self.looker).startswith("\n"))
