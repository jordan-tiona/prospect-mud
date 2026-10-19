"""
Tests for the tool layer / validator (world/actions.py). CLAUDE.md
calls this out explicitly alongside the prompt builder: this is where
a silent bug would let an invalid or out-of-scope action slip through
as if it had been validated.

Needs real DB-backed rooms/NPCs, so these use TestCase (not
SimpleTestCase) and build the phase 1 neighborhood in setUp - each
test runs in its own rolled-back transaction.

Run with:
    evennia test world
"""

from unittest.mock import patch

from django.test import TestCase
from evennia import create_object

from world.actions import (
    ACTION_SCHEMAS,
    _validate_accept_commitment,
    _validate_accept_handoff,
    _validate_accept_help,
    _validate_accept_replacement,
    _validate_ask_for_help,
    _validate_decline_commitment,
    _validate_decline_help,
    _validate_exchange_module,
    _validate_give_faulty_module,
    _validate_propose_commitment,
    _validate_report_commitment_outcome,
    _validate_report_parcel_delivery,
    _validate_verify_revision_report,
    get_quest_state,
    quest_context_for,
    validate_and_apply,
)
from world.build_npcs import build as build_npcs
from world.build_rooms import BUILD_TAG_CATEGORY as ROOM_TAG_CATEGORY
from world.build_rooms import build as build_rooms
from world.build_sector import room_titles
from world.commitments import commitment_context_for, get_fulfilled_commitment
from world.reputation import get_reputation
from world.rumors import has_reputation_credit


class ActionValidatorTests(TestCase):
    def setUp(self):
        rooms = build_rooms()
        npcs = build_npcs()
        self.square = rooms["old_quarter_square"]
        self.cafe = rooms["corner_cafe"]
        self.workshop = rooms["maintenance_workshop"]
        self.office = rooms["civic_office"]
        self.courtyard = rooms["residential_courtyard"]
        self.lift = rooms["lift_concourse"]
        self.mara = npcs["mara_voss"]
        self.tarin = npcs["tarin_os"]
        self.iri = npcs["iri_vael"]
        self.actor = create_object("typeclasses.characters.Character", key="Tester", location=self.cafe)

    # -- serve_drink (Mara) --------------------------------------------

    def test_serve_drink_valid(self):
        result = validate_and_apply(self.mara, self.actor, "serve_drink", {"drink_type": "hot"})
        self.assertTrue(result.applied)
        self.assertIn("Mara Voss", result.narration)
        self.assertIn("hot", result.narration)

    def test_serve_drink_invalid_type_dropped(self):
        result = validate_and_apply(self.mara, self.actor, "serve_drink", {"drink_type": "lukewarm"})
        self.assertFalse(result.applied)
        self.assertEqual(result.narration, "")
        self.assertTrue(result.reason)

    def test_serve_drink_not_permitted_for_other_npc(self):
        result = validate_and_apply(self.tarin, self.actor, "serve_drink", {"drink_type": "hot"})
        self.assertFalse(result.applied)
        self.assertIn("not a permitted action", result.reason)

    # -- give_directions (Iri) -------------------------------------------

    def test_give_directions_adjacent_room(self):
        self.actor.move_to(self.square, quiet=True)
        result = validate_and_apply(self.iri, self.actor, "give_directions", {"destination": "Corner Cafe"})
        self.assertTrue(result.applied)
        self.assertIn("north", result.narration)

    def test_give_directions_matches_despite_missing_accent(self):
        # The real room name is "Corner Café"; a model that drops the
        # accent (or one that includes it) must both still match.
        self.actor.move_to(self.square, quiet=True)
        unaccented = validate_and_apply(self.iri, self.actor, "give_directions", {"destination": "Corner Cafe"})
        accented = validate_and_apply(self.iri, self.actor, "give_directions", {"destination": "Corner Café"})
        self.assertTrue(unaccented.applied)
        self.assertTrue(accented.applied)

    def test_give_directions_across_hub(self):
        self.actor.move_to(self.cafe, quiet=True)
        result = validate_and_apply(self.iri, self.actor, "give_directions", {"destination": "Civic Office"})
        self.assertTrue(result.applied)
        # two hops: cafe -(south)-> square -(west)-> office, each step
        # naming the room it reaches so the model needn't guess one
        self.assertIn(f"south to {self.square.key}, then west to {self.office.key}", result.narration)

    def test_give_directions_already_there(self):
        self.actor.move_to(self.office, quiet=True)
        result = validate_and_apply(self.iri, self.actor, "give_directions", {"destination": "Civic Office"})
        self.assertTrue(result.applied)
        self.assertIn("already there", result.narration)

    def test_give_directions_outside_neighborhood_dropped(self):
        self.actor.move_to(self.square, quiet=True)
        result = validate_and_apply(self.iri, self.actor, "give_directions", {"destination": "Freehold"})
        self.assertFalse(result.applied)
        self.assertIn("not in neighborhood", result.reason)

    # Duplicate titles: the closest room wins, the first in manifest order on
    # a tie. Two extra rooms share a placeholder title; each is reached by
    # its own exit key, so the narration shows which one was picked.

    def _twin_rooms(self, first_exit_from, second_exit_from):
        """Two rooms titled "Twin Room" (manifest order: first, second), each
        reached from the given room (None = unreachable) by an exit named
        "to first" / "to second". Returns a patch of room_titles."""
        for tag, exit_from in (("twin_first", first_exit_from), ("twin_second", second_exit_from)):
            room = create_object("typeclasses.rooms.Room", key="Twin Room")
            room.tags.add(tag, category=ROOM_TAG_CATEGORY)
            if exit_from is not None:
                create_object(
                    "typeclasses.exits.Exit", key=f"to {tag.split('_')[1]}", location=exit_from, destination=room
                )
        titles = room_titles() + [("twin_first", "Twin Room"), ("twin_second", "Twin Room")]
        return patch("world.build_sector.room_titles", return_value=titles)

    def test_give_directions_duplicate_title_picks_closest(self):
        # first is two hops away (via the square), second is next door
        self.actor.move_to(self.cafe, quiet=True)
        with self._twin_rooms(self.square, self.cafe):
            result = validate_and_apply(self.iri, self.actor, "give_directions", {"destination": "Twin Room"})
        self.assertTrue(result.applied)
        self.assertIn("to second", result.narration)
        self.assertNotIn("to first", result.narration)

    def test_give_directions_duplicate_title_tie_picks_first_in_manifest(self):
        self.actor.move_to(self.cafe, quiet=True)
        with self._twin_rooms(self.cafe, self.cafe):
            result = validate_and_apply(self.iri, self.actor, "give_directions", {"destination": "Twin Room"})
        self.assertTrue(result.applied)
        self.assertIn("to first", result.narration)

    def test_give_directions_duplicate_title_skips_unreachable(self):
        self.actor.move_to(self.cafe, quiet=True)
        with self._twin_rooms(None, self.square):
            result = validate_and_apply(self.iri, self.actor, "give_directions", {"destination": "Twin Room"})
        self.assertTrue(result.applied)
        self.assertIn("to second", result.narration)

    def test_give_directions_duplicate_title_none_reachable_dropped(self):
        self.actor.move_to(self.cafe, quiet=True)
        with self._twin_rooms(None, None):
            result = validate_and_apply(self.iri, self.actor, "give_directions", {"destination": "Twin Room"})
        self.assertFalse(result.applied)
        self.assertIn("no known path", result.reason)

    # -- unknown action ----------------------------------------------------

    def test_unknown_action_dropped(self):
        result = validate_and_apply(self.mara, self.actor, "set_drink_price", {"price": 5})
        self.assertFalse(result.applied)

    # -- module-exchange quest (retired from live content, 2026-10-13 -----
    # the heater/module errand served its purpose for 2A's exit test and
    # was dropped from Mara's and Tarin's personas - see mara_voss.md's
    # and tarin_os.md's git history for the content that used to live
    # there. The state-machine code and its validators are untouched and
    # still worth protecting against a silent regression, so these test
    # the private validators directly (same pattern as
    # CommitmentActionWiringTests below) rather than through
    # validate_and_apply, which would now reject every one of these for
    # both NPCs - confirmed by test_retired_actions_rejected_by_persona.

    def test_quest_starts_not_started(self):
        self.assertEqual(get_quest_state(self.actor), "not_started")

    def test_accept_help_before_asking_is_dropped(self):
        # PF-0011: she recorded the yes before the player had given it.
        result = _validate_accept_help(self.mara, self.actor, {})
        self.assertFalse(result.applied)
        self.assertIn("haven't asked", result.reason)
        self.assertEqual(get_quest_state(self.actor), "not_started")

    def test_ask_for_help_marks_the_errand_offered(self):
        self.assertTrue(_validate_ask_for_help(self.mara, self.actor, {}).applied)
        self.assertEqual(get_quest_state(self.actor), "offered")

    def test_ask_for_help_again_while_offered_is_dropped(self):
        _validate_ask_for_help(self.mara, self.actor, {})
        self.assertFalse(_validate_ask_for_help(self.mara, self.actor, {}).applied)
        self.assertEqual(get_quest_state(self.actor), "offered")

    def test_a_repeat_ask_alongside_the_yes_does_not_drop_the_yes(self):
        # Eval 2026-10-17: on "Sure, I'll take it" she called ask_for_help
        # again with accept_help. The re-ask is dropped, so the yes stands.
        _validate_ask_for_help(self.mara, self.actor, {})
        applied = []
        for name in ("ask_for_help", "accept_help", "give_faulty_module"):
            result = validate_and_apply(self.mara, self.actor, name, {"confirmed": True}, applied_earlier=applied)
            if result.applied:
                applied.append(name)
        self.assertEqual(applied, ["accept_help", "give_faulty_module"])
        self.assertEqual(get_quest_state(self.actor), "has_faulty_module")

    def test_ask_for_help_after_accepting_is_dropped(self):
        _validate_ask_for_help(self.mara, self.actor, {})
        _validate_accept_help(self.mara, self.actor, {})
        self.assertFalse(_validate_ask_for_help(self.mara, self.actor, {}).applied)
        self.assertEqual(get_quest_state(self.actor), "accepted")

    def test_accept_help_after_asking(self):
        _validate_ask_for_help(self.mara, self.actor, {})
        result = _validate_accept_help(self.mara, self.actor, {})
        self.assertTrue(result.applied)
        self.assertEqual(get_quest_state(self.actor), "accepted")

    def test_decline_help_returns_the_errand_to_the_start(self):
        _validate_ask_for_help(self.mara, self.actor, {})
        self.assertTrue(_validate_decline_help(self.mara, self.actor, {}).applied)
        self.assertEqual(get_quest_state(self.actor), "not_started")

    def test_decline_help_without_an_ask_is_dropped(self):
        self.assertFalse(_validate_decline_help(self.mara, self.actor, {}).applied)

    def test_accept_help_in_the_same_reply_as_the_ask_is_dropped(self):
        asked = validate_and_apply(self.mara, self.actor, "ask_for_help", {"confirmed": True})
        self.assertTrue(asked.applied)
        result = validate_and_apply(
            self.mara, self.actor, "accept_help", {"confirmed": True}, applied_earlier=["ask_for_help"]
        )
        self.assertFalse(result.applied)
        self.assertIn("haven't answered yet", result.reason)
        self.assertEqual(get_quest_state(self.actor), "offered")

    def test_accept_help_in_a_later_reply_applies(self):
        validate_and_apply(self.mara, self.actor, "ask_for_help", {"confirmed": True})
        result = validate_and_apply(self.mara, self.actor, "accept_help", {"confirmed": True})
        self.assertTrue(result.applied)
        self.assertEqual(get_quest_state(self.actor), "accepted")

    def test_accept_help_twice_is_dropped(self):
        _validate_ask_for_help(self.mara, self.actor, {})
        _validate_accept_help(self.mara, self.actor, {})
        result = _validate_accept_help(self.mara, self.actor, {})
        self.assertFalse(result.applied)
        self.assertEqual(get_quest_state(self.actor), "accepted")

    def test_give_faulty_module_requires_accepted(self):
        result = _validate_give_faulty_module(self.mara, self.actor, {})
        self.assertFalse(result.applied)
        self.assertEqual(get_quest_state(self.actor), "not_started")

    def test_give_faulty_module_after_accepted(self):
        _validate_ask_for_help(self.mara, self.actor, {})
        _validate_accept_help(self.mara, self.actor, {})
        result = _validate_give_faulty_module(self.mara, self.actor, {})
        self.assertTrue(result.applied)
        self.assertEqual(get_quest_state(self.actor), "has_faulty_module")

    def test_exchange_module_requires_faulty_module_in_hand(self):
        result = _validate_exchange_module(self.tarin, self.actor, {})
        self.assertFalse(result.applied)
        self.assertEqual(get_quest_state(self.actor), "not_started")

    def test_full_quest_sequence(self):
        self.assertTrue(_validate_ask_for_help(self.mara, self.actor, {}).applied)
        self.assertTrue(_validate_accept_help(self.mara, self.actor, {}).applied)
        self.assertTrue(_validate_give_faulty_module(self.mara, self.actor, {}).applied)
        self.assertTrue(_validate_exchange_module(self.tarin, self.actor, {}).applied)
        self.assertEqual(get_quest_state(self.actor), "has_replacement_module")
        self.assertTrue(_validate_accept_replacement(self.mara, self.actor, {}).applied)
        self.assertEqual(get_quest_state(self.actor), "completed")

    def test_accept_replacement_too_early_is_dropped(self):
        _validate_ask_for_help(self.mara, self.actor, {})
        _validate_accept_help(self.mara, self.actor, {})
        _validate_give_faulty_module(self.mara, self.actor, {})
        result = _validate_accept_replacement(self.mara, self.actor, {})
        self.assertFalse(result.applied)
        self.assertEqual(get_quest_state(self.actor), "has_faulty_module")

    def test_quest_state_is_per_player(self):
        other = create_object("typeclasses.characters.Character", key="Other", location=self.cafe)
        _validate_ask_for_help(self.mara, self.actor, {})
        _validate_accept_help(self.mara, self.actor, {})
        self.assertEqual(get_quest_state(self.actor), "accepted")
        self.assertEqual(get_quest_state(other), "not_started")

    def test_quest_context_for_npc_without_quest_actions_is_none(self):
        self.assertIsNone(quest_context_for(["give_directions"], self.actor))

    def test_quest_context_for_mara_reflects_current_state(self):
        _validate_ask_for_help(self.mara, self.actor, {})
        _validate_accept_help(self.mara, self.actor, {})
        context = quest_context_for(["serve_drink", "accept_help", "give_faulty_module", "accept_replacement"], self.actor)
        self.assertIn("accepted", context)

    def test_quest_context_for_tarin_hides_states_outside_his_role(self):
        # Tarin's persona has no knowledge of the early stages (Mara's
        # side of the errand) - the engine state fed to him shouldn't
        # contradict that (CLAUDE.md hard rule 5).
        context = quest_context_for(["exchange_module"], self.actor)
        self.assertNotIn("not_started", context)
        self.assertIn("not yet at a stage that involves you", context)

    def test_quest_context_for_tarin_reflects_his_own_stage(self):
        _validate_ask_for_help(self.mara, self.actor, {})
        _validate_accept_help(self.mara, self.actor, {})
        _validate_give_faulty_module(self.mara, self.actor, {})
        context = quest_context_for(["exchange_module"], self.actor)
        self.assertIn("has_faulty_module", context)

    def test_quest_context_tells_tarin_not_to_raise_the_module_first(self):
        # PF-0005: given the bare state, Tarin named the module before
        # the player mentioned it. Mara handed it over, so she may.
        _validate_ask_for_help(self.mara, self.actor, {})
        _validate_accept_help(self.mara, self.actor, {})
        _validate_give_faulty_module(self.mara, self.actor, {})
        self.assertIn("until the player brings it up", quest_context_for(["exchange_module"], self.actor))
        mara_context = quest_context_for(["accept_help", "give_faulty_module", "accept_replacement"], self.actor)
        self.assertNotIn("until the player brings it up", mara_context)

    def test_quest_action_schemas_require_an_argument(self):
        # Confirmed empirically against the live model: an identical
        # zero-argument tool schema is reliably never called (the
        # model just narrates in prose instead), while the same action
        # with one required argument to fill in is called reliably.
        # This isn't a style preference - removing the required
        # argument silently reintroduces that bug.
        for name in ("accept_help", "give_faulty_module", "exchange_module", "accept_replacement"):
            schema = ACTION_SCHEMAS[name]["function"]
            self.assertTrue(
                schema["parameters"]["required"], f"{name}'s schema must require at least one argument"
            )

    def test_heating_module_actions_granted_by_persona(self):
        # The heating-module errand (Quest 1, "A Minor Inconvenience")
        # was revived and wired back into Mara's/Tarin's real personas -
        # confirms the permission gate in validate_and_apply actually
        # grants these now, mirroring the old "rejected" test this
        # replaces.
        for npc, name in (
            (self.mara, "accept_help"),
            (self.mara, "give_faulty_module"),
            (self.mara, "accept_replacement"),
            (self.tarin, "exchange_module"),
        ):
            result = validate_and_apply(npc, self.actor, name, {})
            self.assertNotIn("not a permitted action", result.reason)


class CommitmentActionWiringTests(TestCase):
    """
    Tests the generic commitment actions' wiring to world.commitments
    directly against the private validators, not through
    validate_and_apply. Uses verify_display_revision (Daven proposes/
    holds since docs/errand-redistribution-plan.md, Iri is clerk) purely as an example holder+clerk scenario to
    exercise the shared propose/accept/decline/report_commitment_outcome
    lifecycle - not a test of that scenario's own content. (Originally
    used discrepancy_report; that scenario was removed 2026-10-16 - see
    CLAUDE.md's "One quest offer per NPC" - so this was re-pointed to
    the only other scenario sharing the same holder+clerk shape.)
    """

    COMMITMENT_TYPE = "verify_display_revision"

    def setUp(self):
        rooms = build_rooms()
        npcs = build_npcs()
        self.daven = npcs["daven_varek"]  # the scenario's holder_npc_id
        self.mara = npcs["mara_voss"]  # its holder before the redistribution
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=rooms["corner_cafe"]
        )
        self.iri = npcs["iri_vael"]  # the scenario's clerk_npc_id

    def test_propose_requires_known_commitment_type(self):
        result = _validate_propose_commitment(self.daven, self.actor, {"commitment_type": "nonsense"})
        self.assertFalse(result.applied)

    def test_propose_accept_then_clerk_acknowledges_then_holder_fulfills(self):
        propose = _validate_propose_commitment(self.daven, self.actor, {"commitment_type": self.COMMITMENT_TYPE})
        self.assertTrue(propose.applied)

        accept = _validate_accept_commitment(self.daven, self.actor, {"commitment_type": self.COMMITMENT_TYPE})
        self.assertTrue(accept.applied)

        # The player claims to Daven directly, without having visited
        # Iri - must not fulfill.
        premature = _validate_report_commitment_outcome(
            self.daven, self.actor, {"commitment_type": self.COMMITMENT_TYPE}
        )
        self.assertFalse(premature.applied)

        # Iri's call records acknowledgment, not fulfillment. Uses the
        # bare lifecycle function directly (not verify_revision_report's
        # own precondition check), since this test is about the generic
        # report_commitment_outcome wiring, not revision-matching.
        from world.commitments import record_acknowledgment

        ack = record_acknowledgment(self.actor, self.COMMITMENT_TYPE, "iri_vael")
        self.assertTrue(ack.ok)

        # Now Daven's call actually fulfills.
        fulfill = _validate_report_commitment_outcome(
            self.daven, self.actor, {"commitment_type": self.COMMITMENT_TYPE}
        )
        self.assertTrue(fulfill.applied)

    def test_decline_closes_offer_without_obligation(self):
        _validate_propose_commitment(self.daven, self.actor, {"commitment_type": self.COMMITMENT_TYPE})
        decline = _validate_decline_commitment(self.daven, self.actor, {"commitment_type": self.COMMITMENT_TYPE})
        self.assertTrue(decline.applied)

        # Declining isn't terminal - the offer can be made again.
        reoffer = _validate_propose_commitment(self.daven, self.actor, {"commitment_type": self.COMMITMENT_TYPE})
        self.assertTrue(reoffer.applied)

    def test_former_holder_mara_has_no_role_any_more(self):
        propose = _validate_propose_commitment(self.mara, self.actor, {"commitment_type": self.COMMITMENT_TYPE})
        self.assertFalse(propose.applied)
        self.assertIn("no proposer role", propose.reason)

        _validate_propose_commitment(self.daven, self.actor, {"commitment_type": self.COMMITMENT_TYPE})
        _validate_accept_commitment(self.daven, self.actor, {"commitment_type": self.COMMITMENT_TYPE})
        from world.commitments import record_acknowledgment

        record_acknowledgment(self.actor, self.COMMITMENT_TYPE, "iri_vael")
        fulfill = _validate_report_commitment_outcome(
            self.mara, self.actor, {"commitment_type": self.COMMITMENT_TYPE}
        )
        self.assertFalse(fulfill.applied)

    def test_report_outcome_by_an_npc_with_no_role_is_dropped(self):
        bystander = create_object(
            "typeclasses.npcs.TalkativeNPC", key="Bystander", location=self.actor.location
        )
        bystander.db.npc_id = "tarin_os"
        result = _validate_report_commitment_outcome(
            bystander, self.actor, {"commitment_type": self.COMMITMENT_TYPE}
        )
        self.assertFalse(result.applied)

    def test_commitment_action_schemas_require_an_argument(self):
        for name in (
            "propose_commitment",
            "accept_commitment",
            "decline_commitment",
            "report_commitment_outcome",
            "accept_handoff",
        ):
            schema = ACTION_SCHEMAS[name]["function"]
            self.assertTrue(
                schema["parameters"]["required"], f"{name}'s schema must require at least one argument"
            )


class ParcelActionWiringTests(TestCase):
    """
    docs/phase2c-misdelivered-parcel-proposal.md: Veska proposes the
    errand (Mara until docs/errand-redistribution-plan.md, 2026-10-16)
    and Tarin, its only holder (D2), completes it once the player
    actually carries the real Parcel object to him. Covers the full
    pipeline (parcel creation on accept, the possession check,
    completion) through the private validators, same level as
    CommitmentActionWiringTests above.
    """

    TYPE = "deliver_parcel"

    def setUp(self):
        rooms = build_rooms()
        npcs = build_npcs()
        self.veska = npcs["veska_renn"]  # the scenario's proposer
        self.tarin = npcs["tarin_os"]  # its only holder
        self.mara = npcs["mara_voss"]  # its proposer before the redistribution
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=rooms["corner_cafe"]
        )

    def _carried_parcels(self):
        return [obj for obj in self.actor.contents if obj.is_typeclass("typeclasses.objects.Parcel", exact=False)]

    def _accept(self):
        _validate_propose_commitment(self.veska, self.actor, {"commitment_type": self.TYPE})
        _validate_accept_commitment(self.veska, self.actor, {"commitment_type": self.TYPE})

    def test_accepting_creates_a_real_carried_parcel(self):
        _validate_propose_commitment(self.veska, self.actor, {"commitment_type": self.TYPE})
        self.assertEqual(self._carried_parcels(), [])
        _validate_accept_commitment(self.veska, self.actor, {"commitment_type": self.TYPE})
        self.assertEqual(len(self._carried_parcels()), 1)

    def test_carried_parcel_has_a_description(self):
        # It shouldn't lose its description once handed over - a
        # player should be able to `look` at what they're carrying,
        # same as they could examine it sitting on the counter.
        self._accept()
        parcel = self._carried_parcels()[0]
        self.assertTrue(parcel.db.desc)
        self.assertIn("Tarin Os", parcel.db.desc)

    def test_handoff_without_the_parcel_is_dropped(self):
        self._accept()
        for parcel in self._carried_parcels():
            parcel.location = None  # simulate not actually having it on hand
        result = _validate_accept_handoff(self.tarin, self.actor, {"commitment_type": self.TYPE})
        self.assertFalse(result.applied)

    def test_full_direct_delivery_route(self):
        self._accept()
        self.assertEqual(len(self._carried_parcels()), 1)

        result = _validate_accept_handoff(self.tarin, self.actor, {"commitment_type": self.TYPE})
        self.assertTrue(result.applied)
        # Custody actually transferred - the player no longer carries it.
        self.assertEqual(self._carried_parcels(), [])

    def test_giver_cannot_take_it_back(self):
        # D2: the Civic Office no longer takes the parcel in as an
        # alternative destination - only Tarin can.
        self._accept()
        result = _validate_accept_handoff(self.veska, self.actor, {"commitment_type": self.TYPE})
        self.assertFalse(result.applied)
        self.assertEqual(len(self._carried_parcels()), 1)

    def test_cannot_hand_it_over_twice(self):
        self._accept()
        _validate_accept_handoff(self.tarin, self.actor, {"commitment_type": self.TYPE})

        result = _validate_accept_handoff(self.tarin, self.actor, {"commitment_type": self.TYPE})
        self.assertFalse(result.applied)

    def test_stock_give_cannot_move_the_parcel_to_anyone_else(self):
        self._accept()
        parcel = self._carried_parcels()[0]
        other = create_object("typeclasses.characters.Character", key="Other", location=self.actor.location)
        self.assertFalse(parcel.at_pre_give(self.actor, other))
        self.assertFalse(parcel.at_pre_give(self.actor, self.veska))
        self.assertIs(parcel.location, self.actor)
        self.assertIsNone(get_fulfilled_commitment(self.actor, self.TYPE))

    def test_give_to_tarin_completes_the_handoff(self):
        # Owner, 2026-10-17: `give parcel to Tarin` works, through the
        # same validator as Tarin's own accept_handoff call.
        self._accept()
        self.actor.location = self.tarin.location
        self.actor.execute_cmd("give parcel to Tarin")
        self.assertEqual(self._carried_parcels(), [])
        self.assertIsNotNone(get_fulfilled_commitment(self.actor, self.TYPE))

    def test_give_to_tarin_narration_goes_to_the_giver_only(self):
        # It's written to the giver as "you", so nobody else gets it; and
        # like say.py's narration it's gray, with Tarin's first name
        # (LR-LORE-0009).
        self._accept()
        parcel = self._carried_parcels()[0]
        self.actor.location = self.tarin.location
        bystander = create_object(
            "typeclasses.characters.Character", key="Bystander", location=self.tarin.location, home=self.tarin.location
        )
        to_actor, to_bystander = [], []
        with patch.object(self.actor, "msg", side_effect=lambda text=None, **kw: to_actor.append(text)), \
                patch.object(bystander, "msg", side_effect=lambda text=None, **kw: to_bystander.append(text)):
            parcel.at_pre_give(self.actor, self.tarin)
        self.assertEqual(to_actor, ["|xTarin takes the parcel from you.|n"])
        self.assertEqual(to_bystander, [])

    def test_give_to_tarin_without_an_open_errand_is_refused(self):
        self._accept()
        parcel = self._carried_parcels()[0]
        _validate_accept_handoff(self.tarin, self.actor, {"commitment_type": self.TYPE})
        parcel.location = self.actor  # a stale copy still in hand
        self.assertFalse(parcel.at_pre_give(self.actor, self.tarin))
        self.assertIs(parcel.location, self.actor)

    def test_stock_drop_cannot_move_the_parcel(self):
        self._accept()
        parcel = self._carried_parcels()[0]
        self.assertFalse(parcel.access(self.actor, "drop"))

    def test_only_the_proposer_can_propose_it(self):
        # Confirmed live, 2026-10-13: Tarin holds propose_commitment/
        # accept_commitment generically (for his own discrepancy_report
        # role) and, with no per-call role check, could also invoke
        # them for the parcel errand - handing over a parcel he never
        # actually held, without its giver ever being involved.
        result = _validate_propose_commitment(self.tarin, self.actor, {"commitment_type": self.TYPE})
        self.assertFalse(result.applied)
        self.assertIn("no proposer role", result.reason)

    def test_former_giver_mara_cannot_propose_it(self):
        result = _validate_propose_commitment(self.mara, self.actor, {"commitment_type": self.TYPE})
        self.assertFalse(result.applied)
        self.assertIn("no proposer role", result.reason)

    def test_only_the_proposer_can_accept_it(self):
        _validate_propose_commitment(self.veska, self.actor, {"commitment_type": self.TYPE})
        result = _validate_accept_commitment(self.tarin, self.actor, {"commitment_type": self.TYPE})
        self.assertFalse(result.applied)
        self.assertEqual(self._carried_parcels(), [])

    def test_only_the_proposer_can_decline_it(self):
        _validate_propose_commitment(self.veska, self.actor, {"commitment_type": self.TYPE})
        result = _validate_decline_commitment(self.tarin, self.actor, {"commitment_type": self.TYPE})
        self.assertFalse(result.applied)


class ParcelDeliveryRumorWiringTests(TestCase):
    """
    docs/phase2e-word-gets-around-design.md: the parcel giver's
    (Veska's, since docs/errand-redistribution-plan.md) deliver_parcel
    proposer-side view is held at "open" until report_parcel_delivery
    actually tells her, even once the real commitment is fulfilled -
    and the one-time reputation credit survives a reset/replay of the
    underlying commitment without being awarded twice.
    """

    TYPE = "deliver_parcel"
    REPORT = {"confirmed": True}

    def setUp(self):
        rooms = build_rooms()
        npcs = build_npcs()
        self.veska = npcs["veska_renn"]
        self.tarin = npcs["tarin_os"]
        self.mara = npcs["mara_voss"]
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=rooms["corner_cafe"]
        )

    def _deliver(self):
        _validate_propose_commitment(self.veska, self.actor, {"commitment_type": self.TYPE})
        _validate_accept_commitment(self.veska, self.actor, {"commitment_type": self.TYPE})
        return _validate_accept_handoff(self.tarin, self.actor, {"commitment_type": self.TYPE})

    def _veska_state(self):
        return commitment_context_for(
            "veska_renn", ["propose_commitment", "report_parcel_delivery"], self.actor
        )

    def test_veska_does_not_know_before_being_told(self):
        self._deliver()
        context = self._veska_state()
        self.assertIn("open", context)
        self.assertNotIn("fulfilled", context)

    def test_report_succeeds_and_reveals_fulfillment(self):
        self._deliver()
        result = _validate_report_parcel_delivery(self.veska, self.actor, self.REPORT)
        self.assertTrue(result.applied)
        self.assertIn("Tarin", result.narration)
        self.assertIn("fulfilled", self._veska_state())

    def test_report_awards_reputation_to_veska(self):
        self._deliver()
        self.assertEqual(get_reputation(self.actor, "veska_renn"), 0)
        _validate_report_parcel_delivery(self.veska, self.actor, self.REPORT)
        self.assertEqual(get_reputation(self.actor, "veska_renn"), 1)
        self.assertEqual(get_reputation(self.actor, "mara_voss"), 0)

    def test_report_while_still_in_transit_is_rejected(self):
        _validate_propose_commitment(self.veska, self.actor, {"commitment_type": self.TYPE})
        _validate_accept_commitment(self.veska, self.actor, {"commitment_type": self.TYPE})
        result = _validate_report_parcel_delivery(self.veska, self.actor, self.REPORT)
        self.assertFalse(result.applied)
        self.assertEqual(get_reputation(self.actor, "veska_renn"), 0)
        self.assertIn("open", self._veska_state())

    def test_report_with_no_fulfilled_commitment_is_rejected(self):
        result = _validate_report_parcel_delivery(self.veska, self.actor, self.REPORT)
        self.assertFalse(result.applied)

    def test_only_the_giver_has_a_role_in_this_rumor(self):
        self._deliver()
        for npc in (self.tarin, self.mara):
            result = _validate_report_parcel_delivery(npc, self.actor, self.REPORT)
            self.assertFalse(result.applied, npc.db.npc_id)
            self.assertIn("no role", result.reason)

    def test_repeated_report_does_not_double_credit(self):
        self._deliver()
        _validate_report_parcel_delivery(self.veska, self.actor, self.REPORT)
        result = _validate_report_parcel_delivery(self.veska, self.actor, self.REPORT)
        self.assertFalse(result.applied)
        self.assertEqual(get_reputation(self.actor, "veska_renn"), 1)

    def test_reputation_credited_only_once_across_multiple_commitment_instances(self):
        from world.commitments import reset_commitment

        self._deliver()
        _validate_report_parcel_delivery(self.veska, self.actor, self.REPORT)
        self.assertEqual(get_reputation(self.actor, "veska_renn"), 1)

        reset_commitment(self.actor, self.TYPE)
        self._deliver()
        result = _validate_report_parcel_delivery(self.veska, self.actor, self.REPORT)
        self.assertTrue(result.applied)  # the new instance can still be reported...
        self.assertEqual(get_reputation(self.actor, "veska_renn"), 1)  # ...but credit doesn't stack

    def test_informed_knowledge_is_per_commitment_instance(self):
        from world.commitments import reset_commitment

        self._deliver()
        _validate_report_parcel_delivery(self.veska, self.actor, self.REPORT)
        self.assertTrue(has_reputation_credit(self.actor))


class RememberFactWiringTests(TestCase):
    """world/npc_memory.py's remember_fact through the full permission-
    gated pipeline (validate_and_apply), same level as the other
    *WiringTests classes above."""

    def setUp(self):
        rooms = build_rooms()
        npcs = build_npcs()
        self.mara = npcs["mara_voss"]
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=rooms["corner_cafe"]
        )

    def test_remembered_fact_is_injected_next_turn(self):
        result = validate_and_apply(self.mara, self.actor, "remember_fact", {"fact": "grew up near the Docks", "player_words": "I grew up near the Docks"}, "I grew up near the Docks.")
        self.assertTrue(result.applied)
        from world.npc_memory import memory_context_for

        self.assertIn("grew up near the Docks", memory_context_for("mara_voss", self.actor))

    def test_narration_is_empty_by_default(self):
        result = validate_and_apply(self.mara, self.actor, "remember_fact", {"fact": "likes cold drinks", "player_words": "I like cold drinks"}, "I like cold drinks.")
        self.assertEqual(result.narration, "")

    def test_narration_shows_the_fact_when_debug_enabled(self):
        self.actor.attributes.add("memory_debug_enabled", True)
        result = validate_and_apply(self.mara, self.actor, "remember_fact", {"fact": "likes cold drinks", "player_words": "I like cold drinks"}, "I like cold drinks.")
        self.assertIn("likes cold drinks", result.narration)
        self.assertIn("Mara Voss", result.narration)

    def test_debug_narration_omitted_for_a_dropped_call(self):
        self.actor.attributes.add("memory_debug_enabled", True)
        result = validate_and_apply(self.mara, self.actor, "remember_fact", {"fact": "", "player_words": "I like cold drinks"}, "I like cold drinks.")
        self.assertFalse(result.applied)
        self.assertEqual(result.narration, "")

    def test_flagged_fact_dropped_through_full_pipeline(self):
        result = validate_and_apply(
            self.mara, self.actor, "remember_fact", {"fact": "As an AI, I don't have personal experiences.", "player_words": "I like cold drinks"}, "I like cold drinks."
        )
        self.assertFalse(result.applied)

    def test_fact_the_player_never_stated_is_dropped(self):
        # PF-0004, playtest 2026-10-17: "What race are you?" got Tarin
        # storing his own species as the player's.
        for words, message in [
            ("Drask", "What race are you?"),
            ("What race am I", "What race am I? I can't remember."),
            ("I grew up near the Docks", "hello there"),
            ("I grew up near the Docks", None),
        ]:
            result = validate_and_apply(
                self.mara, self.actor, "remember_fact", {"fact": "is Drask", "player_words": words}, message
            )
            self.assertFalse(result.applied, (words, message))
        from world.npc_memory import memory_context_for

        self.assertIsNone(memory_context_for("mara_voss", self.actor))

    def test_remember_fact_schema_requires_an_argument(self):
        schema = ACTION_SCHEMAS["remember_fact"]["function"]
        self.assertEqual(schema["parameters"]["required"], ["fact", "player_words"])


class VerifyRevisionReportWiringTests(TestCase):
    """
    docs/phase2-quest-prototype-design.md §14 / docs/phase2d-
    noticeboard-check-proposal.md: Iri's corroboration is gated on a
    real structured fact (world/noticeboard.py), not a credibility
    judgment - this is the first corroboration step in the project
    that can genuinely fail. Covers the full pipeline through the
    private validators, same level as the other *WiringTests classes.
    """

    TYPE = "verify_display_revision"

    def setUp(self):
        rooms = build_rooms()
        npcs = build_npcs()
        self.daven = npcs["daven_varek"]  # the scenario's holder
        self.iri = npcs["iri_vael"]
        self.tarin = npcs["tarin_os"]
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=rooms["corner_cafe"]
        )

    def _accept(self):
        _validate_propose_commitment(self.daven, self.actor, {"commitment_type": self.TYPE})
        _validate_accept_commitment(self.daven, self.actor, {"commitment_type": self.TYPE})

    def test_correct_report_succeeds(self):
        from world.noticeboard import get_or_create_expected_revision

        self._accept()
        expected = get_or_create_expected_revision(self.actor)
        result = _validate_verify_revision_report(
            self.iri, self.actor, {"commitment_type": self.TYPE, "reported_revision": expected}
        )
        self.assertTrue(result.applied)

    def test_wrong_report_is_rejected(self):
        from world.noticeboard import get_or_create_expected_revision

        self._accept()
        expected = get_or_create_expected_revision(self.actor)
        wrong = "9999" if expected != "9999" else "1111"
        result = _validate_verify_revision_report(
            self.iri, self.actor, {"commitment_type": self.TYPE, "reported_revision": wrong}
        )
        self.assertFalse(result.applied)

    def test_rejection_reason_does_not_leak_the_expected_value(self):
        from world.noticeboard import get_or_create_expected_revision

        self._accept()
        expected = get_or_create_expected_revision(self.actor)
        wrong = "9999" if expected != "9999" else "1111"
        result = _validate_verify_revision_report(
            self.iri, self.actor, {"commitment_type": self.TYPE, "reported_revision": wrong}
        )
        self.assertNotIn(expected, result.reason)

    def test_wrong_npc_cannot_verify(self):
        from world.noticeboard import get_or_create_expected_revision

        self._accept()
        expected = get_or_create_expected_revision(self.actor)
        result = _validate_verify_revision_report(
            self.tarin, self.actor, {"commitment_type": self.TYPE, "reported_revision": expected}
        )
        self.assertFalse(result.applied)

    def test_retry_after_wrong_report_can_still_succeed(self):
        from world.noticeboard import get_or_create_expected_revision

        self._accept()
        expected = get_or_create_expected_revision(self.actor)
        wrong = "9999" if expected != "9999" else "1111"
        _validate_verify_revision_report(
            self.iri, self.actor, {"commitment_type": self.TYPE, "reported_revision": wrong}
        )
        result = _validate_verify_revision_report(
            self.iri, self.actor, {"commitment_type": self.TYPE, "reported_revision": expected}
        )
        self.assertTrue(result.applied)

    def test_daven_closes_it_after_genuine_acknowledgment(self):
        from world.noticeboard import get_or_create_expected_revision

        self._accept()
        expected = get_or_create_expected_revision(self.actor)
        _validate_verify_revision_report(
            self.iri, self.actor, {"commitment_type": self.TYPE, "reported_revision": expected}
        )
        result = _validate_report_commitment_outcome(self.daven, self.actor, {"commitment_type": self.TYPE})
        self.assertTrue(result.applied)

    def test_daven_cannot_close_it_without_acknowledgment(self):
        self._accept()
        result = _validate_report_commitment_outcome(self.daven, self.actor, {"commitment_type": self.TYPE})
        self.assertFalse(result.applied)

    def test_verify_revision_report_schema_requires_arguments(self):
        schema = ACTION_SCHEMAS["verify_revision_report"]["function"]
        self.assertEqual(set(schema["parameters"]["required"]), {"commitment_type", "reported_revision"})


class TendPlantingBedWiringTests(TestCase):
    """
    docs/prospect-initial-playtest-design-spec.md §6, Quest 2 ("A Little
    Community Work"): Iri proposes/accepts/declines and also fulfills,
    gated on world/garden.py's per-player flag rather than a reported
    value or a physical handoff - set only by commands/use.py's world
    action, never by anything the model proposes.
    """

    TYPE = "tend_planting_bed"

    def setUp(self):
        from world.actions import _validate_confirm_bed_tended

        self._validate_confirm_bed_tended = _validate_confirm_bed_tended
        rooms = build_rooms()
        npcs = build_npcs()
        self.iri = npcs["iri_vael"]
        self.mara = npcs["mara_voss"]
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=rooms["old_quarter_square"]
        )

    def _accept(self):
        _validate_propose_commitment(self.iri, self.actor, {"commitment_type": self.TYPE})
        _validate_accept_commitment(self.iri, self.actor, {"commitment_type": self.TYPE})

    def test_confirm_before_bed_tended_is_dropped(self):
        self._accept()
        result = self._validate_confirm_bed_tended(self.iri, self.actor, {"confirmed": True})
        self.assertFalse(result.applied)

    def test_confirm_after_bed_tended_succeeds(self):
        from world.garden import mark_bed_tended

        self._accept()
        mark_bed_tended(self.actor)
        result = self._validate_confirm_bed_tended(self.iri, self.actor, {"confirmed": True})
        self.assertTrue(result.applied)

    def test_wrong_npc_cannot_confirm(self):
        from world.garden import mark_bed_tended

        self._accept()
        mark_bed_tended(self.actor)
        result = self._validate_confirm_bed_tended(self.mara, self.actor, {"confirmed": True})
        self.assertFalse(result.applied)

    def test_claiming_without_actually_tending_never_fulfills(self):
        # A player who merely says they did it, with no engine fact to
        # back it up, must not be able to complete the errand.
        self._accept()
        self._validate_confirm_bed_tended(self.iri, self.actor, {"confirmed": True})
        from world.commitments import get_state_summary

        self.assertEqual(get_state_summary(self.actor, self.TYPE), "open")

    def test_confirm_bed_tended_schema_requires_an_argument(self):
        schema = ACTION_SCHEMAS["confirm_bed_tended"]["function"]
        self.assertTrue(schema["parameters"]["required"])


class HuntSkittersWiringTests(TestCase):
    """
    docs/prospect-initial-playtest-design-spec.md §6, Quest 3
    ("Unwelcome Guests") / docs/playtest-quest3-skitters-design.md:
    Tarin proposes/accepts/declines and fulfills, gated on
    world/skitters.py's per-player kill count rather than a reported
    value or clerk acknowledgment. accept_commitment also has to hand
    over a real Weapon, same shape as deliver_parcel's accept creating
    a Parcel.
    """

    TYPE = "hunt_skitters"

    def setUp(self):
        from world.actions import _validate_report_skitter_kills_to_tarin

        self._validate_report_skitter_kills_to_tarin = _validate_report_skitter_kills_to_tarin
        rooms = build_rooms()
        npcs = build_npcs()
        self.tarin = npcs["tarin_os"]
        self.mara = npcs["mara_voss"]
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=rooms["old_quarter_square"]
        )

    def _accept(self):
        _validate_propose_commitment(self.tarin, self.actor, {"commitment_type": self.TYPE})
        _validate_accept_commitment(self.tarin, self.actor, {"commitment_type": self.TYPE})

    def test_accepting_hands_over_a_real_weapon(self):
        self._accept()
        weapons = [obj for obj in self.actor.contents if obj.is_typeclass("typeclasses.objects.Weapon", exact=False)]
        self.assertEqual(len(weapons), 1)

    def _batons(self):
        return [obj for obj in self.actor.contents if obj.is_typeclass("typeclasses.objects.Weapon", exact=False)]

    def test_accepting_again_doesnt_hand_over_a_second_baton(self):
        from world.actions import _create_weapon_for

        self._accept()
        _create_weapon_for(self.actor)
        self.assertEqual(len(self._batons()), 1)

    def test_cleanup_keeps_one_baton_while_the_hunt_is_open(self):
        from evennia import create_object

        from world.actions import cleanup_stray_weapons

        self._accept()
        create_object("typeclasses.objects.Weapon", key="a compact shock baton", location=self.actor)
        self.assertEqual(cleanup_stray_weapons(self.actor), 1)
        self.assertEqual(len(self._batons()), 1)

    def test_cleanup_removes_every_baton_with_no_hunt(self):
        from world.actions import cleanup_stray_weapons

        self._accept()
        from world.commitments import reset_commitment

        reset_commitment(self.actor, self.TYPE)
        self.assertEqual(cleanup_stray_weapons(self.actor), 1)
        self.assertEqual(self._batons(), [])

    def test_baton_cannot_be_given_away_or_dropped(self):
        # Owner, 2026-10-17: lending it on would let someone hunt
        # without taking Tarin's quest.
        self._accept()
        baton = next(obj for obj in self.actor.contents if obj.is_typeclass("typeclasses.objects.Weapon", exact=False))
        friend = create_object("typeclasses.characters.Character", key="Friend", location=self.actor.location)
        self.actor.execute_cmd("give baton to Friend")
        self.actor.execute_cmd("drop baton")
        self.assertIs(baton.location, self.actor)

    def test_report_before_enough_kills_is_dropped(self):
        self._accept()
        result = self._validate_report_skitter_kills_to_tarin(self.tarin, self.actor, {"confirmed": True})
        self.assertFalse(result.applied)

    def test_report_after_enough_kills_succeeds(self):
        from world.skitters import record_kill

        self._accept()
        for _ in range(3):
            record_kill(self.actor)
        result = self._validate_report_skitter_kills_to_tarin(self.tarin, self.actor, {"confirmed": True})
        self.assertTrue(result.applied)

    def test_wrong_npc_cannot_report(self):
        from world.skitters import record_kill

        self._accept()
        for _ in range(3):
            record_kill(self.actor)
        result = self._validate_report_skitter_kills_to_tarin(self.mara, self.actor, {"confirmed": True})
        self.assertFalse(result.applied)

    def test_claiming_without_actually_enough_kills_never_fulfills(self):
        from world.commitments import get_state_summary
        from world.skitters import record_kill

        self._accept()
        record_kill(self.actor)
        self._validate_report_skitter_kills_to_tarin(self.tarin, self.actor, {"confirmed": True})
        self.assertEqual(get_state_summary(self.actor, self.TYPE), "open")

    def test_report_skitter_kills_to_tarin_schema_requires_an_argument(self):
        schema = ACTION_SCHEMAS["report_skitter_kills_to_tarin"]["function"]
        self.assertTrue(schema["parameters"]["required"])


class LogDeadSkittersWithIriTests(TestCase):
    """
    The repeatable post-quest loop (project owner, 2026-10-16): once
    Tarin's hunt_skitters quest is fulfilled, new kills only count once
    Iri logs them. Goes through validate_and_apply, so the persona
    grant check is exercised too.
    """

    def setUp(self):
        rooms = build_rooms()
        npcs = build_npcs()
        self.iri = npcs["iri_vael"]
        self.tarin = npcs["tarin_os"]
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=rooms["civic_office"]
        )

    def _finish_hunt(self):
        from world.skitters import record_kill

        _validate_propose_commitment(self.tarin, self.actor, {"commitment_type": "hunt_skitters"})
        _validate_accept_commitment(self.tarin, self.actor, {"commitment_type": "hunt_skitters"})
        for _ in range(3):
            record_kill(self.actor)
        validate_and_apply(self.tarin, self.actor, "report_skitter_kills_to_tarin", {"confirmed": True})

    def _log(self, npc=None):
        return validate_and_apply(npc or self.iri, self.actor, "log_dead_skitters_with_iri", {"confirmed": True})

    def test_dropped_before_tarins_quest_is_finished(self):
        from world.skitters import banked_kills_for, record_kill

        record_kill(self.actor)
        result = self._log()
        self.assertFalse(result.applied)
        self.assertIn("Tarin", result.reason)
        self.assertEqual(banked_kills_for(self.actor), 0)

    def test_logs_every_kill_on_first_report_after_the_quest(self):
        from world.skitters import banked_kills_for

        self._finish_hunt()
        result = self._log()
        self.assertTrue(result.applied)
        # The quest's own three kills count toward the first log too.
        self.assertEqual(banked_kills_for(self.actor), 3)
        self.assertIn("Total on record: 3", result.narration)

    def test_only_new_kills_are_logged_on_a_later_report(self):
        from world.skitters import banked_kills_for, record_kill

        self._finish_hunt()
        self._log()
        record_kill(self.actor)
        record_kill(self.actor)
        result = self._log()
        self.assertTrue(result.applied)
        self.assertIn("logs 2 more skitters", result.narration)
        self.assertEqual(banked_kills_for(self.actor), 5)

    def test_dropped_when_nothing_new_since_the_last_report(self):
        self._finish_hunt()
        self._log()
        result = self._log()
        self.assertFalse(result.applied)
        self.assertIn("nothing new", result.reason)

    def test_tarin_cannot_log_kills(self):
        # Not in his persona's grant at all, so validate_and_apply drops
        # it before the role check even runs.
        self._finish_hunt()
        result = self._log(npc=self.tarin)
        self.assertFalse(result.applied)

    def test_role_check_rejects_any_npc_but_iri(self):
        # The validator's own check, independent of persona grants.
        from world.actions import _validate_log_dead_skitters_with_iri

        self._finish_hunt()
        result = _validate_log_dead_skitters_with_iri(self.tarin, self.actor, {"confirmed": True})
        self.assertFalse(result.applied)

    def test_schema_requires_an_argument(self):
        schema = ACTION_SCHEMAS["log_dead_skitters_with_iri"]["function"]
        self.assertTrue(schema["parameters"]["required"])
