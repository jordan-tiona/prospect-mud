"""
Tests for the "unverified_notice" scenario's per-player approval-mark
and resolution state (world/notice_approval.py),
docs/phase3-unverified-notice-design.md.

Run with:
    evennia test world
"""

from django.test import TestCase
from evennia import create_object

from world.commitments import (
    accept_commitment,
    fulfill_commitment,
    fulfill_commitment_with_precondition,
    get_fulfilled_commitment,
    propose_commitment,
    record_acknowledgment,
)
from world.notice_approval import (
    RESOLUTION_VERIFIED,
    RESOLUTION_WITHDRAWN,
    approval_mark_present,
    get_resolution,
    is_informed_of,
    mark_informed,
    notice_displayed,
    project_tarin_notice_knowledge,
    project_veska_notice_knowledge,
    record_resolution,
    reset_notice,
    set_approval_mark_present,
)


def _fulfill_discrepancy_report(actor) -> None:
    propose_commitment(actor, "discrepancy_report")
    accept_commitment(actor, "discrepancy_report")
    record_acknowledgment(actor, "discrepancy_report", "veska_renn")
    fulfill_commitment(actor, "discrepancy_report", "tarin_os")


class NoticeApprovalStateTests(TestCase):
    def setUp(self):
        room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.actor = create_object("typeclasses.characters.Character", key="Tester", location=room)

    def test_approval_mark_defaults_true(self):
        self.assertTrue(approval_mark_present(self.actor))

    def test_approval_mark_is_stable_once_generated(self):
        first = approval_mark_present(self.actor)
        self.assertEqual(approval_mark_present(self.actor), first)

    def test_approval_mark_override_for_fixtures(self):
        set_approval_mark_present(self.actor, False)
        self.assertFalse(approval_mark_present(self.actor))

    def test_approval_mark_is_per_player(self):
        other = create_object("typeclasses.characters.Character", key="Other")
        set_approval_mark_present(self.actor, False)
        self.assertFalse(approval_mark_present(self.actor))
        self.assertTrue(approval_mark_present(other))

    def test_no_resolution_by_default(self):
        self.assertIsNone(get_resolution(self.actor, "some-id"))

    def test_record_resolution_verified_keeps_notice_displayed(self):
        record_resolution(self.actor, "id-a", RESOLUTION_VERIFIED)
        self.assertEqual(get_resolution(self.actor, "id-a"), RESOLUTION_VERIFIED)
        self.assertTrue(notice_displayed(self.actor))

    def test_record_resolution_withdrawn_hides_notice(self):
        record_resolution(self.actor, "id-a", RESOLUTION_WITHDRAWN)
        self.assertEqual(get_resolution(self.actor, "id-a"), RESOLUTION_WITHDRAWN)
        self.assertFalse(notice_displayed(self.actor))

    def test_not_informed_by_default(self):
        self.assertFalse(is_informed_of(self.actor, "id-a"))

    def test_mark_informed_is_per_commitment_id_and_idempotent(self):
        mark_informed(self.actor, "id-a")
        mark_informed(self.actor, "id-a")
        self.assertTrue(is_informed_of(self.actor, "id-a"))
        self.assertFalse(is_informed_of(self.actor, "id-b"))

    def test_reset_clears_everything(self):
        set_approval_mark_present(self.actor, False)
        record_resolution(self.actor, "id-a", RESOLUTION_WITHDRAWN)
        mark_informed(self.actor, "id-a")
        snapshot = reset_notice(self.actor)
        self.assertFalse(snapshot["previous_approval_mark_present"])
        self.assertEqual(snapshot["previous_resolutions"], {"id-a": RESOLUTION_WITHDRAWN})
        self.assertFalse(snapshot["previous_notice_displayed"])
        self.assertEqual(snapshot["previous_informed_commitment_ids"], ["id-a"])

        self.assertTrue(approval_mark_present(self.actor))
        self.assertIsNone(get_resolution(self.actor, "id-a"))
        self.assertTrue(notice_displayed(self.actor))
        self.assertFalse(is_informed_of(self.actor, "id-a"))

    def test_reset_with_nothing_set_is_a_no_op(self):
        snapshot = reset_notice(self.actor)
        self.assertIsNone(snapshot["previous_approval_mark_present"])
        self.assertEqual(snapshot["previous_resolutions"], {})
        self.assertTrue(snapshot["previous_notice_displayed"])
        self.assertEqual(snapshot["previous_informed_commitment_ids"], [])


class ProjectTarinNoticeKnowledgeTests(TestCase):
    def setUp(self):
        room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.actor = create_object("typeclasses.characters.Character", key="Tester", location=room)
        _fulfill_discrepancy_report(self.actor)

    def _fulfill_notice(self, resolution: str):
        propose_commitment(self.actor, "unverified_notice")
        accept_commitment(self.actor, "unverified_notice")
        # Both real paths (verify succeeding, or withdraw) leave the
        # commitment fulfilled - only verify_notice's own precondition
        # is the approval mark; this helper isn't exercising that
        # validator, just setting up a fulfilled instance to test the
        # projector/informed-state against.
        result = fulfill_commitment_with_precondition(self.actor, "unverified_notice", "veska_renn", True)
        record_resolution(self.actor, result.commitment_id, resolution)
        return result

    def test_non_fulfilled_states_pass_through_unchanged(self):
        for state in ("not offered", "offered, awaiting the player's answer", "open"):
            self.assertEqual(project_tarin_notice_knowledge(self.actor, state), state)

    def test_fulfilled_is_hidden_until_informed(self):
        self._fulfill_notice(RESOLUTION_VERIFIED)
        self.assertEqual(project_tarin_notice_knowledge(self.actor, "fulfilled"), "open")

    def test_fulfilled_is_revealed_once_informed(self):
        self._fulfill_notice(RESOLUTION_WITHDRAWN)
        commitment = get_fulfilled_commitment(self.actor, "unverified_notice")
        mark_informed(self.actor, commitment["commitment_id"])
        self.assertEqual(project_tarin_notice_knowledge(self.actor, "fulfilled"), "fulfilled")

    def test_fulfilled_with_no_matching_commitment_passes_through(self):
        self.assertEqual(project_tarin_notice_knowledge(self.actor, "fulfilled"), "fulfilled")


class ProjectVeskaNoticeKnowledgeTests(TestCase):
    """
    Confirmed live (2026-10-14): without this projector, Veska's own
    engine-state line just said "fulfilled" regardless of which action
    actually fulfilled it, and she hallucinated the wrong resolution
    (claimed withdrawn when the real resolution was verified_posted)
    when asked afterward. Unlike Tarin's projector above, this one
    must never hide the real resolution - Veska is the one who
    performed it, so holding back the one fact that would let her
    answer truthfully would recreate the same bug a different way.
    """

    def setUp(self):
        room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.actor = create_object("typeclasses.characters.Character", key="Tester", location=room)
        _fulfill_discrepancy_report(self.actor)

    def _fulfill_notice(self, resolution: str):
        propose_commitment(self.actor, "unverified_notice")
        accept_commitment(self.actor, "unverified_notice")
        result = fulfill_commitment_with_precondition(self.actor, "unverified_notice", "veska_renn", True)
        record_resolution(self.actor, result.commitment_id, resolution)
        return result

    def test_non_fulfilled_states_pass_through_unchanged(self):
        for state in ("not offered", "offered, awaiting the player's answer", "open"):
            self.assertEqual(project_veska_notice_knowledge(self.actor, state), state)

    def test_fulfilled_via_verify_states_the_real_resolution(self):
        self._fulfill_notice(RESOLUTION_VERIFIED)
        result = project_veska_notice_knowledge(self.actor, "fulfilled")
        self.assertIn("approval mark", result)
        self.assertNotIn("withdr", result)

    def test_fulfilled_via_withdraw_states_the_real_resolution(self):
        self._fulfill_notice(RESOLUTION_WITHDRAWN)
        result = project_veska_notice_knowledge(self.actor, "fulfilled")
        self.assertIn("withdr", result)
        self.assertNotIn("approval mark", result)

    def test_fulfilled_with_no_matching_commitment_passes_through(self):
        self.assertEqual(project_veska_notice_knowledge(self.actor, "fulfilled"), "fulfilled")
