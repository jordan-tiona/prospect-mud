# Game Plan: Expansion Month

**Period:** 2026-10-15 to ~2026-11-15 (one month of Claude Max 5x)
**Owner:** Jordan
**Status:** Active

This is the working plan for moving all project work (development, testing, playtest review, tooling, and lore) into Claude Code and running it as parallel workstreams. It sits alongside `CLAUDE.md` (rules) and the design bible (what the game is). This file is about *how the work gets done*.

---

## 1. Goal for the month

Fill these in before Week 1 ends. The month is a success if:

- [ ] All lore and worldbuilding work happens in this repo; ChatGPT is no longer in the loop.
- [ ] The lane workflow (Section 3) is running and Jordan can keep up with it.
- [ ] At least `__` playtest sessions run with the live findings process (Section 5).
- [ ] RPG systems: `__` (to be decided with Jordan in Week 1).
- [ ] World expansion: `__` new NPCs / `__` rooms / `__` quests (to be decided with Jordan in Week 1).

**Two-week checkpoint (~2026-10-29):** check usage under Settings > Usage, and progress against the goals above. If usage is nowhere near the 5x limits, plan to drop back to Pro after the month.

---

## 2. Starting point

- Hosted model via OpenRouter (local GPU lacked the VRAM). API key has a $25 spend limit.
- 6 talk-capable NPCs, 9 rooms, about 5 quests.
- Adult content is **parked**, not planned (see bible 16.9; update its wording to match).
- Lore has been written in ChatGPT and shuttled into the bible by hand. That stops this month.

---

## 3. Workstreams (lanes)

Each lane runs in its **own git worktree and branch**. Jordan reviews and merges. Lanes coordinate through files in the repo, not through Jordan relaying messages.

| Lane | Does | May edit | Must not |
|---|---|---|---|
| **Lore** | Worldbuilding, NPC persona/knowledge prose, quest content, room descriptions, common-knowledge updates | Bible, `content/` (persona/knowledge/room prose; not `## Actions` sections or `npc-shared-rules.md`), `docs/lore-requests.md` | Change game code; edit `## Actions` sections or `npc-shared-rules.md`; create or place anything directly into the live game (Evennia objects, exits, `world/build_*.py`) |
| **Dev** | RPG systems, features, fixes from findings | Game code, tests, persona `## Actions` sections, `npc-shared-rules.md` | Write or invent lore (hard rule 7). Request it instead. |
| **Tools** | MUD editor and other internal tooling; the pipeline that takes Lore's finished prose and turns it into actual in-game content (object/room creation, `world/build_*.py`, wiring into the world) | Tool code, `world/build_*.py`, in-game object/placement code | Change game behavior/mechanics without a dev-lane review; invent lore |
| **Tests** | Tests for newly merged work, coverage of validator and prompt builder | Tests | Change game code to make tests pass |
| **Playtest review** | Reads logs during and after playtests; writes findings | `docs/playtest-findings.md` | Fix anything. It reports; Jordan triages. |

**Lore/Dev/Tools boundary.** `content/npcs/<npc_id>.md` mixes authored canon (persona, voice, knowledge) with engine-facing prompt engineering (the `## Actions` section) — those are different kinds of work and belong to different lanes even within one file. Lore writes the prose; it never runs or edits `world/build_*.py` and never creates the actual Evennia objects/exits/rooms itself — that's Tools' job (via the editor once it exists) or Dev's, depending on whether it's world placement or an engine mechanic. If a new NPC needs both a persona (Lore) and new actions (Dev) in the same week, do it sequentially — Lore drafts the persona with a stub `## Actions` placeholder, merge, then Dev fills in the real actions — rather than both lanes holding the same file open at once.

**Concurrency:** Normally run **Lore + Dev** side by side. Run **Tools** when there's a defined task. Run **Tests** and **Playtest review** as short, task-shaped sessions, not continuously. Two or three sessions at once is the target; more than that outpaces review.

**Session hygiene:** start a fresh session per task; read only the bible sections the task needs; keep `CLAUDE.md` lean.

---

## 4. Shared files

### `docs/lore-requests.md`: lore request queue

Any lane that needs lore it doesn't have adds an entry instead of inventing it. The Lore lane works through the queue. IDs are prefixed by the requesting lane (`LR-DEV-0001`, `LR-TOOLS-0001`, ...) so entries added on separate branches can't collide at merge.

```
## LR-<LANE>-0001: <short title>
- Requested by: dev | tools | tests | playtest-review
- Needed for: <feature, file, or finding>
- What's needed: <specific question or content>
- Blocking: yes | no
- Status: open | drafted | approved | rejected
- Resolution: <bible section or content file, once approved>
```

### `docs/playtest-findings.md`: playtest findings

One entry per distinct issue, deduplicated. Repeat occurrences increase the count instead of adding entries.

```
## PF-0001: <short title>
- Category: bug | pain point | NPC/canon issue | cost/latency | lore request
- Severity: blocker | high | medium | low
- Occurrences: <count>, players affected: <count>
- First seen / last seen: <timestamps>
- Evidence: <log references, short quotes>
- Notes: <what the player was trying to do; suspected cause>
- Status: new | triaged → <lane> | fixed in <commit> | won't fix
```

---

## 5. Playtest review process

**During a playtest:** a review run every 10–15 minutes reads only log entries since the last checkpoint, then appends to or updates `docs/playtest-findings.md`. Each run starts fresh; no single session reads the whole growing log.

**What it looks for:**

- **Bugs:** errors, failed or rejected tool calls, broken quest states, crashes.
- **Pain points:** unknown commands, the same command retried with variations, `help` lookups, players stuck in one room, quests started and abandoned, long idle stretches.
- **NPC/canon issues:** invented lore, Provisional material leaking, breaking character, player prompt-injection attempts that worked.
- **Cost/latency outliers:** expensive turns, slow responses, unexpected provider changes.
- **Explicit feedback:** everything a player sends with the `bug`/`feedback` command.

**After a playtest:** one consolidation pass to dedupe, set severities, and produce a short summary. Then Jordan triages findings into lanes.

**Player count:** limited by how many findings Jordan can triage, not by the model. Start with 4–6 players.

**Consent:** players are told at login that sessions are logged and reviewed.

---

## 6. Week 0: setup (first 2–3 days)

Do these in order. Each is a separate, reviewable task.

1. **Rescue ChatGPT's context.** Jordan asks ChatGPT to list everything it knows about the setting, characters and goals that is *not* in the current bible. Jordan decides what to keep; the Lore lane adds approved items with proper status labels.
2. **Cost and abuse safeguards audit (Dev).** Confirm or implement:
   - per-player rate limit and cooldown (bible 16.7)
   - input length cap on `talk`
   - `max_tokens` on every model call
   - bounded conversation history per call
   - per-player daily token/cost budget with an in-character fallback
   - in-game daily spend circuit breaker, set below the $25 key limit, with scripted fallback and an alert
   - repeated identical messages get a canned reply instead of a model call
   - invite-only accounts for playtests
3. **Structured logging (Dev).** Every model call logs model, provider, prompt version, tokens, cost and latency. Gameplay events (unknown commands, help lookups, room changes, quest starts/completions/abandons, idle time) are logged as structured events.
4. **`bug` / `feedback` command (Dev).** Writes a tagged marker into the log at that moment.
5. **Split the bible (Lore).** Break `docs/prospect-constellation-design-v0.4.3.md` into topic files (for example peoples, Elsewhere districts, factions, NPCs, systems, engineering) with status labels preserved and an index file. Update `CLAUDE.md` and the lore store to point at the new layout. No content changes in this step; it's a pure reorganization, verified by diff.
6. **Lane scaffolding.** Create `docs/lore-requests.md` and `docs/playtest-findings.md` using the formats in Section 4. Add lane rules (Section 3) to `CLAUDE.md`.
7. **Canon-reviewer subagent.** Define a Claude Code subagent whose only job is checking a diff against the bible: invented lore, Provisional material reaching prompts, hard-rule violations. Run it on every merge before Jordan reviews.
8. **Playtest-review command.** A reusable command or skill that runs one review pass as described in Section 5, given a log checkpoint.

**Known issues flagged for the Tests lane** (found during items 2–3, 2026-10-16; parked here since the lane doesn't exist yet):
- `run_tests.bat` only runs `evennia test commands world` - the `typeclasses` app (which has its own test files, e.g. `test_npcs.py`, `test_rooms.py`, `test_characters.py`) isn't included at all, so its tests never run as part of the normal test command.
- `typeclasses/test_npcs.py`'s `AmbientPoseRotationTests` fails with a dangling-foreign-key `IntegrityError` when run alongside the rest of the suite (a test character created with no explicit room/home, relying on `settings.DEFAULT_HOME` ("#2") existing, which is order-dependent on another test having built one first). Same root cause fixed in `world/test_llm_budget.py`/`world/test_commitments.py`/`world/test_session_log.py` today by giving those tests an explicit room - `test_npcs.py` itself still has the bug.

---

## 7. Weeks 1–4: outline

Adjust as findings come in. Lore and Dev run in parallel throughout.

- **Week 1:** First playtest with the new process. Jordan and Claude decide the month's RPG-system goals and expansion targets (Section 1). Lore lane drafts an expansion plan for Elsewhere: which districts, people and quests come next.
- **Week 2:** Dev builds the first RPG systems. Lore lane produces content in batches against its plan, plus the request queue. Playtest. **Checkpoint.**
- **Week 3:** Continue systems and content. Tools lane builds the MUD editor if not already done. Playtest with a slightly larger group if triage is keeping up.
- **Week 4:** Integrate, fix findings, playtest. Review the month against Section 1 and decide on month two.

---

## 8. Rules that apply to every lane

- `CLAUDE.md` hard rules always apply. In particular: never invent lore; the engine is the source of truth; only Established canon reaches NPC prompts.
- Propose a plan before non-trivial work and wait for approval.
- Anything that looks like a design decision goes to Jordan.
- Bump the bible's version and revision history on every lore change.
