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

from django.test import TestCase
from evennia import create_object

from world.actions import (
    ACTION_SCHEMAS,
    _validate_accept_commitment,
    _validate_accept_handoff,
    _validate_accept_help,
    _validate_accept_replacement,
    _validate_decline_commitment,
    _validate_exchange_module,
    _validate_give_faulty_module,
    _validate_propose_commitment,
    _validate_report_commitment_outcome,
    _validate_report_notice_outcome,
    _validate_report_parcel_delivery,
    _validate_verify_notice,
    _validate_verify_revision_report,
    _validate_withdraw_notice,
    get_quest_state,
    quest_context_for,
    validate_and_apply,
)
from world.build_npcs import build as build_npcs
from world.build_rooms import build as build_rooms
from world.commitments import commitment_context_for, get_fulfilled_commitment
from world.notice_approval import RESOLUTION_VERIFIED
from world.notice_approval import get_resolution as get_notice_resolution
from world.notice_approval import notice_displayed, set_approval_mark_present
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

    # -- hand_over_item (Tarin) -----------------------------------------

    def test_hand_over_item_valid(self):
        result = validate_and_apply(self.tarin, self.actor, "hand_over_item", {"item_type": "spare part"})
        self.assertTrue(result.applied)
        self.assertIn("spare part", result.narration)

    def test_hand_over_item_invalid_type_dropped(self):
        result = validate_and_apply(self.tarin, self.actor, "hand_over_item", {"item_type": "laser cannon"})
        self.assertFalse(result.applied)

    def test_hand_over_item_stock_runs_out(self):
        for _ in range(3):
            result = validate_and_apply(self.tarin, self.actor, "hand_over_item", {"item_type": "hand tool"})
            self.assertTrue(result.applied)
        depleted = validate_and_apply(self.tarin, self.actor, "hand_over_item", {"item_type": "hand tool"})
        self.assertFalse(depleted.applied)
        self.assertIn("out of stock", depleted.reason)

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
        # two hops: cafe -(south)-> square -(west)-> office
        self.assertIn("south", result.narration)
        self.assertIn("west", result.narration)

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

    def test_accept_help_from_not_started(self):
        result = _validate_accept_help(self.mara, self.actor, {})
        self.assertTrue(result.applied)
        self.assertEqual(get_quest_state(self.actor), "accepted")

    def test_accept_help_twice_is_dropped(self):
        _validate_accept_help(self.mara, self.actor, {})
        result = _validate_accept_help(self.mara, self.actor, {})
        self.assertFalse(result.applied)
        self.assertEqual(get_quest_state(self.actor), "accepted")

    def test_give_faulty_module_requires_accepted(self):
        result = _validate_give_faulty_module(self.mara, self.actor, {})
        self.assertFalse(result.applied)
        self.assertEqual(get_quest_state(self.actor), "not_started")

    def test_give_faulty_module_after_accepted(self):
        _validate_accept_help(self.mara, self.actor, {})
        result = _validate_give_faulty_module(self.mara, self.actor, {})
        self.assertTrue(result.applied)
        self.assertEqual(get_quest_state(self.actor), "has_faulty_module")

    def test_exchange_module_requires_faulty_module_in_hand(self):
        result = _validate_exchange_module(self.tarin, self.actor, {})
        self.assertFalse(result.applied)
        self.assertEqual(get_quest_state(self.actor), "not_started")

    def test_full_quest_sequence(self):
        self.assertTrue(_validate_accept_help(self.mara, self.actor, {}).applied)
        self.assertTrue(_validate_give_faulty_module(self.mara, self.actor, {}).applied)
        self.assertTrue(_validate_exchange_module(self.tarin, self.actor, {}).applied)
        self.assertEqual(get_quest_state(self.actor), "has_replacement_module")
        self.assertTrue(_validate_accept_replacement(self.mara, self.actor, {}).applied)
        self.assertEqual(get_quest_state(self.actor), "completed")

    def test_accept_replacement_too_early_is_dropped(self):
        _validate_accept_help(self.mara, self.actor, {})
        _validate_give_faulty_module(self.mara, self.actor, {})
        result = _validate_accept_replacement(self.mara, self.actor, {})
        self.assertFalse(result.applied)
        self.assertEqual(get_quest_state(self.actor), "has_faulty_module")

    def test_quest_state_is_per_player(self):
        other = create_object("typeclasses.characters.Character", key="Other", location=self.cafe)
        _validate_accept_help(self.mara, self.actor, {})
        self.assertEqual(get_quest_state(self.actor), "accepted")
        self.assertEqual(get_quest_state(other), "not_started")

    def test_quest_context_for_npc_without_quest_actions_is_none(self):
        self.assertIsNone(quest_context_for(["give_directions"], self.actor))

    def test_quest_context_for_mara_reflects_current_state(self):
        _validate_accept_help(self.mara, self.actor, {})
        context = quest_context_for(["serve_drink", "accept_help", "give_faulty_module", "accept_replacement"], self.actor)
        self.assertIn("accepted", context)

    def test_quest_context_for_tarin_hides_states_outside_his_role(self):
        # Tarin's persona has no knowledge of the early stages (Mara's
        # side of the errand) - the engine state fed to him shouldn't
        # contradict that (CLAUDE.md hard rule 5).
        context = quest_context_for(["hand_over_item", "exchange_module"], self.actor)
        self.assertNotIn("not_started", context)
        self.assertIn("not yet at a stage that involves you", context)

    def test_quest_context_for_tarin_reflects_his_own_stage(self):
        _validate_accept_help(self.mara, self.actor, {})
        _validate_give_faulty_module(self.mara, self.actor, {})
        context = quest_context_for(["hand_over_item", "exchange_module"], self.actor)
        self.assertIn("has_faulty_module", context)

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

    def test_retired_actions_rejected_by_persona(self):
        # Confirms the retirement actually took: neither NPC's real,
        # current persona grants these any more, so the permission
        # gate in validate_and_apply rejects all of them now, even
        # though the validators above still work correctly on their
        # own terms.
        for npc, name in (
            (self.mara, "accept_help"),
            (self.mara, "give_faulty_module"),
            (self.mara, "accept_replacement"),
            (self.tarin, "exchange_module"),
        ):
            result = validate_and_apply(npc, self.actor, name, {})
            self.assertFalse(result.applied)
            self.assertIn("not a permitted action", result.reason)


class CommitmentActionWiringTests(TestCase):
    """
    Phase 2B step 2 (docs/phase2b-records-discrepancy-proposal.md):
    tests the generic commitment actions' wiring to world.commitments
    directly against the private validators, not through
    validate_and_apply - Tarin's persona doesn't grant these action
    names yet (that's step 6), and Veska doesn't exist as an NPC yet
    (step 5), so the npc objects here are stand-ins for role-checking
    only. The full permission-gated pipeline gets its own tests once
    both personas exist.
    """

    COMMITMENT_TYPE = "discrepancy_report"

    def setUp(self):
        rooms = build_rooms()
        npcs = build_npcs()
        self.tarin = npcs["tarin_os"]  # the scenario's holder_npc_id
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=rooms["maintenance_workshop"]
        )
        self.veska = create_object(
            "typeclasses.npcs.TalkativeNPC", key="Veska Renn", location=rooms["civic_office"]
        )
        self.veska.db.npc_id = "veska_renn"  # the scenario's clerk_npc_id

    def test_propose_requires_known_commitment_type(self):
        result = _validate_propose_commitment(self.tarin, self.actor, {"commitment_type": "nonsense"})
        self.assertFalse(result.applied)

    def test_propose_accept_then_clerk_acknowledges_then_holder_fulfills(self):
        propose = _validate_propose_commitment(self.tarin, self.actor, {"commitment_type": self.COMMITMENT_TYPE})
        self.assertTrue(propose.applied)

        accept = _validate_accept_commitment(self.tarin, self.actor, {"commitment_type": self.COMMITMENT_TYPE})
        self.assertTrue(accept.applied)

        # The player claims to Tarin directly, without having visited
        # Veska - must not fulfill.
        premature = _validate_report_commitment_outcome(
            self.tarin, self.actor, {"commitment_type": self.COMMITMENT_TYPE}
        )
        self.assertFalse(premature.applied)

        # Veska's call records acknowledgment, not fulfillment.
        ack = _validate_report_commitment_outcome(self.veska, self.actor, {"commitment_type": self.COMMITMENT_TYPE})
        self.assertTrue(ack.applied)

        # Now Tarin's call actually fulfills.
        fulfill = _validate_report_commitment_outcome(
            self.tarin, self.actor, {"commitment_type": self.COMMITMENT_TYPE}
        )
        self.assertTrue(fulfill.applied)

    def test_decline_closes_offer_without_obligation(self):
        _validate_propose_commitment(self.tarin, self.actor, {"commitment_type": self.COMMITMENT_TYPE})
        decline = _validate_decline_commitment(self.tarin, self.actor, {"commitment_type": self.COMMITMENT_TYPE})
        self.assertTrue(decline.applied)

        # Declining isn't terminal - the offer can be made again.
        reoffer = _validate_propose_commitment(self.tarin, self.actor, {"commitment_type": self.COMMITMENT_TYPE})
        self.assertTrue(reoffer.applied)

    def test_report_outcome_by_an_npc_with_no_role_is_dropped(self):
        bystander = create_object(
            "typeclasses.npcs.TalkativeNPC", key="Bystander", location=self.actor.location
        )
        bystander.db.npc_id = "mara_voss"
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
    docs/phase2c-misdelivered-parcel-proposal.md, redesigned
    2026-10-13: Mara proposes one generic errand (no destination
    chosen in conversation); whichever of Tarin or Veska the player
    actually carries the real Parcel object to completes it. The
    earlier design (two separate commitment types, destination picked
    at accept time) let the model lock in a destination the player
    never actually said - see git history for that version and why it
    was replaced. Covers the full pipeline (parcel creation on accept,
    the possession check, either-holder completion) through the
    private validators, same level as CommitmentActionWiringTests
    above.
    """

    TYPE = "deliver_parcel"

    def setUp(self):
        rooms = build_rooms()
        npcs = build_npcs()
        self.mara = npcs["mara_voss"]
        self.tarin = npcs["tarin_os"]
        self.veska = npcs["veska_renn"]
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=rooms["corner_cafe"]
        )

    def _carried_parcels(self):
        return [obj for obj in self.actor.contents if obj.is_typeclass("typeclasses.objects.Parcel", exact=False)]

    def _accept(self):
        _validate_propose_commitment(self.mara, self.actor, {"commitment_type": self.TYPE})
        _validate_accept_commitment(self.mara, self.actor, {"commitment_type": self.TYPE})

    def test_accepting_creates_a_real_carried_parcel(self):
        _validate_propose_commitment(self.mara, self.actor, {"commitment_type": self.TYPE})
        self.assertEqual(self._carried_parcels(), [])
        _validate_accept_commitment(self.mara, self.actor, {"commitment_type": self.TYPE})
        self.assertEqual(len(self._carried_parcels()), 1)

    def test_carried_parcel_has_a_description(self):
        # It shouldn't lose its description once handed over - a
        # player should be able to `look` at what they're carrying,
        # same as they could examine it sitting in the cafe.
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

    def test_full_civic_office_route(self):
        # Same single commitment type - Veska completing it instead of
        # Tarin is exactly the point of the redesign: the destination
        # is decided by who the player actually brings it to.
        self._accept()
        result = _validate_accept_handoff(self.veska, self.actor, {"commitment_type": self.TYPE})
        self.assertTrue(result.applied)

    def test_cannot_complete_at_the_other_npc_after_one_completes(self):
        self._accept()
        _validate_accept_handoff(self.tarin, self.actor, {"commitment_type": self.TYPE})

        result = _validate_accept_handoff(self.veska, self.actor, {"commitment_type": self.TYPE})
        self.assertFalse(result.applied)

    def test_stock_give_cannot_move_the_parcel(self):
        self._accept()
        parcel = self._carried_parcels()[0]
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
        # actually held, without Mara ever being involved.
        result = _validate_propose_commitment(self.tarin, self.actor, {"commitment_type": self.TYPE})
        self.assertFalse(result.applied)
        self.assertIn("no proposer role", result.reason)

    def test_only_the_proposer_can_accept_it(self):
        _validate_propose_commitment(self.mara, self.actor, {"commitment_type": self.TYPE})
        result = _validate_accept_commitment(self.tarin, self.actor, {"commitment_type": self.TYPE})
        self.assertFalse(result.applied)
        self.assertEqual(self._carried_parcels(), [])

    def test_only_the_proposer_can_decline_it(self):
        _validate_propose_commitment(self.mara, self.actor, {"commitment_type": self.TYPE})
        result = _validate_decline_commitment(self.tarin, self.actor, {"commitment_type": self.TYPE})
        self.assertFalse(result.applied)


class ParcelDeliveryRumorWiringTests(TestCase):
    """
    docs/phase2e-word-gets-around-design.md: Mara's deliver_parcel
    proposer-side view is held at "open" until report_parcel_delivery
    actually tells her, even once the real commitment is fulfilled -
    and the one-time Mara reputation credit survives a reset/replay of
    the underlying commitment without being awarded twice.
    """

    TYPE = "deliver_parcel"

    def setUp(self):
        rooms = build_rooms()
        npcs = build_npcs()
        self.mara = npcs["mara_voss"]
        self.tarin = npcs["tarin_os"]
        self.veska = npcs["veska_renn"]
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=rooms["corner_cafe"]
        )

    def _deliver_to(self, holder):
        _validate_propose_commitment(self.mara, self.actor, {"commitment_type": self.TYPE})
        _validate_accept_commitment(self.mara, self.actor, {"commitment_type": self.TYPE})
        return _validate_accept_handoff(holder, self.actor, {"commitment_type": self.TYPE})

    def _mara_state(self):
        context = commitment_context_for("mara_voss", ["propose_commitment", "report_parcel_delivery"], self.actor)
        return context

    def test_mara_does_not_know_before_being_told(self):
        self._deliver_to(self.tarin)
        context = self._mara_state()
        self.assertIn("open", context)
        self.assertNotIn("fulfilled", context)

    def test_correct_report_succeeds_and_reveals_fulfillment(self):
        self._deliver_to(self.tarin)
        result = _validate_report_parcel_delivery(self.mara, self.actor, {"reported_recipient": "tarin"})
        self.assertTrue(result.applied)
        self.assertIn("fulfilled", self._mara_state())

    def test_correct_report_awards_reputation(self):
        self._deliver_to(self.tarin)
        self.assertEqual(get_reputation(self.actor, "mara_voss"), 0)
        _validate_report_parcel_delivery(self.mara, self.actor, {"reported_recipient": "tarin"})
        self.assertEqual(get_reputation(self.actor, "mara_voss"), 1)

    def test_report_naming_veska_when_tarin_actually_received_it_is_rejected(self):
        self._deliver_to(self.tarin)
        result = _validate_report_parcel_delivery(self.mara, self.actor, {"reported_recipient": "veska"})
        self.assertFalse(result.applied)
        self.assertEqual(get_reputation(self.actor, "mara_voss"), 0)
        self.assertIn("open", self._mara_state())

    def test_report_with_no_fulfilled_commitment_is_rejected(self):
        result = _validate_report_parcel_delivery(self.mara, self.actor, {"reported_recipient": "tarin"})
        self.assertFalse(result.applied)

    def test_only_mara_has_a_role_in_this_rumor(self):
        self._deliver_to(self.tarin)
        result = _validate_report_parcel_delivery(self.tarin, self.actor, {"reported_recipient": "tarin"})
        self.assertFalse(result.applied)

    def test_repeated_correct_report_does_not_double_credit(self):
        self._deliver_to(self.tarin)
        _validate_report_parcel_delivery(self.mara, self.actor, {"reported_recipient": "tarin"})
        result = _validate_report_parcel_delivery(self.mara, self.actor, {"reported_recipient": "tarin"})
        self.assertFalse(result.applied)
        self.assertEqual(get_reputation(self.actor, "mara_voss"), 1)

    def test_reputation_credited_only_once_across_multiple_commitment_instances(self):
        from world.commitments import reset_commitment

        self._deliver_to(self.tarin)
        _validate_report_parcel_delivery(self.mara, self.actor, {"reported_recipient": "tarin"})
        self.assertEqual(get_reputation(self.actor, "mara_voss"), 1)

        reset_commitment(self.actor, self.TYPE)
        self._deliver_to(self.veska)
        result = _validate_report_parcel_delivery(self.mara, self.actor, {"reported_recipient": "veska"})
        self.assertTrue(result.applied)  # the new instance can still be reported...
        self.assertEqual(get_reputation(self.actor, "mara_voss"), 1)  # ...but credit doesn't stack

    def test_informed_knowledge_is_per_commitment_instance(self):
        from world.commitments import reset_commitment

        self._deliver_to(self.tarin)
        _validate_report_parcel_delivery(self.mara, self.actor, {"reported_recipient": "tarin"})
        self.assertTrue(has_reputation_credit(self.actor))


class NoticeApprovalWiringTests(TestCase):
    """
    docs/phase3-unverified-notice-design.md: Tarin's claim about the
    posted notice gets genuinely confirmed or contradicted by Veska's
    independent inspection, mutual exclusion between verify/withdraw
    falls out of fulfill_commitment_with_precondition's existing
    STATUS_OPEN check, and Tarin's own view stays at "open" until a
    separate, validated report tells him which way it went.
    """

    TYPE = "unverified_notice"

    def setUp(self):
        rooms = build_rooms()
        npcs = build_npcs()
        self.tarin = npcs["tarin_os"]
        self.veska = npcs["veska_renn"]
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=rooms["maintenance_workshop"]
        )

    def _fulfill_discrepancy_report(self):
        _validate_propose_commitment(self.tarin, self.actor, {"commitment_type": "discrepancy_report"})
        _validate_accept_commitment(self.tarin, self.actor, {"commitment_type": "discrepancy_report"})
        _validate_report_commitment_outcome(self.veska, self.actor, {"commitment_type": "discrepancy_report"})
        _validate_report_commitment_outcome(self.tarin, self.actor, {"commitment_type": "discrepancy_report"})

    def _open_notice(self):
        # Only fulfill the prerequisite once - calling this twice in a
        # test (e.g. to open a second instance after a reset) must not
        # try to re-propose an already-fulfilled discrepancy_report.
        if get_fulfilled_commitment(self.actor, "discrepancy_report") is None:
            self._fulfill_discrepancy_report()
        _validate_propose_commitment(self.tarin, self.actor, {"commitment_type": self.TYPE})
        _validate_accept_commitment(self.tarin, self.actor, {"commitment_type": self.TYPE})

    def _tarin_state(self):
        return commitment_context_for("tarin_os", ["propose_commitment", "report_notice_outcome"], self.actor)

    def _veska_state(self):
        return commitment_context_for("veska_renn", ["verify_notice", "withdraw_notice"], self.actor)

    def test_propose_rejected_before_discrepancy_report_fulfilled(self):
        result = _validate_propose_commitment(self.tarin, self.actor, {"commitment_type": self.TYPE})
        self.assertFalse(result.applied)

    def test_verify_confirms_when_approval_mark_present(self):
        self._open_notice()
        result = _validate_verify_notice(self.veska, self.actor, {"confirmed": True})
        self.assertTrue(result.applied)
        commitment = get_fulfilled_commitment(self.actor, self.TYPE)
        self.assertEqual(get_notice_resolution(self.actor, commitment["commitment_id"]), RESOLUTION_VERIFIED)

    def test_verify_contradicts_when_approval_mark_missing(self):
        self._open_notice()
        set_approval_mark_present(self.actor, False)
        result = _validate_verify_notice(self.veska, self.actor, {"confirmed": True})
        self.assertFalse(result.applied)
        # The commitment stays open - the player can still ask for
        # withdrawal instead, a wrong/missing mark doesn't poison it.
        self.assertIn("open", self._tarin_state())

    def test_withdraw_succeeds_regardless_of_approval_mark(self):
        self._open_notice()
        set_approval_mark_present(self.actor, False)
        result = _validate_withdraw_notice(self.veska, self.actor, {"confirmed": True})
        self.assertTrue(result.applied)
        self.assertFalse(notice_displayed(self.actor))

    def test_verify_and_withdraw_are_mutually_exclusive(self):
        self._open_notice()
        verify = _validate_verify_notice(self.veska, self.actor, {"confirmed": True})
        self.assertTrue(verify.applied)

        withdraw = _validate_withdraw_notice(self.veska, self.actor, {"confirmed": True})
        self.assertFalse(withdraw.applied)
        self.assertTrue(notice_displayed(self.actor))  # the verified path's outcome stands

    def test_only_veska_has_a_holder_role(self):
        self._open_notice()
        result = _validate_verify_notice(self.tarin, self.actor, {"confirmed": True})
        self.assertFalse(result.applied)

    def test_tarin_does_not_know_the_resolution_before_being_told(self):
        self._open_notice()
        _validate_verify_notice(self.veska, self.actor, {"confirmed": True})
        # discrepancy_report's own line legitimately says "fulfilled"
        # (the scenario's prerequisite) - check the unverified_notice
        # line specifically, not the whole multi-scenario context.
        self.assertIn("'unverified_notice' commitment with this player (your side): open.", self._tarin_state())

    def test_correct_report_reveals_fulfillment(self):
        self._open_notice()
        _validate_verify_notice(self.veska, self.actor, {"confirmed": True})
        result = _validate_report_notice_outcome(self.tarin, self.actor, {"reported_resolution": "verified"})
        self.assertTrue(result.applied)
        self.assertIn(
            "'unverified_notice' commitment with this player (your side): fulfilled.", self._tarin_state()
        )

    def test_mismatched_report_is_rejected(self):
        self._open_notice()
        _validate_verify_notice(self.veska, self.actor, {"confirmed": True})
        result = _validate_report_notice_outcome(self.tarin, self.actor, {"reported_resolution": "withdrawn"})
        self.assertFalse(result.applied)
        self.assertIn("'unverified_notice' commitment with this player (your side): open.", self._tarin_state())

    def test_veska_sees_the_real_resolution_after_verifying(self):
        # Confirmed live (2026-10-14): without this, Veska's own state
        # line just said "fulfilled" with no indication of which
        # action actually settled it - she hallucinated "withdrawn"
        # when asked afterward, even though she's the one who
        # performed verify_notice. She must see the real fact,
        # unlike Tarin's deliberately-withheld-until-reported view.
        self._open_notice()
        _validate_verify_notice(self.veska, self.actor, {"confirmed": True})
        state = self._veska_state()
        self.assertIn("approval mark", state)
        self.assertNotIn("withdr", state)

    def test_veska_sees_the_real_resolution_after_withdrawing(self):
        self._open_notice()
        _validate_withdraw_notice(self.veska, self.actor, {"confirmed": True})
        state = self._veska_state()
        self.assertIn("withdr", state)
        self.assertNotIn("approval mark", state)

    def test_report_with_no_fulfilled_commitment_is_rejected(self):
        result = _validate_report_notice_outcome(self.tarin, self.actor, {"reported_resolution": "verified"})
        self.assertFalse(result.applied)

    def test_repeated_correct_report_is_rejected(self):
        self._open_notice()
        _validate_withdraw_notice(self.veska, self.actor, {"confirmed": True})
        _validate_report_notice_outcome(self.tarin, self.actor, {"reported_resolution": "withdrawn"})
        result = _validate_report_notice_outcome(self.tarin, self.actor, {"reported_resolution": "withdrawn"})
        self.assertFalse(result.applied)

    def test_informed_state_is_per_commitment_instance(self):
        from world.commitments import reset_commitment

        self._open_notice()
        _validate_withdraw_notice(self.veska, self.actor, {"confirmed": True})
        _validate_report_notice_outcome(self.tarin, self.actor, {"reported_resolution": "withdrawn"})

        reset_commitment(self.actor, self.TYPE)
        self._open_notice()
        result = _validate_verify_notice(self.veska, self.actor, {"confirmed": True})
        self.assertTrue(result.applied)
        # A fresh instance - not yet reported - must not read as already
        # informed just because an earlier, now-cleared instance was.
        self.assertIn("'unverified_notice' commitment with this player (your side): open.", self._tarin_state())


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
        result = validate_and_apply(self.mara, self.actor, "remember_fact", {"fact": "grew up near the Docks"})
        self.assertTrue(result.applied)
        from world.npc_memory import memory_context_for

        self.assertIn("grew up near the Docks", memory_context_for("mara_voss", self.actor))

    def test_narration_is_empty_by_default(self):
        result = validate_and_apply(self.mara, self.actor, "remember_fact", {"fact": "likes cold drinks"})
        self.assertEqual(result.narration, "")

    def test_narration_shows_the_fact_when_debug_enabled(self):
        self.actor.attributes.add("memory_debug_enabled", True)
        result = validate_and_apply(self.mara, self.actor, "remember_fact", {"fact": "likes cold drinks"})
        self.assertIn("likes cold drinks", result.narration)
        self.assertIn("Mara Voss", result.narration)

    def test_debug_narration_omitted_for_a_dropped_call(self):
        self.actor.attributes.add("memory_debug_enabled", True)
        result = validate_and_apply(self.mara, self.actor, "remember_fact", {"fact": ""})
        self.assertFalse(result.applied)
        self.assertEqual(result.narration, "")

    def test_flagged_fact_dropped_through_full_pipeline(self):
        result = validate_and_apply(
            self.mara, self.actor, "remember_fact", {"fact": "As an AI, I don't have personal experiences."}
        )
        self.assertFalse(result.applied)

    def test_remember_fact_schema_requires_an_argument(self):
        schema = ACTION_SCHEMAS["remember_fact"]["function"]
        self.assertTrue(schema["parameters"]["required"])


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
        self.mara = npcs["mara_voss"]
        self.iri = npcs["iri_vael"]
        self.tarin = npcs["tarin_os"]
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=rooms["corner_cafe"]
        )

    def _accept(self):
        _validate_propose_commitment(self.mara, self.actor, {"commitment_type": self.TYPE})
        _validate_accept_commitment(self.mara, self.actor, {"commitment_type": self.TYPE})

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

    def test_mara_closes_it_after_genuine_acknowledgment(self):
        from world.noticeboard import get_or_create_expected_revision

        self._accept()
        expected = get_or_create_expected_revision(self.actor)
        _validate_verify_revision_report(
            self.iri, self.actor, {"commitment_type": self.TYPE, "reported_revision": expected}
        )
        result = _validate_report_commitment_outcome(self.mara, self.actor, {"commitment_type": self.TYPE})
        self.assertTrue(result.applied)

    def test_mara_cannot_close_it_without_acknowledgment(self):
        self._accept()
        result = _validate_report_commitment_outcome(self.mara, self.actor, {"commitment_type": self.TYPE})
        self.assertFalse(result.applied)

    def test_verify_revision_report_schema_requires_arguments(self):
        schema = ACTION_SCHEMAS["verify_revision_report"]["function"]
        self.assertEqual(set(schema["parameters"]["required"]), {"commitment_type", "reported_revision"})
