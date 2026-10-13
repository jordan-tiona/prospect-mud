"""
Generic engine-authoritative commitment lifecycle (docs/phase2b-
records-discrepancy-proposal.md). CLAUDE.md hard rules 1-2 and 5 apply
here exactly as they did to phase 2A's module-exchange quest: this
module is the only place a commitment's state actually changes, and
each NPC's own role in a commitment (who can offer it, who can
acknowledge a report, who can fulfill it) is fixed by scenario
config, never chosen by the model.

A commitment is a promise the player makes to one NPC (the "holder"),
fulfilled only once a different NPC (the "clerk") has engine-recorded
evidence that the player did what the commitment required. State
lives on the player (`actor.db`), persistent, and is handed back to
each NPC fresh every turn (see commitment_context_for) rather than
left to either side's conversation memory.

Only one commitment type is authored for the phase 2B prototype:
"discrepancy_report". The lifecycle itself is written generic so a
future scenario can reuse it by adding another SCENARIOS entry,
without touching this module.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

# actor.db keys. Separate from phase 2A's QUEST_MODULE_EXCHANGE_KEY -
# this is a different, more general mechanism living alongside it,
# not a replacement.
COMMITMENTS_KEY = "commitments"
OFFERS_KEY = "commitment_offers"
ACKS_KEY = "commitment_acks"

STATUS_OPEN = "open"
STATUS_FULFILLED = "fulfilled"
# "broken" is reserved in the design doc for a future designed
# transition (deadlines, cancellation) - deliberately unused here.

# Every generic action this module backs, so world/actions.py's
# quest_context_for-style injection knows which NPCs need a
# commitment_context_for call at all.
COMMITMENT_ACTIONS = {
    "propose_commitment",
    "accept_commitment",
    "decline_commitment",
    "report_commitment_outcome",
}


@dataclass
class ScenarioConfig:
    commitment_type: str
    holder_npc_id: str  # the NPC the player promises, and later reports back to
    clerk_npc_id: str  # the NPC who records the acknowledgment evidence
    # Shown in place of the holder's normal ambient_pose, only to a
    # player who hasn't been offered this commitment yet - a
    # deterministic discoverability hint that doesn't depend on
    # getting the right question past the model (see
    # typeclasses.rooms.Room's _presence_line). Flavor text, same
    # register as the scenario description below - not new setting
    # lore, just this NPC's situational demeanor.
    holder_hint_pose: str = ""


# The one authored scenario for this prototype (docs/phase2b-records-
# discrepancy-proposal.md's "Approved owner scenario"). Scenario
# content (who, why) belongs to the project owner; this config only
# wires the engine roles.
SCENARIOS = {
    "discrepancy_report": ScenarioConfig(
        commitment_type="discrepancy_report",
        holder_npc_id="tarin_os",
        clerk_npc_id="veska_renn",
        holder_hint_pose="frowning over a shipment manifest",
    ),
}


@dataclass
class LifecycleResult:
    ok: bool
    reason: str = ""
    commitment_id: str = ""


def get_scenario(commitment_type: str) -> ScenarioConfig | None:
    return SCENARIOS.get(commitment_type)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _commitments(actor) -> dict:
    return actor.attributes.get(COMMITMENTS_KEY, default={})


def _save_commitments(actor, commitments: dict) -> None:
    actor.attributes.add(COMMITMENTS_KEY, commitments)


def _offers(actor) -> dict:
    return actor.attributes.get(OFFERS_KEY, default={})


def _save_offers(actor, offers: dict) -> None:
    actor.attributes.add(OFFERS_KEY, offers)


def _acks(actor) -> dict:
    return actor.attributes.get(ACKS_KEY, default={})


def _save_acks(actor, acks: dict) -> None:
    actor.attributes.add(ACKS_KEY, acks)


def _find_open_commitment(actor, commitment_type: str) -> dict | None:
    for commitment in _commitments(actor).values():
        if commitment["commitment_type"] == commitment_type and commitment["status"] == STATUS_OPEN:
            return commitment
    return None


def propose_commitment(actor, commitment_type: str) -> LifecycleResult:
    """
    The holder NPC offers the errand. Only records that an offer is
    pending, so accept/decline have something to act on - dropped if
    one's already open or already pending, so re-offering mid-errand
    can't spawn a second instance.
    """
    if get_scenario(commitment_type) is None:
        return LifecycleResult(False, reason=f"unknown commitment_type: {commitment_type!r}")
    if _find_open_commitment(actor, commitment_type):
        return LifecycleResult(False, reason="an open commitment of this type already exists")
    offers = _offers(actor)
    if offers.get(commitment_type):
        return LifecycleResult(False, reason="an offer of this type is already pending")
    offers[commitment_type] = True
    _save_offers(actor, offers)
    return LifecycleResult(True)


def accept_commitment(actor, commitment_type: str) -> LifecycleResult:
    """
    Creates the actual open commitment instance - only valid once an
    offer is pending. Declining an offer and accepting it are mutually
    exclusive answers to the same pending offer, not independent
    actions, so this clears the offer flag same as decline does.
    """
    if get_scenario(commitment_type) is None:
        return LifecycleResult(False, reason=f"unknown commitment_type: {commitment_type!r}")
    offers = _offers(actor)
    if not offers.get(commitment_type):
        return LifecycleResult(False, reason="no pending offer of this type to accept")

    commitment_id = str(uuid.uuid4())
    commitments = _commitments(actor)
    commitments[commitment_id] = {
        "commitment_id": commitment_id,
        "commitment_type": commitment_type,
        "maker_dbref": actor.dbref,
        "holder_npc_id": get_scenario(commitment_type).holder_npc_id,
        "status": STATUS_OPEN,
        "created_at": _now_iso(),
    }
    _save_commitments(actor, commitments)

    offers[commitment_type] = False
    _save_offers(actor, offers)
    return LifecycleResult(True, commitment_id=commitment_id)


def decline_commitment(actor, commitment_type: str) -> LifecycleResult:
    """
    Closes a pending offer without creating an obligation. Per the
    design doc, declining is not breaking a promise - no commitment
    record is created at all, so the offer can simply be made again
    later (propose_commitment only checks for an *open* commitment or
    *pending* offer, neither of which exists after a decline).
    """
    offers = _offers(actor)
    if not offers.get(commitment_type):
        return LifecycleResult(False, reason="no pending offer of this type to decline")
    offers[commitment_type] = False
    _save_offers(actor, offers)
    return LifecycleResult(True)


def record_acknowledgment(actor, commitment_type: str, clerk_npc_id: str) -> LifecycleResult:
    """
    The clerk NPC's role: records that this player reported, tied to
    the specific open commitment *instance* (by commitment_id), never
    to the type in the abstract - so a stale acknowledgment from a
    prior, since-reset instance can never satisfy a new one. Requires
    an accepted, open commitment; visiting the clerk before accepting
    produces no completion evidence.
    """
    scenario = get_scenario(commitment_type)
    if scenario is None or scenario.clerk_npc_id != clerk_npc_id:
        return LifecycleResult(False, reason=f"{clerk_npc_id!r} has no clerk role for {commitment_type!r}")

    commitment = _find_open_commitment(actor, commitment_type)
    if commitment is None:
        return LifecycleResult(False, reason="no open commitment of this type to report")

    acks = _acks(actor)
    if commitment["commitment_id"] in acks:
        return LifecycleResult(False, reason="already acknowledged")

    acks[commitment["commitment_id"]] = {
        "clerk_npc_id": clerk_npc_id,
        "player_dbref": actor.dbref,
        "recorded_at": _now_iso(),
    }
    _save_acks(actor, acks)
    return LifecycleResult(True, commitment_id=commitment["commitment_id"])


def fulfill_commitment(actor, commitment_type: str, holder_npc_id: str) -> LifecycleResult:
    """
    The holder NPC's role: checks for a matching clerk acknowledgment
    - tied to this exact commitment instance, this player, and the
    scenario's actual clerk - before fulfilling. A player merely
    claiming the report was filed is not evidence; only a real
    acknowledgment record is.
    """
    scenario = get_scenario(commitment_type)
    if scenario is None or scenario.holder_npc_id != holder_npc_id:
        return LifecycleResult(False, reason=f"{holder_npc_id!r} has no holder role for {commitment_type!r}")

    commitment = _find_open_commitment(actor, commitment_type)
    if commitment is None:
        return LifecycleResult(False, reason="no open commitment of this type to fulfill")

    ack = _acks(actor).get(commitment["commitment_id"])
    if ack is None or ack["clerk_npc_id"] != scenario.clerk_npc_id or ack["player_dbref"] != actor.dbref:
        return LifecycleResult(False, reason="no matching clerk acknowledgment on record")

    commitment["status"] = STATUS_FULFILLED
    commitments = _commitments(actor)
    commitments[commitment["commitment_id"]] = commitment
    _save_commitments(actor, commitments)
    return LifecycleResult(True, commitment_id=commitment["commitment_id"])


def get_state_summary(actor, commitment_type: str) -> str:
    """
    One line of plain engine fact, for prompt injection - deliberately
    vague about internals a given NPC shouldn't see (see
    commitment_context_for for the per-role filtering on top of this).
    """
    commitment = _find_open_commitment(actor, commitment_type)
    if commitment:
        acked = commitment["commitment_id"] in _acks(actor)
        return "open, acknowledged by the records clerk" if acked else "open, not yet acknowledged"
    if _offers(actor).get(commitment_type):
        return "offered, awaiting the player's answer"
    for commitment in _commitments(actor).values():
        if commitment["commitment_type"] == commitment_type and commitment["status"] == STATUS_FULFILLED:
            return "fulfilled"
    return "not offered"


def commitment_context_for(npc_id: str, npc_actions: list, actor) -> str | None:
    """
    A fresh per-turn system message giving an NPC only the engine
    state its own role in a scenario covers - mirrors
    world.actions.quest_context_for's reasoning, and exists
    specifically to avoid repeating that function's scoping bug
    (CLAUDE.md hard rule 5): the clerk never needs, and never gets,
    the holder's private offer/decline history, only whether there's
    something open to report right now.
    """
    if not COMMITMENT_ACTIONS & set(npc_actions):
        return None

    lines = []
    for scenario in SCENARIOS.values():
        state = get_state_summary(actor, scenario.commitment_type)
        if npc_id == scenario.holder_npc_id:
            lines.append(
                f"Engine state for the {scenario.commitment_type!r} commitment with this player "
                f"(your side): {state}."
            )
        elif npc_id == scenario.clerk_npc_id:
            reportable = state in ("open, not yet acknowledged", "open, acknowledged by the records clerk")
            clerk_state = state if reportable else "no open commitment to report"
            lines.append(
                f"Engine state for the {scenario.commitment_type!r} commitment with this player: "
                f"{clerk_state}."
            )
    return " ".join(lines) if lines else None


def hint_pose_for(npc_id: str, actor) -> str | None:
    """
    A deterministic, per-looker alternative to an NPC's static
    ambient_pose: if this NPC is the holder of a commitment this
    player hasn't been offered yet, return its authored hint pose
    instead - so a player who never asks the right question still
    sees *something* ("Tarin Os is here, frowning over a shipment
    manifest.") the moment they walk in, rather than the errand only
    surfacing if they happen to ask about it. Returns None once it's
    been offered (whatever the answer), so the hint doesn't linger
    after it's served its purpose.
    """
    for scenario in SCENARIOS.values():
        if npc_id != scenario.holder_npc_id or not scenario.holder_hint_pose:
            continue
        if get_state_summary(actor, scenario.commitment_type) == "not offered":
            return scenario.holder_hint_pose
    return None


def reset_commitment(actor, commitment_type: str) -> dict:
    """
    Builder-only full reset of one commitment type for one player:
    clears any pending offer and any open/fulfilled instance plus its
    acknowledgment. Returns a snapshot of what was cleared, for the
    admin command to report and log. A stale acknowledgment can never
    fulfill a later instance regardless (acks are keyed by the old
    commitment_id, which no longer exists once its commitment is
    removed here) - this just also keeps per-player storage from
    accumulating dead entries.
    """
    commitments = _commitments(actor)
    acks = _acks(actor)
    offers = _offers(actor)

    had_offer = bool(offers.pop(commitment_type, False))
    removed_ids = [
        cid for cid, commitment in commitments.items() if commitment["commitment_type"] == commitment_type
    ]
    previous_statuses = [commitments[cid]["status"] for cid in removed_ids]
    for cid in removed_ids:
        commitments.pop(cid, None)
        acks.pop(cid, None)

    _save_offers(actor, offers)
    _save_commitments(actor, commitments)
    _save_acks(actor, acks)

    return {"had_offer": had_offer, "previous_statuses": previous_statuses}
