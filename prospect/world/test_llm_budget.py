"""
Unit tests for the per-player daily spend budget and the global
daily spend circuit breaker (game-plan.md 6.2, items 5-6).

Run with:
    evennia test world
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings
from evennia import GLOBAL_SCRIPTS, create_object
from evennia.utils.create import create_account

from world.llm_budget import (
    budget_exempt,
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

    # 1M prompt tokens at $1.00/1M = $1.00: easy round numbers.
    def _usage(self, dollars):
        return {"prompt_tokens": int(dollars * 1_000_000), "completion_tokens": 0}

    @override_settings(LLM_PLAYER_DAILY_SPEND_USD=1.0)
    @patch("world.llm_budget.datetime")
    def test_granted_so_far_is_a_quarter_up_front_then_hourly(self, mock_datetime):
        mock_datetime.now.return_value = _utc(0)
        self.assertAlmostEqual(player_budget_granted_so_far(), 0.25 + 0.75 / 24)

        mock_datetime.now.return_value = _utc(11)
        self.assertAlmostEqual(player_budget_granted_so_far(), 0.25 + 0.75 * 12 / 24)

        mock_datetime.now.return_value = _utc(23)
        self.assertAlmostEqual(player_budget_granted_so_far(), 1.0)

    @override_settings(LLM_PLAYER_DAILY_SPEND_USD=1.0, LLM_INPUT_COST_PER_1M_TOKENS=1.0)
    @patch("world.llm_budget.datetime")
    def test_player_under_budget_is_not_blocked(self, mock_datetime):
        mock_datetime.now.return_value = _utc(12)
        record_player_usage(self.actor, self._usage(0.10))

        self.assertFalse(player_over_budget(self.actor))

    @override_settings(LLM_PLAYER_DAILY_SPEND_USD=1.0, LLM_INPUT_COST_PER_1M_TOKENS=1.0)
    @patch("world.llm_budget.datetime")
    def test_player_at_or_over_the_granted_amount_is_blocked(self, mock_datetime):
        mock_datetime.now.return_value = _utc(0)  # grants ~$0.28
        record_player_usage(self.actor, self._usage(0.30))

        self.assertTrue(player_over_budget(self.actor))

    @override_settings(LLM_PLAYER_DAILY_SPEND_USD=1.0, LLM_INPUT_COST_PER_1M_TOKENS=1.0)
    @patch("world.llm_budget.datetime")
    def test_usage_rolls_over_within_the_same_day(self, mock_datetime):
        # Spend already granted is never taken away - usage recorded
        # during an early, small-grant hour still counts fully against
        # a later, bigger grant the same day.
        mock_datetime.now.return_value = _utc(0)
        record_player_usage(self.actor, self._usage(0.30))
        self.assertTrue(player_over_budget(self.actor))

        mock_datetime.now.return_value = _utc(5)  # grants $0.4375
        self.assertFalse(player_over_budget(self.actor))
        self.assertAlmostEqual(self.actor.db.llm_spend_today_usd, 0.30)

    @override_settings(LLM_PLAYER_DAILY_SPEND_USD=1.0, LLM_INPUT_COST_PER_1M_TOKENS=1.0)
    @patch("world.llm_budget.datetime")
    def test_usage_resets_on_a_new_utc_day(self, mock_datetime):
        mock_datetime.now.return_value = _utc(23)
        record_player_usage(self.actor, self._usage(1.0))
        self.assertTrue(player_over_budget(self.actor))

        mock_datetime.now.return_value = _utc(0, day_offset=1)
        self.assertFalse(player_over_budget(self.actor))

    @override_settings(LLM_PLAYER_DAILY_SPEND_USD=1.0, LLM_INPUT_COST_PER_1M_TOKENS=1.0)
    def test_admin_and_developer_accounts_are_exempt_but_still_recorded(self):
        for perm in ("Admin", "Developer"):
            with self.subTest(perm):
                account = create_account(f"Budget{perm}", email=None, password="TestPass123!")
                account.permissions.add(perm)
                self.actor.account = account
                record_player_usage(self.actor, self._usage(5.0))
                self.assertTrue(budget_exempt(self.actor))
                self.assertFalse(player_over_budget(self.actor))
                self.assertGreaterEqual(self.actor.db.llm_spend_today_usd, 5.0)

    @override_settings(LLM_PLAYER_DAILY_SPEND_USD=1.0, LLM_INPUT_COST_PER_1M_TOKENS=1.0)
    def test_ordinary_player_account_is_not_exempt(self):
        account = create_account("BudgetPlayer", email=None, password="TestPass123!")
        self.actor.account = account
        record_player_usage(self.actor, self._usage(5.0))
        self.assertFalse(budget_exempt(self.actor))
        self.assertTrue(player_over_budget(self.actor))


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

    @override_settings(
        LLM_INPUT_COST_PER_1M_TOKENS=1.0, LLM_CACHED_INPUT_COST_PER_1M_TOKENS=0.25, LLM_OUTPUT_COST_PER_1M_TOKENS=0
    )
    def test_cached_prompt_tokens_are_priced_at_the_cached_rate(self):
        usage = {"prompt_tokens": 1_000_000, "cached_tokens": 800_000, "completion_tokens": 0}

        self.assertAlmostEqual(call_cost_usd(usage), 0.2 + 0.2)

    def test_provider_reported_cost_wins_over_token_pricing(self):
        usage = {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000, "cost": 0.0123}

        self.assertEqual(call_cost_usd(usage), 0.0123)

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
