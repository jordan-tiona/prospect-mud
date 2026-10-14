"""
Phase 2E (docs/phase2e-word-gets-around-design.md): the project's first
reputation state. Deliberately minimal - a plain per-player, per-NPC
integer, with no decay, caps, or relationship graph. The only thing
protecting it from being farmed is scenario-side (world/rumors.py's
once-per-player reputation_credited flag before this module is ever
called to adjust anything) - this module itself just stores and
reports a number, the same separation of concerns world/commitments.py
keeps from any scenario's own fulfillment logic.
"""

REPUTATION_KEY = "npc_reputation"


def _reputation(actor) -> dict:
    return actor.attributes.get(REPUTATION_KEY, default={})


def _save_reputation(actor, reputation: dict) -> None:
    actor.attributes.add(REPUTATION_KEY, reputation)


def get_reputation(actor, npc_id: str) -> int:
    return _reputation(actor).get(npc_id, 0)


def adjust_reputation(actor, npc_id: str, delta: int) -> int:
    reputation = _reputation(actor)
    reputation[npc_id] = reputation.get(npc_id, 0) + delta
    _save_reputation(actor, reputation)
    return reputation[npc_id]


def reset_reputation(actor, npc_id: str) -> int:
    """Builder-only reset for one NPC's reputation with this player.
    Returns the previous value (0 if there was none), for the admin
    command to report and log."""
    reputation = _reputation(actor)
    previous = reputation.pop(npc_id, 0)
    _save_reputation(actor, reputation)
    return previous


def reputation_context_for(npc_id: str, actor) -> str | None:
    """
    A fresh per-turn system message giving an NPC its own private
    opinion of this player, same injection pattern as world/npc_memory.
    py's memory_context_for. Returns None when reputation is exactly 0
    (the default, and the only value for every NPC before this
    scenario exists) so most NPCs' prompts are completely unaffected -
    this only ever appears for an NPC a scenario has actually adjusted.
    """
    value = get_reputation(actor, npc_id)
    if value == 0:
        return None
    return (
        f"Your own private opinion of this player, as a small engine-tracked number: {value}. "
        "Let it come through in tone, not by stating the number."
    )
