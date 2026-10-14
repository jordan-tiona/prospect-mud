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
from typing import Callable, Optional

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
    "accept_handoff",
    # Phase 3 ("The Unverified Notice"): Veska's two scenario-specific
    # fulfilling actions, parallel to accept_handoff's role for the
    # parcel scenario - without this, commitment_context_for would
    # never inject "unverified_notice" state for her at all, since
    # neither action name is report_commitment_outcome/accept_handoff.
    "verify_notice",
    "withdraw_notice",
}


@dataclass
class ScenarioConfig:
    commitment_type: str
    # Whose validated action actually *completes* this commitment -
    # via fulfill_commitment's clerk-acknowledgment check, or
    # fulfill_commitment_with_precondition's structured-fact check.
    # In 2B this was also the NPC who proposes/accepts/declines; 2C
    # (docs/phase2c-misdelivered-parcel-proposal.md) is the first
    # scenario where those are different NPCs (Mara proposes, Tarin
    # or Veska completes), which is why proposer_npc_id exists below.
    holder_npc_id: str
    # Other NPCs who can *also* fulfill this commitment, besides
    # holder_npc_id - the 2C parcel redesign (2026-10-13): rather than
    # the player naming a destination in conversation (unreliable, see
    # that redesign's rationale), either Tarin or Veska can complete
    # the same single commitment, whichever one the player actually
    # reaches first. Empty for a single-holder scenario like 2B's.
    alt_holder_npc_ids: tuple = ()
    # The NPC who records corroborating evidence the holder checks
    # before fulfilling (fulfill_commitment's pattern). Leave "" for a
    # scenario with no clerk role at all - commitment_context_for and
    # get_state_summary skip the clerk-specific wording in that case.
    clerk_npc_id: str = ""
    # Who proposes/accepts/declines the offer. "" means "same as
    # holder_npc_id" - 2B's original shape, unchanged for that
    # scenario without having to touch its config entry.
    proposer_npc_id: str = ""
    # Shown in place of the holder's normal ambient_pose, only to a
    # player who hasn't been offered this commitment yet - a
    # deterministic discoverability hint that doesn't depend on
    # getting the right question past the model (see
    # typeclasses.rooms.Room's _presence_line). Flavor text, same
    # register as the scenario description below - not new setting
    # lore, just this NPC's situational demeanor.
    holder_hint_pose: str = ""
    # Phase 3 ("The Unverified Notice"): the proposer-side equivalent
    # of holder_hint_pose, for a scenario (like this one) where the
    # proposer isn't also the holder - deliver_parcel hit this same
    # asymmetry and solved it with a physical object instead (Mara had
    # one available); this scenario doesn't, so Tarin needs his own
    # passive cue once he's actually eligible to raise it. Same
    # "not offered" gating as holder_hint_pose, via hint_pose_for below.
    proposer_hint_pose: str = ""
    # Phase 3: an optional prerequisite - this commitment_type can't be
    # offered (and its proposer_hint_pose won't show) until a different
    # commitment_type is already STATUS_FULFILLED for this player. ""
    # means no prerequisite, the default for every existing scenario.
    # Checked in propose_commitment and hint_pose_for, not just left to
    # the proposer's own persona wording - CLAUDE.md hard rule 2 means
    # the engine enforces this, not just hopes the model doesn't offer
    # it early.
    requires_fulfilled_commitment_type: str = ""
    # Narration templates for world/actions.py's validators to render
    # (ActionResult.narration - design-bible 16.5 step 4's "shown to
    # the player together with the narrated outcome"). Formatted with
    # .format(npc=npc.key, actor=actor.key). Authored per scenario so
    # this doesn't read as one identical mechanical line regardless of
    # what's actually happening; the defaults below are a generic
    # fallback for a scenario that hasn't been given its own wording.
    propose_narration: str = "{npc} brings the matter up and offers it to {actor}."
    accept_narration: str = "{npc} takes {actor} up on the offer to help."
    decline_narration: str = "{npc} accepts that {actor} isn't able to help with this."
    ack_narration: str = "{npc} records {actor}'s report."
    fulfill_narration: str = "{npc} confirms the matter is settled."
    # Phase 2E (docs/phase2e-word-gets-around-design.md): lets a
    # scenario keep its proposer from automatically learning its own
    # commitment's real fulfillment the instant a *different* NPC
    # fulfills it - deliver_parcel's Mara doesn't find out the parcel
    # arrived until a separate validated action tells her, even though
    # the commitment itself is already STATUS_FULFILLED underneath.
    # Takes (actor, state) and returns the state string to show the
    # proposer instead - commitment_context_for applies this only on
    # the proposer's own line, never the holder's, so Tarin/Veska still
    # see their own real fulfillment accurately. None (the default)
    # means no projection - every other scenario is unaffected. This
    # module has no idea what Mara or a parcel are; the function itself
    # lives in whatever scenario-specific module needs it (world/
    # rumors.py for deliver_parcel), same separation of concerns
    # fulfill_commitment_with_precondition keeps from a parcel's actual
    # possession check.
    proposer_knowledge_projector: Optional[Callable[[object, str], str]] = None
    # The holder-side equivalent of proposer_knowledge_projector, for a
    # scenario where "fulfilled" alone isn't enough for the holder to
    # answer later questions about what actually happened - e.g.
    # unverified_notice, where Veska is the one who performs either
    # verify_notice or withdraw_notice, and "fulfilled" alone doesn't
    # say which. Confirmed live (2026-10-14): without this, Veska had
    # no engine-grounded fact to answer "which one did I do?" after the
    # tool-call turn itself, and hallucinated the wrong one (claimed
    # she'd withdrawn the notice when she'd actually verified it) - a
    # real narrated contradiction of the engine's own authoritative
    # state, not just a wording quirk, since nothing else in the
    # pipeline ever told her which fact was true. None (the default)
    # means no projection - commitment_context_for then just shows the
    # holder its ordinary unprojected state, same as every scenario
    # before this one.
    holder_knowledge_projector: Optional[Callable[[object, str], str]] = None

    @property
    def effective_proposer_npc_id(self) -> str:
        return self.proposer_npc_id or self.holder_npc_id

    @property
    def holder_npc_ids(self) -> tuple:
        return (self.holder_npc_id, *self.alt_holder_npc_ids)


# The authored scenarios for this prototype. Scenario content (who,
# why) belongs to the project owner; this config only wires the
# engine roles.
SCENARIOS = {
    # docs/phase2b-records-discrepancy-proposal.md's "Approved owner
    # scenario".
    "discrepancy_report": ScenarioConfig(
        commitment_type="discrepancy_report",
        holder_npc_id="tarin_os",
        clerk_npc_id="veska_renn",
        holder_hint_pose="frowning over a shipment manifest",
        propose_narration="{npc} brings up the mismatched manifest and asks {actor} to help sort it out.",
        accept_narration="{npc} is glad {actor} is willing to take this to the Civic Office.",
        ack_narration="{npc} notes the report in {actor}'s file.",
        fulfill_narration="{npc} marks the discrepancy as settled, now that it's on record.",
    ),
    # docs/phase2c-misdelivered-parcel-proposal.md's "Scenario Premise",
    # redesigned 2026-10-13: Mara proposes a single generic errand, not
    # a destination to pick in conversation - either Tarin or Veska can
    # complete it, whichever one the player actually brings the parcel
    # to. That NPC's own fulfillment (see fulfill_commitment_with_
    # precondition's holder_npc_ids check) is what decides the route,
    # not a verbal commitment extracted by Mara beforehand.
    "deliver_parcel": ScenarioConfig(
        commitment_type="deliver_parcel",
        holder_npc_id="tarin_os",
        alt_holder_npc_ids=("veska_renn",),
        proposer_npc_id="mara_voss",
        propose_narration="{npc} explains the mixed-up parcel and asks {actor} to help get it where it belongs.",
        accept_narration="{npc} hands {actor} the parcel.",
        decline_narration="{npc} accepts that {actor} can't help with the parcel right now.",
        fulfill_narration="{npc} takes the parcel from {actor} and sees it's properly accounted for.",
        # Phase 2E: wired below, after import, to avoid a circular
        # import (world/rumors.py imports from this module).
    ),
    # docs/phase2-quest-prototype-design.md §14 / docs/phase2d-
    # noticeboard-check-proposal.md: Mara proposes/closes, Iri
    # corroborates - but unlike discrepancy_report's unconditional
    # acknowledgment, Iri's check is gated on a real structured fact
    # (world/noticeboard.py's stored per-player revision), via
    # record_acknowledgment_with_precondition below. This is the
    # first scenario where corroboration can genuinely fail.
    "verify_display_revision": ScenarioConfig(
        commitment_type="verify_display_revision",
        holder_npc_id="mara_voss",
        clerk_npc_id="iri_vael",
        holder_hint_pose="glancing at the café's information display",
        propose_narration="{npc} asks {actor} to confirm the café's display is showing the current revision.",
        accept_narration="{npc} is glad {actor} is willing to check the number with the Civic Office.",
        ack_narration="{npc} confirms the revision {actor} reported matches the record.",
        fulfill_narration="{npc} is glad to hear the display's revision checked out.",
    ),
    # docs/phase3-scope.md / docs/phase3-unverified-notice-design.md:
    # "The Unverified Notice." Tarin proposes (once his own
    # discrepancy_report is fulfilled - requires_fulfilled_commitment_
    # type below), Veska resolves it one of two mutually-exclusive ways
    # via world/actions.py's verify_notice/withdraw_notice, both routed
    # through fulfill_commitment_with_precondition - whichever fires
    # first leaves no open commitment for the other to find, so mutual
    # exclusion falls out of existing code rather than needing new
    # cross-type bookkeeping. No clerk role, same shape as deliver_parcel.
    "unverified_notice": ScenarioConfig(
        commitment_type="unverified_notice",
        holder_npc_id="veska_renn",
        proposer_npc_id="tarin_os",
        requires_fulfilled_commitment_type="discrepancy_report",
        proposer_hint_pose="looking a little uneasy about something posted at the Civic Office",
        propose_narration="{npc} mentions the posted notice and asks {actor} to help settle whether it's right.",
        accept_narration="{npc} is glad {actor} is willing to take it up with Veska.",
        decline_narration="{npc} accepts that {actor} can't look into the notice right now.",
        fulfill_narration="{npc} will hear how it went once {actor} tells him.",
        # Phase 3: wired below, after import, to avoid a circular
        # import (world/notice_approval.py imports from this module) -
        # same workaround as deliver_parcel's projector.
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


def _prerequisite_met(actor, scenario: "ScenarioConfig") -> bool:
    """Phase 3: True when scenario has no requires_fulfilled_commitment_
    type, or the named prerequisite commitment_type is already
    STATUS_FULFILLED for this player. Shared by propose_commitment and
    hint_pose_for so the engine enforces this, not just persona wording."""
    if not scenario.requires_fulfilled_commitment_type:
        return True
    return get_fulfilled_commitment(actor, scenario.requires_fulfilled_commitment_type) is not None


def propose_commitment(actor, commitment_type: str) -> LifecycleResult:
    """
    The holder NPC offers the errand. Only records that an offer is
    pending, so accept/decline have something to act on - dropped if
    one's already open or already pending, so re-offering mid-errand
    can't spawn a second instance.
    """
    scenario = get_scenario(commitment_type)
    if scenario is None:
        return LifecycleResult(False, reason=f"unknown commitment_type: {commitment_type!r}")
    if not _prerequisite_met(actor, scenario):
        return LifecycleResult(False, reason="prerequisite commitment not yet fulfilled")
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
        "fulfilled_by_npc_id": None,
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


def record_acknowledgment_with_precondition(
    actor, commitment_type: str, clerk_npc_id: str, precondition_ok: bool
) -> LifecycleResult:
    """
    Alternative to record_acknowledgment for a scenario where
    corroboration is a real structured-fact check (docs/phase2-quest-
    prototype-design.md §14's "genuine corroboration") rather than
    2B's unconditional "they brought it to me, that's enough." The
    caller (world/actions.py) computes precondition_ok from real game
    state (e.g. world/noticeboard.py's stored revision) - this
    function has no idea what that fact actually is, same separation
    of concerns fulfill_commitment_with_precondition keeps from the
    parcel's possession check.

    A false precondition changes nothing: no ack is recorded, the
    commitment stays open, and a later attempt (with a corrected
    value) remains possible - a wrong guess must never permanently
    poison the commitment.
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

    if not precondition_ok:
        return LifecycleResult(False, reason="reported value did not match")

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
    if scenario is None or holder_npc_id not in scenario.holder_npc_ids:
        return LifecycleResult(False, reason=f"{holder_npc_id!r} has no holder role for {commitment_type!r}")

    commitment = _find_open_commitment(actor, commitment_type)
    if commitment is None:
        return LifecycleResult(False, reason="no open commitment of this type to fulfill")

    ack = _acks(actor).get(commitment["commitment_id"])
    if ack is None or ack["clerk_npc_id"] != scenario.clerk_npc_id or ack["player_dbref"] != actor.dbref:
        return LifecycleResult(False, reason="no matching clerk acknowledgment on record")

    commitment["status"] = STATUS_FULFILLED
    commitment["fulfilled_by_npc_id"] = holder_npc_id
    commitments = _commitments(actor)
    commitments[commitment["commitment_id"]] = commitment
    _save_commitments(actor, commitments)
    return LifecycleResult(True, commitment_id=commitment["commitment_id"])


def get_fulfilled_commitment(actor, commitment_type: str) -> dict | None:
    """
    Public lookup, parallel to get_open_commitment_id, for anything
    that needs to know *which* commitment instance was fulfilled and
    who actually fulfilled it (e.g. world/rumors.py checking a reported
    recipient against the real fulfilled_by_npc_id, or projecting the
    proposer's own knowledge of it). At most one fulfilled instance of
    a given type can exist for a player at a time in this prototype -
    reset_commitment removes the record entirely rather than leaving a
    second one behind.
    """
    for commitment in _commitments(actor).values():
        if commitment["commitment_type"] == commitment_type and commitment["status"] == STATUS_FULFILLED:
            return commitment
    return None


def get_open_commitment_id(actor, commitment_type: str) -> str | None:
    """
    Public lookup for world/actions.py to tie a physical object (e.g.
    a Parcel) to the exact open commitment *instance*, the same way
    record_acknowledgment ties an acknowledgment to one - never to the
    type in the abstract, so a stale object from a reset or prior
    instance can't satisfy a new one.
    """
    commitment = _find_open_commitment(actor, commitment_type)
    return commitment["commitment_id"] if commitment else None


def fulfill_commitment_with_precondition(
    actor, commitment_type: str, holder_npc_id: str, precondition_ok: bool
) -> LifecycleResult:
    """
    Alternative to fulfill_commitment for a scenario where completion
    is a direct, immediately-checkable physical fact (docs/phase2c-
    misdelivered-parcel-proposal.md §2's "genuine corroboration")
    rather than 2B's separate clerk-acknowledgment step. The caller
    (world/actions.py) computes precondition_ok from real game state
    (e.g. a Parcel object's actual location) - this function has no
    idea what a parcel is, same separation of concerns fulfill_commitment
    keeps from the module-exchange quest's item logic.

    Reusable for any future scenario shaped this way, not just the
    parcel one: nothing here names a parcel. Also reusable for a
    scenario with more than one valid holder (holder_npc_ids) - the
    2C parcel redesign's "whichever NPC the player reaches first"
    shape: the open commitment itself (STATUS_OPEN, checked above) is
    what the second NPC's later attempt finds missing, so no separate
    cross-holder exclusion logic is needed.
    """
    scenario = get_scenario(commitment_type)
    if scenario is None or holder_npc_id not in scenario.holder_npc_ids:
        return LifecycleResult(False, reason=f"{holder_npc_id!r} has no holder role for {commitment_type!r}")

    commitment = _find_open_commitment(actor, commitment_type)
    if commitment is None:
        return LifecycleResult(False, reason="no open commitment of this type to fulfill")

    if not precondition_ok:
        return LifecycleResult(False, reason="required precondition not met")

    commitment["status"] = STATUS_FULFILLED
    commitment["fulfilled_by_npc_id"] = holder_npc_id
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
        scenario = get_scenario(commitment_type)
        if not scenario.clerk_npc_id:
            # No clerk role in this scenario - "acknowledged" would be
            # a fact this commitment_type never produces.
            return "open"
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
        if npc_id == scenario.effective_proposer_npc_id:
            if scenario.proposer_knowledge_projector is not None:
                state = scenario.proposer_knowledge_projector(actor, state)
            lines.append(
                f"Engine state for the {scenario.commitment_type!r} commitment with this player "
                f"(your side): {state}."
            )
        elif npc_id in scenario.holder_npc_ids:
            if scenario.holder_knowledge_projector is not None:
                state = scenario.holder_knowledge_projector(actor, state)
            lines.append(
                f"Engine state for the {scenario.commitment_type!r} commitment with this player "
                f"(your side): {state}."
            )
        elif scenario.clerk_npc_id and npc_id == scenario.clerk_npc_id:
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
        if npc_id in scenario.holder_npc_ids and scenario.holder_hint_pose:
            if get_state_summary(actor, scenario.commitment_type) == "not offered":
                return scenario.holder_hint_pose
        # Phase 3: the proposer-side equivalent, for a scenario where
        # the proposer isn't also the holder (deliver_parcel solved
        # this with a physical object instead; this one doesn't have
        # one). Also gated on the prerequisite, so the pose can't leak
        # eligibility the player hasn't actually earned yet.
        if (
            npc_id == scenario.effective_proposer_npc_id
            and scenario.proposer_hint_pose
            and _prerequisite_met(actor, scenario)
            and get_state_summary(actor, scenario.commitment_type) == "not offered"
        ):
            return scenario.proposer_hint_pose
    return None


def known_commitment_types_for(actor) -> set:
    """
    Every commitment_type the admin `resetcommitment` command should
    consider for this player - the currently-authored SCENARIOS, *and*
    whatever's actually in this player's own stored data, even a type
    that's since been renamed or removed from SCENARIOS entirely (e.g.
    the 2026-10-13 parcel redesign's old "deliver_parcel_to_tarin").
    Without this, a reset silently can't see - and can never clear -
    a commitment filed under a type name the engine no longer knows
    about, leaving it permanently stuck.
    """
    return set(SCENARIOS) | set(_offers(actor)) | {
        c["commitment_type"] for c in _commitments(actor).values()
    }


def open_commitment_ids(actor) -> set:
    """Every commitment_id currently STATUS_OPEN for this player,
    across all commitment types - for world/actions.py to check a
    carried Parcel (or any future scenario's physical object) against,
    so a reset or a renamed/removed commitment_type doesn't leave an
    orphaned, undisposable object with nothing left pointing to it."""
    return {c["commitment_id"] for c in _commitments(actor).values() if c["status"] == STATUS_OPEN}


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
