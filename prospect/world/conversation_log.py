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
    path: Optional[Path] = None,
) -> None:
    """
    Append one turn to the conversation log. Never raises on its own
    account of what it's recording - a bad turn is exactly the kind
    of thing this log exists to capture for review, not to judge.
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
            "reasoning_effort": settings.LLM_REASONING_EFFORT,
        },
        "npc_response": npc_response,
        "tool_calls": tool_calls,
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
