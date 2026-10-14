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

from world.actions import _create_parcel_for, get_tool_schemas, quest_context_for
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

DEFAULT_TRIALS = 5


@dataclass
class EvalScenario:
    name: str
    npc_id: str
    player_message: str
    expect_calls: set = field(default_factory=set)
    expect_no_calls: set = field(default_factory=set)
    history: list = field(default_factory=list)
    setup: callable = None  # optional actor -> None, to seed quest/commitment state
    notes: str = ""


@dataclass
class EvalResult:
    scenario: EvalScenario
    hits: int
    trials: int
    unexpected: list  # the called-action set from each non-matching trial


_TARIN_OFFERED_CONTEXT = [
    {
        "role": "assistant",
        "content": (
            '*Tarin frowns at a sheet of paper.* "Got a mismatched shipment manifest - '
            'could use someone to report it to the Civic Office. You up for that?"'
        ),
    },
]


def _setup_tarin_offered(actor):
    propose_commitment(actor, "discrepancy_report")


def _setup_veska_report_ready(actor):
    propose_commitment(actor, "discrepancy_report")
    accept_commitment(actor, "discrepancy_report")


def _setup_mara_parcel_offered(actor):
    propose_commitment(actor, "deliver_parcel")


def _setup_revision_check_accepted(actor):
    propose_commitment(actor, "verify_display_revision")
    accept_commitment(actor, "verify_display_revision")


def _setup_parcel_accepted(actor):
    # Mirrors what _validate_accept_commitment does for real play: a
    # real, carried Parcel, not just the commitment-lifecycle state -
    # accept_handoff's possession check needs the actual object. One
    # commitment, either Tarin or Veska can complete it (2026-10-13
    # redesign) - this setup is shared by both their eval scenarios.
    propose_commitment(actor, "deliver_parcel")
    accept_commitment(actor, "deliver_parcel")
    _create_parcel_for(actor, get_open_commitment_id(actor, "deliver_parcel"))


def _setup_parcel_delivered_to_tarin(actor):
    # docs/phase2e-word-gets-around-design.md: the commitment is really
    # fulfilled, but Mara's own proposer-side view stays "open" until
    # report_parcel_delivery tells her - called directly here rather
    # than through _validate_accept_handoff, same shortcut
    # _setup_tarin_offered already takes with the lifecycle functions.
    propose_commitment(actor, "deliver_parcel")
    accept_commitment(actor, "deliver_parcel")
    fulfill_commitment_with_precondition(actor, "deliver_parcel", "tarin_os", True)


_MARA_PARCEL_HANDED_OFF_CONTEXT = [
    {"role": "user", "content": "I'll get it to Tarin."},
    {
        "role": "assistant",
        "content": '*Mara hands over the parcel.* "Thanks for taking care of that - let me know how it goes."',
    },
]


_MARA_PARCEL_OFFERED_CONTEXT = [
    {"role": "user", "content": "Anything I can help with today?"},
    {
        "role": "assistant",
        "content": (
            '*Mara wipes down the counter.* "Actually, yeah - a courier left a parcel here '
            'for Tarin by mistake. You could run it to his workshop, or drop it at the Civic '
            'Office with Veska instead. Either works for me."'
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
    EvalScenario(
        name="tarin_propose_commitment_on_direct_opening",
        npc_id="tarin_os",
        player_message="You seem a bit off - something bothering you?",
        expect_calls={"propose_commitment"},
        notes="Tests the discoverability bar added to his persona (prompt_version 12).",
    ),
    EvalScenario(
        name="tarin_bare_greeting_does_not_propose",
        npc_id="tarin_os",
        player_message="Mornin' Tarin.",
        expect_no_calls={"propose_commitment"},
        notes=(
            "Regression for the overshoot found 2026-10-13: prompt_version 9's "
            "same-turn nudge made a bare greeting alone enough to trigger the "
            "offer, which the persona explicitly says not to do unprompted. "
            "Fixed in prompt_version 10."
        ),
    ),
    EvalScenario(
        name="tarin_routine_smalltalk_does_not_propose",
        npc_id="tarin_os",
        player_message="Evenin' Tarin, busy day?",
        expect_no_calls={"propose_commitment"},
        notes=(
            "Regression for the 2026-10-13 feedback that prompt_version 10's bar "
            "was still too low - ordinary small talk ('busy day?') was triggering "
            "the offer on the very first exchange. Raised further in "
            "prompt_version 12 to require something closer to a direct check-in, "
            "not routine pleasantries."
        ),
    ),
    EvalScenario(
        name="tarin_accept_commitment_after_offer",
        npc_id="tarin_os",
        setup=_setup_tarin_offered,
        history=_TARIN_OFFERED_CONTEXT,
        player_message="Yeah, I can do that.",
        expect_calls={"accept_commitment"},
    ),
    EvalScenario(
        name="veska_report_commitment_outcome_low_bar",
        npc_id="veska_renn",
        setup=_setup_veska_report_ready,
        player_message=(
            "Tarin asked me to report a shipment discrepancy - he got 12 components "
            "but the manifest says 16."
        ),
        expect_calls={"report_commitment_outcome"},
        notes="docs/phase2b-records-discrepancy-proposal.md: Veska's trigger should be deliberately low-bar.",
    ),
    # docs/phase2c-misdelivered-parcel-proposal.md scenarios below.
    EvalScenario(
        name="mara_propose_parcel_on_open_opener",
        npc_id="mara_voss",
        player_message="Anything I can help with today?",
        expect_calls={"propose_commitment"},
        notes=(
            "Tests guideline #11's failure mode (narrating the offer without calling "
            "it) on a cold open. This only checks that *some* propose_commitment "
            "fires, not that both routes were offered in the same turn - that needs "
            "manual transcript inspection of the call arguments, not just the name set. "
            "History: at prompt_version 13 this opener was ambiguous between the "
            "parcel and Mara's then-still-unprompted heating-unit need, and the model "
            "often narrated one or both without calling propose_commitment at all "
            "(1/8). A prompt_version 14 wording fix (the rule holds even when the "
            "parcel is only part of a multi-topic reply) raised this to 4/8, with 2 "
            "of those 4 coming back with empty arguments (a model tool-calling quirk, "
            "not a wording gap - commitments.py's get_scenario(None) check drops an "
            "empty/unknown commitment_type safely, so this never corrupted state). "
            "The real fix was a design change, not more wording: prompt_version 15 "
            "retired the heating-unit need's unprompted-mention behavior (it had "
            "already served its purpose for 2A's exit test, and the project owner "
            "doesn't expect prototype content to survive past this phase), leaving "
            "the parcel as Mara's only unprompted hook. That resolved the actual "
            "ambiguity: 6/8 now fire with fully correct arguments, 1/8 fires with "
            "empty arguments (same harmless quirk), 1/8 reasonably reinterprets the "
            "opener as a drink order instead. Two NPCs stacking unprompted-mention "
            "hooks is the thing to avoid; a single NPC with one unprompted hook plus "
            "reactive-only actions (accept_handoff, report_commitment_outcome) is fine."
        ),
    ),
    EvalScenario(
        name="mara_accept_commitment_question_is_not_acceptance",
        npc_id="mara_voss",
        history=_MARA_PARCEL_OFFERED_CONTEXT,
        player_message="Could I take it to Tarin?",
        expect_no_calls={"accept_commitment"},
        notes="Guideline #10's exact failure shape, re-tested against the new action.",
    ),
    EvalScenario(
        name="mara_accept_commitment_clear_choice",
        npc_id="mara_voss",
        history=_MARA_PARCEL_OFFERED_CONTEXT,
        player_message="Sure, I'll take care of it.",
        expect_calls={"accept_commitment"},
        notes=(
            "2026-10-13 redesign: deliberately destination-agnostic wording - "
            "Mara must accept this without asking which NPC the player means, "
            "since that's exactly the question that caused her to lock in a "
            "guessed destination the player never actually chose."
        ),
    ),
    EvalScenario(
        name="tarin_accept_handoff_on_clear_offer",
        npc_id="tarin_os",
        setup=_setup_parcel_accepted,
        player_message="Here, this parcel's for you - Mara had it by mistake.",
        expect_calls={"accept_handoff"},
    ),
    EvalScenario(
        name="tarin_accept_handoff_ambiguous_possession_does_not_fire",
        npc_id="tarin_os",
        setup=_setup_parcel_accepted,
        player_message=(
            "I've got your parcel, but I haven't decided whether to deliver it myself "
            "or leave it at the Civic Office."
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
            "the positive case."
        ),
    ),
    EvalScenario(
        name="veska_accept_handoff_on_explicit_deposit",
        npc_id="veska_renn",
        setup=_setup_parcel_accepted,
        player_message="I'd like to leave this misdirected parcel here for Tarin Os. Please take it.",
        expect_calls={"accept_handoff"},
    ),
    EvalScenario(
        name="veska_accept_handoff_informational_question_does_not_fire",
        npc_id="veska_renn",
        setup=_setup_parcel_accepted,
        player_message="Do you handle lost parcels here?",
        expect_no_calls={"accept_handoff"},
    ),
    # docs/phase2-quest-prototype-design.md §14 / docs/phase2d-
    # noticeboard-check-proposal.md's genuine-corroboration scenario.
    # Pass/fail correctness itself is a deterministic Python unit
    # test (world/test_actions.py); these only check whether Iri
    # calls verify_revision_report at all for each phrasing.
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
    # docs/phase2e-word-gets-around-design.md: Mara learning, via the
    # player, that the parcel she handed off actually arrived.
    EvalScenario(
        name="mara_report_parcel_delivery_clear_report_fires",
        npc_id="mara_voss",
        setup=_setup_parcel_delivered_to_tarin,
        history=_MARA_PARCEL_HANDED_OFF_CONTEXT,
        player_message="Tarin got your parcel - he took it off my hands.",
        expect_calls={"report_parcel_delivery"},
    ),
    EvalScenario(
        name="mara_report_parcel_delivery_question_does_not_fire",
        npc_id="mara_voss",
        setup=_setup_parcel_delivered_to_tarin,
        history=_MARA_PARCEL_HANDED_OFF_CONTEXT,
        player_message="Did Tarin get your parcel?",
        expect_no_calls={"report_parcel_delivery"},
    ),
    EvalScenario(
        name="mara_report_parcel_delivery_uncertain_does_not_fire",
        npc_id="mara_voss",
        setup=_setup_parcel_delivered_to_tarin,
        history=_MARA_PARCEL_HANDED_OFF_CONTEXT,
        player_message="I think I left it with one of them, not sure which.",
        expect_no_calls={"report_parcel_delivery"},
    ),
    EvalScenario(
        name="mara_report_parcel_delivery_vague_report_known_issue",
        npc_id="mara_voss",
        setup=_setup_parcel_delivered_to_tarin,
        history=_MARA_PARCEL_HANDED_OFF_CONTEXT,
        player_message="I delivered your parcel.",
        expect_no_calls={"report_parcel_delivery"},
        notes=(
            "Known issue, guideline #17: correct behavior is to ask which NPC received "
            "it, not call this at all, since neither Tarin nor Veska is named. Confirmed "
            "live (2026-10-14) at roughly 1/5 - the model reliably fills "
            "reported_recipient with a guessed default (the schema's first enum value) "
            "instead, even after a wording rewrite aimed at this exact case produced no "
            "measurable change (pattern 5/10's signal to stop iterating). Not treated as "
            "a correctness bug and deliberately not chased further: the validator checks "
            "the guess against the real fulfilled_by_npc_id regardless of how the model "
            "arrived at it, so a wrong guess is just correctly rejected, never an unearned "
            "success - this scenario's setup happens to make 'tarin' the correct answer, "
            "so a 'miss' here only costs a skipped clarifying question, not corrupted "
            "state. Worth re-running if this persona section changes again."
        ),
    ),
    EvalScenario(
        name="mara_asked_before_being_told_does_not_claim_knowledge",
        npc_id="mara_voss",
        setup=_setup_parcel_delivered_to_tarin,
        history=_MARA_PARCEL_HANDED_OFF_CONTEXT,
        player_message="Has my parcel arrived yet?",
        expect_no_calls={"report_parcel_delivery"},
        notes=(
            "The real thing this checks (that she answers with genuine uncertainty, "
            "not an assumption either way) needs manual transcript inspection, not "
            "just the tool-call set - the commitment is actually fulfilled underneath, "
            "so a model that 'just knows' would be leaking state the projector is "
            "supposed to be hiding from her, not a tool-calling miss."
        ),
    ),
]


def run_scenario(scenario: EvalScenario, trials: int = DEFAULT_TRIALS) -> EvalResult:
    """Run one scenario `trials` times against the real model and
    tally how often it matched expectations. Creates and deletes a
    throwaway Character so quest/commitment state (actor.db) works
    exactly like it does for a real player."""
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
        messages += scenario.history
        messages.append({"role": "user", "content": scenario.player_message})

        hits = 0
        unexpected = []
        for _ in range(trials):
            reply = chat(messages, tools=tools, max_tokens=profile.max_reply_tokens)
            called = {call["name"] for call in reply.tool_calls}
            ok = scenario.expect_calls <= called and not (scenario.expect_no_calls & called)
            if ok:
                hits += 1
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
