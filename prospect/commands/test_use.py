"""
Tests for Quest 2's "use kit on bed" world command (commands/use.py).
Plain world action, no LLM involved - the actual completion fact lives
in world/garden.py, set only here.

Run with:
    evennia test commands
"""

from django.test import TestCase
from evennia import create_object

from world.build_garden_props import build as build_garden_props
from world.build_rooms import build as build_rooms
from world.garden import is_bed_tended


class UseCommandTests(TestCase):
    def setUp(self):
        self.rooms = build_rooms()
        self.props = build_garden_props()
        self.square = self.rooms["old_quarter_square"]
        self.courtyard = self.rooms["residential_courtyard"]
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=self.square
        )
        self.messages = []
        self.actor.msg = lambda text="", **kw: self.messages.append(text)

    def _give_kit(self):
        self.props["gardening_kit"].move_to(self.actor, quiet=True)

    def test_use_kit_on_bed_tends_it(self):
        self._give_kit()
        self.actor.execute_cmd("use gardening kit on planting bed")
        self.assertTrue(is_bed_tended(self.actor))

    def test_tend_bed_with_kit_phrasing_also_works(self):
        self._give_kit()
        self.actor.execute_cmd("tend planting bed with gardening kit")
        self.assertTrue(is_bed_tended(self.actor))

    def test_without_the_kit_in_hand_does_nothing(self):
        self.actor.execute_cmd("use gardening kit on planting bed")
        self.assertFalse(is_bed_tended(self.actor))

    def test_wrong_target_does_nothing(self):
        self._give_kit()
        self.actor.move_to(self.courtyard, quiet=True)
        self.actor.execute_cmd("use gardening kit on planting bed")
        self.assertFalse(is_bed_tended(self.actor))

    def test_using_a_non_kit_item_does_nothing(self):
        junk = create_object("typeclasses.objects.Object", key="a rock", location=self.actor)
        self.actor.execute_cmd("use rock on planting bed")
        self.assertFalse(is_bed_tended(self.actor))

    def test_missing_arguments_prompts_usage(self):
        self.actor.execute_cmd("use")
        self.assertTrue(any("Usage:" in m for m in self.messages))

    def test_plural_target_phrasing_also_matches(self):
        self._give_kit()
        self.actor.execute_cmd("use gardening kit on beds")
        self.assertTrue(is_bed_tended(self.actor))

    def test_retending_an_already_tended_bed_does_not_repeat_the_action_message(self):
        self._give_kit()
        self.actor.execute_cmd("use gardening kit on planting bed")
        self.messages.clear()
        self.actor.execute_cmd("use gardening kit on planting bed")
        self.assertTrue(any("already looks well tended" in m for m in self.messages))
        self.assertFalse(any(m.startswith("You tend to") for m in self.messages))

    def test_is_per_player(self):
        other = create_object(
            "typeclasses.characters.Character", key="Other", location=self.square
        )
        self._give_kit()
        self.actor.execute_cmd("use gardening kit on planting bed")
        self.assertTrue(is_bed_tended(self.actor))
        self.assertFalse(is_bed_tended(other))
