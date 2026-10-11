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

from world.actions import validate_and_apply
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
        self.assertIn("cafe", result.narration)

    def test_give_directions_across_hub(self):
        self.actor.move_to(self.cafe, quiet=True)
        result = validate_and_apply(self.iri, self.actor, "give_directions", {"destination": "Civic Office"})
        self.assertTrue(result.applied)
        # two hops: cafe -> square -> office
        self.assertIn("square", result.narration)
        self.assertIn("office", result.narration)

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
