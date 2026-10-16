"""
Per-player daily spend budget and the global daily spend circuit
breaker (game-plan.md 6.2, items 5-6) - both pure cost/abuse
safeguards checked in commands/say.py's engage_npc before any model
call, and both accounted for afterward from the real usage captured
on LLMReply (world/llm_client.py's `usage`), not from the max_tokens
cap sent with the request.

The per-player budget is in dollars (settings.LLM_PLAYER_DAILY_SPEND_USD),
priced from real usage by call_cost_usd - not tokens, since what it
protects is spend, and a token count stops meaning anything when the
model or its pricing changes (project owner, 2026-10-16: the original
120k-token budget ran out in about six turns, with ~10k-token prompts).

It unlocks gradually over the UTC day: PLAYER_BUDGET_UP_FRONT of it at
midnight, the rest in equal hourly chunks, all of it by the final hour.
A player could start at any hour; this stops an early starter burning
the whole day in one sitting while still giving a 05:00 starter a
usable session. Granted spend is never taken away (unused amounts roll
over within the day), and usage hard-resets at UTC midnight.

Developer/admin accounts are exempt from the per-player budget (not
from the global breaker), so testing doesn't run into it - an explicit
permission check, not a lock (docs/engineering-pitfalls.md #2).

The circuit breaker is a single server-wide daily dollar total, not a
per-player figure - its job is to catch a bug or runaway loop burning
through the OpenRouter key, not to throttle ordinary play.
LLM_DAILY_SPEND_LIMIT_USD is deliberately well above realistic
playtest volume (see docs/game-plan.md 6.2). It's tracked on a
GLOBAL_SCRIPTS singleton (see settings.GLOBAL_SCRIPTS) since this is
server-wide state with no single player or NPC object to live on.
"""
from datetime import datetime, timezone

from django.conf import settings
from evennia import GLOBAL_SCRIPTS
from evennia.utils import logger

PLAYER_BUDGET_UP_FRONT = 0.25
PLAYER_BUDGET_HOURS = 24
BUDGET_EXEMPT_PERMISSION = "Admin"  # Evennia's hierarchy: Developer includes Admin


def _today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _player_spend_today(caller) -> float:
    """Dollars this player has spent today, resetting lazily on day rollover."""
    if caller.db.llm_budget_day != _today_utc():
        return 0.0
    return caller.db.llm_spend_today_usd or 0.0


def player_budget_granted_so_far() -> float:
    """
    How much of the player's daily spend budget has unlocked so far
    today: PLAYER_BUDGET_UP_FRONT at midnight UTC, the rest in equal
    hourly chunks, the full amount from 23:00 UTC.
    """
    hour = datetime.now(timezone.utc).hour
    budget = settings.LLM_PLAYER_DAILY_SPEND_USD
    dripped = (1 - PLAYER_BUDGET_UP_FRONT) * (hour + 1) / PLAYER_BUDGET_HOURS
    return budget * (PLAYER_BUDGET_UP_FRONT + dripped)


def budget_exempt(caller) -> bool:
    account = getattr(caller, "account", None)
    if account is None:
        return False
    return bool(account.is_superuser or account.check_permstring(BUDGET_EXEMPT_PERMISSION))


def player_over_budget(caller) -> bool:
    if budget_exempt(caller):
        return False
    return _player_spend_today(caller) >= player_budget_granted_so_far()


def record_player_usage(caller, usage: dict) -> None:
    """Add one call's real cost to the player's spend for today. Recorded
    for exempt accounts too, so their usage can still be measured."""
    caller.db.llm_spend_today_usd = _player_spend_today(caller) + call_cost_usd(usage)
    caller.db.llm_budget_day = _today_utc()


def _spend_tracker():
    return GLOBAL_SCRIPTS.llm_spend_tracker


def _global_spend_today() -> float:
    tracker = _spend_tracker()
    if tracker.db.spend_day != _today_utc():
        return 0.0
    return tracker.db.spend_today or 0.0


def call_cost_usd(usage: dict) -> float:
    """
    Real dollar cost of one model call from its actual token usage,
    using OpenRouter's per-token rates for the configured model
    (settings.LLM_INPUT_COST_PER_1M_TOKENS / _OUTPUT_). These need
    updating if the model or its pricing changes.
    """
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    return (
        prompt_tokens * settings.LLM_INPUT_COST_PER_1M_TOKENS / 1_000_000
        + completion_tokens * settings.LLM_OUTPUT_COST_PER_1M_TOKENS / 1_000_000
    )


def global_daily_limit_reached() -> bool:
    return _global_spend_today() >= settings.LLM_DAILY_SPEND_LIMIT_USD


def record_global_spend(usage: dict) -> None:
    tracker = _spend_tracker()
    new_total = _global_spend_today() + call_cost_usd(usage)
    tracker.db.spend_today = new_total
    tracker.db.spend_day = _today_utc()
    if new_total >= settings.LLM_DAILY_SPEND_LIMIT_USD:
        logger.log_err(
            f"LLM daily spend circuit breaker tripped: ${new_total:.4f} >= "
            f"${settings.LLM_DAILY_SPEND_LIMIT_USD:.2f} (game-plan.md 6.2)"
        )
