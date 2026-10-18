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

from server.conf.lockfuncs import commitment_hint_visible, module_exchange_hint_visible
from world.actions import _validate_accept_help, _validate_ask_for_help, _validate_decline_help
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


class ModuleExchangeHintVisibleLockFuncTests(TestCase):
    """The heating-unit module-exchange quest (world/actions.py's
    QUEST_MODULE_EXCHANGE_*) predates the generic commitment_type
    mechanism above and has its own hint lock func - same per-player
    "not started" bar, different state source."""

    def setUp(self):
        room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.mara = create_object("typeclasses.npcs.NPC", key="Mara Voss", location=room)
        self.actor = create_object("typeclasses.characters.Character", key="Tester", location=room)

    def test_not_started_is_visible(self):
        self.assertTrue(module_exchange_hint_visible(self.actor, None))

    def test_accepted_is_not_visible(self):
        _validate_ask_for_help(self.mara, self.actor, {})
        _validate_accept_help(self.mara, self.actor, {})
        self.assertFalse(module_exchange_hint_visible(self.actor, None))

    def test_asked_is_not_visible_and_declined_is_visible_again(self):
        _validate_ask_for_help(self.mara, self.actor, {})
        self.assertFalse(module_exchange_hint_visible(self.actor, None))
        _validate_decline_help(self.mara, self.actor, {})
        self.assertTrue(module_exchange_hint_visible(self.actor, None))

    def test_unknown_accessing_obj_denies_rather_than_errors(self):
        self.assertFalse(module_exchange_hint_visible(object(), None))


class BuildQuestPropsTests(TestCase):
    def setUp(self):
        self.rooms = build_rooms()
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=self.rooms["corner_cafe"]
        )

    def test_builds_the_parcel_prop_in_the_civic_office(self):
        props = build()
        parcel = props["misdelivered_parcel_hint"]
        self.assertEqual(parcel.location, self.rooms["civic_office"])
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

    def test_builds_the_faulty_module_prop_in_the_cafe(self):
        props = build()
        module = props["faulty_heating_module_hint"]
        self.assertEqual(module.location, self.rooms["corner_cafe"])
        self.assertTrue(module.access(self.actor, "view"))

    def test_faulty_module_prop_hidden_once_the_errand_is_accepted(self):
        from world.actions import _validate_accept_help, _validate_ask_for_help

        props = build()
        module = props["faulty_heating_module_hint"]
        mara = create_object("typeclasses.npcs.NPC", key="Mara Voss", location=self.rooms["corner_cafe"])
        _validate_ask_for_help(mara, self.actor, {})
        _validate_accept_help(mara, self.actor, {})
        self.assertFalse(module.access(self.actor, "view"))

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
        # The stale one sat in the café, its pre-2026-10-16 room: moved, not orphaned.
        self.assertEqual(props["misdelivered_parcel_hint"].location, self.rooms["civic_office"])
