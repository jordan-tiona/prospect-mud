"""
Tests for the generic commitment lifecycle (world/commitments.py).
This is step 1 of phase 2B (docs/phase2b-records-discrepancy-
proposal.md): the storage and lifecycle only, with no NPCs or
actions.py wiring yet - those arrive in later steps and get their own
tests against validate_and_apply.

Run with:
    evennia test world
"""

from django.test import TestCase
from evennia import create_object

from world.commitments import (
    COMMITMENT_ACTIONS,
    accept_commitment,
    commitment_context_for,
    decline_commitment,
    fulfill_commitment,
    get_state_summary,
    hint_pose_for,
    propose_commitment,
    record_acknowledgment,
    reset_commitment,
)

COMMITMENT_TYPE = "discrepancy_report"
HOLDER = "tarin_os"
CLERK = "veska_renn"


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
        # there's something open to report.
        propose_commitment(self.actor, COMMITMENT_TYPE)
        context = commitment_context_for(CLERK, list(COMMITMENT_ACTIONS), self.actor)
        self.assertIn("no open commitment to report", context)
        self.assertNotIn("offered", context)

    def test_context_for_clerk_reveals_open_unacknowledged(self):
        propose_commitment(self.actor, COMMITMENT_TYPE)
        accept_commitment(self.actor, COMMITMENT_TYPE)
        context = commitment_context_for(CLERK, list(COMMITMENT_ACTIONS), self.actor)
        self.assertIn("open, not yet acknowledged", context)

    def test_context_for_unrelated_npc_is_none(self):
        propose_commitment(self.actor, COMMITMENT_TYPE)
        self.assertIsNone(commitment_context_for("mara_voss", list(COMMITMENT_ACTIONS), self.actor))

    # -- discoverability hint pose ----------------------------------------

    def test_hint_pose_shown_before_any_offer(self):
        self.assertEqual(hint_pose_for(HOLDER, self.actor), "frowning over a shipment manifest")

    def test_hint_pose_gone_once_offered(self):
        propose_commitment(self.actor, COMMITMENT_TYPE)
        self.assertIsNone(hint_pose_for(HOLDER, self.actor))

    def test_hint_pose_gone_after_decline(self):
        propose_commitment(self.actor, COMMITMENT_TYPE)
        decline_commitment(self.actor, COMMITMENT_TYPE)
        # Declining clears the offer flag, putting the state back to
        # "not offered" - deliberately still shows the hint again, the
        # same as before any offer, since nothing prevents re-offering.
        self.assertEqual(hint_pose_for(HOLDER, self.actor), "frowning over a shipment manifest")

    def test_hint_pose_none_for_npc_with_no_holder_role(self):
        self.assertIsNone(hint_pose_for(CLERK, self.actor))
        self.assertIsNone(hint_pose_for("mara_voss", self.actor))

    def test_hint_pose_is_per_player(self):
        other = create_object("typeclasses.characters.Character", key="Other")
        propose_commitment(self.actor, COMMITMENT_TYPE)
        self.assertIsNone(hint_pose_for(HOLDER, self.actor))
        self.assertEqual(hint_pose_for(HOLDER, other), "frowning over a shipment manifest")
