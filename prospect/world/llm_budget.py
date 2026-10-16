"""
Per-player daily token budget and the global daily spend circuit
breaker (game-plan.md 6.2, items 5-6) - both pure cost/abuse
safeguards checked in commands/say.py's engage_npc before any model
call, and both accounted for afterward from the real usage captured
on LLMReply (world/llm_client.py's `usage`), not from the max_tokens
cap sent with the request.

The per-player budget is granted in PLAYER_BUDGET_CHUNKS cumulative
hourly chunks, by UTC hour-of-day, rather than all at once - a
player's session could start at any hour of the day, and granting the
whole day's budget at the first hour mark would let an early starter
burn through it in one sitting while a later one can't (project
owner's call, 2026-10-16). Chunks are cumulative - never taken away
once granted, i.e. unused chunks roll over within the same day - and
the whole thing hard-resets to zero used at UTC midnight regardless
of how much was left unused.

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

PLAYER_BUDGET_CHUNKS = 24


def _today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _player_tokens_used_today(caller) -> int:
    """Tokens this player has used today, resetting lazily on day rollover."""
    if caller.db.llm_budget_day != _today_utc():
        return 0
    return caller.db.llm_tokens_used_today or 0


def player_budget_granted_so_far() -> int:
    """
    How many of the player's daily token budget have unlocked so far
    today, given the current UTC hour - the last chunk unlocks at
    23:00 UTC, so the full budget is only ever available for the
    day's final hour, not from some fixed early cutoff.
    """
    hour = datetime.now(timezone.utc).hour
    chunk = settings.LLM_PLAYER_DAILY_TOKEN_BUDGET / PLAYER_BUDGET_CHUNKS
    return int((hour + 1) * chunk)


def player_over_budget(caller) -> bool:
    return _player_tokens_used_today(caller) >= player_budget_granted_so_far()


def record_player_usage(caller, total_tokens: int) -> None:
    caller.db.llm_tokens_used_today = _player_tokens_used_today(caller) + total_tokens
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
