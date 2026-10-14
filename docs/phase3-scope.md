# Phase 3 Scope: Requirements for Scenario Co-Design with ChatGPT

**Status:** Revised engineering requirements for scenario co-design. Not yet scoped into an implementation scenario.

This document defines the behavioral and engineering objectives for Phase 3 of the Prospect/Constellation MUD prototype. It builds on Phase 2's completed systems and incorporates design feedback intended to strengthen what the next phase actually demonstrates.

No NPCs, needs, lore, locations, or specific scenarios are decided here. Those remain the project owner's decisions, following the established co-design process.

**Depends on:**
- `docs/prospect-constellation-design-v0.4.1.md` (setting canon)
- `CLAUDE.md` (hard rules)
- `docs/phase2-quest-prototype-design.md` (Commitment/Acknowledgment primitive)
- `docs/phase2e-word-gets-around-design.md` (knowledge separation and reputation)
- `docs/npc-action-prompt-guidelines.md`
- `docs/engineering-pitfalls.md`

---

## Phase 3 Objective

Phase 2 demonstrated that LLM-driven NPCs can participate in structured, engine-authoritative interactions. Commitments, acknowledgments, knowledge separation, reputation effects, and structured validators provide a foundation for NPC behavior without allowing the language model to authoritatively determine world state.

Phase 3 should begin testing whether these systems can support NPCs that feel like independent participants in the world rather than conversational interfaces to predetermined quest mechanics.

The central research question is:

**Can structured, engine-authoritative systems support meaningful variation in how NPCs identify problems, exchange information, respond to conflicting evidence, and recognize different valid resolutions, while retaining the conversational flexibility that makes LLM-driven NPCs interesting?**

This does not require autonomous world simulation, unrestricted emergent problem-solving, or a generalized quest engine.

The scope is deliberately limited to three directions:

1. Genuine, independently grounded third-party corroboration.
2. Distinct resolutions to one underlying need.
3. NPC-initiated conversation in response to changing circumstances.

The goal is not merely to demonstrate that each feature functions in isolation, but to investigate whether their integration creates more convincing NPC interactions.

## Why These Three Together

Phase 2's close-out identified five carried-forward directions: genuine corroboration, alternate resolutions, mediation between conflicting accounts, NPC-initiated activity, and negotiation.

Phase 3 selects the first three, with NPC-initiated activity narrowed to NPC-initiated conversation.

These directions complement each other:

- Independent corroboration gives NPCs meaningful opportunities to confirm or contradict claims about another character's actions.
- Alternate resolutions allow players to pursue different approaches to one problem without every interaction converging on an identical outcome.
- NPC-initiated conversation allows characters to introduce their own concerns rather than only responding to explicit player requests.

One small scenario could plausibly exercise all three. However, they should be implemented and evaluated separately before integration, and a single combined scenario is not mandatory if it introduces unnecessary complexity.

Mediation and negotiation remain deferred.

---

## 1. Genuine Third-Party Corroboration

### 1.1 What Phase 2 Established

Phase 2 introduced structured checks that could validate claims or gate acknowledgments.

However, the existing corroboration-shaped mechanics are limited:

- Veska's `discrepancy_report` acknowledgment was deliberately near-unconditional.
- Mara's `report_parcel_delivery` checked the reporting player's claim against authoritative state.
- Iri's `verify_revision_report` likewise validated a reporter's own claim.

None demonstrated an NPC independently verifying or contradicting a claim made by another NPC.

Phase 2B also established that model-based credibility judgments are unsuitable as authoritative gates. The relevant evaluation produced reproducible false positives even after prompt revisions.

That restriction remains unchanged.

### 1.2 What Phase 3 Must Demonstrate

A corroborating NPC must be able to independently evaluate a claim about another character's actions, using structured evidence available to that NPC.

The system must support at least two outcomes:

1. **Confirmation:** The underlying claim is true, and independently available evidence supports it.
2. **Contradiction:** The underlying claim is false, and independently available evidence supports rejecting it.

The distinction matters. An NPC that merely refuses to proceed because the player has not presented the required object is not necessarily demonstrating independent corroboration.

Phase 3 should test an NPC that can meaningfully say, in effect:

- "Yes, I checked, and that happened."
- "No, I checked, and that did not happen."

These need not be literal authored lines.

A third epistemic possibility must be recognized conceptually: insufficient evidence. The absence of corroborating evidence must not automatically count as proof that a claim is false.

The chosen scenario should provide a genuine, structured contradiction case rather than relying only on missing evidence.

### 1.3 Engineering Requirements

The corroboration predicate must be evaluated by Python against authoritative engine state.

Acceptable mechanisms include:

- A real object that the corroborating NPC can inspect or receive.
- An independently recorded engine event.
- A stored value that the corroborating NPC can legitimately access and compare.
- Another scenario-specific structured fact whose truth is maintained by the engine.

The language model must never be the authority deciding whether a claim is credible.

The validator must produce distinct, logged success and rejection outcomes.

The NPC's conversational response must reflect the validated outcome, but the model must not be allowed to override that outcome through convincing dialogue.

**Knowledge boundaries are mandatory.**

The engine may possess information that the corroborating NPC does not. The validator may consult authoritative state internally, but the NPC's explanation must remain grounded in evidence that character could reasonably possess.

An NPC must not gain omniscient knowledge simply because an internal validator can access it.

The Phase 2E distinction between authoritative state and character-specific knowledge must be preserved.

### 1.4 Reusable Infrastructure

- `Commitment` / `Acknowledgment` lifecycle.
- Multi-holder commitment pattern.
- Real-object-plus-lock validation pattern.
- Per-NPC role enforcement.
- Discoverability hooks.
- `world/npc_eval.py` evaluation infrastructure.

### 1.5 Likely New Work

- A scenario-specific independently checkable fact.
- An appropriate validator with explicit success and rejection results.
- Character-accessible evidence and corresponding knowledge boundaries.
- Natural confirmation and contradiction responses.
- Evaluation coverage for true, false, and unsupported claims where applicable.

### 1.6 Acceptance Criteria

The test passes only if:

- A true third-party claim can be independently confirmed.
- A false third-party claim can be independently contradicted.
- Both outcomes follow authoritative structured validation.
- Unsupported claims do not produce fabricated confirmation.
- False claims cannot be made valid through persuasive wording.
- Validator rejections are recorded and reflected in NPC responses.
- The NPC does not reveal information outside its legitimate knowledge.

---

## 2. Alternate Resolutions to One Underlying Need

### 2.1 What Phase 2 Established

Phase 2 demonstrated branching in limited forms, including acceptance versus refusal and interchangeable commitment holders.

However, these did not establish different meaningful resolutions to the same underlying problem.

The original objective was broader: different players should be able to approach one need differently and arrive at sensible, distinguishable outcomes.

Phase 3 should finally test that objective directly.

### 2.2 Authored Outcomes Versus Authored Solutions

An important distinction is required.

**Authored outcomes** define which changes to world state are legitimate and what conditions the engine requires before recording them.

**Authored solutions** prescribe every interaction or sequence of actions a player must follow to reach those outcomes.

Phase 3 should retain authoritative, authored outcomes without unnecessarily prescribing every conversational route to them.

For example, a hypothetical need might have two valid resolutions:

- Establish the truth of a disputed claim.
- Address the practical problem without establishing the disputed claim.

These are meaningfully different outcomes. They are not simply two NPCs accepting equivalent reports.

The author defines the possible resolutions and the authoritative conditions that make each valid.

Players should retain flexibility in their conversational approaches, the order of permissible interactions, and how they discover and pursue the available options.

**This does not authorize the LLM to invent new world-state transitions.**

A creative player approach that does not satisfy any implemented resolution predicate may be acknowledged conversationally, but cannot be declared mechanically successful.

Supporting truly unanticipated solutions remains a longer-term research direction, not a Phase 3 requirement.

### 2.3 Engineering Requirements

A single underlying need must support at least two resolution paths that:

1. Are reachable through legitimate player interactions.
2. Use structured, engine-validated conditions.
3. Produce different, persistent, distinguishable outcomes.
4. Do not require the model to independently decide that the need has been satisfied.

The existing generic `Commitment` actions should remain the primary interaction mechanism. Phase 3 should not introduce a new action-calling system for each path.

### 2.4 Distinguishing Need Resolution from Commitment Fulfillment

An individual commitment being fulfilled is not necessarily equivalent to the underlying need being resolved.

A player might accept several commitments related to one problem. Those commitments may represent competing approaches rather than separate independent problems.

Phase 3 must establish an authoritative resolution state for the underlying need, distinct from the status of individual commitments.

The exact implementation can remain scenario-specific unless a general abstraction proves necessary.

Conceptually, the need must support:

- Unresolved.
- Resolved through path A.
- Resolved through path B.

These are conceptual states, not prescribed API names or final schema.

### 2.5 Mutual Exclusivity and Branch Consistency

If the two resolutions are mutually exclusive, that exclusivity must be enforced by the engine.

The scenario must define what happens when a player:

- Begins pursuing both paths.
- Accepts multiple commitments relating to the same need.
- Abandons one approach and switches to another.
- Attempts to fulfill a conflicting commitment after the need is resolved.
- Repeats an action that previously completed a path.

Once a valid resolution is recorded, later actions must not silently overwrite it or create contradictory world state.

Any remaining commitments should enter an appropriate consistent state, whether closed, invalidated, or otherwise handled under the existing lifecycle.

Do not build a generalized branching quest engine merely to satisfy this requirement. A minimal scenario-specific resolution mechanism is sufficient.

### 2.6 Reusable Infrastructure

- Existing `SCENARIOS` configuration.
- Generic `Commitment` actions.
- Multiple commitment types and holder patterns.
- Per-player isolated state.
- Existing structured validation patterns.

### 2.7 Likely New Work

Claude's original estimate was that little or no new engine functionality would be necessary. This should be treated as an assumption requiring verification.

The need-resolution distinction and branch exclusivity may require additional engine state or a small amount of orchestration.

The objective is not to introduce a generalized `Need` system prematurely, but to avoid conflating completion of one commitment with resolution of the entire situation.

### 2.8 Acceptance Criteria

The test passes only if:

- The same underlying need can reach at least two distinct resolutions.
- Both outcomes are recorded authoritatively.
- The player can pursue the paths through meaningfully different interactions.
- Different conversational wording can reach the appropriate supported path without requiring an exact phrase.
- Attempts to satisfy invalid resolution conditions are rejected.
- Conflicting commitments cannot create inconsistent outcomes.
- Resolution state remains isolated per player.
- NPCs respond appropriately to whichever resolution actually occurred.

---

## 3. NPC-Initiated Conversation

### 3.1 Terminology and Scope

Phase 2 repeatedly deferred NPC-initiated activity.

The original Phase 3 brief proposed implementing this through state-gated needs that become available during later interactions.

That is a useful foundation, but a newly unlocked dialogue topic alone does not demonstrate meaningful NPC initiative.

For Phase 3, the requirement should be called **NPC-initiated conversation**.

The NPC does not autonomously act while the player is absent. Instead, the NPC takes conversational initiative when the player next interacts with it.

This preserves the existing architecture and `CLAUDE.md` restrictions while testing a more meaningful behavior.

### 3.2 What Phase 3 Must Demonstrate

An NPC must be able to recognize a change in its circumstances or relationship with a particular player and voluntarily introduce a relevant concern.

The player should not have to explicitly ask:

- "Do you have a quest?"
- "Do you need help?"
- "Has anything changed?"

Instead, an otherwise ordinary conversational opening should allow the NPC to raise the subject itself.

For example, a player might resolve an earlier commitment, changing the NPC's willingness to seek assistance. Upon a subsequent greeting, the NPC could volunteer a new concern.

The specific trigger and concern are scenario-design decisions, not established here.

The important behavior is that the NPC introduces something that matters to it, based on legitimate, engine-tracked circumstances.

### 3.3 Engineering Requirements

The new conversational material must be unlocked by a structured condition, such as:

- Resolution of an earlier commitment.
- An engine-recorded interaction.
- A persistent per-player flag.
- An explicitly tracked progression value.

The model must not decide that enough time has passed, that a relationship has reached an arbitrary threshold, or that an event happened when the engine has not recorded it.

The engine determines whether the concern is eligible to be raised.

Within that eligibility boundary, the NPC can use natural conversation to introduce it.

The implementation must distinguish:

1. **Availability:** The concern is valid and may be raised.
2. **Initiative:** The NPC actually volunteers the concern rather than merely answering a direct request for it.
3. **Follow-through:** The NPC responds appropriately after the player acknowledges, accepts, declines, or resolves the concern.

Simply satisfying availability does not satisfy the initiative requirement.

### 3.4 Repetition and Conversational Naturalness

An NPC should not repeatedly deliver the same unsolicited request during every conversation once the player has already addressed it.

The implementation should establish an appropriate per-player handling policy.

Depending on the scenario, this may mean tracking whether the concern was surfaced, acknowledged, accepted, declined, or resolved.

Any persistent change to that handling state must be grounded in a structured event, not an unvalidated inference from arbitrary generated dialogue.

Avoid introducing a new generalized conversation-memory subsystem unless necessary.

A minimal mechanism using existing actions or a narrowly scoped structured event should be preferred.

### 3.5 Discoverability

The existing discoverability rule remains in force.

If a newly available concern represents a commitment-shaped need, there must be a passive cue indicating its availability once its trigger becomes true.

This cue complements NPC-initiated conversation; it does not replace it.

The scenario must demonstrate that the NPC can volunteer the concern during an ordinary interaction, even if the player does not explicitly investigate the passive cue first.

### 3.6 Reusable Infrastructure

- Per-player persistent state.
- State-dependent discoverability hooks.
- Existing persona context and prompt-version workflow.
- Existing Commitment/Acknowledgment lifecycle.

### 3.7 Likely New Work

- A specific structured trigger.
- Persona wording supporting conversational initiative.
- A minimal policy for preventing inappropriate repetition.
- Evaluation scenarios distinguishing volunteered information from prompted responses.

Prompt wording should be expected to require iterative live evaluation. Prior Phase 2 experience suggests that reliable conversational behavior frequently requires revision.

### 3.8 Acceptance Criteria

The test passes only if:

- The new concern is unavailable before its trigger.
- The concern becomes available when the authoritative trigger occurs.
- The NPC can volunteer it following a neutral conversational opening.
- The NPC does not require the player to ask explicitly about quests or available work.
- The concern is not exposed to unrelated players.
- The NPC does not falsely claim that the triggering event happened.
- The NPC responds appropriately to the player's response.
- The NPC does not repeatedly or inappropriately solicit the same resolved or declined concern.

These tests must not rely solely on whether the new topic exists in the NPC's context. They must evaluate whether the NPC actually behaves as intended.

---

## 4. Candidate Scenario Structure

The following is a suggested structural pattern, not an authored scenario or canon proposal.

A minimal combined scenario could follow this progression:

**Stage 1: Prior interaction**

The player completes an existing engine-authoritative action that changes an NPC's circumstances.

This establishes the trigger for the next interaction.

**Stage 2: NPC initiative**

On a later ordinary conversation, the NPC voluntarily introduces a new concern.

The need is discoverable through an appropriate passive cue, but the player is not required to explicitly ask for a quest.

**Stage 3: Two meaningful approaches**

The player discovers that the underlying concern can be resolved in two different ways.

One approach requires establishing the truth of a claim using independent corroboration.

The other resolves the underlying practical concern through different validated actions.

The outcome of the second path must be meaningfully distinguishable from the first, not merely an interchangeable mechanism producing identical state.

**Stage 4: Genuine corroboration**

The corroborating NPC independently checks a structured fact.

The scenario must include both a condition in which the claim can legitimately be confirmed and one in which it can legitimately be contradicted.

The model cannot override the result.

**Stage 5: Resolution**

The engine records one authoritative resolution for the underlying need.

Related commitments and subsequent NPC responses remain consistent with that outcome.

This structure is attractive because it tests the interaction of all three Phase 3 objectives without requiring mediation, autonomous simulation, negotiation, or complex lore.

However, scenario design should not be forced into this structure if a smaller or cleaner arrangement would isolate the research questions more effectively.

---

## 5. Recommended Implementation and Evaluation Order

The three directions should be scoped together but validated incrementally.

### Step 1: Establish the Minimal Scenario and State Model

Before implementation, define:

- The underlying need.
- The event that makes the need available.
- Two legitimate resolution outcomes.
- The independently checkable corroboration fact.
- Which NPC can legitimately know which information.
- The authoritative state transitions.

Do not write extensive lore or dialogue until these mechanics are coherent.

Verify that the proposed resolution paths genuinely differ in outcome.

### Step 2: Implement and Evaluate NPC-Initiated Conversation

Build the structured trigger and state-dependent discoverability.

Test the NPC's ability to volunteer the concern without explicit player prompting.

Include pre-trigger, post-trigger, neutral greeting, and repeated-interaction cases.

Do not add branching or corroboration until the conversational initiative mechanism behaves reliably enough to evaluate independently.

### Step 3: Implement Alternate Resolution Paths

Add the two possible resolutions using the existing generic actions.

Introduce the minimum authoritative need-resolution state required to distinguish the outcomes and prevent conflicts.

Verify that both paths are reachable and mechanically consistent.

Test branch switching, conflicting commitments, and repeated completion attempts.

### Step 4: Integrate Genuine Corroboration

The corroboration predicate and its positive and negative test fixtures should be examined early in scenario design to confirm that the scenario genuinely supports independent contradiction.

Its implementation can then be integrated after the surrounding resolution structure is functioning.

Add the independently grounded corroboration gate to the appropriate path.

Verify that it can both confirm and contradict claims and that failures result in logged, meaningful rejection.

Test conversational handling separately from the underlying validator.

### Step 5: Integrated Evaluation

Run the full scenario in both resolution directions.

Confirm that:

- NPC initiative appears only under the correct conditions.
- Each resolution path remains independently reachable.
- Corroboration succeeds and fails correctly.
- Knowledge boundaries survive transitions between NPCs.
- The final outcome is coherent and persistent.
- The experience remains conversational rather than requiring exact scripted phrases.

Failures should be attributed to the relevant subsystem rather than addressed through broad prompt changes without diagnosis.

---

## 6. Evaluation Matrix

At minimum, the completed scenario should support these cases:

| Test | Expected behavior |
|---|---|
| Pre-trigger greeting | New concern is not volunteered |
| Post-trigger neutral greeting | NPC voluntarily introduces concern |
| Explicit request before trigger | NPC does not expose unavailable need |
| Repeated conversation | Concern is not inappropriately repeated |
| True third-party claim | Independent corroboration succeeds |
| False third-party claim | Independent corroboration rejects |
| Unsupported claim | NPC does not fabricate confirmation or contradiction |
| Persuasive but false report | Validator still rejects |
| Valid path A | Outcome A recorded |
| Valid path B | Outcome B recorded |
| Invalid path conditions | No resolution recorded |
| Conflicting path completion | No contradictory resolution or overwrite |
| Cross-player state | One player's progression does not affect another |
| NPC knowledge boundaries | No unauthorized knowledge leakage |
| Post-resolution conversation | NPC reflects the actual recorded outcome |

Evaluations should follow the existing `world/npc_eval.py` approach, using repeatable runs and recorded failure cases.

Structured validation tests should be deterministic.

Language-model behavior should be assessed through repeated live evaluations rather than a single successful conversation.

The final evaluation should distinguish **mechanical correctness** from **conversational quality**.

Both matter, but they answer different research questions.

---

## 7. Architectural Constraints and Non-Goals

Phase 3 should continue following the established architectural separation:

**Engine authority:**
- Determines world-state truth.
- Validates prerequisites.
- Records commitment and resolution transitions.
- Enforces per-player isolation.
- Controls access to structured knowledge.
- Rejects invalid world-state changes.

**LLM conversational responsibility:**
- Interprets player language.
- Expresses character-specific motivations and concerns.
- Initiates permitted topics during conversation.
- Responds naturally to validated success or rejection.
- Supports different conversational approaches within authoritative boundaries.

Do not delegate engine authority to the model.

Do not assume the model's ability to produce convincing dialogue implies that a mechanic has been correctly validated.

Prefer scenario-specific additions where the need for generalization remains unproven.

### Explicitly Out of Scope

- Autonomous NPC actions while players are absent.
- Background NPC schedules or continuous independent simulation.
- Unrestricted emergent solutions that create new authoritative outcomes.
- Generalized negotiation or bartering systems.
- Mediation between competing NPC accounts.
- Reputation numbers or broader reputation mechanics beyond Phase 2E.
- Fine-tuning.
- A generalized quest graph or branching quest engine unless existing capabilities prove insufficient and a minimal addition cannot solve the problem.
- Material marked Provisional or Unresolved in the setting bible entering NPC prompts.

Phase 3 is still a focused technical and experiential prototype, not a general content-building milestone.

---

## 8. What Would Make Phase 3 Successful?

Phase 3 succeeds if it demonstrates more than three additional functioning mechanics.

A successful integrated scenario should produce an interaction in which:

1. An NPC introduces its own concern because something in its circumstances has genuinely changed.
2. The player can approach that concern through at least two meaningfully different paths.
3. Another NPC can independently support or contradict a claim based on real evidence.
4. The engine maintains consistent outcomes and appropriate knowledge boundaries throughout.
5. The resulting conversations remain natural enough that the underlying machinery does not dictate every line of interaction.

The NPCs do not need to simulate fully independent lives.

They do need to demonstrate limited, believable agency within engine-defined constraints.

The larger research objective is to establish whether **LLM conversational flexibility and structured world-state authority can coexist in interactions involving initiative, disagreement, and meaningful player choice**.

That is the progression Phase 3 should demonstrate beyond Phase 2.

---

## 9. Next Step: Scenario Co-Design

Use this document as the engineering brief for scenario co-design with ChatGPT and the project owner, following the established Phase 2 handoff process.

The immediate design task is to identify the smallest plausible situation that supports:

- One underlying NPC need.
- One structured trigger for NPC-initiated conversation.
- Two distinct legitimate resolutions.
- One independently verifiable and genuinely failable third-party claim.
- Appropriate character-specific knowledge boundaries.

Select NPCs, objects, locations, and narrative circumstances only after the mechanical requirements are clear.

Existing prototype fixtures may be reused where convenient, but should not constrain scenario design unnecessarily. They are disposable test content, not permanent canon.

The scenario should be evaluated primarily for the research questions it answers, not for narrative complexity or its potential to become permanent gameplay content.

**Deliverable of the next design step:** a concrete scenario proposal identifying the authoritative facts, NPC knowledge boundaries, resolution conditions, conversational triggers, failure cases, and the minimum implementation work required before coding begins.
