"""
A manually-triggered reliability eval for NPC tool-calling - not part
of the deterministic unit-test suite. CLAUDE.md's testing rules are
about the validator/prompt builder catching silent bugs on every run;
this is a different thing entirely: checking how *reliably* the live
model itself makes the right call for scenarios phase 1/2 playtesting
already found to be tricky (docs/npc-action-prompt-guidelines.md,
especially guidelines #9 and #10). It costs real API usage and is
never run as part of `evennia test` - run it deliberately after
changing a persona, content/npc-shared-rules.md, or the configured
model (world/llm_client.py).

Each scenario sends a fixed system prompt + conversation + player line
to the real model `trials` times and reports how often the expected
tool call(s) fired, and whether any unexpected set showed up instead -
reported as a rate, not a hard pass/fail, since the entire premise is
that these are probabilistic. A low rate on a scenario marked as a
known issue isn't a regression; a low rate anywhere else is worth
investigating the same way guideline #5 describes.

Run with:
    evennia shell -c "from world.npc_eval import run; run()"
"""

from dataclasses import dataclass, field
from uuid import uuid4

from evennia import create_object

from commands.say import FORCE_REACTION_ACTIONS, _build_followup_messages
from world.actions import _create_parcel_for, get_tool_schemas, quest_context_for, validate_and_apply
from world.build_npcs import build as build_npcs
from world.build_rooms import build as build_rooms
from world.commitments import (
    accept_commitment,
    commitment_context_for,
    fulfill_commitment_with_precondition,
    get_open_commitment_id,
    propose_commitment,
)
from world.llm_client import chat
from world.npc_profile import parse_persona
from world.prompt_builder import build_system_prompt
from world.skitters import skitter_record_context_for

DEFAULT_TRIALS = 5


@dataclass
class EvalScenario:
    name: str
    npc_id: str
    player_message: str
    expect_calls: set = field(default_factory=set)
    expect_no_calls: set = field(default_factory=set)
    # Case-insensitive substring checks against the reply's own spoken
    # text - for a scenario whose success/failure isn't about which
    # tool call fired at all (e.g. Veska correctly stating which
    # resolution actually happened), only what the model actually
    # said. Checked in addition to expect_calls/expect_no_calls, not
    # instead of them - a scenario can use either, both, or neither.
    expect_text_contains: list = field(default_factory=list)
    expect_text_absent: list = field(default_factory=list)
    history: list = field(default_factory=list)
    setup: callable = None  # optional actor -> None, to seed quest/commitment state
    notes: str = ""


@dataclass
class EvalResult:
    scenario: EvalScenario
    hits: int
    trials: int
    unexpected: list  # the called-action set from each non-matching trial


def _setup_revision_check_accepted(actor):
    propose_commitment(actor, "verify_display_revision")
    accept_commitment(actor, "verify_display_revision")


def _setup_parcel_accepted(actor):
    # Mirrors what _validate_accept_commitment does for real play: a
    # real, carried Parcel, not just the commitment-lifecycle state -
    # accept_handoff's possession check needs the actual object.
    propose_commitment(actor, "deliver_parcel")
    accept_commitment(actor, "deliver_parcel")
    _create_parcel_for(actor, get_open_commitment_id(actor, "deliver_parcel"))


def _setup_parcel_delivered_to_tarin(actor):
    # docs/phase2e-word-gets-around-design.md: the commitment is really
    # fulfilled, but Veska's own proposer-side view stays "open" until
    # report_parcel_delivery tells her - called directly here rather
    # than through _validate_accept_handoff, same shortcut other
    # setups in this file take with the bare lifecycle functions.
    propose_commitment(actor, "deliver_parcel")
    accept_commitment(actor, "deliver_parcel")
    fulfill_commitment_with_precondition(actor, "deliver_parcel", "tarin_os", True)


_VESKA_PARCEL_HANDED_OFF_CONTEXT = [
    {"role": "user", "content": "I'll get it to Tarin."},
    {
        "role": "assistant",
        "content": '*slides the parcel across the counter.* "Thank you. Let me know when it\'s with him."',
    },
]


def _setup_tarin_hunt_eligible_only(actor):
    # No-op: hunt_skitters is Tarin's only commitment scenario of his
    # own left (discrepancy_report/unverified_notice were removed
    # 2026-10-16 - see CLAUDE.md's "One quest offer per NPC" and
    # docs/npc-action-prompt-guidelines.md guideline #20), so a fresh
    # actor is already the right fixture with nothing left to isolate
    # against. Kept as a named setup, not deleted, so the eval
    # scenarios below keep documenting why a fresh actor is correct.
    pass


def _setup_tarin_hunt_offered(actor):
    propose_commitment(actor, "hunt_skitters")


def _setup_actor_in_room(room_key):
    """Returns a setup callable placing a fresh actor in `room_key` -
    `give_directions`'s BFS (`world/actions.py`'s `_find_exit_path`)
    needs a real starting location, which no existing setup provides."""

    def setup(actor):
        rooms = build_rooms()
        actor.location = rooms[room_key]

    return setup


def _setup_tarin_hunt_report_ready(actor):
    from world.skitters import record_kill

    propose_commitment(actor, "hunt_skitters")
    accept_commitment(actor, "hunt_skitters")
    for _ in range(3):
        record_kill(actor)


def _setup_iri_skitter_log_ready(actor):
    """Post-quest loop: Tarin's quest already fulfilled, two new kills
    since then that haven't been logged with Iri yet."""
    from world.skitters import record_kill

    _setup_tarin_hunt_report_ready(actor)
    fulfill_commitment_with_precondition(actor, "hunt_skitters", "tarin_os", True)
    for _ in range(2):
        record_kill(actor)


_VESKA_PARCEL_OFFERED_CONTEXT = [
    {"role": "user", "content": "Anything I can help with today?"},
    {
        "role": "assistant",
        "content": (
            '*glances at the parcel at her end of the counter.* "As it happens, yes. A courier '
            'left that here by mistake - it\'s addressed to Tarin Os at the Maintenance '
            'Workshop. I can\'t leave the counter. Could you take it to him?"'
        ),
    },
]


SCENARIOS = [
    # The heating-unit/module-exchange quest (2A) was retired from
    # Mara's and Tarin's live personas 2026-10-13 - it served its
    # purpose for 2A's exit test and isn't expected to survive past the
    # prototype. Its old eval scenarios (accept_help's clear-commitment,
    # ambiguous-question, and same-turn-chaining cases) are removed
    # along with it; see git history if that reliability data is ever
    # needed again.
    EvalScenario(
        name="mara_serve_drink_slang",
        npc_id="mara_voss",
        player_message="Could I get a cup of joe?",
        expect_calls={"serve_drink"},
    ),
    EvalScenario(
        name="mara_remember_fact_personal_job",
        npc_id="mara_voss",
        player_message="I work as a dock loader, by the way.",
        expect_calls={"remember_fact"},
        notes="Control case for the known Voldren issue below - this reliably scores well.",
    ),
    EvalScenario(
        name="mara_remember_fact_shared_species_known_issue",
        npc_id="mara_voss",
        player_message="I'm Voldren too, by the way.",
        expect_calls={"remember_fact"},
        notes=(
            "Known issue (guideline #15): 0/5 live even with no prior memory or history - "
            "the model narrates a reaction (often echoing the Cave Crawler section) and "
            "never calls the action. Two correctly-targeted wording fixes made no "
            "measurable difference; not expected to score well. Tracked here so it's "
            "visible if it's ever fixed, and so a persona edit to this section can be "
            "checked for making it worse."
        ),
    ),
    # The heating unit is Mara's only errand again since the errand
    # redistribution (2026-10-16). Live playtest 2026-10-17 (prompt_version
    # 44): three heating cues in a row got no ask, and "What's wrong with the
    # heating?" fired give_directions to the workshop instead - her new
    # redirect role pulling the topic to Tarin. prompt_version 45 limits
    # give_directions to actual route requests; the "ask" itself is pending
    # Lore's LR-DEV-0004. Whether she asks is text, not a tool call (there's
    # no propose step for this errand), so these need transcript inspection
    # too.
    EvalScenario(
        name="mara_heating_cold_cue_does_not_give_directions",
        npc_id="mara_voss",
        player_message="Morning Mara... It's awfully cold in here.",
        expect_no_calls={"give_directions", "accept_help"},
        notes="Transcript check: she should ask the player to take the module to Tarin.",
    ),
    EvalScenario(
        name="mara_heating_question_does_not_give_directions",
        npc_id="mara_voss",
        player_message="What's wrong with the heating?",
        expect_no_calls={"give_directions", "accept_help"},
        notes="Transcript check: explain the module and ask, not 'go ask Tarin'.",
    ),
    EvalScenario(
        name="mara_heating_offer_accepts_and_hands_over",
        npc_id="mara_voss",
        player_message="I'll take the module over to Tarin for you.",
        expect_calls={"accept_help", "give_faulty_module"},
        notes="Guideline #9's same-turn chaining; live 2026-10-17 she accepted but didn't hand it over.",
    ),
    # docs/phase2c-misdelivered-parcel-proposal.md scenarios below.
    # The parcel moved from Mara to Veska 2026-10-16 (docs/errand-
    # redistribution-plan.md); Mara's reliability history for these
    # cases (prompt_versions 13-15) is in git history. Veska's have not
    # been run yet.
    EvalScenario(
        name="veska_propose_parcel_on_open_opener",
        npc_id="veska_renn",
        player_message="Anything I can help with today?",
        expect_calls={"propose_commitment"},
        notes=(
            "Guideline #11's failure mode (narrating the offer without calling it) "
            "on a cold open - the parcel is Veska's only unprompted hook."
        ),
    ),
    EvalScenario(
        name="veska_accept_commitment_question_is_not_acceptance",
        npc_id="veska_renn",
        history=_VESKA_PARCEL_OFFERED_CONTEXT,
        player_message="Where's the Maintenance Workshop?",
        expect_no_calls={"accept_commitment"},
        notes="Guideline #10's exact failure shape.",
    ),
    EvalScenario(
        name="veska_accept_commitment_clear_choice",
        npc_id="veska_renn",
        history=_VESKA_PARCEL_OFFERED_CONTEXT,
        player_message="Sure, I'll take care of it.",
        expect_calls={"accept_commitment"},
    ),
    EvalScenario(
        name="tarin_accept_handoff_on_clear_offer",
        npc_id="tarin_os",
        setup=_setup_parcel_accepted,
        player_message="Here, this parcel's for you - it ended up at the Civic Office by mistake.",
        expect_calls={"accept_handoff"},
    ),
    EvalScenario(
        name="tarin_accept_handoff_ambiguous_possession_does_not_fire",
        npc_id="tarin_os",
        setup=_setup_parcel_accepted,
        player_message=(
            "I've got your parcel somewhere, I'll dig it out for you later."
        ),
        expect_no_calls={"accept_handoff"},
        notes=(
            "docs/phase2c-misdelivered-parcel-proposal.md §5's named test: real "
            "possession must not be enough on its own - the player hasn't actually "
            "offered it yet. Guideline #10's exact pattern recurred here at "
            "prompt_version 13 (2/5: his own hedging dialogue was correct every "
            "trial, but the tool call still fired independently of it 3/5 times) - "
            "unlike that case, this one has a real consequence (it actually "
            "transfers the parcel), so it was worth one more rewrite attempt rather "
            "than accepting it. Making the hedge-check an explicit first step, "
            "phrased to catch the model's own conditional phrasing in its reply as "
            "the tell, fixed it to 8/8 in prompt_version 14 with no regression on "
            "the positive case. The player line was reworded 2026-10-16 once the "
            "Civic Office stopped being an alternative destination (errand "
            "redistribution); it hasn't been re-run since."
        ),
    ),
    # docs/phase2-quest-prototype-design.md §14 / docs/phase2d-
    # noticeboard-check-proposal.md's genuine-corroboration scenario.
    # Pass/fail correctness itself is a deterministic Python unit
    # test (world/test_actions.py); these only check whether Iri
    # calls verify_revision_report at all for each phrasing.
    # The display check moved to Daven 2026-10-16 (docs/errand-
    # redistribution-plan.md). Mentoring is his real job, so the
    # negative case matters as much as the positive one: the errand
    # must never surface as a "what should I do?" suggestion.
    EvalScenario(
        name="daven_display_question_proposes",
        npc_id="daven_varek",
        player_message="What's that display on your wall?",
        expect_calls={"propose_commitment"},
        notes="Explain-and-ask in one reply; the old Mara version needed guideline #11's same-turn rule.",
    ),
    EvalScenario(
        name="daven_what_should_i_do_does_not_propose",
        npc_id="daven_varek",
        player_message="I'm not sure what to do next. Any ideas?",
        expect_no_calls={"propose_commitment"},
    ),
    EvalScenario(
        name="iri_verify_revision_clear_report_fires",
        npc_id="iri_vael",
        setup=_setup_revision_check_accepted,
        player_message="The display reads 4182.",
        expect_calls={"verify_revision_report"},
    ),
    EvalScenario(
        name="iri_verify_revision_question_does_not_fire",
        npc_id="iri_vael",
        setup=_setup_revision_check_accepted,
        player_message="Is the code 4182?",
        expect_no_calls={"verify_revision_report"},
    ),
    EvalScenario(
        name="iri_verify_revision_negation_does_not_fire",
        npc_id="iri_vael",
        setup=_setup_revision_check_accepted,
        player_message="I don't think it said 4182.",
        expect_no_calls={"verify_revision_report"},
    ),
    EvalScenario(
        name="iri_verify_revision_ambiguous_choice_does_not_fire",
        npc_id="iri_vael",
        setup=_setup_revision_check_accepted,
        player_message="Was it 4182 or 4812? I can't remember which.",
        expect_no_calls={"verify_revision_report"},
    ),
    EvalScenario(
        name="iri_verify_revision_forgotten_does_not_fire",
        npc_id="iri_vael",
        setup=_setup_revision_check_accepted,
        player_message="I forgot the number, sorry.",
        expect_no_calls={"verify_revision_report"},
    ),
    EvalScenario(
        name="iri_verify_revision_confident_wrong_guess_still_fires",
        npc_id="iri_vael",
        setup=_setup_revision_check_accepted,
        player_message="It's definitely 9999. Trust me.",
        expect_calls={"verify_revision_report"},
        notes=(
            "Confidence is irrelevant to correctness (the engine decides, not Iri) - "
            "this should still fire and then simply fail the Python-level check."
        ),
    ),
    # docs/phase2e-word-gets-around-design.md: the parcel's giver (Veska
    # since the errand redistribution) learning, via the player, that
    # the parcel she handed off actually arrived.
    EvalScenario(
        name="veska_report_parcel_delivery_clear_report_fires",
        npc_id="veska_renn",
        setup=_setup_parcel_delivered_to_tarin,
        history=_VESKA_PARCEL_HANDED_OFF_CONTEXT,
        player_message="Tarin got your parcel - he took it off my hands.",
        expect_calls={"report_parcel_delivery"},
    ),
    EvalScenario(
        name="veska_report_parcel_delivery_unnamed_report_fires",
        npc_id="veska_renn",
        setup=_setup_parcel_delivered_to_tarin,
        history=_VESKA_PARCEL_HANDED_OFF_CONTEXT,
        player_message="I delivered your parcel.",
        expect_calls={"report_parcel_delivery"},
        notes=(
            "Was guideline #17's known issue under Mara (the model guessed a "
            "reported_recipient instead of asking which of Tarin or Veska). With "
            "Tarin the only possible recipient the argument is gone (plan D1), so "
            "an unnamed report is now a valid one and should fire."
        ),
    ),
    EvalScenario(
        name="veska_report_parcel_delivery_question_does_not_fire",
        npc_id="veska_renn",
        setup=_setup_parcel_delivered_to_tarin,
        history=_VESKA_PARCEL_HANDED_OFF_CONTEXT,
        player_message="Did Tarin get the parcel?",
        expect_no_calls={"report_parcel_delivery"},
    ),
    EvalScenario(
        name="veska_report_parcel_delivery_still_in_transit_does_not_fire",
        npc_id="veska_renn",
        setup=_setup_parcel_delivered_to_tarin,
        history=_VESKA_PARCEL_HANDED_OFF_CONTEXT,
        player_message="I haven't dropped it off yet, I'll get to it later.",
        expect_no_calls={"report_parcel_delivery"},
    ),
    EvalScenario(
        name="veska_asked_before_being_told_does_not_claim_knowledge",
        npc_id="veska_renn",
        setup=_setup_parcel_delivered_to_tarin,
        history=_VESKA_PARCEL_HANDED_OFF_CONTEXT,
        player_message="Has the parcel reached Tarin yet?",
        expect_no_calls={"report_parcel_delivery"},
        notes=(
            "The real thing this checks (that she answers with genuine uncertainty, "
            "not an assumption either way) needs manual transcript inspection, not "
            "just the tool-call set - the commitment is actually fulfilled underneath, "
            "so a model that 'just knows' would be leaking state the projector is "
            "supposed to be hiding from her, not a tool-calling miss."
        ),
    ),
    # Quest 3 ("Unwelcome Guests," docs/playtest-quest3-skitters-
    # design.md).
    EvalScenario(
        name="tarin_generic_checkin_does_not_invent_a_commitment_topic",
        npc_id="tarin_os",
        setup=_setup_tarin_hunt_eligible_only,
        player_message="You seem a bit off - something bothering you?",
        expect_text_absent=["manifest", "shipment", "discrepancy", "components", "notice"],
        notes=(
            "2026-10-16: discrepancy_report and unverified_notice (the scenarios "
            "this originally regression-tested against, after a real live-playtest "
            "leak - see docs/playtest-quest3-skitters-design.md and docs/npc-"
            "action-prompt-guidelines.md guideline #20) were removed entirely. "
            "Kept as a plain regression check that the removal was clean - Tarin's "
            "persona no longer has any manifest/notice content at all for the "
            "model to hallucinate from on a generic check-in."
        ),
    ),
    EvalScenario(
        name="tarin_hunt_skitters_specific_ask_proposes",
        npc_id="tarin_os",
        setup=_setup_tarin_hunt_eligible_only,
        player_message="Are the skitters still giving you trouble around here?",
        expect_calls={"propose_commitment"},
        notes="Reactive-only bar should still fire reliably on an on-topic ask.",
    ),
    EvalScenario(
        name="tarin_hunt_skitters_accept_after_offer",
        npc_id="tarin_os",
        setup=_setup_tarin_hunt_offered,
        player_message="Yeah, I'll take care of them.",
        expect_calls={"accept_commitment"},
    ),
    EvalScenario(
        name="tarin_report_skitter_kills_after_enough",
        npc_id="tarin_os",
        setup=_setup_tarin_hunt_report_ready,
        player_message="I've cleared three of them, like you asked.",
        expect_calls={"report_skitter_kills_to_tarin"},
    ),
    EvalScenario(
        name="iri_logs_more_dead_skitters",
        npc_id="iri_vael",
        setup=_setup_iri_skitter_log_ready,
        player_message="I killed some more skitters.",
        expect_calls={"log_dead_skitters_with_iri"},
    ),
    EvalScenario(
        name="iri_skitter_total_question_does_not_log",
        npc_id="iri_vael",
        setup=_setup_iri_skitter_log_ready,
        player_message="How many skitters do I have on record?",
        expect_no_calls={"log_dead_skitters_with_iri"},
        notes=(
            "Asking for the total is answered from the injected per-turn context, "
            "not by logging - the count should only move when they report kills."
        ),
    ),
    EvalScenario(
        name="tarin_hunt_skitters_question_is_not_acceptance",
        npc_id="tarin_os",
        setup=_setup_tarin_hunt_offered,
        player_message="What is a skitter?",
        expect_no_calls={"accept_commitment"},
        notes=(
            "2026-10-15 live playtest miss: Tarin's accept_commitment wording "
            "already states plainly that a question about the tool, the "
            "skitters, or how it works is still just a question - this fired "
            "anyway, handing over the shock baton. Scored 5/5 here (2026-10-15 "
            "controlled re-run) - didn't reproduce the live miss, which likely "
            "needs the real conversation history (Tarin's own propose_commitment "
            "reply immediately before it) to trigger, not just a bare "
            "'offered' state with no history. Kept as a permanent regression "
            "check; worth adding the real preceding history to this scenario if "
            "it ever misses again, rather than assuming today's clean 5/5 means "
            "the live failure can't recur."
        ),
    ),
    # Directions, 2026-10-15 live playtest: Given, Iri, Daven, and Mara all
    # gave different-sounding, sometimes-wrong routes. world/actions.py's
    # _validate_give_directions does a real BFS over the actual room graph -
    # it cannot be wrong - so any bad route in play means the model narrated
    # a route in prose instead of calling the action (guideline #1's exact
    # failure mode). These scenarios check the call actually fires; they
    # don't need to check the route text itself, since the engine guarantees
    # that part once the call happens at all.
    EvalScenario(
        name="given_give_directions_fires_on_direct_ask",
        npc_id="given_marr",
        setup=_setup_actor_in_room("medical_bay"),
        player_message="How do I get out of here to Old Quarter Square?",
        expect_calls={"give_directions"},
    ),
    EvalScenario(
        name="daven_give_directions_fires_on_direct_ask",
        npc_id="daven_varek",
        setup=_setup_actor_in_room("daven_office"),
        player_message="How do I get to the Maintenance Workshop from here?",
        expect_calls={"give_directions"},
    ),
    EvalScenario(
        name="iri_give_directions_fires_on_direct_ask",
        npc_id="iri_vael",
        setup=_setup_actor_in_room("civic_office"),
        player_message="How do I get to the Corner Cafe from here?",
        expect_calls={"give_directions"},
    ),
    EvalScenario(
        name="mara_give_directions_fires_on_direct_ask",
        npc_id="mara_voss",
        setup=_setup_actor_in_room("corner_cafe"),
        player_message="How do I get to the Maintenance Workshop from here?",
        expect_calls={"give_directions"},
        notes=(
            "2026-10-15: Mara didn't have give_directions at all before this - "
            "she gave a freehand, unvalidated route to Tarin's workshop live. "
            "Newly added action; this is its first reliability check."
        ),
    ),
    # docs/playtest-findings.md PF-0002 (2026-10-17): give_directions fired on
    # lines that never asked the way - the NPC offered directions and called
    # the action in the same reply. The player lines are the live ones.
    EvalScenario(
        name="given_unwell_does_not_give_directions",
        npc_id="given_marr",
        setup=_setup_actor_in_room("medical_bay"),
        player_message="I think I'm gonna be sick.",
        expect_no_calls={"give_directions"},
    ),
    EvalScenario(
        name="daven_lost_does_not_give_directions",
        npc_id="daven_varek",
        setup=_setup_actor_in_room("daven_office"),
        player_message="I don't know what to do.",
        expect_no_calls={"give_directions"},
    ),
    EvalScenario(
        name="daven_where_to_look_does_not_give_directions",
        npc_id="daven_varek",
        setup=_setup_actor_in_room("daven_office"),
        player_message="Where should I be looking?",
        expect_no_calls={"give_directions"},
        notes="Borderline: 'where' without a destination. Not asking the way to anywhere.",
    ),
]


def run_scenario(scenario: EvalScenario, trials: int = DEFAULT_TRIALS) -> EvalResult:
    """Run one scenario `trials` times against the real model and
    tally how often it matched expectations. Creates and deletes a
    throwaway Character so quest/commitment state (actor.db) works
    exactly like it does for a real player.

    2026-10-16: now actually runs each tool call through
    validate_and_apply (same as commands/say.py's real pipeline), and
    for an action in FORCE_REACTION_ACTIONS, simulates the real
    follow-up "react to what actually happened" call and scores
    *that* reply's text - not the first completion's - against
    expect_text_contains/expect_text_absent. Before this, the harness
    only ever looked at the first completion, so it could not catch a
    bug where the tool call itself was correctly rejected by the
    engine but the reaction's own text still asserted the rejected
    claim as true (confirmed live, 2026-10-15/16, Tarin's hunt_
    skitters/discrepancy_report priority gate) - the exact shape of
    gap docs/engineering-pitfalls.md #8 already named for the display
    layer, recurring here in the eval harness instead. expect_calls/
    expect_no_calls still check the *original* completion's tool
    calls - that's what actually gets applied, never the reaction's."""
    build_rooms()
    npc = build_npcs()[scenario.npc_id]
    actor = create_object("typeclasses.characters.Character", key=f"EvalActor-{uuid4().hex[:8]}")
    try:
        if scenario.setup:
            scenario.setup(actor)

        profile = parse_persona(scenario.npc_id)
        system_prompt = build_system_prompt(scenario.npc_id)
        tools = get_tool_schemas(profile.actions)

        messages = [{"role": "system", "content": system_prompt.text}]
        quest_ctx = quest_context_for(profile.actions, actor)
        if quest_ctx:
            messages.append({"role": "system", "content": quest_ctx})
        commitment_ctx = commitment_context_for(scenario.npc_id, profile.actions, actor)
        if commitment_ctx:
            messages.append({"role": "system", "content": commitment_ctx})
        skitter_ctx = skitter_record_context_for(profile.actions, actor)
        if skitter_ctx:
            messages.append({"role": "system", "content": skitter_ctx})
        messages += scenario.history
        messages.append({"role": "user", "content": scenario.player_message})

        hits = 0
        unexpected = []
        for _ in range(trials):
            reply = chat(messages, tools=tools, max_tokens=profile.max_reply_tokens)
            called = {call["name"] for call in reply.tool_calls}

            displayed_text = reply.text
            if reply.tool_calls and (called & FORCE_REACTION_ACTIONS):
                tool_results = [
                    {
                        "applied": (result := validate_and_apply(npc, actor, call["name"], call["arguments"], scenario.player_message)).applied,
                        "reason": result.reason,
                        "narration": result.narration,
                    }
                    for call in reply.tool_calls
                ]
                followup_messages = _build_followup_messages(
                    messages, reply.text, reply.tool_calls, tool_results
                )
                reaction = chat(followup_messages, max_tokens=profile.max_reply_tokens)
                displayed_text = reaction.text

            text = (displayed_text or "").lower()
            ok = (
                scenario.expect_calls <= called
                and not (scenario.expect_no_calls & called)
                and all(s.lower() in text for s in scenario.expect_text_contains)
                and not any(s.lower() in text for s in scenario.expect_text_absent)
            )
            if ok:
                hits += 1
            elif scenario.expect_text_contains or scenario.expect_text_absent:
                # A text-content scenario's failure is usually about
                # wording, not the tool-call set - keep the actual text
                # alongside it rather than just the (likely correct,
                # unhelpful) called-action set.
                unexpected.append((called, displayed_text))
            else:
                unexpected.append(called)
        return EvalResult(scenario, hits, trials, unexpected)
    finally:
        actor.delete()


def run(trials: int = DEFAULT_TRIALS, scenarios=None) -> list:
    """Run every scenario (or a given subset) and print a rate report."""
    scenarios = SCENARIOS if scenarios is None else scenarios
    results = [run_scenario(scenario, trials=trials) for scenario in scenarios]

    print(f"\nNPC tool-call reliability eval ({trials} trials each)\n" + "-" * 60)
    for result in results:
        print(f"{result.scenario.name}: {result.hits}/{result.trials}")
        if result.scenario.notes:
            print(f"    note: {result.scenario.notes}")
        if result.unexpected:
            print(f"    unexpected tool-call sets seen: {result.unexpected}")
    print("-" * 60)
    return results
