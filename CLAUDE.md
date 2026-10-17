# Prospect and the Constellation

A text-based multiplayer sci-fi MUD built on **Evennia** (Python), where some NPCs are voiced by an LLM. Solo project. Past the original phase 1 conversation prototype; now building toward a small external **playtest** (see `docs/prospect-initial-playtest-design-spec.md`) that adds character creation, light combat, and persistent per-player quest state on top of the existing LLM-NPC/commitment infrastructure.

## Source of truth

- **`docs/bible/00-index.md`** is the authoritative design bible's index - start there. It's split into topic files under `docs/bible/` (see its layout table); read only the file(s) a task needs, not the whole bible. The old single-file `docs/prospect-constellation-design-v0.4.3.md` (and earlier versions) remain in `docs/` as historical snapshots, not updated further.
- Engineering sections to know: **13.5–13.7** (prototype scope, rooms, travel) and **14.2, 14.4, 14.6, 14.7** (NPC knowledge, generation/game-state boundary, prototype cast, logging), both in `docs/bible/s13-14-gameplay-and-npc-design.md`; **16.4–16.8** (stack, request flow, lore store, safety, roadmap) in `docs/bible/s16-tech-and-implementation.md`.
- If code, task instructions and the bible disagree, stop and ask rather than picking one.

## Hard rules

These are non-negotiable architecture constraints:

1. **The engine is the source of truth; the LLM is only the NPC's voice.** Generated text never changes game state directly.
2. **Every NPC game action is a tool call validated by the engine** against authoritative state, rules, caps and cooldowns. Invalid calls are dropped, not "fixed up."
3. **NPCs never set or negotiate prices.** No bartering.
4. **Only Established canon goes into NPC prompts.** The bible tags material as Established, Provisional or Unresolved. Provisional/Unresolved content (e.g. Freehold, Meridian, the Sealing) must never reach a prompt.
5. **Each NPC sees only its own knowledge scope** of lore, not the whole bible.
6. **Player text is always labeled as player text** in prompts, and player claims are never stored as fact.
7. **Never invent setting lore** in code, comments, fixtures, test data, room descriptions or prompts. Use placeholders like `TODO(lore): ...` and flag it instead. Writing new in-world content is the project owner's call.
8. **The model is accessed only through one client module** that speaks the OpenAI-compatible API. No model-specific calls anywhere else.

## Stack

- **Game engine:** Evennia (Python).
- **Model serving (dev):** Ollama on a local RTX 3080 Ti (12 GB VRAM), via its OpenAI-compatible endpoint (default `http://localhost:11434/v1`).
- **Model:** open-weight ~8B–14B at 4-bit (candidates: Qwen3 14B, Phi-4 14B, Gemma 3 12B). Not yet chosen; keep it configurable.
- **Config:** model name, base URL and API key come from settings/environment, never hard-coded. Switching to vLLM or a hosted API later must be a config change only.
- **Lore store:** plain files or SQLite, chunked from the bible with status tags.

## Current scope

**`docs/prospect-initial-playtest-design-spec.md`** is the current source of truth for what's in and out of scope, superseding the "Phase 1 prototype scope" section below where the two disagree. It explicitly adds character creation/persistent identity, light combat, and shared-world entities (the skitters) — all previously listed as out of scope for phase 1. The phase 1 section is kept as historical record of the original conversation-test boundaries, not an active restriction.

## Phase 1 prototype scope (historical — superseded by the current playtest spec above)

In scope:

- Six rooms on Elsewhere (bible 13.6): Lift Concourse, Old Quarter Square, Corner Café, Maintenance Workshop, Residential Courtyard, Civic Office.
- Three LLM NPCs (bible 14.6): Mara Voss, Tarin Os, Iri Vael. Ambient characters are static description only, no LLM.
- NPC addressing via the `say` command (bible 16.4): explicit naming, or implicit when exactly one player and one talk-capable NPC share a room, clearly distinguishes talk-capable NPCs from scenery.
- Prompt builder: persona + common-knowledge sheet + scoped lore.
- Tool layer with **one simple validated action per NPC** (e.g. serving an item, handing over a part).
- Output check for out-of-character/offensive replies (a simple filter is fine at first).
- Conversation logging with the fields in bible 14.7, including the full prompt, model ID/settings and prompt version for every turn.
- Graceful handling when the model is slow or unavailable.

Out of scope for phase 1 (don't build unless asked): persistent NPC memory, quests, reputation, economy, combat, inventory progression, ferries/travel, other habitats, the surface, Dynamicism/Fieldworks systems, fine-tuning.

## Content files

NPC personas and the common-knowledge sheet are **authored content**, written by the project owner. Code loads them; code does not generate them. Suggested layout (adjust if Evennia conventions suggest better):

```
docs/bible/00-index.md        # authoritative design bible's index (docs/bible/ holds the topic files)
content/common-knowledge.md   # what any ordinary Elsewhere resident knows
content/npc-shared-rules.md   # behavior rules shared by every talk-capable NPC
content/npcs/<npc_id>.md      # persona, knowledge scope, permitted actions
```

Each NPC prompt is assembled in this order: common-knowledge sheet → shared rules → persona file → scoped lore → conversation. Persona files begin with an HTML comment holding machine-readable metadata (`npc_id`, `room`, `prompt_version`, `knowledge_scope`, `actions`); parse it, and strip **all** HTML comments from content files before sending them to the model. `TODO(lore)` notes for the project owner live inside HTML comments, so they never reach a prompt.

**Bump `prompt_version` on every edit that changes what reaches a persona's prompt**, whichever lane makes it: prose, `## Actions`, or metadata like `actions`. Each conversation-log turn records it (bible 14.7), and an unbumped edit makes logs from before and after the change indistinguishable. The 2026-10-16 species rename touched all six personas without a bump. Bump once per commit even when several sections change, and take the higher number when merging two branches that both bumped.

If a content file doesn't exist yet, use a clearly marked stub and tell me, rather than writing the content.

Personas and lore (personality, voice, knowledge, setting content) are authored by the project owner. The `## Actions` section of a persona file, and the tool-calling rules in `content/npc-shared-rules.md`, are different: they describe engine mechanics in prompt form, which is implementation work. Before writing or editing either, check **`docs/npc-action-prompt-guidelines.md`** for prompt-wording pitfalls found during playtesting — they recur with every new action regardless of model.

Before adding a new generic multi-scenario action, a new per-player visibility mechanic, or a new admin reset/cleanup command, check **`docs/engineering-pitfalls.md`** — engine/architecture mistakes (missing role checks, Evennia's superuser lock bypass, reset tools that only know about current config, orphaned objects, incomplete turn logging) caught live during phase 2; they're a different kind of recurring bug than the prompt-wording ones above.

## Quest/commitment discoverability

**Every quest or commitment a player can discover must have a passive, in-world cue** — not only a conversational trigger a player has to think to ask about. No "going up to every NPC asking 'need any help?'" (project owner, 2026-10-13). Concretely, a quest-giving NPC needs at least one of:

- A per-player pose hint (`world.commitments.hint_pose_for`, e.g. Tarin "frowning at the clicking sound of something skittering along the workshop wall"), and/or
- A discoverable room object (a `quest_prop` entity placed in `sectors/elsewhere/sector.json`, with its text in `content/objects/` and its lock func from the `quest_prop` kind in `world/entity_kinds.py`; built by `world/build_sector.py`, e.g. the misdelivered parcel on Mara's counter) — a real, inspectable, non-pickable object whose `view`/`search` locks are wired to `server/conf/lockfuncs.py`'s `commitment_hint_visible(<commitment_type>)`, so it's visible only to a player whose own state for that commitment is still `"not offered"`. This makes it genuinely per-player (quests are isolated per player, not shared-world, per the design doc) with no separate timer or respawn logic — it falls out of the lock check alone.

Apply this to every new quest/commitment scenario going forward; the actual hint text (pose or object description) is still authored content.

## One quest offer per NPC

**An NPC can be involved in many commitment scenarios, but only one of them may actually be offerable to a given player at a time.** Enforced in the engine (`world/commitments.py`'s `_blocking_scenario_for_proposal`, checked inside `propose_commitment` itself — CLAUDE.md hard rule 2: the losing call is dropped, not narrated around), not left as a prompt convention, because it isn't reliably controllable through wording alone (confirmed live, 2026-10-15/16, two independent wording passes with no fix — see `docs/npc-action-prompt-guidelines.md` guideline #20).

- `ScenarioConfig.mandatory: bool` marks an actual quest (reserved for the playtest's real quests, not legacy/demo commitment scenarios). A mandatory scenario outranks every non-mandatory one on the same NPC by `hint_priority`, and **declining it does not release the block** — only fulfilling it does. There's no timer and no "running out of quests": a declined mandatory scenario just returns to `"not offered"`, where it's still the dominant, re-offerable thing the moment its own trigger comes up again.
- An **ordinary** (non-mandatory) scenario that's been declined at least once becomes exempt from this contention afterward, in both directions — declining it counts as "dealt with," the standard case unless a scenario is explicitly marked mandatory.
- While anything from an NPC is actively offered-pending-answer or accepted-but-unfulfilled, nothing else from that same NPC can be newly proposed, regardless of priority — an NPC doesn't start a second errand while the first is genuinely in progress.
- Apply `mandatory=True` to every future tutorial-sequence quest sharing an NPC with other commitment content, from the start — don't wait for a live cross-contamination bug to surface before adding it.

## Workstream lanes (2026-10-16 onward)

Work on this project runs in parallel lanes, each in its own git worktree and branch (see `docs/game-plan.md` Section 3 for the full rationale, concurrency guidance and the Lore/Dev/Tools boundary). Know which lane a session is in before touching anything.

| Lane | May edit | Must not |
|---|---|---|
| **Lore** | `docs/bible/`, `content/` persona/knowledge/room prose (not `## Actions` sections or `npc-shared-rules.md`), `docs/lore-requests.md` | Change game code; edit `## Actions` sections or `npc-shared-rules.md`; create or place anything directly into the live game (Evennia objects, exits, `world/build_*.py`) |
| **Dev** | Game code, tests, persona `## Actions` sections, `npc-shared-rules.md` | Write or invent lore (hard rule 7) - add a `docs/lore-requests.md` entry instead |
| **Tools** | Tool code, `world/build_*.py`, in-game object/placement code | Change game behavior/mechanics without a Dev-lane review; invent lore |
| **Tests** | Tests | Change game code to make tests pass |
| **Playtest review** | `docs/playtest-findings.md` | Fix anything - it reports, the project owner triages |

Need lore a lane doesn't have? Add an entry to `docs/lore-requests.md` (format in that file) instead of inventing it. Found a bug or pain point reviewing a playtest? Add or update an entry in `docs/playtest-findings.md` (format in that file) rather than fixing it directly.

## Working style

- **Propose a plan before writing code** for anything beyond a small change, and wait for approval.
- Work in small, runnable steps. After each step, say how to try it (commands to run, what to type in the game).
- Prefer Evennia's built-in patterns (typeclasses, commands, scripts) over custom frameworks.
- Write tests for the tool validator and prompt builder; these are where silent bugs would corrupt game state or leak non-canon lore.
- Keep dependencies minimal. Ask before adding a new one.
- When unsure whether something is a code decision or a design decision, treat it as a design decision and ask.
