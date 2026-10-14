"""
Tests for the discoverable quest-prop builder (world/build_quest_props.py)
and its lock function (server/conf/lockfuncs.py's commitment_hint_visible) -
the project owner's discoverability rule (2026-10-13): every quest/
commitment should have a passive, in-world cue, not just a
conversational trigger. Covers that the prop is genuinely per-player
(visible only to a looker who hasn't been offered the commitment yet)
and that the builder is idempotent.

Run with:
    evennia test world
"""

from unittest.mock import PropertyMock, patch

from django.test import TestCase
from evennia import create_object

from server.conf.lockfuncs import commitment_hint_visible
from world.build_quest_props import QUEST_PROP_TAG_CATEGORY, build
from world.build_rooms import build as build_rooms
from world.commitments import accept_commitment, decline_commitment, propose_commitment


class CommitmentHintVisibleLockFuncTests(TestCase):
    def setUp(self):
        room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.actor = create_object("typeclasses.characters.Character", key="Tester", location=room)

    def test_no_commitment_type_arg_denies(self):
        self.assertFalse(commitment_hint_visible(self.actor, None))

    def test_not_offered_is_visible(self):
        self.assertTrue(commitment_hint_visible(self.actor, None, "deliver_parcel"))

    def test_offered_is_not_visible(self):
        propose_commitment(self.actor, "deliver_parcel")
        self.assertFalse(commitment_hint_visible(self.actor, None, "deliver_parcel"))

    def test_accepted_is_not_visible(self):
        propose_commitment(self.actor, "deliver_parcel")
        accept_commitment(self.actor, "deliver_parcel")
        self.assertFalse(commitment_hint_visible(self.actor, None, "deliver_parcel"))

    def test_declined_is_visible_again(self):
        # Declining isn't terminal (world.commitments.decline_commitment's
        # own docstring, and hint_pose_for's existing identical
        # behavior) - the offer can be made again, so the prop
        # reappears rather than staying hidden.
        propose_commitment(self.actor, "deliver_parcel")
        decline_commitment(self.actor, "deliver_parcel")
        self.assertTrue(commitment_hint_visible(self.actor, None, "deliver_parcel"))

    def test_unknown_accessing_obj_denies_rather_than_errors(self):
        # Defensive: a non-Character accessing_obj (or anything without
        # real commitment state) must fail closed, not raise.
        self.assertFalse(commitment_hint_visible(object(), None, "deliver_parcel"))


class BuildQuestPropsTests(TestCase):
    def setUp(self):
        self.rooms = build_rooms()
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=self.rooms["corner_cafe"]
        )

    def test_builds_the_parcel_prop_in_the_cafe(self):
        props = build()
        parcel = props["misdelivered_parcel_hint"]
        self.assertEqual(parcel.location, self.rooms["corner_cafe"])
        self.assertTrue(parcel.is_typeclass("typeclasses.objects.RoomObject", exact=False))

    def test_rerun_does_not_duplicate(self):
        build()
        build()
        from evennia import search_tag

        matches = search_tag(key="misdelivered_parcel_hint", category=QUEST_PROP_TAG_CATEGORY)
        self.assertEqual(len(matches), 1)

    def test_not_pickable(self):
        props = build()
        parcel = props["misdelivered_parcel_hint"]
        self.assertFalse(parcel.access(self.actor, "get"))

    def test_visible_to_a_player_who_has_not_been_offered_it(self):
        props = build()
        parcel = props["misdelivered_parcel_hint"]
        self.assertTrue(parcel.access(self.actor, "view"))
        self.assertTrue(parcel.access(self.actor, "search"))

    def test_hidden_once_offered(self):
        props = build()
        parcel = props["misdelivered_parcel_hint"]
        propose_commitment(self.actor, "deliver_parcel")
        self.assertFalse(parcel.access(self.actor, "view"))
        self.assertFalse(parcel.access(self.actor, "search"))

    def test_different_players_see_it_independently(self):
        props = build()
        parcel = props["misdelivered_parcel_hint"]
        other = create_object(
            "typeclasses.characters.Character", key="Other", location=self.rooms["corner_cafe"]
        )
        propose_commitment(self.actor, "deliver_parcel")
        self.assertFalse(parcel.access(self.actor, "view"))
        self.assertTrue(parcel.access(other, "view"))

    def test_hidden_even_from_a_superuser(self):
        # Confirmed live, 2026-10-13: Evennia's access() bypasses every
        # lock for a superuser by default - exactly wrong here, since
        # the project owner's own account is the superuser actually
        # playtesting this. CommitmentHintObject must defeat that
        # bypass for view/search specifically.
        props = build()
        parcel = props["misdelivered_parcel_hint"]
        propose_commitment(self.actor, "deliver_parcel")
        with patch.object(type(self.actor), "is_superuser", new_callable=PropertyMock, return_value=True):
            self.assertFalse(parcel.access(self.actor, "view"))
            self.assertFalse(parcel.access(self.actor, "search"))

    def test_upgrades_a_prop_created_as_plain_room_object(self):
        # Migration path for a prop that already exists from before
        # this typeclass existed.
        from evennia import create_object as _create, search_tag

        stale = _create(
            "typeclasses.objects.RoomObject", key="a small parcel", location=self.rooms["corner_cafe"]
        )
        stale.tags.add("misdelivered_parcel_hint", category=QUEST_PROP_TAG_CATEGORY)

        props = build()

        matches = search_tag(key="misdelivered_parcel_hint", category=QUEST_PROP_TAG_CATEGORY)
        self.assertEqual(len(matches), 1)
        self.assertTrue(
            props["misdelivered_parcel_hint"].is_typeclass(
                "typeclasses.objects.CommitmentHintObject", exact=True
            )
        )
