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


class GardeningKitSupplyTests(TestCase):
    """
    The courtyard's kit is a supply: `get kit` gives each player their
    own copy and the supply stays put. Caught live 2026-10-19, when the
    only kit sat in one character's inventory and nobody else could
    start Iri's quest.
    """

    def setUp(self):
        self.courtyard = create_object("typeclasses.rooms.Room", key="Courtyard")
        self.square = create_object("typeclasses.rooms.Room", key="Square")
        self.supply = create_object(
            "typeclasses.objects.GardeningKit",
            key="a gardening kit",
            location=self.courtyard,
            aliases=["kit"],
            attributes=[("desc", "A worn kit.")],
        )
        self.first = create_object("typeclasses.characters.Character", key="First", location=self.courtyard)
        self.second = create_object("typeclasses.characters.Character", key="Second", location=self.courtyard)

    def _kits(self, holder):
        from world.garden import carried_kits

        return carried_kits(holder)

    def test_get_gives_a_copy_and_the_supply_stays(self):
        self.first.execute_cmd("get kit")
        self.assertIs(self.supply.location, self.courtyard)
        kits = self._kits(self.first)
        self.assertEqual(len(kits), 1)
        self.assertIsNot(kits[0], self.supply)
        self.assertEqual(kits[0].db.desc, "A worn kit.")

    def test_copy_carries_no_build_tags(self):
        self.supply.tags.add("gardening_kit", category="garden_prop")
        self.first.execute_cmd("get kit")
        self.assertFalse(self._kits(self.first)[0].tags.all())

    def test_every_player_can_get_one(self):
        self.first.execute_cmd("get kit")
        self.second.execute_cmd("get kit")
        self.assertEqual(len(self._kits(self.first)), 1)
        self.assertEqual(len(self._kits(self.second)), 1)

    def test_only_one_per_player(self):
        self.first.execute_cmd("get kit")
        self.first.execute_cmd("get kit")
        self.assertEqual(len(self._kits(self.first)), 1)

    def test_get_from_the_locker_phrasing(self):
        self.first.execute_cmd("get kit from locker")
        self.assertEqual(len(self._kits(self.first)), 1)

    def test_dropping_next_to_the_supply_returns_it(self):
        self.first.execute_cmd("get kit")
        self.first.execute_cmd("drop kit")
        self.assertEqual(self._kits(self.first), [])
        self.assertEqual(
            [obj for obj in self.courtyard.contents if obj.is_typeclass("typeclasses.objects.GardeningKit")],
            [self.supply],
        )

    def test_cannot_drop_away_from_the_supply(self):
        self.first.execute_cmd("get kit")
        self.first.move_to(self.square, quiet=True)
        self.first.execute_cmd("drop kit")
        self.assertEqual(len(self._kits(self.first)), 1)

    def test_copy_works_on_the_bed(self):
        from world.garden import is_bed_tended

        create_object("typeclasses.objects.PlantingBed", key="a planting bed", location=self.square, aliases=["bed"])
        self.first.execute_cmd("get kit")
        self.first.move_to(self.square, quiet=True)
        self.first.execute_cmd("use kit on bed")
        self.assertTrue(is_bed_tended(self.first))

    def _into_locker(self):
        locker = create_object("typeclasses.objects.Container", key="a communal equipment locker",
                               location=self.courtyard, aliases=["locker"])
        self.supply.move_to(locker, quiet=True)
        return locker

    def test_get_reaches_into_the_locker(self):
        locker = self._into_locker()
        self.first.execute_cmd("get kit")
        self.second.execute_cmd("get kit from locker")
        self.assertEqual(len(self._kits(self.first)), 1)
        self.assertEqual(len(self._kits(self.second)), 1)
        self.assertIs(self.supply.location, locker)

    def test_dropping_returns_it_to_a_supply_in_the_locker(self):
        self._into_locker()
        self.first.execute_cmd("get kit")
        self.first.execute_cmd("drop kit")
        self.assertEqual(self._kits(self.first), [])

    def test_looking_at_the_locker_does_not_list_its_contents(self):
        locker = self._into_locker()
        self.assertEqual(locker.get_display_things(self.first), "")

    def test_reset_cleanup_removes_only_personal_kits(self):
        from world.garden import cleanup_personal_kits

        self.first.execute_cmd("get kit")
        self.assertEqual(cleanup_personal_kits(self.first), 1)
        self.assertEqual(self._kits(self.first), [])
        self.supply.move_to(self.first, quiet=True)
        self.assertEqual(cleanup_personal_kits(self.first), 0)
        self.assertIs(self.supply.location, self.first)
