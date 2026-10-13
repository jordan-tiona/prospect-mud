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
    _validate_decline_commitment,
    _validate_propose_commitment,
    _validate_report_commitment_outcome,
    get_quest_state,
    quest_context_for,
    validate_and_apply,
)
from world.build_npcs import build as build_npcs
from world.build_rooms import build as build_rooms


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

    # -- module-exchange quest (Mara + Tarin) -----------------------------

    def test_quest_starts_not_started(self):
        self.assertEqual(get_quest_state(self.actor), "not_started")

    def test_accept_help_from_not_started(self):
        result = validate_and_apply(self.mara, self.actor, "accept_help", {})
        self.assertTrue(result.applied)
        self.assertEqual(get_quest_state(self.actor), "accepted")

    def test_accept_help_twice_is_dropped(self):
        validate_and_apply(self.mara, self.actor, "accept_help", {})
        result = validate_and_apply(self.mara, self.actor, "accept_help", {})
        self.assertFalse(result.applied)
        self.assertEqual(get_quest_state(self.actor), "accepted")

    def test_give_faulty_module_requires_accepted(self):
        result = validate_and_apply(self.mara, self.actor, "give_faulty_module", {})
        self.assertFalse(result.applied)
        self.assertEqual(get_quest_state(self.actor), "not_started")

    def test_give_faulty_module_after_accepted(self):
        validate_and_apply(self.mara, self.actor, "accept_help", {})
        result = validate_and_apply(self.mara, self.actor, "give_faulty_module", {})
        self.assertTrue(result.applied)
        self.assertEqual(get_quest_state(self.actor), "has_faulty_module")

    def test_exchange_module_requires_faulty_module_in_hand(self):
        result = validate_and_apply(self.tarin, self.actor, "exchange_module", {})
        self.assertFalse(result.applied)
        self.assertEqual(get_quest_state(self.actor), "not_started")

    def test_exchange_module_not_permitted_for_mara(self):
        validate_and_apply(self.mara, self.actor, "accept_help", {})
        validate_and_apply(self.mara, self.actor, "give_faulty_module", {})
        result = validate_and_apply(self.mara, self.actor, "exchange_module", {})
        self.assertFalse(result.applied)
        self.assertIn("not a permitted action", result.reason)

    def test_full_quest_sequence(self):
        self.assertTrue(validate_and_apply(self.mara, self.actor, "accept_help", {}).applied)
        self.assertTrue(validate_and_apply(self.mara, self.actor, "give_faulty_module", {}).applied)
        self.assertTrue(validate_and_apply(self.tarin, self.actor, "exchange_module", {}).applied)
        self.assertEqual(get_quest_state(self.actor), "has_replacement_module")
        self.assertTrue(validate_and_apply(self.mara, self.actor, "accept_replacement", {}).applied)
        self.assertEqual(get_quest_state(self.actor), "completed")

    def test_accept_replacement_too_early_is_dropped(self):
        validate_and_apply(self.mara, self.actor, "accept_help", {})
        validate_and_apply(self.mara, self.actor, "give_faulty_module", {})
        result = validate_and_apply(self.mara, self.actor, "accept_replacement", {})
        self.assertFalse(result.applied)
        self.assertEqual(get_quest_state(self.actor), "has_faulty_module")

    def test_quest_state_is_per_player(self):
        other = create_object("typeclasses.characters.Character", key="Other", location=self.cafe)
        validate_and_apply(self.mara, self.actor, "accept_help", {})
        self.assertEqual(get_quest_state(self.actor), "accepted")
        self.assertEqual(get_quest_state(other), "not_started")

    def test_quest_context_for_npc_without_quest_actions_is_none(self):
        self.assertIsNone(quest_context_for(["give_directions"], self.actor))

    def test_quest_context_for_mara_reflects_current_state(self):
        validate_and_apply(self.mara, self.actor, "accept_help", {})
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
        validate_and_apply(self.mara, self.actor, "accept_help", {})
        validate_and_apply(self.mara, self.actor, "give_faulty_module", {})
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
        ):
            schema = ACTION_SCHEMAS[name]["function"]
            self.assertTrue(
                schema["parameters"]["required"], f"{name}'s schema must require at least one argument"
            )
