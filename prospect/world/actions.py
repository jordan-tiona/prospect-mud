"""
Tool layer and validator (design-bible 16.5; CLAUDE.md hard rule 2).

The model can only *propose* an action by name plus arguments; it
never changes game state directly. `validate_and_apply` is the one
place that checks a proposal against authoritative state (the NPC's
declared permissions, stock, the real room graph) and either applies
it or drops it. Dropped calls are never "fixed up" into something
valid - the caller (step 7's talk command) narrates the drop as the
NPC being unable to help, not as a corrected action.

Phase 1 gives each prototype NPC exactly one action, per design-bible
13.5: `serve_drink` (Mara), `hand_over_item` (Tarin), `give_directions`
(Iri).
"""

import unicodedata
from dataclasses import dataclass

from world.build_rooms import BUILD_TAG_CATEGORY as ROOM_TAG_CATEGORY
from world.build_rooms import ROOMS as NEIGHBORHOOD_ROOMS
from world.commitments import SCENARIOS
from world.commitments import accept_commitment as _accept_commitment
from world.commitments import decline_commitment as _decline_commitment
from world.commitments import fulfill_commitment as _fulfill_commitment
from world.commitments import fulfill_commitment_with_precondition as _fulfill_commitment_with_precondition
from world.commitments import get_fulfilled_commitment as _get_fulfilled_commitment
from world.commitments import get_open_commitment_id as _get_open_commitment_id
from world.commitments import propose_commitment as _propose_commitment
from world.commitments import record_acknowledgment as _record_acknowledgment
from world.commitments import record_acknowledgment_with_precondition as _record_acknowledgment_with_precondition
from world.notice_approval import RESOLUTION_VERIFIED, RESOLUTION_WITHDRAWN
from world.notice_approval import approval_mark_present as _approval_mark_present
from world.notice_approval import get_resolution as _get_notice_resolution
from world.notice_approval import is_informed_of as _is_informed_of_notice
from world.notice_approval import mark_informed as _mark_notice_informed
from world.notice_approval import project_tarin_notice_knowledge as _project_tarin_notice_knowledge
from world.notice_approval import project_veska_notice_knowledge as _project_veska_notice_knowledge
from world.notice_approval import record_resolution as _record_notice_resolution
from world.npc_memory import remember_fact as _remember_fact
from world.npc_profile import parse_persona
from world.reputation import adjust_reputation as _adjust_reputation
from world.rumors import has_reputation_credit as _has_reputation_credit
from world.rumors import is_informed_of as _is_informed_of
from world.rumors import mark_informed as _mark_informed
from world.rumors import mark_reputation_credited as _mark_reputation_credited
from world.rumors import project_mara_parcel_knowledge as _project_mara_parcel_knowledge

# Phase 2E/3: wired here, not in world/commitments.py's SCENARIOS
# literal, since world/rumors.py and world/notice_approval.py both
# import from world/commitments.py and this avoids a circular import.
# SCENARIOS is the same dict object commitments.py's own functions
# read from, so mutating this field in place is visible everywhere,
# not just through this module.
SCENARIOS["deliver_parcel"].proposer_knowledge_projector = _project_mara_parcel_knowledge
SCENARIOS["unverified_notice"].proposer_knowledge_projector = _project_tarin_notice_knowledge
SCENARIOS["unverified_notice"].holder_knowledge_projector = _project_veska_notice_knowledge


@dataclass
class ActionResult:
    applied: bool
    # Shown to the player as the narrated outcome of a valid action
    # (design-bible 16.5 step 4). Empty when the call was dropped.
    narration: str
    # Why a call was dropped. For logs/debugging, not necessarily
    # shown to the player verbatim.
    reason: str = ""


def validate_and_apply(npc, actor, action_name: str, arguments: dict) -> ActionResult:
    """
    The engine validator. Checks that `action_name` is one of this
    NPC's declared permitted actions before running its specific
    validator, so an NPC can't be talked into an action its persona
    never granted it.
    """
    arguments = arguments or {}

    profile = parse_persona(npc.db.npc_id)
    if action_name not in profile.actions:
        return ActionResult(
            applied=False,
            narration="",
            reason=f"'{action_name}' is not a permitted action for {profile.npc_id}.",
        )

    validator = _ACTION_VALIDATORS.get(action_name)
    if validator is None:
        return ActionResult(
            applied=False,
            narration="",
            reason=f"No validator implemented for action '{action_name}'.",
        )

    return validator(npc, actor, arguments)


def _validate_serve_drink(npc, actor, arguments: dict) -> ActionResult:
    drink_type = arguments.get("drink_type")
    if drink_type not in ("hot", "cold"):
        return ActionResult(False, "", reason=f"invalid drink_type: {drink_type!r}")
    return ActionResult(True, f"{npc.key} serves {actor.key} a {drink_type} drink.")


# Starting stock for a hand_over_item NPC (currently just Tarin). Also
# used by commands/admin.py's builder-only `restock` testing command,
# since a finite stock that never refills makes repeated testing run
# dry - there's no in-fiction restocking action (phase 1 keeps each
# NPC to one action, per CLAUDE.md), just this manual admin reset.
DEFAULT_STOCK = {"spare part": 3, "hand tool": 3}


def _validate_hand_over_item(npc, actor, arguments: dict) -> ActionResult:
    item_type = arguments.get("item_type")
    if item_type not in ("spare part", "hand tool"):
        return ActionResult(False, "", reason=f"invalid item_type: {item_type!r}")

    stock = npc.db.stock
    if stock is None:
        stock = dict(DEFAULT_STOCK)

    if stock.get(item_type, 0) <= 0:
        npc.db.stock = stock
        return ActionResult(False, "", reason=f"out of stock: {item_type}")

    stock[item_type] -= 1
    npc.db.stock = stock
    return ActionResult(True, f"{npc.key} hands {actor.key} a {item_type}.")


# Phase 2's first quest (design-bible 13.5; docs/phase2-quest-prototype-
# design.md): Mara's heating unit needs a faulty module taken to Tarin
# and swapped for a working one. State lives on the *player* (`actor`),
# not either NPC, since it's the player's errand - and on `db`, not
# `ndb`, since unlike phase 1's conversation history this is meant to
# survive a reload (design-bible 13.5's "persistent per-player memory"
# half of phase 2, not just "a simple quest").
QUEST_MODULE_EXCHANGE_KEY = "quest_module_exchange"
QUEST_MODULE_EXCHANGE_STATES = (
    "not_started",
    "accepted",
    "has_faulty_module",
    "has_replacement_module",
    "completed",
)


def get_quest_state(actor) -> str:
    return actor.attributes.get(QUEST_MODULE_EXCHANGE_KEY, default="not_started")


def _set_quest_state(actor, state: str) -> None:
    actor.attributes.add(QUEST_MODULE_EXCHANGE_KEY, state)


def _validate_quest_step(actor, required_state: str, next_state: str, narration: str) -> ActionResult:
    """
    Shared precondition check for every module-exchange step: each one
    only fires from its own required prior state, so a repeated or
    out-of-order call (the player asking twice, or asking Tarin before
    ever visiting Mara) is dropped rather than silently re-applied or
    skipped ahead.
    """
    state = get_quest_state(actor)
    if state != required_state:
        return ActionResult(
            False, "", reason=f"quest step requires state {required_state!r}, actor is at {state!r}"
        )
    _set_quest_state(actor, next_state)
    return ActionResult(True, narration)


def _validate_accept_help(npc, actor, arguments: dict) -> ActionResult:
    return _validate_quest_step(
        actor, "not_started", "accepted", f"{npc.key} agrees to let {actor.key} help with the heating unit."
    )


def _validate_give_faulty_module(npc, actor, arguments: dict) -> ActionResult:
    return _validate_quest_step(
        actor,
        "accepted",
        "has_faulty_module",
        f"{npc.key} hands {actor.key} the faulty temperature-control module.",
    )


def _validate_exchange_module(npc, actor, arguments: dict) -> ActionResult:
    return _validate_quest_step(
        actor,
        "has_faulty_module",
        "has_replacement_module",
        f"{npc.key} inspects the module and hands {actor.key} a working replacement.",
    )


def _validate_accept_replacement(npc, actor, arguments: dict) -> ActionResult:
    return _validate_quest_step(
        actor,
        "has_replacement_module",
        "completed",
        f"{npc.key} takes the replacement module from {actor.key} and thanks them.",
    )


# Which actions touch the module-exchange quest, so the prompt-builder
# step (commands/say.py's engage_npc) knows which NPCs need the
# player's current quest state injected as fresh, per-turn context -
# engine truth the NPC reacts to, not something it has to remember
# correctly from its own conversation history.
QUEST_MODULE_EXCHANGE_ACTIONS = {
    "accept_help",
    "give_faulty_module",
    "exchange_module",
    "accept_replacement",
}


# Which quest states each action's own NPC actually has a reason to
# know, per CLAUDE.md hard rule 5 (each NPC sees only its own
# knowledge scope). Mara's actions span the whole errand (she's the
# one who proposes it and takes the replacement back); Tarin only
# becomes a party to it once the module physically reaches him -
# his persona already claims no knowledge of the earlier stages, so
# the engine state fed to him shouldn't contradict that.
QUEST_STATE_VISIBILITY = {
    "accept_help": {"not_started", "accepted"},
    "give_faulty_module": {"accepted", "has_faulty_module"},
    "accept_replacement": {"has_replacement_module", "completed"},
    "exchange_module": {"has_faulty_module", "has_replacement_module"},
}


def quest_context_for(npc_actions: list, actor) -> str | None:
    """
    A one-line system message giving an NPC the player's actual
    module-exchange quest state, or None if this NPC has no quest
    action at all (most NPCs, and all of phase 1's cast before this
    quest existed). The persona file's own wording is responsible for
    explaining what each state means and when its action is valid -
    this just supplies the raw fact every turn, fresh, so a stale or
    mistaken belief from earlier in the conversation can never override
    what the engine actually recorded. Scoped per-NPC via
    QUEST_STATE_VISIBILITY above, so an NPC whose own actions don't
    cover the current state learns only that it isn't their concern
    yet, not the actual value.
    """
    relevant_actions = QUEST_MODULE_EXCHANGE_ACTIONS & set(npc_actions)
    if not relevant_actions:
        return None

    state = get_quest_state(actor)
    visible_states = set()
    for action in relevant_actions:
        visible_states |= QUEST_STATE_VISIBILITY.get(action, set())

    if state in visible_states:
        return f"Engine state for the heating-unit module errand with this player: {state!r}."
    return (
        "Engine state for the heating-unit module errand with this player: "
        "not yet at a stage that involves you."
    )


# Phase 2B's generalized commitment prototype (docs/phase2b-records-
# discrepancy-proposal.md): unlike the module-exchange quest above,
# these four actions are generic - any NPC granted one of them plays
# whichever role (holder or clerk) world.commitments.SCENARIOS says
# its npc_id has for the given commitment_type. The model names the
# commitment_type; it never gets to choose its own role.


def _require_proposer_role(npc, commitment_type) -> ActionResult | None:
    """
    propose/accept/decline are generic actions an NPC's persona grants
    by name, with no per-call role check of their own (unlike
    report_commitment_outcome/accept_handoff, which already check the
    calling npc_id against the scenario). Without this, any NPC holding
    one of these three actions for its *own* scenario (e.g. Tarin,
    for discrepancy_report) could also invoke it for a *different*
    scenario it has no role in (e.g. Tarin proposing and accepting
    Mara's parcel errand on his own, handing over a parcel he never
    actually held - confirmed live, 2026-10-13). Returns a dropped
    ActionResult if the calling npc_id isn't this commitment_type's
    proposer, else None to let the caller proceed.
    """
    scenario = SCENARIOS.get(commitment_type)
    if scenario is None:
        return ActionResult(False, "", reason=f"unknown commitment_type: {commitment_type!r}")
    npc_id = npc.db.npc_id
    if npc_id != scenario.effective_proposer_npc_id:
        return ActionResult(False, "", reason=f"{npc_id!r} has no proposer role for {commitment_type!r}")
    return None


def _validate_propose_commitment(npc, actor, arguments: dict) -> ActionResult:
    commitment_type = arguments.get("commitment_type")
    denied = _require_proposer_role(npc, commitment_type)
    if denied:
        return denied
    result = _propose_commitment(actor, commitment_type)
    if not result.ok:
        return ActionResult(False, "", reason=result.reason)
    scenario = SCENARIOS[commitment_type]
    return ActionResult(True, scenario.propose_narration.format(npc=npc.key, actor=actor.key))


def _validate_accept_commitment(npc, actor, arguments: dict) -> ActionResult:
    commitment_type = arguments.get("commitment_type")
    denied = _require_proposer_role(npc, commitment_type)
    if denied:
        return denied
    result = _accept_commitment(actor, commitment_type)
    if not result.ok:
        return ActionResult(False, "", reason=result.reason)
    if commitment_type in PARCEL_COMMITMENT_TYPES:
        _create_parcel_for(actor, result.commitment_id)
    scenario = SCENARIOS[commitment_type]
    return ActionResult(True, scenario.accept_narration.format(npc=npc.key, actor=actor.key))


def _validate_decline_commitment(npc, actor, arguments: dict) -> ActionResult:
    commitment_type = arguments.get("commitment_type")
    denied = _require_proposer_role(npc, commitment_type)
    if denied:
        return denied
    result = _decline_commitment(actor, commitment_type)
    if not result.ok:
        return ActionResult(False, "", reason=result.reason)
    scenario = SCENARIOS[commitment_type]
    return ActionResult(True, scenario.decline_narration.format(npc=npc.key, actor=actor.key))


def _validate_report_commitment_outcome(npc, actor, arguments: dict) -> ActionResult:
    commitment_type = arguments.get("commitment_type")
    scenario = SCENARIOS.get(commitment_type)
    if scenario is None:
        return ActionResult(False, "", reason=f"unknown commitment_type: {commitment_type!r}")

    npc_id = npc.db.npc_id
    if npc_id == scenario.clerk_npc_id:
        result = _record_acknowledgment(actor, commitment_type, npc_id)
        if not result.ok:
            return ActionResult(False, "", reason=result.reason)
        return ActionResult(True, scenario.ack_narration.format(npc=npc.key, actor=actor.key))
    if npc_id in scenario.holder_npc_ids:
        result = _fulfill_commitment(actor, commitment_type, npc_id)
        if not result.ok:
            return ActionResult(False, "", reason=result.reason)
        return ActionResult(True, scenario.fulfill_narration.format(npc=npc.key, actor=actor.key))
    return ActionResult(False, "", reason=f"{npc_id!r} has no role in commitment_type {commitment_type!r}")


# docs/phase2c-misdelivered-parcel-proposal.md: commitment types whose
# accepted commitment comes with a real Parcel object (rather than
# 2B's clerk-acknowledgment evidence) and whose completion is
# accept_handoff, not report_commitment_outcome.
PARCEL_COMMITMENT_TYPES = {"deliver_parcel"}
PARCEL_TAG_CATEGORY = "parcel_commitment"


def _create_parcel_for(actor, commitment_id: str) -> None:
    """
    Mara's side of accepting a parcel-commitment offer: puts a real,
    locked typeclasses.objects.Parcel (see that class's docstring)
    directly into the player's inventory, tagged with this exact
    commitment *instance* id - never the type in the abstract, so a
    stale object from a reset or earlier instance can't satisfy a
    new one (same discipline as commitments.py's acknowledgment
    records).
    """
    from evennia import create_object

    parcel = create_object(
        "typeclasses.objects.Parcel",
        key="a small misdirected parcel",
        location=actor,
    )
    # Same information the discoverable hint object in the café gave
    # (world/build_quest_props.py) - without that version's "not here"
    # framing, which only made sense sitting on Mara's counter and
    # would read oddly once the player is carrying it elsewhere.
    parcel.db.desc = (
        'A small, plainly wrapped parcel. The shipping label reads: '
        '"Tarin Os, Maintenance Workshop."'
    )
    parcel.tags.add(commitment_id, category=PARCEL_TAG_CATEGORY)


def _actor_has_correct_parcel(actor, commitment_id: str) -> bool:
    """The engine-checkable fact accept_handoff validates against:
    does the player actually, currently carry the one real object
    tied to this exact commitment instance."""
    return any(
        commitment_id in obj.tags.get(category=PARCEL_TAG_CATEGORY, return_list=True)
        for obj in actor.contents
        if obj.is_typeclass("typeclasses.objects.Parcel", exact=False)
    )


def cleanup_stray_parcels(actor) -> int:
    """
    Delete any carried Parcel not tied to one of this player's
    currently STATUS_OPEN commitments - e.g. left stranded by
    `resetcommitment` clearing the commitment data out from under it,
    or orphaned by a commitment_type rename (the parcel's own tag
    still names the old commitment_id, which no longer corresponds to
    anything). Parcel is locked against get/drop/give by design
    (typeclasses.objects.Parcel), so without this an orphaned one
    would otherwise sit in the player's inventory forever with no way
    to remove it. Returns how many were deleted, for the admin command
    to report.
    """
    from world.commitments import open_commitment_ids

    open_ids = open_commitment_ids(actor)
    removed = 0
    for obj in list(actor.contents):
        if not obj.is_typeclass("typeclasses.objects.Parcel", exact=False):
            continue
        tags = obj.tags.get(category=PARCEL_TAG_CATEGORY, return_list=True)
        if not any(tag in open_ids for tag in tags):
            obj.delete()
            removed += 1
    return removed


def _validate_remember_fact(npc, actor, arguments: dict) -> ActionResult:
    fact = arguments.get("fact", "")
    result = _remember_fact(actor, npc.db.npc_id, fact)
    if not result.ok:
        return ActionResult(False, "", reason=result.reason)
    # No narrated outcome by default - nothing observable in the world
    # changed (design-bible 16.5 step 4's narration is for game-state
    # consequences like an item changing hands; remembering something
    # has none). But a Builder can flip this player's own
    # memory_debug_enabled flag (commands/admin.py's `memorydebug`)
    # to see exactly what got stored, for testing without having to
    # read the conversation log. commands/say.py only shows a
    # narration at all when it's non-empty, so leaving this "" when
    # debug is off still shows nothing.
    if actor.attributes.get("memory_debug_enabled", default=False):
        return ActionResult(True, f"[memory] {npc.key} notes: \"{fact}\"")
    return ActionResult(True, "")


def _validate_accept_handoff(npc, actor, arguments: dict) -> ActionResult:
    commitment_type = arguments.get("commitment_type")
    scenario = SCENARIOS.get(commitment_type)
    if scenario is None:
        return ActionResult(False, "", reason=f"unknown commitment_type: {commitment_type!r}")

    npc_id = npc.db.npc_id
    if npc_id not in scenario.holder_npc_ids:
        return ActionResult(False, "", reason=f"{npc_id!r} has no holder role for {commitment_type!r}")

    commitment_id = _get_open_commitment_id(actor, commitment_type)
    precondition_ok = bool(commitment_id) and _actor_has_correct_parcel(actor, commitment_id)

    result = _fulfill_commitment_with_precondition(actor, commitment_type, npc_id, precondition_ok)
    if not result.ok:
        return ActionResult(False, "", reason=result.reason)

    for obj in list(actor.contents):
        if obj.is_typeclass("typeclasses.objects.Parcel", exact=False) and commitment_id in obj.tags.get(
            category=PARCEL_TAG_CATEGORY, return_list=True
        ):
            obj.move_to(npc, quiet=True, move_type="give")
    return ActionResult(True, scenario.fulfill_narration.format(npc=npc.key, actor=actor.key))


def _validate_verify_revision_report(npc, actor, arguments: dict) -> ActionResult:
    commitment_type = arguments.get("commitment_type")
    scenario = SCENARIOS.get(commitment_type)
    if scenario is None:
        return ActionResult(False, "", reason=f"unknown commitment_type: {commitment_type!r}")

    npc_id = npc.db.npc_id
    if npc_id != scenario.clerk_npc_id:
        return ActionResult(False, "", reason=f"{npc_id!r} has no clerk role for {commitment_type!r}")

    # The actual check (docs/phase2-quest-prototype-design.md §14):
    # the model only ever supplies reported_revision as an argument,
    # the same way every other action's free-text argument works
    # (e.g. serve_drink's drink_type) - it never sees whether that
    # value is correct. revision_matches is the one place that
    # decides, in Python, against the real stored value.
    from world.noticeboard import revision_matches

    reported_revision = arguments.get("reported_revision", "")
    precondition_ok = revision_matches(actor, reported_revision)

    result = _record_acknowledgment_with_precondition(actor, commitment_type, npc_id, precondition_ok)
    if not result.ok:
        return ActionResult(False, "", reason=result.reason)
    return ActionResult(True, scenario.ack_narration.format(npc=npc.key, actor=actor.key))


# Phase 2E (docs/phase2e-word-gets-around-design.md): Mara doesn't
# automatically learn that her misdelivered parcel reached Tarin or
# Veska - see world/rumors.py's project_mara_parcel_knowledge, wired
# into the "deliver_parcel" scenario's proposer_knowledge_projector.
# This is the action that actually tells her, once the player reports
# it - scenario-specific to Mara and the parcel errand, not a generic
# commitment action, the same way the old module-exchange quest's
# actions were each specific to their one scenario rather than routed
# through commitments.py's generic lifecycle.
_RUMOR_RECIPIENT_NPC_IDS = {"tarin": "tarin_os", "veska": "veska_renn"}
_RUMOR_RECIPIENT_DISPLAY_NAMES = {"tarin_os": "Tarin", "veska_renn": "Veska"}


def _validate_report_parcel_delivery(npc, actor, arguments: dict) -> ActionResult:
    npc_id = npc.db.npc_id
    if npc_id != "mara_voss":
        return ActionResult(False, "", reason=f"{npc_id!r} has no role in the parcel-delivery rumor")

    reported_recipient = arguments.get("reported_recipient")
    reported_npc_id = _RUMOR_RECIPIENT_NPC_IDS.get(reported_recipient)
    if reported_npc_id is None:
        return ActionResult(False, "", reason=f"invalid reported_recipient: {reported_recipient!r}")

    commitment = _get_fulfilled_commitment(actor, "deliver_parcel")
    if commitment is None:
        return ActionResult(False, "", reason="no fulfilled deliver_parcel commitment on record")

    if reported_npc_id != commitment["fulfilled_by_npc_id"]:
        return ActionResult(
            False,
            "",
            reason=(
                f"reported recipient {reported_recipient!r} does not match the actual "
                f"recipient {commitment['fulfilled_by_npc_id']!r}"
            ),
        )

    commitment_id = commitment["commitment_id"]
    if _is_informed_of(actor, commitment_id):
        return ActionResult(False, "", reason="already informed of this delivery")

    _mark_informed(actor, commitment_id)
    if not _has_reputation_credit(actor):
        _mark_reputation_credited(actor)
        _adjust_reputation(actor, "mara_voss", 1)

    recipient_name = _RUMOR_RECIPIENT_DISPLAY_NAMES[reported_npc_id]
    return ActionResult(True, f"{npc.key} is glad to hear the parcel reached {recipient_name}.")


# Phase 3 "The Unverified Notice" (docs/phase3-unverified-notice-
# design.md): Tarin proposes/is told the outcome; Veska independently
# resolves it one of two mutually-exclusive ways. Both verify_notice
# and withdraw_notice route through fulfill_commitment_with_precondition,
# which already requires STATUS_OPEN to proceed - so once either path
# succeeds, the other finds no open commitment left and is rejected,
# the same mutual-exclusion-for-free mechanism 2C's multi-holder parcel
# already relies on. Neither action takes a real argument (the model's
# only decision is which of the two to call); each still needs one
# required field per docs/npc-action-prompt-guidelines.md guideline #7
# (a zero-argument schema is reliably skipped in favor of narrating in
# prose instead of calling the tool).
def _validate_verify_notice(npc, actor, arguments: dict) -> ActionResult:
    npc_id = npc.db.npc_id
    scenario = SCENARIOS["unverified_notice"]
    if npc_id not in scenario.holder_npc_ids:
        return ActionResult(False, "", reason=f"{npc_id!r} has no holder role for 'unverified_notice'")

    commitment_id = _get_open_commitment_id(actor, "unverified_notice")
    precondition_ok = bool(commitment_id) and _approval_mark_present(actor)

    result = _fulfill_commitment_with_precondition(actor, "unverified_notice", npc_id, precondition_ok)
    if not result.ok:
        return ActionResult(False, "", reason=result.reason)

    _record_notice_resolution(actor, result.commitment_id, RESOLUTION_VERIFIED)
    return ActionResult(True, f"{npc.key} checks the notice herself and confirms the approval mark is there.")


def _validate_withdraw_notice(npc, actor, arguments: dict) -> ActionResult:
    npc_id = npc.db.npc_id
    scenario = SCENARIOS["unverified_notice"]
    if npc_id not in scenario.holder_npc_ids:
        return ActionResult(False, "", reason=f"{npc_id!r} has no holder role for 'unverified_notice'")

    commitment_id = _get_open_commitment_id(actor, "unverified_notice")
    # Withdrawal doesn't contest Tarin's claim either way - it only
    # requires an actual open commitment to act on, same bar as any
    # other commitment action's basic precondition.
    precondition_ok = bool(commitment_id)

    result = _fulfill_commitment_with_precondition(actor, "unverified_notice", npc_id, precondition_ok)
    if not result.ok:
        return ActionResult(False, "", reason=result.reason)

    _record_notice_resolution(actor, result.commitment_id, RESOLUTION_WITHDRAWN)
    return ActionResult(True, f"{npc.key} pulls the notice from public display until it's sorted out.")


_NOTICE_RESOLUTION_ARG_MAP = {"verified": RESOLUTION_VERIFIED, "withdrawn": RESOLUTION_WITHDRAWN}


def _validate_report_notice_outcome(npc, actor, arguments: dict) -> ActionResult:
    npc_id = npc.db.npc_id
    if npc_id != "tarin_os":
        return ActionResult(False, "", reason=f"{npc_id!r} has no role in the notice-resolution report")

    reported_resolution = arguments.get("reported_resolution")
    expected = _NOTICE_RESOLUTION_ARG_MAP.get(reported_resolution)
    if expected is None:
        return ActionResult(False, "", reason=f"invalid reported_resolution: {reported_resolution!r}")

    commitment = _get_fulfilled_commitment(actor, "unverified_notice")
    if commitment is None:
        return ActionResult(False, "", reason="no fulfilled unverified_notice commitment on record")

    actual = _get_notice_resolution(actor, commitment["commitment_id"])
    if expected != actual:
        return ActionResult(
            False,
            "",
            reason=(
                f"reported resolution {reported_resolution!r} does not match the actual "
                f"resolution {actual!r}"
            ),
        )

    commitment_id = commitment["commitment_id"]
    if _is_informed_of_notice(actor, commitment_id):
        return ActionResult(False, "", reason="already informed of this resolution")

    _mark_notice_informed(actor, commitment_id)
    if actual == RESOLUTION_VERIFIED:
        return ActionResult(True, f"{npc.key} is relieved to hear the notice checked out and stayed up.")
    return ActionResult(True, f"{npc.key} is glad the notice was pulled until it's sorted out.")


def _fold_accents(text: str) -> str:
    # "Corner Café" has to still match a model that writes "Corner
    # Cafe" without the accent - strip combining marks rather than
    # require an exact character match.
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def _find_neighborhood_room(destination_name: str):
    """Match free-text destination against the six known rooms, by
    display name, case- and accent-insensitively. Returns the room
    object, or None if it's not one of the six (per persona: "Don't
    describe routes to places outside this neighborhood")."""
    from evennia import search_tag

    destination_name = _fold_accents((destination_name or "").strip().lower())
    for tag, name, _desc in NEIGHBORHOOD_ROOMS:
        if _fold_accents(name.lower()) == destination_name:
            matches = search_tag(key=tag, category=ROOM_TAG_CATEGORY)
            return matches[0] if matches else None
    return None


def _find_exit_path(start_room, target_room, max_depth=4):
    """
    BFS over the *actual* exits between rooms (not an assumed map),
    so directions reflect authoritative state. Returns a list of exit
    keys to follow, [] if already there, or None if unreachable
    within max_depth.
    """
    if start_room == target_room:
        return []

    visited = {start_room}
    frontier = [(start_room, [])]
    while frontier:
        next_frontier = []
        for room, path in frontier:
            if len(path) >= max_depth:
                continue
            for exi in room.exits:
                dest = exi.destination
                if dest is None or dest in visited:
                    continue
                new_path = path + [exi.key]
                if dest == target_room:
                    return new_path
                visited.add(dest)
                next_frontier.append((dest, new_path))
        frontier = next_frontier
    return None


def _validate_give_directions(npc, actor, arguments: dict) -> ActionResult:
    destination_name = arguments.get("destination", "")
    target_room = _find_neighborhood_room(destination_name)
    if target_room is None:
        return ActionResult(False, "", reason=f"destination not in neighborhood: {destination_name!r}")

    start_room = actor.location
    if start_room is None:
        return ActionResult(False, "", reason="actor has no location")

    path = _find_exit_path(start_room, target_room)
    if path is None:
        return ActionResult(False, "", reason=f"no known path from {start_room} to {target_room}")

    if not path:
        return ActionResult(True, f"{npc.key} says you're already there.")

    route_text = ", then ".join(f'take "{step}"' for step in path)
    return ActionResult(True, f"{npc.key} explains the way: {route_text}.")


_ACTION_VALIDATORS = {
    "serve_drink": _validate_serve_drink,
    "hand_over_item": _validate_hand_over_item,
    "give_directions": _validate_give_directions,
    "accept_help": _validate_accept_help,
    "give_faulty_module": _validate_give_faulty_module,
    "exchange_module": _validate_exchange_module,
    "accept_replacement": _validate_accept_replacement,
    "propose_commitment": _validate_propose_commitment,
    "accept_commitment": _validate_accept_commitment,
    "decline_commitment": _validate_decline_commitment,
    "report_commitment_outcome": _validate_report_commitment_outcome,
    "accept_handoff": _validate_accept_handoff,
    "verify_revision_report": _validate_verify_revision_report,
    "report_parcel_delivery": _validate_report_parcel_delivery,
    "verify_notice": _validate_verify_notice,
    "withdraw_notice": _validate_withdraw_notice,
    "report_notice_outcome": _validate_report_notice_outcome,
    "remember_fact": _validate_remember_fact,
}


# OpenAI-style tool/function definitions, offered to the model so it
# can *propose* an action by name. This is the only part of the tool
# layer the model ever sees; validate_and_apply() above is what
# actually decides whether a proposal does anything.
ACTION_SCHEMAS = {
    "serve_drink": {
        "type": "function",
        "function": {
            "name": "serve_drink",
            "description": "Serve the player a drink from the cafe's simple menu.",
            "parameters": {
                "type": "object",
                "properties": {
                    "drink_type": {
                        "type": "string",
                        "enum": ["hot", "cold"],
                        "description": "Whether to serve a hot drink or a cold drink.",
                    }
                },
                "required": ["drink_type"],
            },
        },
    },
    "hand_over_item": {
        "type": "function",
        "function": {
            "name": "hand_over_item",
            "description": "Hand the player an item from the workshop's small stock of spares.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_type": {
                        "type": "string",
                        "enum": ["spare part", "hand tool"],
                        "description": "Which kind of item to hand over.",
                    }
                },
                "required": ["item_type"],
            },
        },
    },
    "give_directions": {
        "type": "function",
        "function": {
            "name": "give_directions",
            "description": (
                "Give the player directions to one of the six rooms in this "
                "neighborhood (Lift Concourse, Old Quarter Square, Corner "
                "Cafe, Maintenance Workshop, Residential Courtyard, Civic "
                "Office). Do not use this for places outside the "
                "neighborhood - say you don't know instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "description": "The exact name of the destination room.",
                    }
                },
                "required": ["destination"],
            },
        },
    },
    "accept_help": {
        "type": "function",
        "function": {
            "name": "accept_help",
            "description": (
                "Agree to let the player help with the broken heating unit. Call "
                "this with confirmed=true the moment you agree, before handing "
                "over anything - it records the commitment itself, separately "
                "from physically giving them the module."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmed": {
                        "type": "boolean",
                        "description": "Set to true to confirm you're agreeing to accept their help, not just discussing it.",
                    }
                },
                "required": ["confirmed"],
            },
        },
    },
    "give_faulty_module": {
        "type": "function",
        "function": {
            "name": "give_faulty_module",
            "description": (
                "Hand the player the faulty temperature-control module, once "
                "they've agreed to help. Call with confirmed=true."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmed": {
                        "type": "boolean",
                        "description": "Set to true to confirm you're handing over the module, not just talking about it.",
                    }
                },
                "required": ["confirmed"],
            },
        },
    },
    "exchange_module": {
        "type": "function",
        "function": {
            "name": "exchange_module",
            "description": (
                "Take the faulty temperature-control module the player brought, and hand "
                "them back a working replacement. Call with confirmed=true."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmed": {
                        "type": "boolean",
                        "description": "Set to true to confirm you're doing the swap, not just talking about it.",
                    }
                },
                "required": ["confirmed"],
            },
        },
    },
    "accept_replacement": {
        "type": "function",
        "function": {
            "name": "accept_replacement",
            "description": (
                "Take the working replacement module back from the player, completing "
                "the errand. Call with confirmed=true."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmed": {
                        "type": "boolean",
                        "description": "Set to true to confirm you're accepting the replacement, not just talking about it.",
                    }
                },
                "required": ["confirmed"],
            },
        },
    },
    "propose_commitment": {
        "type": "function",
        "function": {
            "name": "propose_commitment",
            "description": (
                "Offer the player this specific errand. Call it when you decide to raise it, "
                "or when the player asks what's wrong and you choose to explain. This only "
                "records that you've offered it - it does not require the player to have "
                "agreed yet. Wait for their answer, then call accept_commitment or "
                "decline_commitment to record it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "commitment_type": {
                        "type": "string",
                        "enum": list(SCENARIOS.keys()),
                        "description": "Which errand you're offering.",
                    }
                },
                "required": ["commitment_type"],
            },
        },
    },
    "accept_commitment": {
        "type": "function",
        "function": {
            "name": "accept_commitment",
            "description": (
                "Record that the player has actually, personally committed to do this - not "
                "just that they seem willing or interested. Only valid after you've offered "
                "it with propose_commitment and they've answered."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "commitment_type": {
                        "type": "string",
                        "enum": list(SCENARIOS.keys()),
                        "description": "Which errand they've agreed to.",
                    }
                },
                "required": ["commitment_type"],
            },
        },
    },
    "decline_commitment": {
        "type": "function",
        "function": {
            "name": "decline_commitment",
            "description": (
                "Record that the player has turned down this errand. Only valid after you've "
                "offered it with propose_commitment. Declining isn't breaking a promise - "
                "nothing is owed afterward, and you can offer it again later."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "commitment_type": {
                        "type": "string",
                        "enum": list(SCENARIOS.keys()),
                        "description": "Which errand they've declined.",
                    }
                },
                "required": ["commitment_type"],
            },
        },
    },
    "report_commitment_outcome": {
        "type": "function",
        "function": {
            "name": "report_commitment_outcome",
            "description": (
                "Record what you've been told about this commitment, in your own role in it. "
                "The engine decides what that means for you specifically and will tell you "
                "the result - it is not something you can choose or guess. Call it the moment "
                "the player reports or claims the outcome to you, so the engine's answer, not "
                "your own assumption, decides whether anything actually happened."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "commitment_type": {
                        "type": "string",
                        "enum": list(SCENARIOS.keys()),
                        "description": "Which errand this report concerns.",
                    }
                },
                "required": ["commitment_type"],
            },
        },
    },
    "accept_handoff": {
        "type": "function",
        "function": {
            "name": "accept_handoff",
            "description": (
                "Take physical custody of what the player is handing you for this errand. "
                "Call it the moment they actually offer it to you, not just mention having "
                "it or talk about possibly bringing it. The engine checks whether they really "
                "have it on them and will tell you the result - it is not something you can "
                "tell just by what they say."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "commitment_type": {
                        "type": "string",
                        "enum": list(SCENARIOS.keys()),
                        "description": "Which errand this handoff completes.",
                    }
                },
                "required": ["commitment_type"],
            },
        },
    },
    "verify_revision_report": {
        "type": "function",
        "function": {
            "name": "verify_revision_report",
            "description": (
                "Check a revision number the player has just reported to you against the "
                "authoritative record. Call it the moment they state a specific four-digit "
                "number as what the display showed - the engine decides whether it matches, "
                "not you; you have no way to know the real value yourself. Only call this for "
                "an actual affirmative report of one specific number. Do not call it for a "
                "question ('Is it 4182?'), a guess between options ('Was it 4182 or 4812?'), "
                "a case where they're unsure or can't remember, or a number mentioned while "
                "denying or doubting it ('I don't think it said 4182') - none of those is them "
                "actually telling you the number is correct. If they haven't given you one "
                "clear number as their report, ask for it instead of calling this."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "commitment_type": {
                        "type": "string",
                        "enum": list(SCENARIOS.keys()),
                        "description": "Which errand this report concerns.",
                    },
                    "reported_revision": {
                        "type": "string",
                        "description": "The exact four-digit number the player just reported, as digits only.",
                    },
                },
                "required": ["commitment_type", "reported_revision"],
            },
        },
    },
    "report_parcel_delivery": {
        "type": "function",
        "function": {
            "name": "report_parcel_delivery",
            "description": (
                "Record that the player has just told you your misdelivered parcel actually "
                "reached its recipient. Call it the moment they affirmatively report this, "
                "naming which of Tarin or Veska took it in. The engine checks that against the "
                "real record and will tell you the result - it is not something you can tell "
                "just by what they say. Do not call it for a question ('Did Tarin get it?'), a "
                "guess between options ('Was it Tarin or Veska?'), a case where they're unsure, "
                "or a claim that leaves it unresolved ('I think I left it with one of them'). If "
                "they haven't clearly named one recipient as their report, ask instead of "
                "calling this."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reported_recipient": {
                        "type": "string",
                        "enum": ["tarin", "veska"],
                        "description": "Which of Tarin or Veska the player says actually received the parcel.",
                    }
                },
                "required": ["reported_recipient"],
            },
        },
    },
    "verify_notice": {
        "type": "function",
        "function": {
            "name": "verify_notice",
            "description": (
                "Go check the posted notice yourself for the required approval mark, rather "
                "than taking anyone's word for it. Call it the moment the player asks you to "
                "confirm the notice is correctly approved, instead of asking them to take it "
                "down. The engine tells you what you actually find when you check - it is not "
                "something you can assume or guess at."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmed": {
                        "type": "boolean",
                        "description": (
                            "Always true - this action takes no real argument, it just "
                            "confirms you're acting now."
                        ),
                    }
                },
                "required": ["confirmed"],
            },
        },
    },
    "withdraw_notice": {
        "type": "function",
        "function": {
            "name": "withdraw_notice",
            "description": (
                "Pull the posted notice from public display, regardless of whether its "
                "approval mark actually checks out. Call it the moment the player asks you to "
                "take the notice down instead of verifying it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmed": {
                        "type": "boolean",
                        "description": (
                            "Always true - this action takes no real argument, it just "
                            "confirms you're acting now."
                        ),
                    }
                },
                "required": ["confirmed"],
            },
        },
    },
    "report_notice_outcome": {
        "type": "function",
        "function": {
            "name": "report_notice_outcome",
            "description": (
                "Record that the player has just told you what happened with the notice at "
                "the Civic Office - either that Veska checked it herself and it's staying up, "
                "or that she pulled it. The engine checks that against the real record and "
                "will tell you the result - it is not something you can tell just by what they "
                "say. Do not call it for a question, a guess between the two, a case where "
                "they're unsure, or a claim that leaves it unresolved."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reported_resolution": {
                        "type": "string",
                        "enum": ["verified", "withdrawn"],
                        "description": "Which outcome the player says actually happened.",
                    }
                },
                "required": ["reported_resolution"],
            },
        },
    },
    "remember_fact": {
        "type": "function",
        "function": {
            "name": "remember_fact",
            "description": (
                "Note down one short, specific thing the PLAYER just told you about "
                "THEMSELVES - where they're from, what they do, something that happened to "
                "them, a preference or opinion they stated. Call it the moment they share "
                "something like that, in the same turn, so you don't lose it. Never call this "
                "for something you said about yourself, your own job, or your own life - you "
                "already know everything about yourself permanently; this is only for "
                "remembering the other person, never for noting your own words back to "
                "yourself. This is also not for things about the world or other people, or "
                "anything you'd need to verify - just what this specific player told you about "
                "themselves. Don't call it for small talk with nothing specific in it, and "
                "don't call it more than once or twice in a single conversation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {
                        "type": "string",
                        "description": (
                            "The fact itself, short and specific, in your own words - e.g. "
                            "'grew up near the Docks' or 'used to work in maintenance before "
                            "this.' Not a direct quote, not a full sentence of dialogue."
                        ),
                    }
                },
                "required": ["fact"],
            },
        },
    },
}


def get_tool_schemas(action_names: list) -> list:
    """Tool definitions for the action names an NPC's persona grants."""
    return [ACTION_SCHEMAS[name] for name in action_names if name in ACTION_SCHEMAS]
