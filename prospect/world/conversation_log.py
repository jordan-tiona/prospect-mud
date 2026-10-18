"""
Conversation logging (design-bible 14.7): every NPC conversation turn
is appended as one JSON record - including the full prompt sent and
the model's raw response - so a human can later review and curate
material for a potential setting-adapted LoRA. This module only
records; curation is a separate, human step, explicitly out of scope
here per CLAUDE.md phase 1 ("Human review and curation are integral
to the plan").

Logs are append-only JSONL under server/logs/conversations.jsonl -
gitignored, like the rest of server/logs/, since this is runtime
data (including real player chat) rather than code.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from django.conf import settings

# world/conversation_log.py -> parents[1] is the game dir (prospect/)
DEFAULT_LOG_PATH = Path(__file__).resolve().parents[1] / "server" / "logs" / "conversations.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_turn(
    *,
    conversation_id: str,
    turn_id: int,
    npc_id: str,
    location: str,
    actor_key: str,
    actor_dbref: str,
    player_message: str,
    prompt_messages: list,
    model: str,
    prompt_version: str,
    npc_response: Optional[str],
    tool_calls: list,
    flagged: bool,
    flag_reason: str = "",
    initial_response: Optional[str] = None,
    reaction_tools: Optional[list] = None,
    usage: Optional[dict] = None,
    cost_usd: Optional[float] = None,
    latency_ms: Optional[float] = None,
    path: Optional[Path] = None,
) -> None:
    """
    Append one turn to the conversation log. Never raises on its own
    account of what it's recording - a bad turn is exactly the kind
    of thing this log exists to capture for review, not to judge.

    `initial_response` is only set for a turn where a tool call
    triggered a follow-up "react to what you just did" model call
    (commands/say.py's `_handle_action_reaction` - see
    `FORCE_REACTION_ACTIONS`/`needs_reaction`): it's the raw text from
    that *first* completion (what was actually spoken/emoted to the
    player before the tool result came back), while `npc_response`
    stays the final reply. Without this, that first completion's text
    was never logged at all - lost entirely, even though the player
    saw it - leaving `npc_response` holding only the reaction and
    `tool_calls` from a different completion than the text next to it.

    `reaction_tools` is the action names that follow-up call was
    offered (world/actions.py's REACTION_RETRIES/REACTION_FOLLOW_ONS),
    `[]` when it had none, and `None` when the turn had no follow-up.
    Without it the log couldn't say whether a reaction that only talked
    about an action could have made the call (2026-10-18).

    `usage`/`cost_usd`/`latency_ms` (game-plan.md 6.2's structured-
    logging item) cover the *whole turn* as the player experienced it,
    not just one completion - for a turn with a follow-up reaction
    call, that's both completions combined (see commands/say.py's
    `_combine_usage` and the latency measured from the very first
    model call's dispatch, not reset for the second one). All three
    are `None` when no model call happened at all (e.g. a dropped
    turn from one of engage_npc's pre-call safeguard gates never
    calls log_turn in the first place, but a turn where the model was
    simply unavailable still does, with these left at their defaults).
    """
    record = {
        "conversation_id": conversation_id,
        "turn_id": turn_id,
        "timestamp": _now_iso(),
        "npc_id": npc_id,
        "location": location,
        "actor_key": actor_key,
        "actor_dbref": actor_dbref,
        "player_message": player_message,
        "prompt": prompt_messages,
        "model": model,
        "prompt_version": prompt_version,
        # Never log the API key, even a dummy local one.
        "model_settings": {
            "base_url": settings.LLM_BASE_URL,
            "provider": settings.LLM_PROVIDER,
            "reasoning_effort": settings.LLM_REASONING_EFFORT,
        },
        "initial_response": initial_response,
        "reaction_tools": reaction_tools,
        "npc_response": npc_response,
        "tool_calls": tool_calls,
        "usage": usage,
        "cost_usd": cost_usd,
        "latency_ms": latency_ms,
        "flagged": flagged,
        "flag_reason": flag_reason,
        # Filled in later by a human reviewer, per design-bible 14.7;
        # never auto-populated here.
        "review_status": None,
        "annotations": None,
    }

    target_path = path or DEFAULT_LOG_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_quest_reset(
    *,
    quest_key: str,
    previous_state: str,
    actor_key: str,
    actor_dbref: str,
    path: Optional[Path] = None,
) -> None:
    """
    Append a marker record for a `resetquest` command (see
    commands/admin.py's CmdResetQuest) - a human resetting a player's
    quest progress mid-test. Distinguished from `log_reset`'s "forget"
    event (which clears conversation history, not quest state) by its
    own `"event": "quest_reset"`.
    """
    record = {
        "event": "quest_reset",
        "timestamp": _now_iso(),
        "quest_key": quest_key,
        "previous_state": previous_state,
        "actor_key": actor_key,
        "actor_dbref": actor_dbref,
    }

    target_path = path or DEFAULT_LOG_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_commitment_reset(
    *,
    commitment_type: str,
    had_offer: bool,
    previous_statuses: list,
    actor_key: str,
    actor_dbref: str,
    had_declined: bool = False,
    path: Optional[Path] = None,
) -> None:
    """
    Append a marker record for a `resetcommitment` command (see
    commands/admin.py's CmdResetCommitment) - a human clearing a
    player's commitment progress mid-test. Distinguished from
    `log_quest_reset`'s "quest_reset" event (a different, older
    per-player state machine) by its own `"event": "commitment_reset"`.

    `had_declined` (2026-10-16): whether this player's sticky decline-
    history fact for this commitment_type was also cleared - separate
    from had_offer/previous_statuses, since a decline can be the only
    thing on record (no pending offer, no commitment instance) for an
    ordinary scenario a player turned down once and never revisited.
    """
    record = {
        "event": "commitment_reset",
        "timestamp": _now_iso(),
        "commitment_type": commitment_type,
        "had_offer": had_offer,
        "previous_statuses": previous_statuses,
        "had_declined": had_declined,
        "actor_key": actor_key,
        "actor_dbref": actor_dbref,
    }

    target_path = path or DEFAULT_LOG_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_memory_reset(
    *,
    npc_id: str,
    previous_facts: list,
    actor_key: str,
    actor_dbref: str,
    path: Optional[Path] = None,
) -> None:
    """
    Append a marker record for a `resetmemory` command (see
    commands/admin.py's CmdResetMemory) - a human clearing a player's
    stored NPC memory (design-bible 16.6) mid-test. Its own
    `"event": "memory_reset"`, parallel to `log_commitment_reset`.
    """
    record = {
        "event": "memory_reset",
        "timestamp": _now_iso(),
        "npc_id": npc_id,
        "previous_facts": previous_facts,
        "actor_key": actor_key,
        "actor_dbref": actor_dbref,
    }

    target_path = path or DEFAULT_LOG_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_rumor_reset(
    *,
    previous_informed_commitment_ids: list,
    previous_reputation_credited: bool,
    previous_reputations: dict,
    actor_key: str,
    actor_dbref: str,
    path: Optional[Path] = None,
) -> None:
    """
    Append a marker record for the rumor/reputation portion of a
    `resetcommitment` command (see commands/admin.py's
    CmdResetCommitment) - a human clearing a player's phase 2E
    parcel-rumor knowledge and the giver's reputation credit mid-test.
    Its own `"event": "rumor_reset"`, parallel to `log_commitment_reset`.
    `previous_reputations` maps npc_id -> the nonzero value cleared;
    it replaced the single `previous_mara_reputation` field when the
    parcel moved to Veska (docs/errand-redistribution-plan.md), so
    older records in the log still carry that field instead.
    """
    record = {
        "event": "rumor_reset",
        "timestamp": _now_iso(),
        "previous_informed_commitment_ids": previous_informed_commitment_ids,
        "previous_reputation_credited": previous_reputation_credited,
        "previous_reputations": previous_reputations,
        "actor_key": actor_key,
        "actor_dbref": actor_dbref,
    }

    target_path = path or DEFAULT_LOG_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_reset(
    *,
    conversation_id: Optional[str],
    npc_id: str,
    actor_key: str,
    actor_dbref: str,
    path: Optional[Path] = None,
) -> None:
    """
    Append a marker record for a `forget` command (see commands/admin.py's
    CmdForget) - a human clearing an NPC's conversation history mid-test.
    Logged in the same file as regular turns, distinguished by
    `"event": "forget"`, so a reviewer scanning the log can tell exactly
    where a conversation was deliberately reset rather than mistake a
    sudden change in tool-call behavior for something the model did on
    its own.
    """
    record = {
        "event": "forget",
        "conversation_id": conversation_id,
        "timestamp": _now_iso(),
        "npc_id": npc_id,
        "actor_key": actor_key,
        "actor_dbref": actor_dbref,
    }

    target_path = path or DEFAULT_LOG_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
