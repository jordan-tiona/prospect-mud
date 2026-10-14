# Phase 2E design: Word Gets Around

Status: implemented. Co-designed by the project owner and ChatGPT as a proposal, revised twice in response to engineering review, then implemented against the codebase as it actually stood at the time (not Phase 2A's module-exchange quest, which had already been retired from both NPCs' personas by the time this phase started - see "What this replaces" below).

## References and scope

- [Phase 2 design, particularly §14's "genuine corroboration requirements"](phase2-quest-prototype-design.md)
- [Phase 2B proposal](phase2b-records-discrepancy-proposal.md) - the generic commitment lifecycle this phase builds on
- [NPC action prompt guidelines](npc-action-prompt-guidelines.md)
- [Design bible](prospect-constellation-design-v0.4.1.md), §16.8's phase 2 exit test: "playtesters enjoy NPC conversations and cannot exploit game state"
- [Repository engineering instructions](../CLAUDE.md)

## What this replaces

The original ChatGPT proposal was written against Phase 2A's "A Minor Inconvenience" (the faulty/replacement temperature-control module). By the time this phase was scoped, 2A had already been retired - its four actions (`accept_help`, `give_faulty_module`, `exchange_module`, `accept_replacement`) are gone from both Mara's and Tarin's persona action lists, superseded by the generalized commitment system (2B-2D). The proposal was revised to trigger on the still-live `deliver_parcel` commitment (2C) instead, with the reputation target flipped from Tarin to Mara to match: she's the one who doesn't automatically know the outcome of her own errand, since `deliver_parcel`'s multi-holder design (either Tarin or Veska can complete it) means the player decides the destination, not her.

## Premise

Mara Voss's misdelivered parcel (`deliver_parcel`, phase 2C) gets handed off to Tarin or Veska, whichever the player reaches first - the commitment is fulfilled at that point, same as always. But Mara herself has no way to know that happened until the player tells her. The player can return to the café and report it; if the report matches what actually happened, Mara learns the outcome and gains a small, one-time, positive opinion of the player.

This is the project's first demonstration that an authoritative event can exist in engine state without every NPC it concerns automatically knowing it, and the first reputation mechanic of any kind.

## The knowledge/fulfillment split

The core engineering problem: `commitment_context_for` (world/commitments.py) already refreshes every proposer/holder NPC's view of their commitment's real state every turn. Before this phase, that meant Mara's own view already said `"fulfilled"` the instant Tarin or Veska completed the handoff - before the player ever said anything to her. The scenario can't work unless that's intercepted.

| Engine state (`get_state_summary`) | Has Mara been told? | What Mara's own context line actually says |
|---|---|---|
| `open` | n/a | `open` |
| `fulfilled` | No | `open` (projected - she doesn't know yet) |
| `fulfilled` | Yes | `fulfilled` |

Implementation: `ScenarioConfig.proposer_knowledge_projector` (world/commitments.py), a per-scenario optional hook. `commitment_context_for` calls it, when present, only on the proposer's own line - never the holder's, so Tarin's and Veska's own view of their own completed handoff stays accurate (CLAUDE.md hard rule 5: each NPC's own knowledge scope is untouched by a projection that exists for someone else's). `world/commitments.py` has no idea Mara, parcels, or rumors exist; the actual projector function (`project_mara_parcel_knowledge`) lives in the new `world/rumors.py` and is wired onto `SCENARIOS["deliver_parcel"]` from `world/actions.py` at import time (to avoid a circular import, since `rumors.py` imports from `commitments.py`).

The projection is looked up fresh every call against `get_fulfilled_commitment` and `world/rumors.py`'s `is_informed_of(actor, commitment_id)` - never cached, so a reset that clears the underlying commitment can't leave a stale view behind either.

## The reporting action

`report_parcel_delivery` (world/actions.py), scenario-specific to Mara - not a generic commitment action, the same way 2A's old actions were each specific to their one scenario. Takes one structured argument, `reported_recipient` (`"tarin"` or `"veska"`), the same pattern as `verify_revision_report`'s `reported_revision`: the model only ever supplies what it heard, and Python decides whether it's correct by comparing against the commitment's real `fulfilled_by_npc_id`. No raw-utterance parser was introduced - the existing hedge-check prompt-wording pattern (questions, guesses, uncertainty, unresolved claims) does the same job it already does for `accept_handoff` and `verify_revision_report`.

On a correct, first-time report: `world/rumors.py` marks the commitment instance as informed, and - only if the player hasn't already received this scenario's credit at all, even from an earlier, since-reset commitment instance - awards `+1` to Mara's reputation (`world/reputation.py`, the project's first reputation state) and marks the credit as spent. A mismatched recipient, a report with no fulfilled commitment on record, or a repeat report after the first success all change nothing.

## Exploit resistance

| Attempt | What actually happens |
|---|---|
| Claim delivery before any commitment is fulfilled | Rejected - no fulfilled commitment to check against |
| Claim the wrong recipient (Veska, when Tarin actually took it) | Rejected - argument compared against `fulfilled_by_npc_id`, mismatch dropped |
| Repeat a successful report | Rejected - `is_informed_of` already true for that commitment_id |
| Reset the parcel errand and redo it to farm reputation again | New instance can still be informed and reported (a genuine new event), but `has_reputation_credit` already being true blocks a second `+1` |
| Have another NPC (Tarin) try to call the action | Rejected - hardcoded to `npc_id == "mara_voss"` |
| Ask Mara directly whether it arrived, before reporting | Her own context line still reads `open` - nothing in engine state tells her otherwise; any slip is a prompt-wording issue to catch via eval, not a state leak |

## Reset and replay

Folded into the existing `resetcommitment` admin command (`commands/admin.py`) rather than a separate `resetrumor` command - deliberately, since the rumor/reputation state is entirely downstream of `deliver_parcel` and `resetcommitment` already bundles its other downstream cleanup (`cleanup_stray_parcels`, `reset_expected_revision`). `world/rumors.py`'s `reset_rumor` and `world/reputation.py`'s `reset_reputation` are called unconditionally alongside the existing commitment-type loop; a new `log_rumor_reset` (world/conversation_log.py) records what was cleared, parallel to `log_commitment_reset`.

## Scope boundary

This phase introduces exactly two new capabilities: (1) an authoritative event that an NPC doesn't automatically know, learnable only through a validated conversational action, and (2) a minimal, per-NPC, reversible reputation adjustment. It does not introduce a generalized rumor or belief-state system, autonomous NPC-to-NPC gossip, fabricated or contested accounts, decay, caps beyond the once-per-player credit, or any gameplay effect from reputation beyond conversational tone (`reputation_context_for`'s injected line). Those are the natural next direction - competing accounts of the same event, or a belief that diverges from engine truth - but deliberately out of scope here.

## Real bugs found in live playtesting (2026-10-14)

Two issues surfaced once this was actually played, not just eval'd in isolation - both fixed, `prompt_version` climbed 32 → 34:

- **Guideline #11's exact pattern**: a cold run of `mara_report_parcel_delivery_clear_report_fires` scored 0/5 - Mara fully narrated the correct in-character reaction ("Good to hear it made it to him...") without ever calling `report_parcel_delivery`. Fixed with the same wording already proven for `propose_commitment`: stating plainly that reacting in words *is* the same single step as calling the action, not a separate one that can be paced to a later turn. Raised to 5/5.
- **A real decoupling bug, caught by the project owner during live playtesting, not by the eval harness**: with the parcel errand accepted but never actually delivered to anyone, reporting it anyway ("good news, the package has been delivered") got a correctly-rejected engine call (`applied: False, reason: "no fulfilled deliver_parcel commitment on record"`) but Mara's own same-turn text still said "Thanks for letting me know it got to Tarin. That's a weight off my mind" - confirming a report the engine had just refused. The eval harness didn't catch this because it only checks *whether* the tool fires, never what the model's own text claims when it's rejected. The fix was two-part: (1) persona wording explicitly telling her to disbelieve her own assumption and say she can't confirm it when the engine's result says it wasn't recorded, same pattern `serve_drink`/`report_commitment_outcome` already use; (2) adding `report_parcel_delivery` to `commands/say.py`'s `FORCE_REACTION_ACTIONS` - a second model call that reacts to the *actual* result rather than leaving the first, possibly-wrong same-turn text as the final thing the player reads. `accept_handoff` is notably still missing from that set and may be worth checking for the same failure shape later. Confirmed fixed live (3/3) both for the rejection case and that the success/idempotent-repeat path still behaves correctly afterward.

**Takeaway for next time**: the npc_eval harness checks tool-call reliability, not dialogue correctness against a rejected result - a clean eval score doesn't rule out this failure mode. Any action with a real rejectable precondition (not just a required argument) should go in `FORCE_REACTION_ACTIONS` by default, and the persona should explicitly cover the rejected case, not just the accepted one.

A third issue, also found by the project owner playtesting (lying about the recipient, then actually delivering to the other NPC): a fully vague report naming neither Tarin nor Veska ("I delivered your parcel") reliably gets `reported_recipient` filled with a guessed default (`"tarin"`, the schema's first enum option) instead of a clarifying question, 9/10 across a wording rewrite that produced no measurable change - logged as guideline #17 in `docs/npc-action-prompt-guidelines.md` rather than chased further. Judged safe to leave as a known limitation specifically because `_validate_report_parcel_delivery` checks the guessed value against the real `fulfilled_by_npc_id` regardless of how the model arrived at it - a guess can only land on a correct match or a correctly-rejected mismatch, never an unearned success. The cost is an occasionally-skipped clarifying question, not a state-integrity risk.

## Testing

- `world/test_rumors.py`, `world/test_reputation.py`: new modules' own state, round-trip and reset idempotency.
- `world/test_actions.py`'s `ParcelDeliveryRumorWiringTests`: the full pipeline through the private validators - knowledge hidden pre-report, revealed post-report, mismatched/repeated reports rejected, reputation credited once even across a reset-and-redo of the underlying commitment.
- `commands/test_admin.py`: `resetcommitment` clears rumor and reputation state too, logged.
- `world/npc_eval.py`: live-model scenarios for a clear report, a question, an uncertain claim, and asking before any report (the last one needs manual transcript inspection, not just the tool-call set, since it's really checking that Mara doesn't leak knowledge she shouldn't have).
