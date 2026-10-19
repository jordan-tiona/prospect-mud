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
13.5: `serve_drink` (Mara), `give_directions` (Iri). (Tarin's original
phase 1 action, `hand_over_item`, was retired 2026-10-15 once nothing
granted it anymore.)
"""

import unicodedata
from dataclasses import dataclass

from world.build_rooms import BUILD_TAG_CATEGORY as ROOM_TAG_CATEGORY
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
from world.garden import is_bed_tended as _is_bed_tended
from world.npc_memory import check_fact, check_player_words
from world.npc_memory import remember_fact as _remember_fact
from world.npc_profile import parse_persona
from world.reputation import adjust_reputation as _adjust_reputation
from world.rumors import has_reputation_credit as _has_reputation_credit
from world.rumors import is_informed_of as _is_informed_of
from world.rumors import mark_informed as _mark_informed
from world.rumors import mark_reputation_credited as _mark_reputation_credited
from world.rumors import project_giver_parcel_knowledge as _project_giver_parcel_knowledge

# Phase 2E: wired here, not in world/commitments.py's SCENARIOS
# literal, since world/rumors.py imports from world/commitments.py and
# this avoids a circular import. SCENARIOS is the same dict object
# commitments.py's own functions read from, so mutating this field in
# place is visible everywhere, not just through this module.
SCENARIOS["deliver_parcel"].proposer_knowledge_projector = _project_giver_parcel_knowledge


@dataclass
class ActionResult:
    applied: bool
    # Shown to the player as the narrated outcome of a valid action
    # (design-bible 16.5 step 4). Empty when the call was dropped.
    narration: str
    # Why a call was dropped. For logs/debugging, not necessarily
    # shown to the player verbatim.
    reason: str = ""


# An answer can't come in the same reply as its own question: these
# actions are dropped when the action they answer was applied earlier in
# the same reply. Without it Mara asked "would you take it?" and recorded
# the yes in one breath (docs/playtest-findings.md PF-0011, guideline
# #10). Only Mara's errand so far - a player who volunteers before being
# asked now has to confirm once more, a cost the working commitment
# quests haven't been asked to pay.
SAME_REPLY_EXCLUSIONS = {"accept_help": "ask_for_help"}

# A yes dropped because the question was only ever asked in words, never
# recorded: the follow-up reaction (commands/say.py) re-asks, and gets
# the asking action as its one tool so that re-ask is recorded too.
# Without it the reaction had no tools, so every later yes was dropped
# the same way - seen live 2026-10-18, Mara prompt_version 52, the trap
# guideline #24 (b) describes. The engine still validates the call.
REACTION_RETRIES = {"accept_help": "ask_for_help"}

# The other way round: an applied action whose next step belongs in the
# same reply, when the reply didn't make it. Live 2026-10-18 (v52): on
# the yes she called accept_help alone, and the reaction said "Here's
# the faulty module" with no way to hand it over.
REACTION_FOLLOW_ONS = {"accept_help": "give_faulty_module"}


def reaction_action_names(calls, results, applied_earlier=()) -> list:
    """The actions the follow-up reaction may call, given this reply's
    `calls` and their results (commands/say.py's tool_results dicts)."""
    names = []
    for call, result in zip(calls, results):
        table = REACTION_FOLLOW_ONS if result["applied"] else REACTION_RETRIES
        name = table.get(call["name"])
        if name and name not in applied_earlier and name not in names:
            names.append(name)
    return names


def validate_and_apply(
    npc, actor, action_name: str, arguments: dict, player_message: str | None = None, applied_earlier=()
) -> ActionResult:
    """
    The engine validator. Checks that `action_name` is one of this
    NPC's declared permitted actions before running its specific
    validator, so an NPC can't be talked into an action its persona
    never granted it. `player_message` is the player's text this turn,
    for the validators in _PLAYER_MESSAGE_VALIDATORS that check a call
    against it. `applied_earlier` names the actions already applied in
    this same reply, for SAME_REPLY_EXCLUSIONS.
    """
    arguments = arguments or {}

    if SAME_REPLY_EXCLUSIONS.get(action_name) in applied_earlier:
        return ActionResult(
            applied=False,
            narration="",
            reason=(
                "you've only just asked them - they haven't answered yet. Wait for their reply "
                "before treating it as agreed, and don't hand anything over. If they already sounded "
                "willing, say you're glad and check once more, plainly, that they'll take it - "
                "without talking about asking or asking properly"
            ),
        )

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

    if action_name in _PLAYER_MESSAGE_VALIDATORS:
        return validator(npc, actor, arguments, player_message)
    return validator(npc, actor, arguments)


def _validate_serve_drink(npc, actor, arguments: dict) -> ActionResult:
    drink_type = arguments.get("drink_type")
    if drink_type not in ("hot", "cold"):
        return ActionResult(False, "", reason=f"invalid drink_type: {drink_type!r}")
    return ActionResult(True, f"{npc.key} serves you a {drink_type} drink.")


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
    "offered",
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


def _validate_ask_for_help(npc, actor, arguments: dict) -> ActionResult:
    # The "offered" step (docs/playtest-findings.md PF-0011), the same
    # shape as propose_commitment. Asking again after a decline is fine.
    # A repeat ask while the first is still pending is dropped, like a
    # repeat propose_commitment - and it has to be: the model often
    # re-calls this alongside accept_help on the player's yes, and an
    # applied re-ask would make SAME_REPLY_EXCLUSIONS drop that yes.
    state = get_quest_state(actor)
    if state == "offered":
        return ActionResult(
            False, "", reason="you've already asked them, and that ask stands - don't ask again"
        )
    if state != "not_started":
        return ActionResult(
            False, "", reason=f"they've already agreed to help (state {state!r}) - don't ask again"
        )
    _set_quest_state(actor, "offered")
    return ActionResult(
        True, f"{npc.key} asks you to take the heating unit's faulty module to Tarin Os."
    )


def _validate_accept_help(npc, actor, arguments: dict) -> ActionResult:
    if get_quest_state(actor) == "not_started":
        return ActionResult(
            False,
            "",
            reason=(
                "you haven't asked them to take the module yet, so there's nothing for them to have "
                "agreed to - don't hand anything over or thank them for agreeing. Ask them now, "
                "with ask_for_help, and wait for their answer"
            ),
        )
    return _validate_quest_step(
        actor, "offered", "accepted", f"{npc.key} agrees to let you help with the heating unit."
    )


def _validate_decline_help(npc, actor, arguments: dict) -> ActionResult:
    return _validate_quest_step(
        actor,
        "offered",
        "not_started",
        f"{npc.key} lets the heating unit go for now.",
    )


def _validate_give_faulty_module(npc, actor, arguments: dict) -> ActionResult:
    return _validate_quest_step(
        actor,
        "accepted",
        "has_faulty_module",
        f"{npc.key} hands you the faulty temperature-control module.",
    )


def _validate_exchange_module(npc, actor, arguments: dict) -> ActionResult:
    return _validate_quest_step(
        actor,
        "has_faulty_module",
        "has_replacement_module",
        f"{npc.key} inspects the module and hands you a working replacement.",
    )


def _validate_accept_replacement(npc, actor, arguments: dict) -> ActionResult:
    return _validate_quest_step(
        actor,
        "has_replacement_module",
        "completed",
        f"{npc.key} takes the replacement module from you.",
    )


# Which actions touch the module-exchange quest, so the prompt-builder
# step (commands/say.py's engage_npc) knows which NPCs need the
# player's current quest state injected as fresh, per-turn context -
# engine truth the NPC reacts to, not something it has to remember
# correctly from its own conversation history.
QUEST_MODULE_EXCHANGE_ACTIONS = {
    "ask_for_help",
    "accept_help",
    "decline_help",
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
    "ask_for_help": {"not_started", "offered"},
    "accept_help": {"not_started", "offered", "accepted"},
    "decline_help": {"offered"},
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
        context = f"Engine state for the heating-unit module errand with this player: {state!r}."
        if state == "has_faulty_module" and "give_faulty_module" not in relevant_actions:
            # Tarin's view: he needs the state to know the exchange is
            # valid, but stated bare he greeted the player with "the
            # faulty heating-unit module" before it came up
            # (docs/playtest-findings.md PF-0005).
            context += (
                " You can't see it and haven't been told about it: don't mention the module "
                "or the heating unit until the player brings it up or hands it over."
            )
        return context
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
    if commitment_type in WEAPON_COMMITMENT_TYPES:
        _create_weapon_for(actor)
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
    The giver's side of accepting a parcel-commitment offer: puts a real,
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
    # Same information the discoverable hint object on the Civic
    # Office counter gives (content/objects/misdelivered_parcel_hint.md)
    # - without that version's room-specific framing, which would read
    # oddly once the player is carrying it elsewhere.
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


# docs/playtest-quest3-skitters-design.md ("Unwelcome Guests"):
# commitment types whose accepted commitment comes with a real Weapon
# object, parallel to PARCEL_COMMITMENT_TYPES above.
WEAPON_COMMITMENT_TYPES = {"hunt_skitters"}


def _create_weapon_for(actor) -> None:
    """Tarin's side of accepting the hunt_skitters offer: puts a real
    typeclasses.objects.Weapon directly into the player's inventory.
    Unlike _create_parcel_for, not tied to the commitment instance by
    tag - a Weapon is ordinary, undistinguished gear, not a single
    specific physical object the engine has to track possession of.
    A player who already carries one isn't given another: re-accepting
    after a reset used to stack them up (five on one tester, 2026-10-17),
    and they can't be dropped."""
    from evennia import create_object

    if _carried_weapons(actor):
        return

    weapon = create_object(
        "typeclasses.objects.Weapon",
        key="a compact shock baton",
        location=actor,
    )
    # docs/playtest-quest3-skitters-design.md's approved weapon lore
    # (project owner, 2026-10-15): a plain, practical piece of
    # pest-control equipment, not military gear - lent by Tarin, not
    # given outright (CLAUDE.md's "whether the player keeps it
    # afterward" is left open by that doc, not decided here).
    weapon.db.desc = (
        "A short, scuffed shock baton with a textured insulating grip and two metal contacts "
        "at its blunt end. A small status light shows it's ready for use. It's nothing "
        "military-grade - just something durable enough for tight service passages against "
        "small pests - but repeated solid hits carry a jolt that can put one down."
    )
    weapon.db.damage = 1


def _carried_weapons(actor) -> list:
    return [obj for obj in actor.contents if obj.is_typeclass("typeclasses.objects.Weapon", exact=False)]


def cleanup_stray_weapons(actor) -> int:
    """
    The baton's counterpart to cleanup_stray_parcels (engineering-
    pitfalls #4): the reset path has to find and remove the physical
    object itself, since clearing the commitment record doesn't. A
    player keeps one baton while hunt_skitters is open or fulfilled
    (the post-quest skitter loop still needs it), and none otherwise.
    Weapons can't be dropped (typeclasses.objects.Weapon), so without
    this a stale one could never be got rid of. Returns how many were
    deleted.
    """
    keep = 0
    for commitment_type in WEAPON_COMMITMENT_TYPES:
        if _get_open_commitment_id(actor, commitment_type) or _get_fulfilled_commitment(actor, commitment_type):
            keep = 1
    removed = 0
    for weapon in _carried_weapons(actor)[keep:]:
        weapon.delete()
        removed += 1
    return removed


def _validate_report_skitter_kills_to_tarin(npc, actor, arguments: dict) -> ActionResult:
    from world.skitters import REQUIRED_KILLS, kills_for

    npc_id = npc.db.npc_id
    scenario = SCENARIOS["hunt_skitters"]
    if npc_id not in scenario.holder_npc_ids:
        return ActionResult(False, "", reason=f"{npc_id!r} has no holder role for 'hunt_skitters'")

    precondition_ok = kills_for(actor) >= REQUIRED_KILLS
    result = _fulfill_commitment_with_precondition(actor, "hunt_skitters", npc_id, precondition_ok)
    if not result.ok:
        return ActionResult(False, "", reason=result.reason)
    return ActionResult(True, scenario.fulfill_narration.format(npc=npc.key, actor=actor.key))


def _validate_log_dead_skitters_with_iri(npc, actor, arguments: dict) -> ActionResult:
    """
    The repeatable post-quest loop (project owner, 2026-10-16): logs
    every skitter the engine actually saw this player kill since their
    last report. The amount is never an argument - the model can't
    supply or inflate it, and a player's own claim of how many they got
    plays no part (CLAUDE.md hard rule 6).
    """
    from world.skitters import LEDGER_NPC_ID, bank_kills, banked_kills_for, has_finished_hunt

    npc_id = npc.db.npc_id
    if npc_id != LEDGER_NPC_ID:
        return ActionResult(False, "", reason=f"{npc_id!r} doesn't keep the skitter log")
    # Rejection reasons are worded as direct instructions, per
    # docs/npc-action-prompt-guidelines.md #20: the follow-up reaction
    # call sees this exact string, and that's what actually steers it.
    if not has_finished_hunt(actor):
        return ActionResult(
            False,
            "",
            reason=(
                "nothing to log yet - they haven't finished helping Tarin with the skitters; "
                "tell them that comes first"
            ),
        )
    newly_logged = bank_kills(actor)
    if not newly_logged:
        return ActionResult(
            False,
            "",
            reason=(
                "no new kills to log since their last report - tell them honestly there's "
                "nothing new on record, without guessing at any number"
            ),
        )
    plural = "" if newly_logged == 1 else "s"
    return ActionResult(
        True,
        f"{npc.key} logs {newly_logged} more skitter{plural} for you. "
        f"Total on record: {banked_kills_for(actor)}.",
    )


def _validate_remember_fact(npc, actor, arguments: dict, player_message: str | None) -> ActionResult:
    fact = arguments.get("fact", "")
    quote_problem = check_player_words(arguments.get("player_words", ""), player_message) or check_fact(fact, npc.key)
    if quote_problem:
        return ActionResult(False, "", reason=quote_problem)
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


# Phase 2E (docs/phase2e-word-gets-around-design.md): the parcel's
# giver doesn't automatically learn that it reached Tarin - see
# world/rumors.py's project_giver_parcel_knowledge, wired into the
# "deliver_parcel" scenario's proposer_knowledge_projector. This is the
# action that actually tells her, once the player reports it -
# scenario-specific to the parcel errand, not a generic commitment
# action, the same way the old module-exchange quest's actions were
# each specific to their one scenario rather than routed through
# commitments.py's generic lifecycle.
#
# Since the errand redistribution (docs/errand-redistribution-plan.md
# D1, 2026-10-16) Tarin is the only possible recipient, so there's no
# reported_recipient to check any more - the fulfilled commitment
# record is the whole fact. confirmed is the trivial required argument
# guideline #7 calls for; its value is ignored.


def _validate_report_parcel_delivery(npc, actor, arguments: dict) -> ActionResult:
    npc_id = npc.db.npc_id
    giver_npc_id = SCENARIOS["deliver_parcel"].effective_proposer_npc_id
    if npc_id != giver_npc_id:
        return ActionResult(False, "", reason=f"{npc_id!r} has no role in the parcel-delivery rumor")

    commitment = _get_fulfilled_commitment(actor, "deliver_parcel")
    if commitment is None:
        return ActionResult(False, "", reason="no fulfilled deliver_parcel commitment on record")

    commitment_id = commitment["commitment_id"]
    if _is_informed_of(actor, commitment_id):
        return ActionResult(False, "", reason="already informed of this delivery")

    _mark_informed(actor, commitment_id)
    if not _has_reputation_credit(actor):
        _mark_reputation_credited(actor)
        _adjust_reputation(actor, giver_npc_id, 1)

    return ActionResult(True, f"{npc.key} notes that the parcel reached Tarin Os.")


# docs/prospect-initial-playtest-design-spec.md §6, Quest 2 ("A Little
# Community Work"): Iri's fulfilling action. Unlike verify_revision_report,
# there's no player-reported value to check - world/garden.py's per-player
# flag is the only fact involved, set by a plain world action (commands/
# use.py), never by anything the model proposes. confirmed is a trivial
# required argument, same guideline-#7 reasoning as accept_help
# above (a zero-argument schema goes
# reliably uncalled).
def _validate_confirm_bed_tended(npc, actor, arguments: dict) -> ActionResult:
    npc_id = npc.db.npc_id
    scenario = SCENARIOS["tend_planting_bed"]
    if npc_id not in scenario.holder_npc_ids:
        return ActionResult(False, "", reason=f"{npc_id!r} has no holder role for 'tend_planting_bed'")

    precondition_ok = _is_bed_tended(actor)
    result = _fulfill_commitment_with_precondition(actor, "tend_planting_bed", npc_id, precondition_ok)
    if not result.ok:
        return ActionResult(False, "", reason=result.reason)
    return ActionResult(True, scenario.fulfill_narration.format(npc=npc.key, actor=actor.key))


def _fold_accents(text: str) -> str:
    # "Corner Café" has to still match a model that writes "Corner
    # Cafe" without the accent - strip combining marks rather than
    # require an exact character match.
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def _npc_sector(npc):
    """The sector the NPC's room was built in (world.build_sector tags every
    room with it); the default sector for a room that predates sector tags."""
    from world.build_sector import DEFAULT_SECTOR, SECTOR_TAG_CATEGORY

    room = getattr(npc, "location", None)
    sectors = room.tags.get(category=SECTOR_TAG_CATEGORY, return_list=True) if room is not None else []
    return sectors[0] if sectors else DEFAULT_SECTOR


def _find_neighborhood_rooms(destination_name: str, sector_id=None):
    """Match free-text destination against the room titles in the NPC's
    sector manifest, case- and accent-insensitively - by name, since
    that's how players ask (owner, 2026-10-16). Any room in the sector
    is a valid destination; persona and knowledge limit which ones an
    NPC actually offers (docs/build-sector-proposal.md Section 5).
    Returns every built room with that title, in manifest order (several
    rooms can share a title); [] if none.
    """
    from evennia import search_tag

    from world.build_sector import DEFAULT_SECTOR, room_titles

    destination_name = _fold_accents((destination_name or "").strip().lower())
    rooms = []
    for tag, name in room_titles(sector_id or DEFAULT_SECTOR):
        if _fold_accents(name.lower()) == destination_name:
            matches = search_tag(key=tag, category=ROOM_TAG_CATEGORY)
            if matches:
                rooms.append(matches[0])
    return rooms


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
    candidates = _find_neighborhood_rooms(destination_name, _npc_sector(npc))
    if not candidates:
        return ActionResult(False, "", reason=f"destination not in neighborhood: {destination_name!r}")

    start_room = actor.location
    if start_room is None:
        return ActionResult(False, "", reason="actor has no location")

    # Several rooms can share a title: the player means the closest one
    # (fewest exits from where they stand); on a tie, the first in manifest
    # order - min() keeps the first of equals (owner, 2026-10-16).
    routes = [path for room in candidates if (path := _find_exit_path(start_room, room)) is not None]
    if not routes:
        return ActionResult(False, "", reason=f"no known path from {start_room} to {destination_name!r}")
    path = min(routes, key=len)

    if not path:
        return ActionResult(True, f"{npc.key} says you're already there.")

    route_text = ", then ".join(_name_waypoints(start_room, path))
    return ActionResult(True, f"{npc.key} points the way: {route_text}.")


def _name_waypoints(start_room, path):
    """Each step of a route with the room it reaches ("east to Old
    Quarter Square"). Bare exit keys left the model to supply the
    landmark itself, and live (2026-10-18) Iri sent people "east along
    Old Quarter Street" when the route ran through the square."""
    steps = []
    room = start_room
    for key in path:
        exi = next(e for e in room.exits if e.key == key)
        room = exi.destination
        steps.append(f"{key} to {room.key}")
    return steps


# Validators that also take the player's message this turn.
_PLAYER_MESSAGE_VALIDATORS = {"remember_fact"}

_ACTION_VALIDATORS = {
    "serve_drink": _validate_serve_drink,
    "give_directions": _validate_give_directions,
    "ask_for_help": _validate_ask_for_help,
    "accept_help": _validate_accept_help,
    "decline_help": _validate_decline_help,
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
    "remember_fact": _validate_remember_fact,
    "confirm_bed_tended": _validate_confirm_bed_tended,
    "report_skitter_kills_to_tarin": _validate_report_skitter_kills_to_tarin,
    "log_dead_skitters_with_iri": _validate_log_dead_skitters_with_iri,
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
    "ask_for_help": {
        "type": "function",
        "function": {
            "name": "ask_for_help",
            "description": (
                "Ask the player to take the faulty heating-unit module to Tarin. Call "
                "this with confirmed=true in the same reply where you ask them."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmed": {
                        "type": "boolean",
                        "description": "Set to true to confirm you're asking them, not just mentioning the heating.",
                    }
                },
                "required": ["confirmed"],
            },
        },
    },
    "accept_help": {
        "type": "function",
        "function": {
            "name": "accept_help",
            "description": (
                "Record that the player has said yes to taking the module to Tarin, "
                "after you asked them in an earlier reply. Call this with "
                "confirmed=true the moment they agree, before handing over "
                "anything - it records the commitment itself, separately from "
                "physically giving them the module."
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
    "decline_help": {
        "type": "function",
        "function": {
            "name": "decline_help",
            "description": "Record that the player has said no to taking the module to Tarin. Call with confirmed=true.",
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmed": {
                        "type": "boolean",
                        "description": "Set to true to confirm they actually said no.",
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
                "decline_commitment to record it. If this call doesn't actually go through, "
                "that means something else of yours needs attention first and this genuinely "
                "isn't the moment to raise it - your reply has to stand completely on its own, "
                "as if you had never been about to mention it: don't describe the errand, the "
                "problem behind it, or anything about it. Respond only to whatever the player "
                "actually said, the same way you would if this topic had simply never occurred "
                "to you yet."
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
                "reached Tarin. Call it the moment they affirmatively report that it's been "
                "delivered. The engine checks that against the real record and will tell you the "
                "result - it is not something you can tell just by what they say. Do not call it "
                "for a question ('Did Tarin get it?'), a case where they're unsure, or a claim "
                "that it's still on its way."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmed": {
                        "type": "boolean",
                        "description": "Always true: the player has just reported the parcel delivered.",
                    }
                },
                "required": ["confirmed"],
            },
        },
    },
    "confirm_bed_tended": {
        "type": "function",
        "function": {
            "name": "confirm_bed_tended",
            "description": (
                "Confirm whether the player has actually tended the planting bed in Old Quarter "
                "Square. Call it the moment they tell you they've done it, or ask you to check - "
                "the engine checks whether they really used the gardening kit on the bed and will "
                "tell you the result; you have no way to know that yourself, however confident "
                "they sound."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmed": {
                        "type": "boolean",
                        "description": (
                            "Always true - this action takes no real argument, it just confirms "
                            "you're checking now."
                        ),
                    }
                },
                "required": ["confirmed"],
            },
        },
    },
    "report_skitter_kills_to_tarin": {
        "type": "function",
        "function": {
            "name": "report_skitter_kills_to_tarin",
            "description": (
                "Check whether the player has actually cleared enough skitters, and close the "
                "matter out if so. Call it the moment they tell you they've been hunting them or "
                "ask you to check - the engine checks the real count and will tell you the "
                "result; you have no way to know that yourself, however confident they sound."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmed": {
                        "type": "boolean",
                        "description": (
                            "Always true - this action takes no real argument, it just confirms "
                            "you're checking now."
                        ),
                    }
                },
                "required": ["confirmed"],
            },
        },
    },
    "log_dead_skitters_with_iri": {
        "type": "function",
        "function": {
            "name": "log_dead_skitters_with_iri",
            "description": (
                "Log the skitters this player has killed since their last report into the "
                "office's pest log. Call it the moment they tell you they've killed more "
                "skitters, or ask you to log or record them. You don't decide or ask how many - "
                "the engine counts the real kills and tells you the result."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmed": {
                        "type": "boolean",
                        "description": (
                            "Always true - this action takes no real argument, it just confirms "
                            "you're logging now."
                        ),
                    }
                },
                "required": ["confirmed"],
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
                "don't call it more than once or twice in a single conversation. A question "
                "is never a fact: if they ask something (\"what are you?\", \"what am I?\"), "
                "there's nothing to remember. You must quote their own words that state it; "
                "the engine drops the call if those words aren't in their latest message."
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
                    },
                    "player_words": {
                        "type": "string",
                        "description": (
                            "The player's own words from their latest message that state this "
                            "fact about themselves, copied exactly - e.g. 'I grew up near the "
                            "Docks'."
                        ),
                    },
                },
                "required": ["fact", "player_words"],
            },
        },
    },
}


def get_tool_schemas(action_names: list) -> list:
    """Tool definitions for the action names an NPC's persona grants."""
    return [ACTION_SCHEMAS[name] for name in action_names if name in ACTION_SCHEMAS]
