"""
Tests for Quest 3's attack command (commands/attack.py). Plain world
command, no LLM involved - the actual combat mechanics live in
typeclasses/creatures.py, exercised here through the command.

Run with:
    evennia test commands
"""

from django.test import TestCase
from evennia import create_object

from world.build_rooms import build as build_rooms
from world.commitments import accept_commitment, propose_commitment
from world.skitters import kills_for


class AttackCommandTests(TestCase):
    def setUp(self):
        self.rooms = build_rooms()
        self.room = self.rooms["old_quarter_square"]
        self.actor = create_object(
            "typeclasses.characters.Character", key="Hunter", location=self.room
        )
        self.messages = []
        self.actor.msg = lambda text="", **kw: self.messages.append(text)

    def _make_eligible(self):
        propose_commitment(self.actor, "hunt_skitters")
        accept_commitment(self.actor, "hunt_skitters")

    def _give_weapon(self, damage=1):
        weapon = create_object("typeclasses.objects.Weapon", key="a control wand", location=self.actor)
        weapon.db.damage = damage
        return weapon

    def _make_skitter(self, hp=3):
        skitter = create_object("typeclasses.creatures.Skitter", key="a skitter", location=self.room)
        skitter.db.hp = hp
        return skitter

    def test_eligible_player_with_weapon_damages_the_skitter(self):
        self._make_eligible()
        self._give_weapon()
        skitter = self._make_skitter(hp=3)
        self.actor.execute_cmd("attack skitter")
        self.assertEqual(skitter.db.hp, 2)

    def test_first_hit_shows_light_scratches_descriptor(self):
        self._make_eligible()
        self._give_weapon()
        self._make_skitter(hp=3)
        self.actor.execute_cmd("attack skitter")
        self.assertTrue(any("has a few light scratches" in m for m in self.messages))

    def test_second_hit_shows_badly_hurt_descriptor(self):
        self._make_eligible()
        self._give_weapon()
        self._make_skitter(hp=2)
        self.actor.execute_cmd("attack skitter")
        self.assertTrue(any("looks badly hurt" in m for m in self.messages))

    def test_defeat_message_has_no_health_descriptor(self):
        self._make_eligible()
        self._give_weapon()
        self._make_skitter(hp=1)
        self.actor.execute_cmd("attack skitter")
        self.assertFalse(any("scratches" in m or "badly hurt" in m for m in self.messages))

    def test_ineligible_player_cannot_see_or_target_the_skitter(self):
        self._give_weapon()
        self._make_skitter(hp=3)
        self.actor.execute_cmd("attack skitter")
        self.assertTrue(any("don't see" in m for m in self.messages))

    def test_without_a_weapon_attack_does_nothing(self):
        self._make_eligible()
        skitter = self._make_skitter(hp=3)
        self.actor.execute_cmd("attack skitter")
        self.assertEqual(skitter.db.hp, 3)
        self.assertTrue(any("anything to fight it with" in m for m in self.messages))

    def test_defeat_records_a_kill_and_respawns(self):
        self._make_eligible()
        self._give_weapon()
        self._make_skitter(hp=1)
        self.actor.execute_cmd("attack skitter")
        self.assertEqual(kills_for(self.actor), 1)
        self.assertTrue(any("You defeat" in m for m in self.messages))

    def test_kill_alias_also_works(self):
        self._make_eligible()
        self._give_weapon()
        self._make_skitter(hp=1)
        self.actor.execute_cmd("kill skitter")
        self.assertEqual(kills_for(self.actor), 1)

    def test_with_item_phrasing_uses_the_named_weapon(self):
        self._make_eligible()
        self._give_weapon()
        self._make_skitter(hp=1)
        self.actor.execute_cmd("attack skitter with control wand")
        self.assertEqual(kills_for(self.actor), 1)

    def test_missing_target_prompts_usage(self):
        self.actor.execute_cmd("attack")
        self.assertTrue(any("Attack what?" in m for m in self.messages))
