"""
Phase 2E (docs/phase2e-word-gets-around-design.md): the "deliver_parcel"
commitment's proposer, Mara Voss, does not automatically learn that the
parcel reached Tarin or Veska just because the commitment itself
becomes STATUS_FULFILLED - that fact belongs to whichever NPC actually
took physical custody of it. She only learns it once the player tells
her, through a separate validated action (world/actions.py's
_validate_report_parcel_delivery) that checks the player's report
against the real commitment record before recording anything.

This module owns that per-player "has Mara been told" state, plus the
one-time reputation credit for successfully relaying it, and the
projector function wired into world/commitments.py's SCENARIOS entry
for "deliver_parcel". world/commitments.py has no idea any of this
exists - it only knows a scenario may supply a proposer_knowledge_
projector, generically.
"""

from world.commitments import STATUS_FULFILLED, get_fulfilled_commitment

RUMOR_KEY = "parcel_rumor"


def _state(actor) -> dict:
    return actor.attributes.get(
        RUMOR_KEY, default={"informed_commitment_ids": [], "reputation_credited": False}
    )


def _save_state(actor, state: dict) -> None:
    actor.attributes.add(RUMOR_KEY, state)


def is_informed_of(actor, commitment_id: str) -> bool:
    return commitment_id in _state(actor)["informed_commitment_ids"]


def mark_informed(actor, commitment_id: str) -> None:
    state = _state(actor)
    if commitment_id not in state["informed_commitment_ids"]:
        state["informed_commitment_ids"].append(commitment_id)
    _save_state(actor, state)


def has_reputation_credit(actor) -> bool:
    return _state(actor)["reputation_credited"]


def mark_reputation_credited(actor) -> None:
    state = _state(actor)
    state["reputation_credited"] = True
    _save_state(actor, state)


def project_mara_parcel_knowledge(actor, state: str) -> str:
    """
    world/commitments.py's proposer_knowledge_projector for
    "deliver_parcel". Only intercepts the "fulfilled" state - every
    other state (not offered, offered, open) already means Mara hasn't
    learned anything she shouldn't, since those are all stages she's
    actively part of. Once the real commitment is fulfilled, this holds
    her view at "open" (an ongoing errand she's still waiting to hear
    about) until the specific fulfilled commitment_id has been reported
    to her - looked up fresh each time, never cached, so a reset that
    clears the commitment can't leave a stale "fulfilled" view behind
    either (get_fulfilled_commitment would simply find nothing).
    """
    if state != STATUS_FULFILLED:
        return state
    commitment = get_fulfilled_commitment(actor, "deliver_parcel")
    if commitment is None:
        return state
    if is_informed_of(actor, commitment["commitment_id"]):
        return state
    return "open"


def reset_rumor(actor) -> dict:
    """
    Builder-only reset (commands/admin.py's CmdResetCommitment folds
    this in alongside its other deliver_parcel-adjacent cleanup).
    Returns a snapshot of what was cleared, for logging. Idempotent -
    resetting an already-clear state just returns the same empty
    snapshot again.
    """
    previous = _state(actor)
    _save_state(actor, {"informed_commitment_ids": [], "reputation_credited": False})
    return {
        "informed_commitment_ids": list(previous["informed_commitment_ids"]),
        "reputation_credited": previous["reputation_credited"],
    }
