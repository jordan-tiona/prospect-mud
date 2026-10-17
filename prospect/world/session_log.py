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

from django.conf import settings

# world/session_log.py -> parents[1] is the game dir (prospect/)
DEFAULT_LOG_PATH = Path(__file__).resolve().parents[1] / "server" / "logs" / "sessions.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Where an account's current login session_id is kept. An Attribute,
# not ndb: `evennia reload` wipes ndb while players stay connected, so
# every command after a reload went unlogged (docs/playtest-findings.md
# PF-0008). at_post_login overwrites it on each login.
SESSION_ID_ATTRIBUTE = "session_id"
SESSION_ID_CATEGORY = "session_log"


def set_session_id(account, session_id: str) -> None:
    account.attributes.add(SESSION_ID_ATTRIBUTE, session_id, category=SESSION_ID_CATEGORY)


def account_session_id(account) -> Optional[str]:
    return account.attributes.get(SESSION_ID_ATTRIBUTE, category=SESSION_ID_CATEGORY)


def session_id_for(character) -> Optional[str]:
    """
    The session_id an online Character's account is tracking
    (typeclasses/accounts.py sets this at login), or None if there
    isn't one - not currently puppeted, no account at all, or not
    really logged in. Centralized here so every gameplay-event call
    site (commands/command.py's logging mixin, typeclasses/
    characters.py's at_post_move, world/commitments.py's lifecycle
    functions) derives it the same way instead of repeating the same
    account/ndb lookup.
    """
    account = getattr(character, "account", None)
    return account_session_id(account) if account else None


def _write(record: dict, path: Optional[Path]) -> None:
    if path is None and getattr(settings, "TEST_ENVIRONMENT", False):
        # Tests exercising quest/commitment code would otherwise append
        # to the real playtest log, and parallel workers writing at once
        # left truncated lines in it (PF-0009). Tests of this module
        # pass an explicit path.
        return
    target_path = path or DEFAULT_LOG_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_session_start(
    *, session_id: str, account_key: str, staff: bool = False, path: Optional[Path] = None
) -> None:
    # `staff` lets a playtest-review pass tell the owner's or a mod's
    # sessions apart from testers' (world/stealth.py).
    _write(
        {
            "event": "session_start",
            "timestamp": _now_iso(),
            "session_id": session_id,
            "account_key": account_key,
            "staff": staff,
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


def log_unknown_command(
    *,
    session_id: str,
    actor_key: str,
    actor_dbref: str,
    location: str,
    raw_input: str,
    path: Optional[Path] = None,
) -> None:
    """
    A line that matched no command at all (commands/command.py's
    CmdNoMatch) - distinct from log_command, which only ever fires for
    input that *did* resolve to a real command, so a playtest-review
    pass can find these (game-plan.md's "unknown commands" pain-point
    signal) without parsing every raw_input for Evennia's own "Huh?"
    text.
    """
    _write(
        {
            "event": "unknown_command",
            "timestamp": _now_iso(),
            "session_id": session_id,
            "actor_key": actor_key,
            "actor_dbref": actor_dbref,
            "location": location,
            "raw_input": raw_input,
        },
        path,
    )


def log_room_changed(
    *,
    session_id: str,
    actor_key: str,
    actor_dbref: str,
    from_location: str,
    to_location: str,
    path: Optional[Path] = None,
) -> None:
    _write(
        {
            "event": "room_changed",
            "timestamp": _now_iso(),
            "session_id": session_id,
            "actor_key": actor_key,
            "actor_dbref": actor_dbref,
            "from_location": from_location,
            "to_location": to_location,
        },
        path,
    )


def log_quest_event(
    *,
    session_id: Optional[str],
    actor_key: str,
    actor_dbref: str,
    event: str,
    commitment_type: str,
    mandatory: bool,
    commitment_id: Optional[str] = None,
    path: Optional[Path] = None,
) -> None:
    """
    `event` is one of "quest_started" (accept_commitment),
    "quest_abandoned" (decline_commitment), or "quest_completed"
    (fulfill_commitment/fulfill_commitment_with_precondition) - see
    world/commitments.py, which calls this at each of those three
    genuine transitions, never on a rejected/duplicate call. Covers
    every commitment scenario, not just the playtest's `mandatory`
    ones (CLAUDE.md's "One quest offer per NPC" section) - `mandatory`
    is carried along so a playtest-review pass can tell a real quest
    from phase 2B/3 demo content without a separate lookup.
    """
    _write(
        {
            "event": event,
            "timestamp": _now_iso(),
            "session_id": session_id,
            "actor_key": actor_key,
            "actor_dbref": actor_dbref,
            "commitment_type": commitment_type,
            "mandatory": mandatory,
            "commitment_id": commitment_id,
        },
        path,
    )


def log_feedback(
    *,
    session_id: Optional[str],
    actor_key: str,
    actor_dbref: str,
    location: str,
    category: str,
    message: str,
    path: Optional[Path] = None,
) -> None:
    """
    A marker for commands/feedback.py's `bug`/`feedback` command
    (game-plan.md 6's Week 0 item 4) - the player explicitly flagged
    something, right then, rather than this being inferred from
    other activity. `category` is "bug" or "feedback", whichever
    word they actually typed (see that command's own docstring).
    """
    _write(
        {
            "event": "feedback",
            "timestamp": _now_iso(),
            "session_id": session_id,
            "actor_key": actor_key,
            "actor_dbref": actor_dbref,
            "location": location,
            "category": category,
            "message": message,
        },
        path,
    )


def log_idle(
    *,
    session_id: str,
    actor_key: str,
    actor_dbref: str,
    location: str,
    idle_seconds: float,
    path: Optional[Path] = None,
) -> None:
    _write(
        {
            "event": "idle",
            "timestamp": _now_iso(),
            "session_id": session_id,
            "actor_key": actor_key,
            "actor_dbref": actor_dbref,
            "location": location,
            "idle_seconds": idle_seconds,
        },
        path,
    )
