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

from world.actions import get_tool_schemas, quest_context_for
from world.commitments import accept_commitment, commitment_context_for, propose_commitment
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


# Mara having already raised the heating-unit errand, for scenarios
# that depend on it being mid-conversation rather than a cold open.
_MARA_HEATING_UNIT_CONTEXT = [
    {"role": "user", "content": "Is something wrong with the heater in here?"},
    {
        "role": "assistant",
        "content": (
            '*Mara rubs her hands together.* "A bit - probably the temperature module. '
            'Could use a hand getting it to Tarin."'
        ),
    },
]

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


SCENARIOS = [
    EvalScenario(
        name="mara_accept_help_clear_commitment",
        npc_id="mara_voss",
        history=_MARA_HEATING_UNIT_CONTEXT,
        player_message="Sure, I'll take it over to him.",
        expect_calls={"accept_help"},
    ),
    EvalScenario(
        name="mara_accept_help_ambiguous_question",
        npc_id="mara_voss",
        history=_MARA_HEATING_UNIT_CONTEXT,
        player_message="You need someone to take it to Tarin?",
        expect_no_calls={"accept_help"},
        notes=(
            "Known issue (guideline #10): historically fires on this question "
            "even though it's not a first-person commitment - two persona "
            "rewrites didn't change it. Tracked here to notice if that ever "
            "changes, not expected to score well."
        ),
    ),
    EvalScenario(
        name="mara_serve_drink_slang",
        npc_id="mara_voss",
        player_message="Could I get a cup of joe?",
        expect_calls={"serve_drink"},
    ),
    EvalScenario(
        name="mara_accept_help_and_give_module_same_turn",
        npc_id="mara_voss",
        history=_MARA_HEATING_UNIT_CONTEXT,
        player_message="Yes, I'll take it to him right now.",
        expect_calls={"accept_help", "give_faulty_module"},
        notes="Guideline #9: both should fire in the same completion, not paced across turns.",
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
