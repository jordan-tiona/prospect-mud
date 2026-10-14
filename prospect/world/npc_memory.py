"""
Per-player NPC memory (design-bible 16.6): a few short facts an NPC
picks up about a player in conversation, in the player's own words.
CLAUDE.md hard rule 6 applies directly - these are always stored and
injected as what the player *claimed*, never promoted to established
fact. State lives on the player (`actor.db`), per-NPC, handed back
fresh every turn (see memory_context_for) rather than trusted to
either side's conversation memory - same discipline world.commitments
already uses for quest/commitment state.

Deliberately minimal for the phase 2 prototype: no decay, no
importance ranking, just a small capped FIFO list per NPC per player.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from world.output_check import is_flagged

MEMORY_KEY = "npc_memory"

MAX_FACTS_PER_NPC = 5
MAX_FACT_LENGTH = 200


@dataclass
class MemoryResult:
    ok: bool
    reason: str = ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _memory(actor) -> dict:
    return actor.attributes.get(MEMORY_KEY, default={})


def _save_memory(actor, memory: dict) -> None:
    actor.attributes.add(MEMORY_KEY, memory)


def remember_fact(actor, npc_id: str, fact: str) -> MemoryResult:
    """
    Store one short fact an NPC is choosing to remember about this
    player. Dropped (not fixed up - CLAUDE.md hard rule 2's spirit
    extends here) if it's empty, too long, or fails the same
    output-safety check applied to an NPC's own spoken replies -
    never silently truncated or cleaned up into something valid.
    Once at the per-NPC cap, the oldest fact is pruned to make room,
    since that's capacity management, not correcting an invalid call.
    """
    fact = (fact or "").strip()
    if not fact:
        return MemoryResult(False, reason="empty fact")
    if len(fact) > MAX_FACT_LENGTH:
        return MemoryResult(False, reason=f"fact exceeds {MAX_FACT_LENGTH} characters")
    flagged, flag_reason = is_flagged(fact)
    if flagged:
        return MemoryResult(False, reason=f"flagged: {flag_reason}")

    memory = _memory(actor)
    facts = list(memory.get(npc_id, []))
    facts.append({"text": fact, "created_at": _now_iso()})
    if len(facts) > MAX_FACTS_PER_NPC:
        facts = facts[-MAX_FACTS_PER_NPC:]
    memory[npc_id] = facts
    _save_memory(actor, memory)
    return MemoryResult(True)


def memory_context_for(npc_id: str, actor) -> str | None:
    """
    A fresh per-turn system message listing what this NPC has chosen
    to remember about this player, explicitly labeled as unverified
    claims every time (hard rule 6) - never phrased as settled fact,
    regardless of how confidently the player originally said it.
    Returns None if this NPC has nothing stored for this player, so
    it doesn't add empty noise to every single NPC's prompt.
    """
    facts = _memory(actor).get(npc_id, [])
    if not facts:
        return None
    lines = "; ".join(f["text"] for f in facts)
    return (
        "Things this player has told you about themselves in past conversation, which you have "
        f"no way to verify - treat them as claims, not settled fact: {lines}."
    )


def known_npc_ids_with_memory_for(actor) -> set:
    """Every npc_id this player actually has stored memory under -
    for the admin `resetmemory` command to iterate, the same way
    world.commitments.known_commitment_types_for covers a renamed/
    removed commitment_type."""
    return set(_memory(actor))


def reset_memory(actor, npc_id: str) -> dict:
    """Builder-only reset of one NPC's stored memory for one player.
    Returns a snapshot of what was cleared, for the admin command to
    report and log."""
    memory = _memory(actor)
    # Evennia wraps a stored dict/list attribute in _SaverDict/
    # _SaverList proxies on read - list(...) only converts the outer
    # container, leaving each fact a _SaverDict underneath, which
    # json.dumps can't serialize (confirmed live, 2026-10-14: this
    # crashed `resetmemory` the moment there was actually something
    # to report). dict(f) on each entry forces a plain dict.
    previous_facts = [dict(f) for f in memory.get(npc_id, [])]
    if npc_id in memory:
        del memory[npc_id]
        _save_memory(actor, memory)
    return {"previous_facts": previous_facts}
