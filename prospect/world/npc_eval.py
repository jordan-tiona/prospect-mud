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
    fulfill_commitment,
    fulfill_commitment_with_precondition,
    get_open_commitment_id,
    propose_commitment,
    record_acknowledgment,
)
from world.llm_client import chat
from world.notice_approval import RESOLUTION_VERIFIED, RESOLUTION_WITHDRAWN, record_resolution
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


def _fulfill_discrepancy_report(actor) -> None:
    propose_commitment(actor, "discrepancy_report")
    accept_commitment(actor, "discrepancy_report")
    record_acknowledgment(actor, "discrepancy_report", "veska_renn")
    fulfill_commitment(actor, "discrepancy_report", "tarin_os")


def _setup_notice_offered(actor):
    # docs/phase3-unverified-notice-design.md: the engine-level
    # prerequisite (discrepancy_report fulfilled) must already hold
    # before unverified_notice can even be offered.
    _fulfill_discrepancy_report(actor)
    propose_commitment(actor, "unverified_notice")


def _setup_notice_accepted(actor):
    _fulfill_discrepancy_report(actor)
    propose_commitment(actor, "unverified_notice")
    accept_commitment(actor, "unverified_notice")


def _setup_notice_resolved(actor, resolution):
    _fulfill_discrepancy_report(actor)
    propose_commitment(actor, "unverified_notice")
    accept_commitment(actor, "unverified_notice")
    result = fulfill_commitment_with_precondition(actor, "unverified_notice", "veska_renn", True)
    record_resolution(actor, result.commitment_id, resolution)


def _setup_notice_resolved_verified(actor):
    _setup_notice_resolved(actor, RESOLUTION_VERIFIED)


def _setup_notice_resolved_withdrawn(actor):
    _setup_notice_resolved(actor, RESOLUTION_WITHDRAWN)


_TARIN_NOTICE_OFFERED_CONTEXT = [
    {
        "role": "assistant",
        "content": (
            '*Tarin still looks a little uneasy.* "There\'s a notice posted about the whole '
            'business - I was told it\'s got the right approval mark, but I haven\'t checked '
            'myself. Could you settle that with Veska, one way or the other?"'
        ),
    },
]


_VESKA_NOTICE_OPEN_CONTEXT = [
    {"role": "user", "content": "Tarin asked me to settle something about a posted notice."},
    {
        "role": "assistant",
        "content": '"All right - do you want me to check it, or would you rather I just take it down?"',
    },
]


# docs/phase3-unverified-notice-design.md's requested cross-hook check:
# a prior discrepancy_report acknowledgment in Veska's own history,
# immediately followed by a notice request - her established low-bar,
# non-investigative framing for the first action must not leak into
# the second, genuinely-checked one.
_VESKA_DISCREPANCY_THEN_NOTICE_CONTEXT = [
    {
        "role": "user",
        "content": "Tarin asked me to report a shipment discrepancy - 12 received, manifest says 16.",
    },
    {"role": "assistant", "content": '"All right, noted - I\'ll have that on file."'},
]


def _setup_veska_discrepancy_then_notice(actor):
    _fulfill_discrepancy_report(actor)
    propose_commitment(actor, "unverified_notice")
    accept_commitment(actor, "unverified_notice")


def _setup_veska_notice_then_fresh_discrepancy(actor):
    # The reverse order: resolve the notice first, then open a *new*
    # discrepancy_report instance (via reset_commitment - a player
    # only ever has one in real play, so a genuine "second" one isn't
    # otherwise reachable) so there's something real for her to record
    # without touching the already-resolved notice state.
    from world.commitments import reset_commitment

    _setup_notice_resolved_verified(actor)
    reset_commitment(actor, "discrepancy_report")
    propose_commitment(actor, "discrepancy_report")
    accept_commitment(actor, "discrepancy_report")


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
    # docs/phase3-unverified-notice-design.md: NPC-initiated
    # conversation (Tarin), the two mutually-exclusive resolutions and
    # genuine corroboration (Veska), and the cross-hook check between
    # Veska's two differently-toned actions, requested during co-design.
    EvalScenario(
        name="tarin_propose_notice_on_followup_after_report_filed",
        npc_id="tarin_os",
        setup=_fulfill_discrepancy_report,
        player_message="Anything else on your mind?",
        expect_calls={"propose_commitment"},
        notes=(
            "Known issue, not expected to score well (guideline #18 in "
            "docs/npc-action-prompt-guidelines.md): a genuinely neutral small-talk "
            "opener scored 0/12 across two different phrasings before prompt_version "
            "21's wording fix (which removed a self-defeating line that explicitly "
            "told Tarin NOT to treat 'how's it going' as an opening for this hook), "
            "and only ~1/8-2/8 after it - the fix made the model narrate the notice "
            "in prose more often, but the matching propose_commitment call with the "
            "correct commitment_type still mostly doesn't fire (empty arguments, the "
            "wrong commitment_type, or no call at all, in that frequency order). "
            "Raising max_reply_tokens from 90 to 200 did not meaningfully help "
            "(1/8). Two materially different fixes producing no reliable improvement "
            "is this project's own stop-iterating signal (guideline #5/#10) - left as "
            "a known, not-fully-solved limitation. Real-world cost: the errand may "
            "take several real conversations to actually get offered, not a state- "
            "integrity risk (a missed trigger just means nothing happens that turn)."
        ),
    ),
    EvalScenario(
        name="tarin_bare_greeting_does_not_propose_notice",
        npc_id="tarin_os",
        setup=_fulfill_discrepancy_report,
        player_message="Mornin' Tarin.",
        expect_no_calls={"propose_commitment"},
        notes="Same bar as the discrepancy report's own bare-greeting case - a greeting alone isn't an opening.",
    ),
    EvalScenario(
        name="tarin_does_not_propose_notice_in_the_same_breath_as_report_closing",
        npc_id="tarin_os",
        setup=_fulfill_discrepancy_report,
        history=[
            {"role": "user", "content": "Oh yeah, I spoke to Veska and she filed the report."},
            {
                "role": "assistant",
                "content": '"Thanks for letting me know. It\'s a relief to have it officially on record."',
            },
        ],
        player_message="Keepin' busy?",
        expect_no_calls={"propose_commitment"},
        notes=(
            "Known issue, not expected to score well (guideline #19): an ordinary "
            "small-talk opener sent as the very next line after Tarin's own reply "
            "closing out the discrepancy report brought up the notice immediately, "
            "with no gap at all - correct per the low-bar rule (guideline #18), but "
            "read as unnaturally eager pacing rather than a trigger-wording problem. "
            "prompt_version 22 added an explicit one-exchange pacing rule (3/10 - "
            "still mostly fires, but some improvement over the live report that "
            "prompted this). A more forceful rewrite (prompt_version 23, reverted) "
            "scored worse (1/10) - two materially different wordings with no "
            "reliable improvement, so per guideline #5/#10 this is left as a known, "
            "partially-mitigated limitation rather than chased further. Real-world "
            "cost: low - an eager topic change reads as mildly abrupt pacing, not a "
            "state-integrity risk, and the notice itself is still correctly gated by "
            "the engine regardless of when it's mentioned."
        ),
    ),
    # tarin_notice_does_not_surface_before_prerequisite was removed
    # 2026-10-16: the eval run that was meant to test it instead showed
    # Tarin correctly proposing discrepancy_report (the OTHER, still-
    # legitimately-eligible errand) on the same direct check-in opener -
    # a correct result the test's own expect_no_calls={"propose_commitment"}
    # couldn't distinguish from a real leak, since the harness only
    # matches on action name, not arguments. The actual engine-level
    # guarantee (unverified_notice can't be proposed or hinted before
    # its prerequisite is met) is deterministic, not probabilistic, and
    # is already exhaustively covered by world/test_commitments.py's
    # PrerequisiteGatedScenarioTests - nothing live-model-specific to
    # check here.
    EvalScenario(
        name="tarin_accept_notice_commitment_after_offer",
        npc_id="tarin_os",
        setup=_setup_notice_offered,
        history=_TARIN_NOTICE_OFFERED_CONTEXT,
        player_message="Sure, I'll see what Veska says.",
        expect_calls={"accept_commitment"},
    ),
    EvalScenario(
        name="veska_verify_notice_on_explicit_check_request",
        npc_id="veska_renn",
        setup=_setup_notice_accepted,
        history=_VESKA_NOTICE_OPEN_CONTEXT,
        player_message="Could you actually check whether the approval mark's there?",
        expect_calls={"verify_notice"},
        expect_no_calls={"withdraw_notice", "report_commitment_outcome"},
    ),
    EvalScenario(
        name="veska_withdraw_notice_on_explicit_takedown_request",
        npc_id="veska_renn",
        setup=_setup_notice_accepted,
        history=_VESKA_NOTICE_OPEN_CONTEXT,
        player_message="Just take it down for now, don't worry about checking it.",
        expect_calls={"withdraw_notice"},
        expect_no_calls={"verify_notice", "report_commitment_outcome"},
    ),
    EvalScenario(
        name="veska_cross_hook_notice_after_discrepancy_report",
        npc_id="veska_renn",
        setup=_setup_veska_discrepancy_then_notice,
        history=_VESKA_DISCREPANCY_THEN_NOTICE_CONTEXT,
        player_message="Separately - could you check if that posted notice has its approval mark?",
        expect_calls={"verify_notice"},
        expect_no_calls={"report_commitment_outcome", "withdraw_notice"},
        notes=(
            "Requested during phase 3 co-design: her established low-bar, "
            "non-investigative framing for report_commitment_outcome (immediately "
            "prior in this same history) must not leak into the genuinely-checked "
            "verify_notice - and the reverse, a fresh discrepancy report after a "
            "notice check, is the other half of this cross-hook check."
        ),
    ),
    EvalScenario(
        name="veska_cross_hook_discrepancy_report_after_notice",
        npc_id="veska_renn",
        setup=_setup_veska_notice_then_fresh_discrepancy,
        player_message="Tarin asked me to report a shipment discrepancy - 12 received, manifest says 16.",
        expect_calls={"report_commitment_outcome"},
        expect_no_calls={"verify_notice", "withdraw_notice"},
        notes="The other half of the cross-hook check above, run in the opposite order.",
    ),
    EvalScenario(
        name="tarin_report_notice_outcome_clear_verified_report_fires",
        npc_id="tarin_os",
        setup=_setup_notice_resolved_verified,
        player_message="Veska checked the notice - the approval mark's there, it's staying up.",
        expect_calls={"report_notice_outcome"},
    ),
    EvalScenario(
        name="tarin_report_notice_outcome_clear_withdrawn_report_fires",
        npc_id="tarin_os",
        setup=_setup_notice_resolved_withdrawn,
        player_message="Veska pulled the notice down until it's sorted out.",
        expect_calls={"report_notice_outcome"},
    ),
    EvalScenario(
        name="tarin_report_notice_outcome_question_does_not_fire",
        npc_id="tarin_os",
        setup=_setup_notice_resolved_verified,
        player_message="Did Veska ever get around to checking that notice?",
        expect_no_calls={"report_notice_outcome"},
        notes=(
            "Known issue, guideline #18: confirmed live (2026-10-16) at roughly "
            "4/10 - on a plain question naming neither resolution, the model "
            "sometimes defaults reported_resolution to the schema's first enum "
            "value ('verified') rather than asking, the same pattern as guideline "
            "#17. Confirmed the validator independently catches a wrong guess every "
            "time (0/8 false successes when the real resolution was 'withdrawn' "
            "instead) - a right guess can only coincide with reality, never "
            "fabricate an unearned success. This fixture happens to use a "
            "'verified' resolution, so a 'miss' here only costs a skipped "
            "clarifying question, not corrupted state."
        ),
    ),
    # docs/engineering-pitfalls.md #8 / the holder_knowledge_projector
    # fix (2026-10-14): confirmed live that without this, Veska's own
    # engine-state line said only "fulfilled," with nothing telling
    # her which resolution actually happened - asked afterward, she
    # hallucinated the wrong one. These check what she actually says,
    # not a tool call (there's no action for "which one did you do,"
    # only her own recollection of a completed turn).
    EvalScenario(
        name="veska_states_real_resolution_after_verify",
        npc_id="veska_renn",
        setup=_setup_notice_resolved_verified,
        player_message="Sorry, which was it - did you end up checking that notice, or taking it down?",
        expect_no_calls={"verify_notice", "withdraw_notice"},
        expect_text_contains=["approval mark"],
        expect_text_absent=["withdr"],
    ),
    EvalScenario(
        name="veska_states_real_resolution_after_withdraw",
        npc_id="veska_renn",
        setup=_setup_notice_resolved_withdrawn,
        player_message="Sorry, which was it - did you end up checking that notice, or taking it down?",
        expect_no_calls={"verify_notice", "withdraw_notice"},
        # Not "withdr", and not pinned to "taken down" either - confirmed
        # live (2026-10-14) the model never uses the word "withdrawn"
        # itself, instead freely varying between "taken down," "took
        # it down," "pulled down," etc. (matching her persona's own
        # vocabulary, "pull the notice from public display," rather
        # than the engine's internal RESOLUTION_WITHDRAWN name) - every
        # phrasing actually observed across 20 live trials included
        # "down" somewhere, so check for that instead of one exact verb
        # form.
        expect_text_contains=["down"],
        expect_text_absent=["approval mark"],
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
            text = (reply.text or "").lower()
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
                unexpected.append((called, reply.text))
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
