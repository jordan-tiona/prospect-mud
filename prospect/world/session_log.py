"""
Per-session command/transcript logging - separate from world/
conversation_log.py's conversations.jsonl. That file is dedicated,
curated material for a future setting-adapted LoRA (its own
docstring says so); mixing in raw command spam - every `look`,
`north`, `get kit` - would bury that signal.

This module exists purely for debugging/playtesting: a full per-
player session trace (every command typed, tied to a session_id that
spans one login-to-logout) lets a human reconstruct exactly what
someone did and when, without piecing it together after the fact
from the NPC-turn log alone - something that would have caught
2026-10-14/15's Mara/Tarin module-handoff confusion and the
"take"/"beds" command mismatches immediately instead of needing a
log dive to find.

Not meant to be kept forever - delete server/logs/sessions.jsonl
whenever it's no longer useful. server/logs/ is entirely gitignored,
so there's nothing to clean up in git either.

Logs are append-only JSONL under server/logs/sessions.jsonl.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# world/session_log.py -> parents[1] is the game dir (prospect/)
DEFAULT_LOG_PATH = Path(__file__).resolve().parents[1] / "server" / "logs" / "sessions.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(record: dict, path: Optional[Path]) -> None:
    target_path = path or DEFAULT_LOG_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_session_start(*, session_id: str, account_key: str, path: Optional[Path] = None) -> None:
    _write(
        {
            "event": "session_start",
            "timestamp": _now_iso(),
            "session_id": session_id,
            "account_key": account_key,
        },
        path,
    )


def log_session_end(
    *, session_id: str, account_key: str, reason: str = "", path: Optional[Path] = None
) -> None:
    _write(
        {
            "event": "session_end",
            "timestamp": _now_iso(),
            "session_id": session_id,
            "account_key": account_key,
            "reason": reason,
        },
        path,
    )


def log_command(
    *,
    session_id: str,
    actor_key: str,
    actor_dbref: str,
    location: str,
    raw_input: str,
    path: Optional[Path] = None,
) -> None:
    _write(
        {
            "event": "command",
            "timestamp": _now_iso(),
            "session_id": session_id,
            "actor_key": actor_key,
            "actor_dbref": actor_dbref,
            "location": location,
            "raw_input": raw_input,
        },
        path,
    )
