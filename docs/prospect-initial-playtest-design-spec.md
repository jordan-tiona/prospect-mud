# Prospect and the Constellation — Initial Playtest Design Spec

**Status:** Draft for project-owner approval and Claude Code engineering review  
**Date:** 2026-10-14  
**Audience:** A small external test group (approximately 4–5 players)  
**Purpose:** Define the desired player experience and test boundaries, not prescribe an engine architecture or establish new setting-wide canon.

## 1. Purpose and guiding principle

This playtest is the first small **playable science-fiction MUD experience**, extending the earlier LLM-NPC feasibility prototypes. Its central question is whether players enjoy inhabiting Elsewhere: creating a character, navigating a recognizable neighborhood, talking naturally with its residents, doing a few conventional RPG activities, and encountering introductory combat.

**Prospect is an MMO/MUD first, not a puzzle game.** LLM-driven NPCs should make interactions and quests feel unusually natural, flexible, and grounded in setting lore. They should not turn ordinary gameplay into a series of conversational riddles or require players to find magic dialogue phrases. The existing technical scenarios are test fixtures, not a template for the finished gameplay loop.

A successful playtest need not resemble a complete game. It should make players curious about Elsewhere and interested in continuing, while revealing where the NPCs, game mechanics, and command interface fall short.

## 2. Confirmed scope and explicit exclusions

**In scope**

- Scripted, in-world character creation, leading into an added medical recovery room.
- Two distinct introductory NPCs: **Given Marr**, the medical technician, and **Daven Varek**, a recurring guide for newly awakened residents.
- The existing six-room Old Quarter neighborhood, plus a **Medical Bay**, a **street beyond Old Quarter Square**, and **Daven's office** (approximately nine rooms total).
- A simple orientation objective, then **three introductory activities/quests**: Mara's heating-unit problem, Iri's planting-bed project, and Tarin's skitter-control task.
- Basic navigation, examining, inventory/items, relevant object interactions, simple equipment and combat, multiplayer presence, persistent character/quest state, and flexible command phrasing.
- Validated NPC actions, limited in-world knowledge, and logs suitable for testing and eventual *curated* training examples.

**Out of scope for this playtest**

- Appearance customization, professions/classes or profession selection, skill trees, character progression systems, crafting, commerce/economy simulation, extensive combat systems, and a complete tutorial for the future MMO.
- New habitats, visits to Prospect, a full map of Elsewhere, or deep explanations for why each character was originally in cryosleep.
- Requiring players to complete the quests in a rigid order, aside from the introductory guidance and any dependencies within an individual quest.
- NPC autonomy, sophisticated cross-NPC memory, generalized quest negotiation, and additional lore not necessary to playtest the experience.

Existing approved world content and working engine functionality should be **reused rather than replaced** wherever practical.

## 3. Player opening: cryosleep and identity

All newly created player characters begin in a brief, **non-LLM** awakening sequence. The player regains partial awareness, hears a calm computer voice, and is told they are being revived from cryogenic suspension. Identity and simple cognitive verification serve as the narrative framing for character creation; **there is no quiz to fail**.

The program obtains:

1. **Character name** — permanent after confirmation.
2. **Sex** — male or female as currently envisioned; permanent after confirmation.
3. **People/species** — one of the seven established playable peoples (Kell, Drask, Lirra, Revari, Astrel, Voldren, Selk); permanent after confirmation.
4. **Account credentials/password** — securely handled by the game's authentication system, presented in fiction as the means of reestablishing control when returning from stasis.

Allow the player to review and correct permanent identity choices **before confirming**. No appearance questions in this build; later cosmetic customization is a separate future feature. No profession choice at any point during this playtest.

Passwords must never enter LLM prompts, conversation logs, or general command telemetry. Claude should resolve whether Evennia account creation happens before, during, or behind this narrative flow; the player-facing experience should feel continuous.

Once complete, the character becomes fully conscious in a **Medical Bay**, with ordinary environmental description and Given Marr present. The awakening is a starting convention, **not** a requirement to invent a hidden mystery or universal explanation for cryosleep.

## 4. Two-part orientation

### Part A: Given Marr — first contact

**Given Marr** is the medical technician supervising the player's recovery. The role is practical, calm, and professional rather than a deep personal backstory. The previously proposed Selk species association can remain a working choice pending review.

Given can answer ordinary questions about the medical bay, Elsewhere, Prospect, Haven, the Constellation, and the seven peoples **within a normal resident's knowledge**. He is not an omniscient lore encyclopedia or a specialist in every field.

He checks that the player is ready to leave and recommends visiting **Daven Varek**, who helps people newly awakened from cryosleep adjust to life on Elsewhere. Given says Daven's office is **past Old Quarter Square**, and indicates that posted directions can help. He does **not** issue exact movement commands or enumerate every turn.

The player should be able to leave freely, ask questions, or find Daven without delivering a precise dialogue trigger. This encounter informally tests basic talking, understanding exits, and asking for guidance.

### Part B: Daven Varek — recurring mentor

**Daven Varek** is responsible for helping the ongoing stream of people awakening from cryosleep settle into ordinary life. The player is not the first person he has helped, nor expected to be the last. His earlier proposed Kell species association can remain a working choice pending review.

Daven has a modest office **beyond the square, down a short street**. He is approachable and knowledgeable about the neighborhood. He offers practical guidance, introduces everyday opportunities, and remains someone the player can return to when thinking, *“I don't know what to do next.”*

**Daven is not the quest giver for the three activities.** He can suggest that the player visit Mara, Iri, or Tarin, and can help with confusion, but those characters present their own needs. The player should also be able to discover the quests independently, without first receiving a Daven-issued task.

*Placeholder (2026-10-16):* Daven currently has one small side errand of his own: checking his office's civic display revision with Iri (`verify_display_revision`, moved from Mara; see `docs/errand-redistribution-plan.md`). This is a stopgap, because with one errand per NPC, five errands needed five NPCs, and giving it to Given didn't fit. It isn't part of his intended role, and he never offers it as a suggested next step. When a new NPC joins the neighborhood, move the display check to them and return Daven to being a mentor only.

### Orientation objective

Getting from the medical bay to Daven's office is the introductory **navigation/orientation objective**, separate from the three main quests. The square's already existing notice board/directory should indicate the route to the new street and Daven's office, using **actual engine exit directions**, supplied and checked by Claude.

Finding the office should require reading the environment or exploring, **not solving a puzzle**. No exact-phrase gating. It should reveal whether first-time players understand `look`, examining the directory, exits, and movement.

## 5. Room footprint and geography

The original six-room neighborhood remains the spatial foundation:

- Lift Concourse
- Old Quarter Square (the hub)
- Corner Café (Mara)
- Maintenance Workshop (Tarin)
- Residential Courtyard
- Civic Office (Iri)

Add three rooms:

- **Medical Bay** — initial recovery and Given's location; connected into the existing arrival route (proposed through Lift Concourse).
- **Old Quarter street** — a short route branching from Old Quarter Square; exact name and appearance to be approved.
- **Daven's office** — reached from that street.

**Conceptual sequence:** Medical Bay ↔ Lift Concourse ↔ Old Quarter Square ↔ New Street ↔ Daven's Office, with the café, workshop, courtyard, and civic office still connected to the square.

This is a **conceptual layout**, not authorization to assign cardinal directions or room IDs. Claude owns the room graph and should check all signage against it. New room text and any revisions to the notice board must use the approved content-file format (`## Glance`, `## Description`, appropriate metadata), with sparse room listings and player-perspective descriptions. New local details remain drafts until approved.

## 6. Introductory activities and quests

The three quests should be **discoverable through normal play**, not hard-gated behind completing the previous quest. The order below is the intended learning progression, not necessarily an enforced sequence. Each quest's game state is engine-authoritative; speech alone never transfers an item, modifies a room, or marks an objective complete.

### Quest 1 — A Minor Inconvenience (Mara and Tarin)

**Scenario:** Mara Voss's café heating unit intermittently fails. She has a removable faulty temperature-control module and needs a working replacement from Tarin Os in the workshop.

**Player actions:**

1. Learn about Mara's problem and offer to help.
2. Receive the faulty module through a validated NPC handoff.
3. Take it to Tarin, who accepts it and provides a compatible replacement through validated actions.
4. Return the replacement to Mara and complete the task through a validated handoff/state check.

**What this tests:** Natural quest discovery; voluntary acceptance; talking to two NPCs; inventory and item handoffs; correct state awareness, including declined or interrupted conversations. The game must not trust dialogue such as “I already fixed it” as proof.

This is a **concrete first quest**, not a requirement to build a universal Commitment abstraction before the playtest. Reuse any working commitment/item-transfer infrastructure already proven in prototypes, without redesigning it unnecessarily.

### Quest 2 — A Little Community Work (Iri)

**Scenario:** Iri Vael is coordinating work on neglected communal planting beds in Old Quarter Square. She needs help, but the necessary tools are stored elsewhere rather than handed over immediately.

**Proposed simple path:**

1. Learn about the work and volunteer to help Iri.
2. Visit the **Residential Courtyard** and retrieve a gardening kit from a communal equipment locker/shed (subject to local content approval).
3. Return to the square and use the kit on the relevant planting bed through an engine-validated world/object action.
4. Return to Iri, who can acknowledge the completed work.

The locker should be easy to find and use, **not locked behind a code or puzzle**. The planting beds were previously folded into the room's prose to reduce listing density; Claude should propose the smallest way to make the relevant bed targetable without bloating the room listing (for example, one justified interactable object or an equivalent engine target).

**What this tests:** Finding an item in the environment, natural command targeting, using tools on the world, and NPC awareness of **verified** actions. The plant-bed restoration should be tracked per player or use an explicitly resettable test arrangement, rather than letting one tester permanently consume everyone else's opportunity. Do not silently establish irreversible shared-world landscaping.

### Quest 3 — Unwelcome Guests (Tarin; light combat)

**Scenario:** Small, rat-sized invasive vermin, provisionally called **skitters**, are an ordinary nuisance in parts of Elsewhere. Tarin asks the player to help control them and supplies or arranges access to a simple weapon appropriate for this task.

The creatures are **not automatically native to Prospect**: their biology and origin are undecided, and a routine incursion of Prospect's native organisms into a habitat would have serious setting implications. The name, appearance, and exact weapon remain draft local content pending approval.

**Player actions:**

1. Accept Tarin's request and receive an appropriate starter weapon/tool.
2. Find skitters across the accessible neighborhood, rather than in one designated combat room.
3. Equip/use the weapon and defeat a small requested number of skitters (**three** is the current suggestion, so players experience respawning).
4. Return to Tarin for acknowledgment based on the validated kill count.

**Shared spawning and visibility requirements:**

- Maintain **approximately two globally active skitters at a time across the playable eligible rooms**. They are shared world entities, not per-player clones.
- When one is defeated, another spawns in a **different eligible room**. The system should not repeatedly place them in the defeated creature's room or in inaccessible spaces.
- Skitters appear in room listings and become targetable **only to players with Tarin's active hunting task/eligibility**. The creatures are not literally invisible in-world; this is a player-specific presentation and interaction rule, not a lore fact.
- Players without eligibility cannot see, target, damage, or otherwise interact with them. No manual rat-visibility toggle is needed.
- Preserve shared multiplayer consistency: kills count once, concurrent attacks cannot duplicate rewards or corrupt entity state, and combat messaging should not reveal hidden targets to ineligible observers.
- On quest completion, visibility can cease for that character during the playtest; whether to retain ratting as an accessible repeatable activity afterward is a **future design question**, not part of this build.

**What this tests:** Searching the neighborhood, equipment handling, a minimal combat loop, shared enemy state, per-player visibility, and a straightforward combat quest objective.

Keep combat deliberately small: reliable targeting, damage/defeat, a safe recovery/failure policy, and accurate kill credit. No complex combat abilities, profession requirements, ammunition economy, weapon durability, or full progression system is needed.

## 7. Command-language design requirement

A core product goal is to let players use **ordinary language where practical**, including standard MUD syntax, fragments, full sentences, and abbreviations. The playtest must expose this to actual users, rather than requiring everyone to know precise commands.

Examples of intended equivalence (subject to parser review):

| Intent | Candidate player inputs |
|---|---|
| Examine a board | `look board`; `l board`; `examine the notice board`; `look at the board` |
| Move to a known destination | `north`; `n`; `go north`; `walk toward the square` (when unambiguous and mapped) |
| Retrieve supplies | `get kit`; `take the tools`; `grab the gardening kit from the locker` |
| Use an item | `use kit on planting bed`; `tend the planting bed with the kit` |
| Attack an eligible target | `attack skitter`; `kill skitter`; `k skitter`; `hit the skitter with my baton` |

These are **input-design examples, not a guarantee that unrestricted language understanding is in scope**. Prefer deterministic normalization, aliases, and target resolution for core game commands where feasible. A conversational command directed at an NPC may instead be handled through the existing LLM-to-validated-action pipeline. Either way, **Evennia authorizes the resulting action**.

Ambiguity should yield a helpful clarification or error, not an unsafe guess. Track rejected/unrecognized commands and which common alternatives users attempt, with sensitive fields excluded, so the parser can be improved based on actual playtest behavior.

## 8. Login, logout, and stasis

Initial cryosleep **is not** the explanation for every logout. A character who disconnects or logs out is fictionally in a network-mediated **stasis** state: they cannot affect or be affected by the world while offline. This can remain a light setting convention without explaining its physics.

Expected presentation:

- On logout, other nearby players may briefly see a restrained message that the character becomes still or unresponsive; the character then **disappears** from room listings and the online `who` list.
- The disconnected character cannot be targeted, damaged, or interacted with.
- On returning and authenticating securely, the character resumes at their persisted location with appropriate persistent state; no trip to a cryogenic pod is implied.
- A network interruption should not strand a vulnerable visible body or break the character's saved state.

The stasis/login metaphor must never require handing a password to an NPC or LLM. Claude should review edge cases around asynchronous logout, session disconnects, visibility, combat, and duplicate logins. Rules for later high-stakes combat/disconnect abuse may be deferred, but today's behavior must be deterministic.

## 9. NPC behavior, lore, and authority

The playtest's primary LLM NPCs are **Given**, **Daven**, **Mara**, **Tarin**, and **Iri**. Their roles must remain recognizable without elaborate personalities or autonomous schedules.

- NPCs draw on **Established** setting material and approved local content; no provisional habitats, institutions, historical explanations, or creature origins may be improvised as factual canon.
- NPCs know what an ordinary person in their position would know and can admit ignorance; they're not narrators or quest-selection menus.
- Given answers recovery and general-setting questions, then suggests Daven.
- Daven acts as a recurring navigator/mentor, helping players find things to do but **not issuing all quests himself**.
- Mara, Iri, and Tarin each have a personal, plausible reason to request assistance; players can talk about unrelated topics and decline requests.
- World changes, transfers, combat results, quest states, and memory claims must be checked against engine state. NPC dialogue alone is not authoritative.
- Give each NPC only the relevant, scoped view of quest state; the player's unverified assertions should not become confirmed NPC knowledge.

Conversation and action logs should support **manual review and curation** for potential future LoRA training, not indiscriminate training on raw interactions. Plan for player notice/consent, protection of account secrets, and retention controls before bringing in external testers.

## 10. State and multiplayer boundaries

Most introductory objectives should be **per character**, so four or five testers can each complete them. Avoid letting a player's actions permanently block another player's tutorial. At the same time, the skitters are explicitly **global shared entities**, not character-local instances.

The specific technical representation of quest steps, item instances, NPC memory, plant-bed completion, and access gating is Claude's engineering decision, subject to these constraints:

- A player cannot complete an objective through a statement alone.
- Item handoffs and world actions are validated exactly once.
- Abandoning, interrupting, or reconnecting should not silently corrupt progress.
- NPCs should not claim a different objective state from what the player can actually act on.
- Competing testers should not duplicate items, kills, or rewards through races.
- The world remains explorable without unlocking a fixed sequence of dialogue prompts.

Where per-player quest state causes fictional inconsistency in a shared location (especially Mara's equipment or Iri's beds), propose a simple, explicit resolution or reset policy for this playtest rather than inventing complex world simulation.

## 11. What the playtest should reveal

Test approximately **four or five players**, ideally including at least some who do not already know traditional MUD commands. Focus observations on these questions:

1. Can someone create a character, leave the medical bay, find Daven, and understand basic movement **without coaching outside the game**?
2. Do Given and Daven feel like inhabitants with jobs, rather than interfaces speaking in character?
3. Do players discover and understand the three quests through natural conversation, and can they finish them without guessing precise dialogue?
4. Are inventory, interacting with objects, and the light combat understandable and enjoyable?
5. Can users type natural commands and get predictable results? Which attempted phrasings fail?
6. Do NPC knowledge, world state, per-player progress, and the globally shared skitters remain consistent across multiple players and reconnections?
7. **Do players want to stay and talk or explore after the required activities are complete?**

A few modest game activities are enough to evaluate these questions. Avoid expanding the playable world or implementing professions to disguise shortcomings in the core experience.

### Suggested minimum acceptance checks

- A new character completes identity setup; permanent choices are confirmed and stored; credentials remain private.
- After a logout/reconnect, the character's location and objective state persist, and they aren't listed as present while offline.
- The player can reach Daven using environmental cues and the verified directory; no dialogue trigger is required.
- Each of the three quests can be discovered, accepted, declined, and completed through valid game actions; no unverified dialogue can force completion.
- Iri's tools can be retrieved and used on the intended environmental target, with independent progress for different testers.
- Exactly one shared skitter kill is credited per defeated creature; new spawns occur elsewhere; ineligible players cannot see/attack the creatures or receive misleading combat output.
- Common full/short/abbreviated commands work or receive understandable feedback; failures are recorded safely.
- The game recovers gracefully when an NPC model is unavailable or returns an invalid tool request, without losing authoritative state.

## 12. Questions for Claude Code's engineering review

Please review this spec before implementation and flag **only the decisions necessary to avoid incompatible or excessive engineering work**:

1. How should scripted character creation integrate with existing Evennia account/character creation, name uniqueness, and persistent identity?
2. Can the proposed medical bay → concourse → square → street → office route be added cleanly to the current room graph, including the notice-board directory?
3. How much of the existing quest/commitment, item-transfer, and NPC tool infrastructure can be reused unchanged?
4. What is the smallest validated interaction model for the communal locker, gardening kit, and planting-bed repair, including multiplayer reset/state?
5. What minimal combat/stats/recovery support is essential, and how should **two globally shared enemies with per-player visibility** be implemented safely?
6. What command-normalization/alias coverage is realistic for this playtest, and how should ambiguous natural phrasing behave?
7. How will character logout/stasis, `who`, room listing, connection loss, and reconnect persistence interact?
8. What failure handling, player consent, and safe logging changes are required before testing with outside players?
9. Which **new local content** needs project-owner approval (Given, Daven, the two new rooms, planting tools, skitters, weapon, etc.), and what can be reused as already approved?

**Implementation division:** The project owner approves all new in-world content and gameplay direction; ChatGPT drafts lore, scenes, character text, and content files; Claude Code owns engineering, validators, integration, and technical consistency checks. Do not treat this draft as permission to invent lore or turn provisional suggestions into established facts.
