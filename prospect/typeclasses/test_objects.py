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


class ParcelLockTests(TestCase):
    """
    Phase 2C (docs/phase2c-misdelivered-parcel-proposal.md) requires
    the parcel to move only through the scenario's validated actions,
    never a player's own get/give/drop. These confirm all three are
    actually blocked, not just the lock string that one of them
    (give) doesn't consult.
    """

    def setUp(self):
        self.room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.owner = create_object(
            "typeclasses.characters.Character", key="Owner", location=self.room
        )
        self.other = create_object(
            "typeclasses.characters.Character", key="Other", location=self.room
        )

    def test_cannot_get_from_room(self):
        parcel = create_object(
            "typeclasses.objects.Parcel", key="a small parcel", location=self.room
        )
        self.assertFalse(parcel.access(self.owner, "get"))

    def test_cannot_drop(self):
        parcel = create_object(
            "typeclasses.objects.Parcel", key="a small parcel", location=self.owner
        )
        self.assertFalse(parcel.at_pre_drop(self.owner))

    def test_cannot_give(self):
        parcel = create_object(
            "typeclasses.objects.Parcel", key="a small parcel", location=self.owner
        )
        self.assertFalse(parcel.at_pre_give(self.owner, self.other))
        self.assertIs(parcel.location, self.owner)


class PlantingBedDescTests(TestCase):
    """
    Quest 2's planting bed must reflect this specific looker's own
    world.garden.is_bed_tended fact, not a single shared state -
    caught live during playtesting (2026-10-14), where the bed still
    read "overgrown" after it had actually been tended.
    """

    def setUp(self):
        self.room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.tender = create_object(
            "typeclasses.characters.Character", key="Tender", location=self.room
        )
        self.other = create_object(
            "typeclasses.characters.Character", key="Other", location=self.room
        )
        self.bed = create_object(
            "typeclasses.objects.PlantingBed",
            key="a planting bed",
            location=self.room,
            attributes=[("desc", "Overgrown and in need of tending.")],
        )

    def test_untended_looker_sees_the_plain_desc(self):
        self.assertIn("Overgrown", self.bed.get_display_desc(self.tender))

    def test_tending_player_sees_updated_desc(self):
        from world.garden import mark_bed_tended

        mark_bed_tended(self.tender)
        self.assertIn("tended to it yourself", self.bed.get_display_desc(self.tender))

    def test_other_player_still_sees_the_plain_desc(self):
        from world.garden import mark_bed_tended

        mark_bed_tended(self.tender)
        self.assertIn("Overgrown", self.bed.get_display_desc(self.other))
