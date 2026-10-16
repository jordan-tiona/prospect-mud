"""
Unit tests for the per-player daily token budget and the global
daily spend circuit breaker (game-plan.md 6.2, items 5-6).

Run with:
    evennia test world
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings
from evennia import GLOBAL_SCRIPTS, create_object

from world.llm_budget import (
    call_cost_usd,
    global_daily_limit_reached,
    player_budget_granted_so_far,
    player_over_budget,
    record_global_spend,
    record_player_usage,
)


def _utc(hour, day_offset=0):
    return datetime(2026, 10, 16, hour, 0, 0, tzinfo=timezone.utc) + timedelta(days=day_offset)


class PlayerBudgetTests(TestCase):
    def setUp(self):
        # An explicit room/home, rather than relying on the default
        # home (settings.DEFAULT_HOME, "#2") existing - whether it
        # does depends on test run order/isolation from other test
        # modules that happen to build it, which caused an
        # intermittent dangling-foreign-key IntegrityError when this
        # file ran alongside the rest of the suite (2026-10-16).
        room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=room, home=room
        )

    @override_settings(LLM_PLAYER_DAILY_TOKEN_BUDGET=24000)
    @patch("world.llm_budget.datetime")
    def test_granted_so_far_scales_with_the_hour(self, mock_datetime):
        mock_datetime.now.return_value = _utc(0)
        self.assertEqual(player_budget_granted_so_far(), 1000)

        mock_datetime.now.return_value = _utc(23)
        self.assertEqual(player_budget_granted_so_far(), 24000)

    @override_settings(LLM_PLAYER_DAILY_TOKEN_BUDGET=24000)
    @patch("world.llm_budget.datetime")
    def test_player_under_budget_is_not_blocked(self, mock_datetime):
        mock_datetime.now.return_value = _utc(12)
        record_player_usage(self.actor, 500)

        self.assertFalse(player_over_budget(self.actor))

    @override_settings(LLM_PLAYER_DAILY_TOKEN_BUDGET=24000)
    @patch("world.llm_budget.datetime")
    def test_player_at_or_over_the_granted_amount_is_blocked(self, mock_datetime):
        mock_datetime.now.return_value = _utc(0)  # grants 1000
        record_player_usage(self.actor, 1000)

        self.assertTrue(player_over_budget(self.actor))

    @override_settings(LLM_PLAYER_DAILY_TOKEN_BUDGET=24000)
    @patch("world.llm_budget.datetime")
    def test_usage_rolls_over_within_the_same_day(self, mock_datetime):
        # Chunks already granted are never taken away - usage recorded
        # during an early, small-grant hour still counts fully against
        # a later, bigger grant the same day.
        mock_datetime.now.return_value = _utc(0)
        record_player_usage(self.actor, 1000)  # uses up the whole hour-0 grant

        mock_datetime.now.return_value = _utc(5)  # grants 6000
        self.assertFalse(player_over_budget(self.actor))
        self.assertEqual(self.actor.db.llm_tokens_used_today, 1000)

    @override_settings(LLM_PLAYER_DAILY_TOKEN_BUDGET=24000)
    @patch("world.llm_budget.datetime")
    def test_usage_resets_on_a_new_utc_day(self, mock_datetime):
        mock_datetime.now.return_value = _utc(23)
        record_player_usage(self.actor, 24000)
        self.assertTrue(player_over_budget(self.actor))

        mock_datetime.now.return_value = _utc(0, day_offset=1)
        self.assertFalse(player_over_budget(self.actor))


class GlobalSpendTests(TestCase):
    def setUp(self):
        tracker = GLOBAL_SCRIPTS.llm_spend_tracker
        tracker.db.spend_today = None
        tracker.db.spend_day = None

    def test_call_cost_is_computed_from_real_usage(self):
        usage = {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}

        cost = call_cost_usd(usage)

        self.assertAlmostEqual(
            cost,
            settings.LLM_INPUT_COST_PER_1M_TOKENS + settings.LLM_OUTPUT_COST_PER_1M_TOKENS,
        )

    @override_settings(LLM_DAILY_SPEND_LIMIT_USD=0.01)
    def test_limit_not_reached_below_the_ceiling(self):
        record_global_spend({"prompt_tokens": 1000, "completion_tokens": 0})

        self.assertFalse(global_daily_limit_reached())

    @override_settings(
        LLM_DAILY_SPEND_LIMIT_USD=0.001,
        LLM_INPUT_COST_PER_1M_TOKENS=1000.0,
        LLM_OUTPUT_COST_PER_1M_TOKENS=0.0,
    )
    def test_limit_reached_trips_the_breaker(self):
        record_global_spend({"prompt_tokens": 10, "completion_tokens": 0})

        self.assertTrue(global_daily_limit_reached())

    @patch("world.llm_budget._today_utc")
    def test_spend_resets_on_a_new_utc_day(self, mock_today):
        mock_today.return_value = "2026-10-16"
        record_global_spend({"prompt_tokens": 1_000_000, "completion_tokens": 0})
        self.assertGreater(GLOBAL_SCRIPTS.llm_spend_tracker.db.spend_today, 0)

        mock_today.return_value = "2026-10-17"
        self.assertFalse(global_daily_limit_reached())
