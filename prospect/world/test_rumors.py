"""
Tests for the parcel-delivery rumor's per-player knowledge state
(world/rumors.py), docs/phase2e-word-gets-around-design.md.

Run with:
    evennia test world
"""

from django.test import TestCase
from evennia import create_object

from world.commitments import (
    accept_commitment,
    fulfill_commitment_with_precondition,
    get_fulfilled_commitment,
    propose_commitment,
)
from world.rumors import (
    has_reputation_credit,
    is_informed_of,
    mark_informed,
    mark_reputation_credited,
    project_giver_parcel_knowledge,
    reset_rumor,
)


class RumorStateTests(TestCase):
    def setUp(self):
        room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.actor = create_object("typeclasses.characters.Character", key="Tester", location=room)

    def test_not_informed_by_default(self):
        self.assertFalse(is_informed_of(self.actor, "some-id"))

    def test_mark_informed_is_per_commitment_id(self):
        mark_informed(self.actor, "id-a")
        self.assertTrue(is_informed_of(self.actor, "id-a"))
        self.assertFalse(is_informed_of(self.actor, "id-b"))

    def test_mark_informed_is_idempotent(self):
        mark_informed(self.actor, "id-a")
        mark_informed(self.actor, "id-a")
        self.assertTrue(is_informed_of(self.actor, "id-a"))

    def test_no_reputation_credit_by_default(self):
        self.assertFalse(has_reputation_credit(self.actor))

    def test_mark_reputation_credited(self):
        mark_reputation_credited(self.actor)
        self.assertTrue(has_reputation_credit(self.actor))

    def test_reset_clears_both_fields(self):
        mark_informed(self.actor, "id-a")
        mark_reputation_credited(self.actor)
        snapshot = reset_rumor(self.actor)
        self.assertEqual(snapshot["informed_commitment_ids"], ["id-a"])
        self.assertTrue(snapshot["reputation_credited"])
        self.assertFalse(is_informed_of(self.actor, "id-a"))
        self.assertFalse(has_reputation_credit(self.actor))

    def test_reset_with_nothing_set_is_a_no_op(self):
        snapshot = reset_rumor(self.actor)
        self.assertEqual(snapshot["informed_commitment_ids"], [])
        self.assertFalse(snapshot["reputation_credited"])


class ProjectGiverParcelKnowledgeTests(TestCase):
    def setUp(self):
        room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.actor = create_object("typeclasses.characters.Character", key="Tester", location=room)

    def _fulfill_parcel(self):
        propose_commitment(self.actor, "deliver_parcel")
        accept_commitment(self.actor, "deliver_parcel")
        fulfill_commitment_with_precondition(self.actor, "deliver_parcel", "tarin_os", True)

    def test_non_fulfilled_states_pass_through_unchanged(self):
        for state in ("not offered", "offered, awaiting the player's answer", "open"):
            self.assertEqual(project_giver_parcel_knowledge(self.actor, state), state)

    def test_fulfilled_is_hidden_until_informed(self):
        self._fulfill_parcel()
        self.assertEqual(project_giver_parcel_knowledge(self.actor, "fulfilled"), "open")

    def test_fulfilled_is_revealed_once_informed(self):
        self._fulfill_parcel()
        commitment = get_fulfilled_commitment(self.actor, "deliver_parcel")
        mark_informed(self.actor, commitment["commitment_id"])
        self.assertEqual(project_giver_parcel_knowledge(self.actor, "fulfilled"), "fulfilled")

    def test_fulfilled_with_no_matching_commitment_passes_through(self):
        # Defensive case: "fulfilled" reported with nothing actually on
        # record (shouldn't happen in practice, but must not crash).
        self.assertEqual(project_giver_parcel_knowledge(self.actor, "fulfilled"), "fulfilled")
