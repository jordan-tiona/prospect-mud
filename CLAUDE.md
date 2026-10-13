# Prospect and the Constellation

A text-based multiplayer sci-fi MUD built on **Evennia** (Python), where some NPCs are voiced by an LLM. Solo project. Currently building the **phase 1 prototype**: a small conversation test, not a vertical slice of the full game.

## Source of truth

- **`docs/prospect-constellation-design-v0.4.1.md`** is the authoritative design document for both setting canon and engineering decisions. Read the relevant sections before starting a task; don't load the whole file into context unless needed.
- Engineering sections to know: **13.5–13.7** (prototype scope, rooms, travel), **14.2, 14.4, 14.6, 14.7** (NPC knowledge, generation/game-state boundary, prototype cast, logging), **16.4–16.8** (stack, request flow, lore store, safety, roadmap).
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

## Phase 1 prototype scope

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
docs/prospect-constellation-design-v0.4.1.md  # authoritative design doc
content/common-knowledge.md   # what any ordinary Elsewhere resident knows
content/npc-shared-rules.md   # behavior rules shared by every talk-capable NPC
content/npcs/<npc_id>.md      # persona, knowledge scope, permitted actions
```

Each NPC prompt is assembled in this order: common-knowledge sheet → shared rules → persona file → scoped lore → conversation. Persona files begin with an HTML comment holding machine-readable metadata (`npc_id`, `room`, `prompt_version`, `knowledge_scope`, `actions`); parse it, and strip **all** HTML comments from content files before sending them to the model. `TODO(lore)` notes for the project owner live inside HTML comments, so they never reach a prompt.

If a content file doesn't exist yet, use a clearly marked stub and tell me, rather than writing the content.

Personas and lore (personality, voice, knowledge, setting content) are authored by the project owner. The `## Actions` section of a persona file, and the tool-calling rules in `content/npc-shared-rules.md`, are different: they describe engine mechanics in prompt form, which is implementation work. Before writing or editing either, check **`docs/npc-action-prompt-guidelines.md`** for prompt-wording pitfalls found during playtesting — they recur with every new action regardless of model.

## Working style

- **Propose a plan before writing code** for anything beyond a small change, and wait for approval.
- Work in small, runnable steps. After each step, say how to try it (commands to run, what to type in the game).
- Prefer Evennia's built-in patterns (typeclasses, commands, scripts) over custom frameworks.
- Write tests for the tool validator and prompt builder; these are where silent bugs would corrupt game state or leak non-canon lore.
- Keep dependencies minimal. Ask before adding a new one.
- When unsure whether something is a code decision or a design decision, treat it as a design decision and ask.
