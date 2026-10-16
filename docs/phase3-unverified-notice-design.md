# Phase 3 design: The Unverified Notice

Status: implemented and manually playtested (2026-10-14) - closed. Co-designed by the project owner and ChatGPT per `docs/phase3-scope.md`'s engineering brief, with one mid-design revision (Veska replaces Iri as corroborator, an approval-mark boolean replaces a revision-number comparison) made specifically to avoid a documented bug class before any code was written. See "Real bugs found in manual playtesting" below for what the first live playtest actually surfaced.

**REMOVED 2026-10-16.** This scenario depended on `discrepancy_report` being fulfilled first (its `requires_fulfilled_commitment_type`); once `discrepancy_report` was removed after conflicting with Tarin's actual tutorial quest (`hunt_skitters`), this scenario became permanently unreachable and was removed with it - see `docs/playtest-quest3-skitters-design.md`'s "One quest to dispense per NPC" section and CLAUDE.md's rule of the same name. Kept here as a historical record, not as live or reviveable content as written.

## References and scope

- [Phase 3 scope: requirements for co-design with ChatGPT](phase3-scope.md) - the engineering brief this scenario was designed against.
- [Phase 2 design](phase2-quest-prototype-design.md), especially §14/§15's "genuine corroboration" track, which this scenario finally closes.
- [Phase 2E design](phase2e-word-gets-around-design.md) - the knowledge/fulfillment-split pattern (`proposer_knowledge_projector`) this scenario reuses directly.
- [NPC action prompt guidelines](npc-action-prompt-guidelines.md), especially guidelines #7, #11, and #12.
- [Design bible](prospect-constellation-design-v0.4.1.md), §13.5/1152's phase 2 exit test, and this project's phase 3 research question (per `phase3-scope.md`'s §Objective).

## Premise

Tarin's shipment-discrepancy report (phase 2B) gets filed with Veska, same as always. Once it's actually on file, a second, genuinely separate concern occurs to him: a notice went up at the Civic Office about the whole business, and he was told it carries the required approval mark - but he hasn't checked that himself, and would rather not leave it unconfirmed. He raises this unprompted, on an ordinary later conversation, without the player having to ask whether he needs anything.

The player can settle it with Veska one of two ways: she can actually go check the notice for the approval mark (confirming or genuinely contradicting Tarin's belief), or she can simply pull the notice from public display without checking, resolving the matter a different way. Either way, Tarin doesn't learn the outcome until the player tells him - and his report has to match what actually happened, the same discipline as every other validated claim in this project.

This is the project's first NPC-initiated conversational hook (no previous commitment has ever been unprompted-but-conditional on *another* commitment's resolution), its first corroboration that can actually fail for a structured reason rather than being near-unconditional (2B's Veska) or self-reported (2E's Mara, 2D's Iri), and its first demonstration of two mutually-exclusive resolutions to one underlying need.

## Why Veska, not Iri, and an approval mark, not a revision number

The first version of this scenario (ChatGPT's initial proposal) put the corroboration role on Iri, using the same "revision number" concept 2D's `verify_revision_report` already checks. Before any code was written, this was flagged and changed: Iri already holds one revision-number-checking action, and guideline #12 documented a real, reproducible bug class from exactly this shape - two similar-sounding hooks on the same NPC bleeding into each other (triggering both, neither, or with the wrong argument) even when the wording was written carefully. Giving her a *second* revision-like check was judged too close to that failure mode to risk, especially since the new check also needed a materially different trigger shape (an unconditional inspection, not a model-reported value to validate).

Two changes resolved this:
1. **Veska corroborates instead of Iri.** Her existing actions (`report_commitment_outcome`, `accept_handoff`) are both explicitly low-bar and non-investigative by design - "you just take it down as told." The new action is the opposite in kind (a genuine inspection with a real pass/fail), which is a different *tone* risk than guideline #12's wording-overlap risk, and gets its own explicit persona wording (see "Checking the notice yourself" in her persona) rather than relying on trigger-phrase separation alone.
2. **An approval-mark boolean replaces a revision number.** `world/notice_approval.py`'s `approval_mark_present` is a separate per-player fact, under its own attribute key, with no relationship to `world/noticeboard.py`'s `REVISION_KEY` - there's no shared storage for a reset or a test fixture to accidentally collide with.

## The two resolutions, and how mutual exclusion falls out of existing code

`SCENARIOS["unverified_notice"]` (`world/commitments.py`): Tarin proposes (`proposer_npc_id="tarin_os"`), Veska holds and resolves it directly (`holder_npc_id="veska_renn"`, no clerk role). Two scenario-specific actions, both routed through the existing `fulfill_commitment_with_precondition`:

- **`verify_notice`**: precondition is `world/notice_approval.py`'s `approval_mark_present(actor)` - a real per-player fact, generated once (default `True`, the ordinary case where Tarin's belief turns out correct), never computed from anything the model says. A `False` value is a genuine, logged contradiction, not just a missing-evidence drop.
- **`withdraw_notice`**: precondition is just "is there an open commitment to act on" - withdrawal doesn't contest Tarin's claim either way; taking the notice down is itself the resolution.

Because both route through `fulfill_commitment_with_precondition`, which already requires `STATUS_OPEN` to proceed, whichever action succeeds first leaves no open commitment for the other to find - its later attempt is rejected the same way 2C's multi-holder parcel already handles "whichever NPC the player reaches first." No new cross-type bookkeeping was needed for mutual exclusion; it's the same mechanism already proven elsewhere, just exercised with two *actions* on one holder instead of two holders on one action.

A new module, `world/notice_approval.py`, records *which* path actually fulfilled the commitment (`record_resolution`, keyed by `commitment_id`, mirroring `world/rumors.py`'s staleness discipline exactly) - `fulfill_commitment_with_precondition` itself only knows `fulfilled_by_npc_id`, not which of two actions got there, so this had to live in its own scenario-specific module rather than touching the generic one.

## The engine-enforced prerequisite

Before this scenario, nothing in `world/commitments.py` let one commitment type's availability depend on a *different* commitment type's state - `propose_commitment` only checked for an existing open commitment or pending offer of its own type. Without a real gate, Tarin's persona wording would have been the only thing stopping the model from offering the notice errand before the discrepancy report was even filed - an engine-side gap this project has avoided everywhere else (CLAUDE.md hard rule 2).

`ScenarioConfig.requires_fulfilled_commitment_type` (new, optional, empty for every pre-existing scenario) closes this. `propose_commitment` rejects the offer outright if the named prerequisite type isn't `STATUS_FULFILLED` for that player yet. `hint_pose_for` got the same check for its new `proposer_hint_pose` field - without it, Tarin's passive discoverability pose for the new errand would have shown up immediately, before the player had actually earned it, which would have been a real discoverability-rule violation (CLAUDE.md's "a per-player pose hint... visible only to a player whose own state... is still eligible").

## The proposer-side discoverability gap

Every prior holder-side hint used `holder_hint_pose`, shown only while that NPC's *own* commitment is `"not offered"`. Tarin isn't the holder here - Veska is - so that mechanism alone wouldn't cover him. `deliver_parcel` hit the identical asymmetry (Mara proposes, Tarin/Veska hold) and solved it with a physical object (`world/build_quest_props.py`) because Mara had one naturally available. Tarin doesn't have an equivalent physical prop for this errand, so `hint_pose_for` was generalized with a parallel `proposer_hint_pose` field, gated on the same `"not offered"` + prerequisite-met check as the holder-side version. This is the first scenario to use it; it's written generically enough that a future proposer-only NPC can reuse it without further engine changes.

## The knowledge/fulfillment split, reused directly from 2E

Tarin's own view of `unverified_notice` stays `"open"` even after Veska's action has actually resolved it (`STATUS_FULFILLED` underneath), until a separate validated action - `report_notice_outcome` - tells him which way it went. `world/notice_approval.py`'s `project_tarin_notice_knowledge` is structurally identical to `world/rumors.py`'s `project_mara_parcel_knowledge`: looked up fresh every call, never cached, intercepting only the `"fulfilled"` state. Wired onto `SCENARIOS["unverified_notice"].proposer_knowledge_projector` from `world/actions.py` at import time, same circular-import workaround 2E used.

`report_notice_outcome` (Tarin's action) takes an enum argument (`reported_resolution`: `"verified"` or `"withdrawn"`), checked in Python against the real stored resolution via `get_resolution` - the same structured-argument-checked-against-truth pattern as `report_parcel_delivery`, not a raw-utterance parser. A mismatched report changes nothing; a repeat report after the first success is rejected the same way.

## Exploit resistance

| Attempt | What actually happens |
|---|---|
| Offer or hint the notice errand before discrepancy_report is filed | Engine-rejected (`propose_commitment`'s prerequisite check); hint pose doesn't show either |
| Claim the approval mark checks out when it doesn't | Rejected - `verify_notice`'s precondition is a real per-player fact, never the model's judgment |
| Ask for withdrawal to avoid a failed verification | Allowed - withdrawal was always a legitimate, unconditional second path, not a workaround |
| Try both `verify_notice` and `withdraw_notice` on the same instance | The second attempt finds no open commitment left, rejected |
| Tell Tarin a resolution that never happened, or the wrong one | Rejected - `report_notice_outcome` checks the claim against the real stored resolution |
| Repeat a successful report to Tarin | Rejected - `is_informed_of` already true for that commitment_id |
| Have Tarin try to call `verify_notice`/`withdraw_notice` himself | Rejected - hardcoded to Veska's holder role |
| Reset and redo the errand | A new instance can be resolved and reported again (a genuine new event) - no reputation/credit mechanic exists here to double-award in the first place |

## Scope boundary

Per `docs/phase3-scope.md`, this closes exactly the piece of the "genuine corroboration" track that was still open after phase 2: a corroboration gate that can demonstrably confirm *and* contradict a real claim, with a logged rejection and an authored "no, that's not right" line, gated on a structured fact a validator checks in Python. It does not introduce a generalized need-resolution abstraction (the resolution label lives in a small scenario-specific module, not a new engine primitive), autonomous NPC action while the player is absent, negotiation, or mediation between two NPCs' conflicting accounts - all still deliberately out of scope per `phase3-scope.md` §7.

## Testing

- `world/test_notice_approval.py`: the new module's own state, round-trip, reset idempotency, and the projector's behavior in isolation.
- `world/test_commitments.py`'s `PrerequisiteGatedScenarioTests`: the engine-enforced prerequisite on `propose_commitment` and `hint_pose_for`, including per-player isolation.
- `world/test_actions.py`'s `NoticeApprovalWiringTests`: the full pipeline through the private validators - confirmation, contradiction, mutual exclusion, role checks, knowledge hidden pre-report, revealed post-report, mismatched/repeated reports rejected, a fresh instance after reset not reading as already-informed.
- `commands/test_admin.py`: `resetcommitment` clears the notice-approval fact, resolution record, and informed state too, logged.
- `commands/test_say.py`: `report_notice_outcome` added to `FORCE_REACTION_ACTIONS`, regression-tested the same way as `report_parcel_delivery`'s 2E fix.
- `world/npc_eval.py`: live-model scenarios for the NPC-initiated trigger (on-opener and bare-greeting control, plus a before-prerequisite control), both resolution paths' trigger reliability, `report_notice_outcome`'s trigger reliability, and the cross-hook check requested during co-design - Veska's low-bar `report_commitment_outcome` framing run immediately before and after the genuinely-checked `verify_notice`, in both orders, to confirm neither leaks into the other.

## Real findings from the first live-model eval pass (2026-10-16)

Run before any manual playtesting, per the usual workflow. `prompt_version` climbed Tarin 20 → 21.

- **A real, now-fixed wording bug** (not a model limitation): the first draft of Tarin's notice section told him "don't let a generic 'how's it going'... pull you toward this" - directly contradicting the design intent that this hook should have a genuinely *lower* bar than the manifest's, once eligible. Confirmed live: 0/12 across two different neutral small-talk openers, with the model narrating nothing at all. Removing that line and stating the low bar explicitly (prompt_version 21) made the model start narrating the concern in prose on a real fraction of trials - a measurable behavioral change, so this was a genuine wording bug, not a model-capability issue.

- **A known issue, not expected to score well** (guideline #18 in `docs/npc-action-prompt-guidelines.md`): even after that fix, the matching `propose_commitment` call (with the correct `commitment_type`) still mostly doesn't fire - roughly 1-2/8 clean hits, the rest split between no call at all, a call with empty arguments, or the wrong `commitment_type`. A second, independent fix attempt (raising `max_reply_tokens` from 90 to 200, on the hypothesis that the longer narration this topic needs was truncating the tool call) made no reliable difference (1/8). Two materially different fixes producing no reliable improvement is this project's own signal to stop iterating (guidelines #5/#10) - logged as a known limitation rather than chased further. The real-world cost is low: a missed trigger just means the errand doesn't get offered on that particular turn, not a state-integrity risk, and he remains eligible to try again on a later ordinary turn.

- **Another known issue, the same shape as guideline #17, recurring on `report_notice_outcome`**: a plain question naming no resolution (`"Did Veska ever get around to checking that notice?"`) got `reported_resolution` defaulted to the schema's first enum value (`"verified"`) on a real fraction of trials (confirmed ~4/10) instead of a clarifying question. Verified the validator's independent check catches a wrong guess every time (0/8 false successes when the real resolution was actually `"withdrawn"`) - the same reasoning #17 already established: a guess can only coincide with reality, never fabricate an unearned success. Logged as guideline #18 alongside the finding above.

- **Two of the originally-written eval scenarios tested the wrong thing**, caught by inspecting raw model text/arguments rather than trusting the hit-rate number alone: one expected `propose_commitment` to never fire on a direct "something bothering you?" check-in before the prerequisite was met, without noticing that opener is *also* a legitimate trigger for the still-eligible `discrepancy_report` hook (the harness only matches action names, not arguments, so it couldn't tell "proposed the right thing early" apart from "proposed the unrelated, still-valid thing"). The actual engine-level guarantee is deterministic and already covered exhaustively by `world/test_commitments.py`, so that scenario was removed rather than fixed. The other assumed a "fresh second discrepancy report" could exist after the notice was resolved without actually creating one in its setup - fixed by having the setup explicitly reset and reopen a real instance; it now passes 5/5.

Everything else - both resolution paths' trigger reliability, the accept flow, and both directions of the cross-hook check Veska's tonal-contrast wording was specifically written for - came back clean (5/5 each) after these fixes.

## Open after this eval pass

No manual playtesting has happened yet. Based on this project's track record (every prior scenario surfaced at least one additional real bug only visible once actually played), expect at least one more, particularly around:
- Whether `verify_notice`'s rejection case (the approval mark genuinely missing) reads naturally in Veska's dialogue across a real conversation, the same category of bug 2E's `report_parcel_delivery` had before `FORCE_REACTION_ACTIONS` caught it live.
- Whether the NPC-initiated trigger's low live hit-rate is actually noticeable in practice during ordinary play, or whether a few real conversational turns are enough that it doesn't feel broken even though the isolated single-turn eval rate is low.

This section should be updated with what's actually found, the same way `phase2e-word-gets-around-design.md`'s own "real bugs found in live playtesting" section was.

## Real bugs found in manual playtesting (2026-10-14)

Four real bugs, all now fixed and confirmed (deterministic suite + live eval where applicable), plus one known-and-accepted limitation. None required rolling back any of the design above.

- **The model's own first-pass text, on a `FORCE_REACTION_ACTIONS` turn, was reaching the player before validation ever ran** - not specific to this scenario, a pre-existing bug in `commands/say.py` that this scenario happened to make obvious (Tarin volunteering the notice on a plain "how's work?" before visibly backtracking once `propose_commitment` was actually rejected for the unmet prerequisite). `_render_reply_segments` was called unconditionally on the first completion, before `validate_and_apply` and before checking whether a corrective reaction was coming - defeating the entire premise of `FORCE_REACTION_ACTIONS`, whose own comment already says the reaction's text is meant to be "the final thing the player reads." Fixed by hoisting the `needs_reaction` check above the render call and skipping it whenever a reaction is coming. Logged as `docs/engineering-pitfalls.md` #8, since it's an architecture bug, not a wording one - it affects every action in that set, and the existing tests for the mechanism only ever checked the *logged* text, never the *displayed* text, which is why 426 green tests missed it. A new test (`test_reaction_turn_never_shows_the_player_the_pre_validation_text`) now checks the player-visible message stream directly.

- **The reaction's own corrective text, once the bug above stopped hiding it, still read as meta** - "Let me rephrase that," and later "or should I put that another way?" - both referring to a prior utterance the player (once the fix above landed) never actually heard. Root cause: nothing told the model that a reaction turn is the *only* thing the player hears, so it naturally wrote as if continuing/correcting its own immediately preceding line. Fixed with a `content/npc-shared-rules.md` addition (not a per-persona fix, since this is the shared reaction mechanism, not NPC-specific content) stating plainly that a reaction reply stands completely on its own, with no self-reference, no offer to rephrase, and no status-tracking vocabulary ("on file," "confirmed," "pending"). Needed two passes: the first ban listed specific phrases and a new phrasing slipped past it; the second generalized the ban to the underlying *shape* (implying something was said a moment ago worth revisiting) rather than a phrase list.

- **Veska hallucinated the wrong resolution when asked about it after the fact** - asked which of the two outcomes actually happened, she said the notice had been taken down when she had actually verified and left it up. Root cause: `commitment_context_for`'s per-turn state line told her only `"fulfilled"`, with nothing distinguishing *which* action had fulfilled it - unlike Tarin's proposer-side view (which deliberately withholds the outcome for a different, intentional reason), Veska had no engine-grounded fact available at all to answer from, so she guessed. Fixed with a new `ScenarioConfig.holder_knowledge_projector` field (the holder-side counterpart to the existing `proposer_knowledge_projector`), wired to a new `project_veska_notice_knowledge` in `world/notice_approval.py` that always surfaces the real resolution to her. Confirmed live afterward: 10/10 on both resolution paths, 0 hallucinations across 40 total trials (the first eval pass at this needed two of its own wording fixes along the way - not because Veska was wrong, but because the eval's own expected substrings ("withdr") didn't match her actual, equally-correct phrasing ("taken down," "took it down") - a reminder that a live-eval text check needs to tolerate natural paraphrasing, not pin to one exact word).

- **A pacing issue, not a trigger-reliability one**: once guideline #18's reliability fix made the notice trigger actually fire, it started firing in the exact same reply that also closed out the unrelated discrepancy report - two unrelated pieces of news landing in the same breath, correct per the low bar but reading as unnaturally eager. Logged as guideline #19: a pacing rule addition improved it (3/10 same-breath firings, down from the live report that prompted this) but a second, more forceful rewrite scored worse (1/10) - two tries, no reliable improvement, so left as a known, partially-mitigated limitation per #5/#10 rather than chased to zero. Low real-world cost (mild immersion wrinkle, not a state or lore risk), and the project owner's own call: this scenario is a technical experiment for the engine capabilities it exercises, not a template for finished-game quest pacing (see memory/`project_core_gameplay_vision.md` - not worth over-polishing probabilistic NPC behavior here).

- **Two self-inflicted eval-harness bugs caught before they shipped**: the new `expect_text_contains=["verified"]`/`["withdr"]` assertions in the deterministic unit tests initially collided with the commitment type's own name (`"unverified_notice"` contains the substring `"verified"`), producing a false failure; fixed by checking for `"approval mark"` instead, a phrase that can't collide with the type name. Worth remembering for any future text-content check on this scenario specifically.

After all of the above: full deterministic suite at 436/436, two new eval scenarios (`veska_states_real_resolution_after_verify/_after_withdraw`) at 10/10 live, and the project owner's own manual playtest came back clean on everything else - both resolution paths, the accept flow, the cross-hook check, and the report-back step.
