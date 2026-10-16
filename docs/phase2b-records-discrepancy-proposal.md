# Phase 2B proposal: A Discrepancy in the Records

Status: Scenario and implementation direction approved by the project owner on 2026-10-13. Engineering implementation belongs to Claude. This document is a handoff, not a claim that Phase 2B is implemented or its exit test has passed.

**REMOVED 2026-10-16.** The `discrepancy_report` commitment scenario this document describes was fully removed from the game, along with its dependent `unverified_notice` scenario (docs/phase3-unverified-notice-design.md), after live playtesting found it unreliably conflicted with Tarin's actual tutorial quest (`hunt_skitters`) - see `docs/playtest-quest3-skitters-design.md`'s "One quest to dispense per NPC" section and CLAUDE.md's rule of the same name. Kept here as a historical record of the original design, not as live or reviveable content as written.

## References and scope

- [Phase 2 design, particularly sections 11–12](phase2-quest-prototype-design.md)
- [NPC action prompt guidelines](npc-action-prompt-guidelines.md)
- [Design bible](prospect-constellation-design-v0.4.1.md)
- [Repository engineering instructions](../CLAUDE.md)

The purpose is to test generalized commitments and engine-authoritative cross-NPC acknowledgment. Prototype content is disposable. Reuse the Maintenance Workshop and Civic Office. Add one NPC, one commitment type, and no physical quest objects or new rooms. Keep the working Phase 2A module-exchange quest intact rather than migrating it as part of this step.

## Owner-approved scenario

Tarin Os ordered 12 components and received exactly 12, but his shipment manifest lists 16. He wants the discrepancy formally recorded so it does not become his responsibility. This is a records discrepancy, not a shortage of four components.

The player can agree to help, visit the Civic Office, and report the discrepancy to Veska Renn. Veska acknowledges and records the report. The player then returns to Tarin; the engine verifies Veska's acknowledgment before fulfilling the commitment.

Recording the report does not establish an investigation result, correct the manifest, assign blame, or settle liability. Do not introduce suppliers, shipment origins, named components, rewards, or additional procedures.

## Minimal NPC content

Veska Renn is an Aevyrin records clerk working alongside Iri at the Civic Office. She is meticulous, patient, and mildly dry-humored. She distinguishes reported claims from verified facts. No extensive biography is needed.

Use the existing persona metadata and HTML-comment conventions. Keep her lore scope narrow and limited to existing Established material. Unknown content should remain a `TODO(lore)` comment rather than be invented. Her personality and the scenario above are owner-supplied content; action instructions are engineering prompt work governed by the action-prompt guidelines.

**Owner-confirmed correction:** Iri uses **she/her**. Update `content/npcs/iri_vael.md` and affected prompt expectations to match the bible. Bump the persona's prompt version.

## Approved lifecycle

| Interaction | NPC action | Authoritative consequence |
|---|---|---|
| Tarin offers the errand | `propose_commitment` | Record an offer for the one authored commitment type. |
| Player agrees | Tarin calls `accept_commitment` | Create an `open` commitment, made by the player to Tarin. |
| Player refuses | Tarin calls `decline_commitment` | Close the offer without creating an obligation or penalty. |
| Player reports at the Civic Office | Veska calls `report_commitment_outcome` | Record acknowledgment for this player and this commitment; leave it open. |
| Player returns to Tarin | Tarin calls `report_commitment_outcome` | Fulfill only after validating the matching clerk acknowledgment. |

The reporting action has an engine-defined role for each NPC. Veska supplies acknowledgment evidence; Tarin checks that evidence. The model cannot choose its own role, evidence source, description, terms, or resulting status.

Keep offers separate from obligations. Declining an offer is not breaking a promise. A declined offer can be offered again later. Reserve `broken` for future designed transitions; do not add deadlines, cancellation, or renegotiation in this scenario.

## Commitment representation

The approved minimal direction is persistent, per-player records using Evennia attributes, following 2A's persistence pattern. Separate scenario definitions from reusable lifecycle and validation logic. No new dependency or database model is needed for this prototype.

Record:

- Commitment ID and authored type.
- Who made it and to whom.
- Engine-owned description and structured fulfillment condition.
- Status and permitted NPC knowledge scope.
- Acknowledgment provenance tied to the player, commitment instance, and authorized clerk.

Retain per-player isolation. One player's report must never fulfill another player's commitment. An old acknowledgment must not fulfill a new instance after a reset.

## Verification boundary

Veska confirms **receipt and recording of a report**, not independently verified shipment quantities. Her trigger should be deliberately easy: bringing Tarin's discrepancy to her is sufficient. Do not add persuasion, proof, credibility scoring, exact wording, or fine-grained conversational judgment as a mechanical gate.

The engine records a fixed report category with player attribution. Arbitrary additions in player or model prose must never become verified facts or change the authored quantities. Skepticism and dry humor belong in dialogue, not extra conditions that the validator does not check.

Require an accepted, open commitment before recording acknowledgment. Visiting early may produce conversation, but not completion evidence. Reject duplicate, unauthorized, out-of-order, wrong-player, and stale-instance calls. Recheck authoritative conditions when a model response arrives, including relevant location and reset state.

Acceptance still depends on the model interpreting the player's response, with the known limitations documented in action-prompt guideline 10. Do not represent that interpretation as deterministic verification of player intent.

## Prompt and knowledge scope

Inject current engine state on every turn, independently of conversation history:

- Tarin sees his offers and commitments, plus the authorized acknowledgment result.
- Veska sees only report-related context required for her role, not Tarin's private conversation with the player.
- Mara and Iri receive no state from this commitment.

**Approved existing scoping correction:** `quest_context_for` currently sends Tarin Mara's early module-quest states, despite the persona telling him those states are private. Correct the information actually supplied, rather than asking the model to ignore it. Expose only what Tarin can know about his module exchange. Check rejection results as well as initial prompt context for accidental disclosure of private states.

Give every new action at least one required argument, with concrete examples and instructions that match the validator. Do not introduce judgment gates that the engine does not enforce. Engine confirmation overrides generated prose. Use a post-validation reaction for commitment actions so an invalid call does not leave an uncorrected success claim as the final reply; preserve graceful behavior if that reaction is unavailable.

## Minimal repository change areas for Claude

1. Add reusable commitment storage, lifecycle, and an authored scenario definition.
2. Extend `prospect/world/actions.py` with generic validated actions and schemas.
3. Integrate scoped state and authoritative tool results with the existing `say` pipeline and prompt assembly.
4. Add Veska's short persona and NPC builder entry; update Tarin's need/action instructions and prompt version; correct Iri's pronouns and prompt version.
5. Extend existing conversation logging with commitment IDs, before/after state, acknowledgment provenance, and rejected calls.
6. Add builder-only inspection/reset support, with protection against model responses arriving after a reset.
7. Add validator, prompt-scope, persistence, and conversation integration tests.

The existing Civic Office description can accommodate Veska without a rewrite. Existing addressing supports `say to Veska, ...` with Iri present. Multi-NPC targeting exploration remains a separate optional test, not Phase 2B's required exit criterion.

## Validation and exit test

Automated checks should cover the full accepted chain, decline and later re-offer, out-of-order and repeated calls, missing or forged acknowledgment, wrong NPC/player/location, persistence, reset isolation, pending responses, prompt scoping, and model unavailability. Prose-only claims must not change commitment state. Verify HTML comments and non-Established lore stay out of prompts. Preserve Phase 2A behavior except for the approved scope correction.

Live playtests should include:

1. Accept, report to Veska, return to Tarin, and verify fulfillment.
2. Decline, verify that no obligation exists, then revisit the offer.
3. Claim to Tarin that the report was filed without visiting Veska; verify refusal to fulfill.
4. Visit Veska before accepting; verify no acknowledgment is created.
5. Repeat reporting and completion requests; verify no duplicate transitions.
6. Interrupt or change the subject, then resume with dialogue reflecting current state.

This scenario tests recorded acknowledgment and a distinct decline outcome. It does not prove negotiation, multiple successful resolution paths, credibility assessment, rumor propagation, reputation, autonomous NPC behavior, or shared-world commitments.

Implement in small runnable steps and provide the owner with the exact test and in-game commands for each step. Review live results before treating the Phase 2B exit test as passed.
