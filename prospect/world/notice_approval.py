"""
Phase 3 "The Unverified Notice" (docs/phase3-scope.md,
docs/phase3-unverified-notice-design.md): Tarin believes a notice
posted at the Civic Office carries the approval mark it needs, but he
hasn't checked it himself. Veska can - genuinely confirming or
contradicting his claim against a real, engine-tracked fact, not a
model-judged credibility call (CLAUDE.md hard rule 2).

This module owns that per-player fact (`approval_mark_present`), which
of the two mutually-exclusive resolutions actually happened for a
given fulfilled commitment instance, whether the notice is still
publicly displayed, and - mirroring world/rumors.py's "has Mara been
told" pattern exactly - whether Tarin has actually been informed of
the outcome yet. world/commitments.py has no idea any of this exists;
it only knows a scenario may supply a proposer_knowledge_projector,
generically.
"""

from world.commitments import STATUS_FULFILLED, get_fulfilled_commitment

NOTICE_KEY = "notice_approval"

RESOLUTION_VERIFIED = "verified_posted"
RESOLUTION_WITHDRAWN = "withdrawn"


def _default_state() -> dict:
    return {
        "approval_mark_present": None,  # None = not yet generated
        "resolutions": {},  # commitment_id -> RESOLUTION_*
        "notice_displayed": True,
        "informed_commitment_ids": [],
    }


def _state(actor) -> dict:
    return actor.attributes.get(NOTICE_KEY, default=_default_state())


def _save_state(actor, state: dict) -> None:
    actor.attributes.add(NOTICE_KEY, state)


def approval_mark_present(actor) -> bool:
    """
    Whether the actual posted notice carries the required approval
    mark - generated once per player (default True, the ordinary
    case where Tarin's belief turns out correct), stable afterward
    until a builder reset or an explicit override. The model never
    sees this value; world/actions.py's verify_notice validator only
    relays the boolean result of checking it, never the fact itself.
    """
    state = _state(actor)
    if state["approval_mark_present"] is None:
        state["approval_mark_present"] = True
        _save_state(actor, state)
    return state["approval_mark_present"]


def set_approval_mark_present(actor, present: bool) -> None:
    """
    Test/eval-fixture-only override, the same way other scenarios'
    negative fixtures are built (e.g. world/noticeboard.py's tests
    poke REVISION_KEY directly) - not reachable through any
    conversational action.
    """
    state = _state(actor)
    state["approval_mark_present"] = present
    _save_state(actor, state)


def record_resolution(actor, commitment_id: str, resolution: str) -> None:
    """
    Records which of the two mutually-exclusive paths actually
    fulfilled this commitment instance - world/commitments.py's own
    fulfill_commitment_with_precondition only stores fulfilled_by_npc_id,
    not which action did it, since it has no idea a "verify vs
    withdraw" distinction exists. Withdrawal also flips notice_displayed
    to False here - the real, observable effect on public-display
    state the design calls for, not just a different completion message.
    """
    state = _state(actor)
    state["resolutions"][commitment_id] = resolution
    if resolution == RESOLUTION_WITHDRAWN:
        state["notice_displayed"] = False
    _save_state(actor, state)


def get_resolution(actor, commitment_id: str) -> str | None:
    return _state(actor)["resolutions"].get(commitment_id)


def notice_displayed(actor) -> bool:
    return _state(actor)["notice_displayed"]


def is_informed_of(actor, commitment_id: str) -> bool:
    return commitment_id in _state(actor)["informed_commitment_ids"]


def mark_informed(actor, commitment_id: str) -> None:
    state = _state(actor)
    if commitment_id not in state["informed_commitment_ids"]:
        state["informed_commitment_ids"].append(commitment_id)
    _save_state(actor, state)


def project_tarin_notice_knowledge(actor, state: str) -> str:
    """
    world/commitments.py's proposer_knowledge_projector for
    "unverified_notice". Mirrors world/rumors.py's
    project_mara_parcel_knowledge exactly: only intercepts "fulfilled",
    holding Tarin's own view at "open" (an ongoing matter he's still
    waiting to hear about) until the specific fulfilled commitment_id
    has actually been reported to him via report_notice_outcome -
    looked up fresh each time, never cached, so a reset can't leave a
    stale "fulfilled" view behind either.
    """
    if state != STATUS_FULFILLED:
        return state
    commitment = get_fulfilled_commitment(actor, "unverified_notice")
    if commitment is None:
        return state
    if is_informed_of(actor, commitment["commitment_id"]):
        return state
    return "open"


def project_veska_notice_knowledge(actor, state: str) -> str:
    """
    world/commitments.py's holder_knowledge_projector for
    "unverified_notice". Veska is the one who actually performs
    verify_notice or withdraw_notice, so unlike Tarin's proposer-side
    projector above (which deliberately hides the outcome until
    reported), she must always see the real resolution exactly -
    confirmed live (2026-10-14) that without this, "fulfilled" alone
    gave her nothing to answer "which one did I do?" with, and she
    hallucinated withdrawn when the real resolution was verified_posted.
    """
    if state != STATUS_FULFILLED:
        return state
    commitment = get_fulfilled_commitment(actor, "unverified_notice")
    if commitment is None:
        return state
    resolution = get_resolution(actor, commitment["commitment_id"])
    if resolution == RESOLUTION_VERIFIED:
        return "fulfilled - you verified the approval mark and left the notice up"
    if resolution == RESOLUTION_WITHDRAWN:
        return "fulfilled - you withdrew/took down the notice"
    return state


def reset_notice(actor) -> dict:
    """
    Builder-only reset (commands/admin.py's CmdResetCommitment folds
    this in alongside its other per-scenario cleanup, same as 2E's
    reset_rumor/reset_reputation). Returns a snapshot of what was
    cleared, for logging. Idempotent.
    """
    previous = _state(actor)
    _save_state(actor, _default_state())
    return {
        "previous_approval_mark_present": previous["approval_mark_present"],
        "previous_resolutions": dict(previous["resolutions"]),
        "previous_notice_displayed": previous["notice_displayed"],
        "previous_informed_commitment_ids": list(previous["informed_commitment_ids"]),
    }
