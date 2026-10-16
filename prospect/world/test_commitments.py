"""
Tests for the generic commitment lifecycle (world/commitments.py).
This is step 1 of phase 2B (docs/phase2b-records-discrepancy-
proposal.md): the storage and lifecycle only, with no NPCs or
actions.py wiring yet - those arrive in later steps and get their own
tests against validate_and_apply.

Run with:
    evennia test world
"""

from unittest.mock import patch

from django.test import TestCase
from evennia import create_object

from world.commitments import (
    COMMITMENT_ACTIONS,
    SCENARIOS,
    ScenarioConfig,
    accept_commitment,
    commitment_context_for,
    decline_commitment,
    fulfill_commitment,
    fulfill_commitment_with_precondition,
    get_open_commitment_id,
    get_state_summary,
    has_been_declined,
    hint_pose_for,
    propose_commitment,
    record_acknowledgment,
    record_acknowledgment_with_precondition,
    reset_commitment,
)

# CommitmentLifecycleTests below uses verify_display_revision purely
# as an example holder+clerk scenario to test the generic lifecycle,
# not a test of that scenario's own content - same reasoning as
# world/test_actions.py's CommitmentActionWiringTests. (Originally
# used discrepancy_report; removed 2026-10-16, see CLAUDE.md's "One
# quest offer per NPC".) Mara has no other hint-eligible scenario
# (deliver_parcel's holder_hint_pose is unset for her), so these tests
# don't need any hunt_skitters-style isolation dance the way the
# original discrepancy_report fixture did once hunt_skitters joined
# Tarin's roster.
COMMITMENT_TYPE = "verify_display_revision"
HOLDER = "mara_voss"
CLERK = "iri_vael"

# docs/phase2c-misdelivered-parcel-proposal.md's parcel scenario,
# redesigned 2026-10-13: one commitment type, two valid holders -
# whichever of Tarin or Veska the player reaches first.
PARCEL_TYPE = "deliver_parcel"
PARCEL_HOLDER_A = "tarin_os"
PARCEL_HOLDER_B = "veska_renn"


class CommitmentLifecycleTests(TestCase):
    def setUp(self):
        self.actor = create_object("typeclasses.characters.Character", key="Tester")
        self.other = create_object("typeclasses.characters.Character", key="Other")

    # -- propose -----------------------------------------------------

    def test_propose_unknown_type_dropped(self):
        result = propose_commitment(self.actor, "not_a_real_type")
        self.assertFalse(result.ok)

    def test_propose_then_state_is_offered(self):
        result = propose_commitment(self.actor, COMMITMENT_TYPE)
        self.assertTrue(result.ok)
        self.assertEqual(get_state_summary(self.actor, COMMITMENT_TYPE), "offered, awaiting the player's answer")

    def test_propose_twice_is_dropped(self):
        propose_commitment(self.actor, COMMITMENT_TYPE)
        second = propose_commitment(self.actor, COMMITMENT_TYPE)
        self.assertFalse(second.ok)

    def test_propose_while_open_is_dropped(self):
        propose_commitment(self.actor, COMMITMENT_TYPE)
        accept_commitment(self.actor, COMMITMENT_TYPE)
        result = propose_commitment(self.actor, COMMITMENT_TYPE)
        self.assertFalse(result.ok)

    # -- accept / decline ---------------------------------------------

    def test_accept_without_offer_dropped(self):
        result = accept_commitment(self.actor, COMMITMENT_TYPE)
        self.assertFalse(result.ok)
        self.assertEqual(get_state_summary(self.actor, COMMITMENT_TYPE), "not offered")

    def test_accept_creates_open_commitment(self):
        propose_commitment(self.actor, COMMITMENT_TYPE)
        result = accept_commitment(self.actor, COMMITMENT_TYPE)
        self.assertTrue(result.ok)
        self.assertTrue(result.commitment_id)
        self.assertEqual(get_state_summary(self.actor, COMMITMENT_TYPE), "open, not yet acknowledged")

    def test_decline_without_offer_dropped(self):
        result = decline_commitment(self.actor, COMMITMENT_TYPE)
        self.assertFalse(result.ok)

    def test_decline_clears_offer_without_creating_commitment(self):
        propose_commitment(self.actor, COMMITMENT_TYPE)
        result = decline_commitment(self.actor, COMMITMENT_TYPE)
        self.assertTrue(result.ok)
        self.assertEqual(get_state_summary(self.actor, COMMITMENT_TYPE), "not offered")

    def test_decline_then_reoffer_allowed(self):
        propose_commitment(self.actor, COMMITMENT_TYPE)
        decline_commitment(self.actor, COMMITMENT_TYPE)
        result = propose_commitment(self.actor, COMMITMENT_TYPE)
        self.assertTrue(result.ok)

    # -- acknowledgment (clerk role) ------------------------------------

    def test_acknowledge_before_accept_dropped(self):
        result = record_acknowledgment(self.actor, COMMITMENT_TYPE, CLERK)
        self.assertFalse(result.ok)

    def test_acknowledge_by_wrong_clerk_dropped(self):
        propose_commitment(self.actor, COMMITMENT_TYPE)
        accept_commitment(self.actor, COMMITMENT_TYPE)
        result = record_acknowledgment(self.actor, COMMITMENT_TYPE, "some_other_npc")
        self.assertFalse(result.ok)

    def test_acknowledge_valid(self):
        propose_commitment(self.actor, COMMITMENT_TYPE)
        accept_commitment(self.actor, COMMITMENT_TYPE)
        result = record_acknowledgment(self.actor, COMMITMENT_TYPE, CLERK)
        self.assertTrue(result.ok)
        self.assertEqual(
            get_state_summary(self.actor, COMMITMENT_TYPE), "open, acknowledged by the records clerk"
        )

    def test_acknowledge_twice_dropped(self):
        propose_commitment(self.actor, COMMITMENT_TYPE)
        accept_commitment(self.actor, COMMITMENT_TYPE)
        record_acknowledgment(self.actor, COMMITMENT_TYPE, CLERK)
        second = record_acknowledgment(self.actor, COMMITMENT_TYPE, CLERK)
        self.assertFalse(second.ok)

    # -- fulfillment (holder role) --------------------------------------

    def test_fulfill_without_acknowledgment_dropped(self):
        propose_commitment(self.actor, COMMITMENT_TYPE)
        accept_commitment(self.actor, COMMITMENT_TYPE)
        result = fulfill_commitment(self.actor, COMMITMENT_TYPE, HOLDER)
        self.assertFalse(result.ok)

    def test_fulfill_by_wrong_holder_dropped(self):
        propose_commitment(self.actor, COMMITMENT_TYPE)
        accept_commitment(self.actor, COMMITMENT_TYPE)
        record_acknowledgment(self.actor, COMMITMENT_TYPE, CLERK)
        result = fulfill_commitment(self.actor, COMMITMENT_TYPE, "some_other_npc")
        self.assertFalse(result.ok)

    def test_fulfill_valid(self):
        propose_commitment(self.actor, COMMITMENT_TYPE)
        accept_commitment(self.actor, COMMITMENT_TYPE)
        record_acknowledgment(self.actor, COMMITMENT_TYPE, CLERK)
        result = fulfill_commitment(self.actor, COMMITMENT_TYPE, HOLDER)
        self.assertTrue(result.ok)
        self.assertEqual(get_state_summary(self.actor, COMMITMENT_TYPE), "fulfilled")

    def test_fulfill_twice_dropped(self):
        propose_commitment(self.actor, COMMITMENT_TYPE)
        accept_commitment(self.actor, COMMITMENT_TYPE)
        record_acknowledgment(self.actor, COMMITMENT_TYPE, CLERK)
        fulfill_commitment(self.actor, COMMITMENT_TYPE, HOLDER)
        second = fulfill_commitment(self.actor, COMMITMENT_TYPE, HOLDER)
        self.assertFalse(second.ok)

    # -- another player's commitment is a separate instance ---------------

    def test_another_players_acknowledgment_does_not_fulfill_this_one(self):
        # self.other accepts and gets acknowledged...
        propose_commitment(self.other, COMMITMENT_TYPE)
        accept_commitment(self.other, COMMITMENT_TYPE)
        record_acknowledgment(self.other, COMMITMENT_TYPE, CLERK)
        # ...self.actor separately accepts but was never acknowledged.
        propose_commitment(self.actor, COMMITMENT_TYPE)
        accept_commitment(self.actor, COMMITMENT_TYPE)
        result = fulfill_commitment(self.actor, COMMITMENT_TYPE, HOLDER)
        self.assertFalse(result.ok)

    # -- reset -------------------------------------------------------

    def test_reset_clears_open_commitment(self):
        propose_commitment(self.actor, COMMITMENT_TYPE)
        accept_commitment(self.actor, COMMITMENT_TYPE)
        record_acknowledgment(self.actor, COMMITMENT_TYPE, CLERK)
        snapshot = reset_commitment(self.actor, COMMITMENT_TYPE)
        self.assertEqual(snapshot["previous_statuses"], ["open"])
        self.assertEqual(get_state_summary(self.actor, COMMITMENT_TYPE), "not offered")

    def test_reset_then_old_acknowledgment_cannot_fulfill_new_instance(self):
        propose_commitment(self.actor, COMMITMENT_TYPE)
        accept_commitment(self.actor, COMMITMENT_TYPE)
        record_acknowledgment(self.actor, COMMITMENT_TYPE, CLERK)
        reset_commitment(self.actor, COMMITMENT_TYPE)

        # Start a brand-new instance after the reset; it has never
        # been acknowledged, even though the player was acknowledged
        # before under the old (now-removed) commitment_id.
        propose_commitment(self.actor, COMMITMENT_TYPE)
        accept_commitment(self.actor, COMMITMENT_TYPE)
        result = fulfill_commitment(self.actor, COMMITMENT_TYPE, HOLDER)
        self.assertFalse(result.ok)

    def test_reset_reports_previous_offer(self):
        propose_commitment(self.actor, COMMITMENT_TYPE)
        snapshot = reset_commitment(self.actor, COMMITMENT_TYPE)
        self.assertTrue(snapshot["had_offer"])

    # -- prompt-scoped context -------------------------------------------

    def test_context_none_for_npc_with_no_commitment_actions(self):
        self.assertIsNone(commitment_context_for("mara_voss", ["serve_drink"], self.actor))

    def test_context_for_holder_reveals_offer_state(self):
        propose_commitment(self.actor, COMMITMENT_TYPE)
        context = commitment_context_for(HOLDER, list(COMMITMENT_ACTIONS), self.actor)
        self.assertIn("offered, awaiting the player's answer", context)

    def test_context_for_clerk_hides_offer_state(self):
        # An offer is pending but nothing has been accepted yet - the
        # clerk has no legitimate reason to know that, only whether
        # there's something open to report. (Iri is also a holder for
        # a different, unrelated scenario of her own, tend_planting_bed -
        # checking the exact verify_display_revision line, not the
        # whole string, keeps this test from breaking every time
        # another scenario is added.)
        propose_commitment(self.actor, COMMITMENT_TYPE)
        context = commitment_context_for(CLERK, list(COMMITMENT_ACTIONS), self.actor)
        self.assertIn(
            "'verify_display_revision' commitment with this player: no open commitment to report", context
        )

    def test_context_for_clerk_reveals_open_unacknowledged(self):
        propose_commitment(self.actor, COMMITMENT_TYPE)
        accept_commitment(self.actor, COMMITMENT_TYPE)
        context = commitment_context_for(CLERK, list(COMMITMENT_ACTIONS), self.actor)
        self.assertIn("open, not yet acknowledged", context)

    def test_context_for_unrelated_npc_is_none(self):
        # Every real NPC now has a role in *some* authored scenario
        # (Mara, Tarin, Veska, Iri) - a genuinely fake npc_id is the
        # only reliably unrelated case left.
        propose_commitment(self.actor, COMMITMENT_TYPE)
        self.assertIsNone(commitment_context_for("nobody_npc", list(COMMITMENT_ACTIONS), self.actor))

    # -- discoverability hint pose ----------------------------------------
    # Mara has no other hint-eligible scenario (deliver_parcel's own
    # holder_hint_pose is unset for her), so unlike the original
    # discrepancy_report/hunt_skitters fixture these need no isolation
    # dance at all. The priority-tie mechanism itself (when an NPC
    # *does* have two hint-eligible scenarios) is tested independently
    # with synthetic scenarios in OneQuestAtATimeTests below.

    def test_hint_pose_shown_before_any_offer(self):
        self.assertEqual(hint_pose_for(HOLDER, self.actor), "glancing at the café's information display")

    def test_hint_pose_gone_once_offered(self):
        propose_commitment(self.actor, COMMITMENT_TYPE)
        self.assertIsNone(hint_pose_for(HOLDER, self.actor))

    def test_hint_pose_gone_after_decline(self):
        propose_commitment(self.actor, COMMITMENT_TYPE)
        decline_commitment(self.actor, COMMITMENT_TYPE)
        # Declining clears the offer flag, putting the state back to
        # "not offered" - deliberately still shows the hint again, the
        # same as before any offer, since nothing prevents re-offering.
        self.assertEqual(hint_pose_for(HOLDER, self.actor), "glancing at the café's information display")

    def test_hint_pose_none_for_npc_with_no_holder_role(self):
        # Not CLERK (iri_vael) - she's also the holder of her own,
        # unrelated tend_planting_bed hint, so she'd legitimately show
        # one here. veska_renn currently holds no hint-eligible role
        # at all (her only commitment role, deliver_parcel's alt-
        # holder, has no holder_hint_pose set for her).
        self.assertIsNone(hint_pose_for("veska_renn", self.actor))
        self.assertIsNone(hint_pose_for("nobody_npc", self.actor))

    def test_hint_pose_is_per_player(self):
        other = create_object("typeclasses.characters.Character", key="Other")
        propose_commitment(self.actor, COMMITMENT_TYPE)
        self.assertIsNone(hint_pose_for(HOLDER, self.actor))
        self.assertEqual(hint_pose_for(HOLDER, other), "glancing at the café's information display")


class MultiHolderFulfillmentTests(TestCase):
    """
    docs/phase2c-misdelivered-parcel-proposal.md's parcel scenario,
    redesigned 2026-10-13: one commitment type, two valid holders -
    whichever of Tarin or Veska the player actually reaches first
    fulfills it, and the other's later attempt must find it already
    closed. No separate cross-holder exclusion logic exists; this is
    the open-commitment check (shared with every other scenario)
    doing double duty.
    """

    def setUp(self):
        room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.actor = create_object("typeclasses.characters.Character", key="Tester", location=room)

    def test_either_holder_can_fulfill(self):
        propose_commitment(self.actor, PARCEL_TYPE)
        accept_commitment(self.actor, PARCEL_TYPE)
        result = fulfill_commitment_with_precondition(self.actor, PARCEL_TYPE, PARCEL_HOLDER_B, True)
        self.assertTrue(result.ok)

    def test_wrong_holder_role_dropped(self):
        propose_commitment(self.actor, PARCEL_TYPE)
        accept_commitment(self.actor, PARCEL_TYPE)
        result = fulfill_commitment_with_precondition(self.actor, PARCEL_TYPE, "mara_voss", True)
        self.assertFalse(result.ok)

    def test_no_open_commitment_dropped(self):
        result = fulfill_commitment_with_precondition(self.actor, PARCEL_TYPE, PARCEL_HOLDER_A, True)
        self.assertFalse(result.ok)

    def test_false_precondition_dropped_even_with_open_commitment(self):
        propose_commitment(self.actor, PARCEL_TYPE)
        accept_commitment(self.actor, PARCEL_TYPE)
        result = fulfill_commitment_with_precondition(self.actor, PARCEL_TYPE, PARCEL_HOLDER_A, False)
        self.assertFalse(result.ok)
        self.assertEqual(get_state_summary(self.actor, PARCEL_TYPE), "open")

    def test_true_precondition_fulfills(self):
        propose_commitment(self.actor, PARCEL_TYPE)
        accept_commitment(self.actor, PARCEL_TYPE)
        commitment_id = get_open_commitment_id(self.actor, PARCEL_TYPE)
        result = fulfill_commitment_with_precondition(self.actor, PARCEL_TYPE, PARCEL_HOLDER_A, True)
        self.assertTrue(result.ok)
        self.assertEqual(result.commitment_id, commitment_id)
        self.assertEqual(get_state_summary(self.actor, PARCEL_TYPE), "fulfilled")

    def test_the_other_holder_cannot_also_fulfill_it(self):
        # The exact bug this redesign fixes: once one NPC completes
        # it, the commitment is closed - the other NPC's attempt
        # (even with a theoretically-valid precondition) must fail,
        # without needing any destination to have been chosen earlier.
        propose_commitment(self.actor, PARCEL_TYPE)
        accept_commitment(self.actor, PARCEL_TYPE)
        fulfill_commitment_with_precondition(self.actor, PARCEL_TYPE, PARCEL_HOLDER_A, True)

        result = fulfill_commitment_with_precondition(self.actor, PARCEL_TYPE, PARCEL_HOLDER_B, True)
        self.assertFalse(result.ok)

    def test_get_open_commitment_id_none_when_nothing_open(self):
        self.assertIsNone(get_open_commitment_id(self.actor, PARCEL_TYPE))


class RecordAcknowledgmentWithPreconditionTests(TestCase):
    """
    docs/phase2-quest-prototype-design.md §14's "genuine corroboration":
    unlike record_acknowledgment's unconditional "they brought it to
    me, that's enough," this gates on an engine-checked boolean the
    caller supplies.
    """

    TYPE = "verify_display_revision"
    CLERK = "iri_vael"

    def setUp(self):
        room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.actor = create_object("typeclasses.characters.Character", key="Tester", location=room)

    def test_wrong_clerk_role_dropped(self):
        propose_commitment(self.actor, self.TYPE)
        accept_commitment(self.actor, self.TYPE)
        result = record_acknowledgment_with_precondition(self.actor, self.TYPE, "mara_voss", True)
        self.assertFalse(result.ok)

    def test_no_open_commitment_dropped(self):
        result = record_acknowledgment_with_precondition(self.actor, self.TYPE, self.CLERK, True)
        self.assertFalse(result.ok)

    def test_false_precondition_dropped_and_commitment_stays_open(self):
        propose_commitment(self.actor, self.TYPE)
        accept_commitment(self.actor, self.TYPE)
        result = record_acknowledgment_with_precondition(self.actor, self.TYPE, self.CLERK, False)
        self.assertFalse(result.ok)
        self.assertEqual(get_state_summary(self.actor, self.TYPE), "open, not yet acknowledged")

    def test_true_precondition_acknowledges(self):
        propose_commitment(self.actor, self.TYPE)
        accept_commitment(self.actor, self.TYPE)
        result = record_acknowledgment_with_precondition(self.actor, self.TYPE, self.CLERK, True)
        self.assertTrue(result.ok)
        self.assertEqual(get_state_summary(self.actor, self.TYPE), "open, acknowledged by the records clerk")

    def test_retry_after_a_wrong_report_can_still_succeed(self):
        # The exact invariant the proposal calls out: a wrong guess
        # must never permanently poison the commitment.
        propose_commitment(self.actor, self.TYPE)
        accept_commitment(self.actor, self.TYPE)
        record_acknowledgment_with_precondition(self.actor, self.TYPE, self.CLERK, False)
        result = record_acknowledgment_with_precondition(self.actor, self.TYPE, self.CLERK, True)
        self.assertTrue(result.ok)

    def test_already_acknowledged_is_dropped(self):
        propose_commitment(self.actor, self.TYPE)
        accept_commitment(self.actor, self.TYPE)
        record_acknowledgment_with_precondition(self.actor, self.TYPE, self.CLERK, True)
        result = record_acknowledgment_with_precondition(self.actor, self.TYPE, self.CLERK, True)
        self.assertFalse(result.ok)

    def test_mara_can_still_fulfill_after_genuine_acknowledgment(self):
        # fulfill_commitment (the existing, unconditional holder check)
        # must keep working unchanged against an ack created by the
        # new precondition-gated path - same ack shape either way.
        propose_commitment(self.actor, self.TYPE)
        accept_commitment(self.actor, self.TYPE)
        record_acknowledgment_with_precondition(self.actor, self.TYPE, self.CLERK, True)
        result = fulfill_commitment(self.actor, self.TYPE, "mara_voss")
        self.assertTrue(result.ok)




# Synthetic scenarios isolated from the real roster (SCENARIOS), so
# these tests exercise _blocking_scenario_for_proposal's mechanism
# directly rather than depending on real quests' own side effects
# (hunt_skitters' kill count, discrepancy_report's clerk step, etc.) -
# same reasoning MultiHolderFulfillmentTests already uses a dedicated
# npc_id for. Both share a holder/proposer NPC that doesn't exist for
# real, so nothing here can collide with any other test's state.
_FAKE_NPC = "fake_test_npc"
_FAKE_MANDATORY = ScenarioConfig(
    commitment_type="fake_mandatory",
    holder_npc_id=_FAKE_NPC,
    hint_priority=10,
    mandatory=True,
)
_FAKE_ORDINARY = ScenarioConfig(
    commitment_type="fake_ordinary",
    holder_npc_id=_FAKE_NPC,
    hint_priority=0,
    mandatory=False,
)


class OneQuestAtATimeTests(TestCase):
    """
    2026-10-16, project owner's call: an NPC can be involved in many
    scenarios but should only ever have one actually offerable right
    now. docs/playtest-quest3-skitters-design.md's live-eval finding
    is what motivated this; the mechanism itself
    (world.commitments._blocking_scenario_for_proposal) is generic,
    tested here independent of any real scenario's content.
    """

    def setUp(self):
        room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=room
        )
        patcher = patch.dict(
            SCENARIOS, {"fake_mandatory": _FAKE_MANDATORY, "fake_ordinary": _FAKE_ORDINARY}
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_mandatory_blocks_ordinary_while_both_not_offered(self):
        result = propose_commitment(self.actor, "fake_ordinary")
        self.assertFalse(result.ok)
        self.assertEqual(get_state_summary(self.actor, "fake_ordinary"), "not offered")

    def test_mandatory_can_itself_be_proposed(self):
        result = propose_commitment(self.actor, "fake_mandatory")
        self.assertTrue(result.ok)

    def test_declining_mandatory_does_not_release_the_block(self):
        propose_commitment(self.actor, "fake_mandatory")
        decline_commitment(self.actor, "fake_mandatory")
        self.assertTrue(has_been_declined(self.actor, "fake_mandatory"))
        result = propose_commitment(self.actor, "fake_ordinary")
        self.assertFalse(result.ok)

    def test_fulfilling_mandatory_releases_the_block(self):
        propose_commitment(self.actor, "fake_mandatory")
        accept_commitment(self.actor, "fake_mandatory")
        fulfill_commitment_with_precondition(self.actor, "fake_mandatory", _FAKE_NPC, True)
        result = propose_commitment(self.actor, "fake_ordinary")
        self.assertTrue(result.ok)

    def test_an_active_offer_blocks_a_different_proposal_regardless_of_priority(self):
        # fake_ordinary is offered (active, awaiting an answer) -
        # fake_mandatory can't be newly proposed either, even though
        # it outranks fake_ordinary by priority: something already in
        # progress blocks everything else from the same NPC.
        propose_commitment(self.actor, "fake_mandatory")
        accept_commitment(self.actor, "fake_mandatory")
        fulfill_commitment_with_precondition(self.actor, "fake_mandatory", _FAKE_NPC, True)
        propose_commitment(self.actor, "fake_ordinary")
        result = propose_commitment(self.actor, "fake_mandatory")
        self.assertFalse(result.ok)

    def test_declining_ordinary_exempts_it_from_future_priority_contention(self):
        # Directly exercises the exemption clause itself, bypassing
        # the real blocking order (fake_mandatory would otherwise have
        # to be dealt with first) - this confirms a *declined* ordinary
        # scenario stops competing for priority at all afterward, not
        # just that it happens to succeed once nothing else is pending.
        offers = self.actor.attributes.get("commitment_offers", default={})
        offers["fake_ordinary"] = True
        self.actor.attributes.add("commitment_offers", offers)
        decline_commitment(self.actor, "fake_ordinary")
        self.assertTrue(has_been_declined(self.actor, "fake_ordinary"))

        result = propose_commitment(self.actor, "fake_ordinary")
        self.assertTrue(result.ok, "a declined ordinary scenario must stay exempt, not re-blocked")

    def test_reset_clears_the_decline_history(self):
        propose_commitment(self.actor, "fake_mandatory")
        decline_commitment(self.actor, "fake_mandatory")
        snapshot = reset_commitment(self.actor, "fake_mandatory")
        self.assertTrue(snapshot["had_declined"])
        self.assertFalse(has_been_declined(self.actor, "fake_mandatory"))
