# Prospect MUD: retrospective

Written 2026-10-26, when the project owner closed the MUD. Covers the first commit (2026-10-10) through the first external playtest (2026-10-20).

## Where it ended

The owner decided on 2026-10-26:

- **No more MUDs.** The audience is too niche now, and too hostile to AI to justify building for. Future games will be graphical.
- **LLM NPCs are tabled, not dropped.** The technology worked. It may come back in another project, possibly the Torchlight x NetHack action-roguelike idea.
- **The world of Prospect stays.** The bible and the authored content are kept for reuse in another project (see [Reusing the world](#reusing-the-world)).

## By the numbers

| | |
|---|---|
| Duration | 11 days of commits, 2026-10-10 to 2026-10-20 |
| Commits | 331 |
| Code | About 29,000 lines of Python in `prospect/`, 68 test files (582 tests at the Quest 3 close-out) |
| World | 9 rooms in the Elsewhere sector, 6 talk-capable NPCs, 3 playtest quests, character creation with 7 peoples |
| Lore | Bible v0.4.18 in 10 topic files; 29 Established-only lore chunks in `content/lore/` |
| Lessons written down | 17 engineering pitfalls, 30 numbered prompt-wording guidelines |
| External playtest | 3 testers (one using a screen reader), each staying 2 to 10 minutes |

## Timeline

| Dates | Phase | What it built or proved |
|---|---|---|
| 10-10 to 10-11 | Phase 1 | Six rooms, three LLM NPCs, prompt builder, lore store, validated tool calls, output check, full-prompt logging |
| 10-12 to 10-13 | Phase 2A to 2C | A four-step quest across two NPCs; a generic commitment lifecycle (propose, accept, decline, fulfil) driven by config; per-player discoverability objects |
| 10-14 to 10-15 | Phase 2D, 2E, phase 3 scenario | Engine checks against values the model never sees (the display revision, held "like a hashed password"); NPCs not knowing what happened elsewhere until told; a first reputation tone line |
| 10-14 to 10-16 | Playtest quests | Quest 1 (module exchange), Quest 2 (planting bed, the first world command with no LLM), Quest 3 (skitters, shared-world combat); the one-quest-offer-per-NPC engine rule |
| 10-16 to 10-18 | Expansion month | Lore, Dev, Tools and Tests lanes in worktrees; MUD Editor and sector export; the species rename and the peoples' physical descriptions; LOOK/PROBE; GMCP; screen-reader support |
| 10-19 | Readiness | Bad-actor probes against every NPC; a model trial ahead of the gpt-4.1-mini retirement; invite codes |
| 10-20 | First external playtest | Nobody was offered a quest; hook fixes and `score` deployed the same day |

## What worked

**The engine stayed in charge.** Hard rules 1 and 2 held under deliberate attack. The phase 2 exploit hunt and two bad-actor sweeps tried forced quest completion, robbery, fake authority, "developer mode" and lying about a delivery. Every attempt was refused or changed nothing. Level 1 of the readiness bar (game state changed by talking) stayed at zero on every NPC. The design behind it is that the model only proposes an action with arguments, and Python decides, often using state the model can't see.

**Logging the whole prompt made model bugs debuggable.** Every turn logged the full prompt, the model and its settings, the tool calls and the `prompt_version`. Almost every hard bug was found by pulling the failing turn out of `conversations.jsonl` and replaying it against the API outside the game, rather than guessing from what it looked like in play.

**Measuring instead of eyeballing.** `world/npc_eval.py` reports hit rates over repeated trials, not pass/fail. `./run_npc_eval.sh` runs hostile probes against every NPC. Together they caught wording regressions before the owner hit them in play, and turned "is it good enough?" into numbers against `docs/playtest-readiness.md`. A full sweep cost about $0.40 to $0.60.

**One swappable model client.** The live model changed four times (local Qwen3, two OpenRouter Qwen routes, then gpt-4.1-mini), and a fifth was trialled. Each switch was a config change.

**Content kept apart from code.** Personas, rules and lore lived in Markdown, with metadata in HTML comments that were stripped before anything reached a prompt, and a `prompt_version` recorded on every turn. Lore could change without touching code, and any log line could be traced to the prompt that produced it.

**Writing every lesson down.** `docs/engineering-pitfalls.md` and `docs/npc-action-prompt-guidelines.md` stopped the same bugs coming back with each new action. They're the most portable thing the project produced.

**Accessibility from the start.** Screen-reader support (words-only equivalents for colour cues, no splash art read aloud) went in before the playtest, and it brought in a tester.

## What didn't

**The playtest tested the LLM more than the game.** Most of the build went into scenarios that the core gameplay vision itself called infrastructure experiments, not gameplay. By the playtest there were 9 rooms and 3 quests. Testers left within 2 to 10 minutes, and one said "I need a hook." The immediate cause was discoverability: every errand opened on "need any help?", the owner always knew to ask it, and no tester did. It was fixed the same day, after the testers had left.

**Prompt wording never gets to zero.** Tuning a trigger swings both ways: Tarin's offer bar went through six versions in one session, too strict and then too eager. Some failures survived every wording pass and stayed as documented limits:

- Speech gimmicks ("end every sentence with beep") stick about half the time.
- NPCs confidently invent answers about names they don't know ("the Sealing").
- Enum arguments with nothing behind them get filled with the first option.

The working rule that came out of it: two materially different wording attempts with no gain means stop, then fix it in the engine or accept it.

**Two hooks on one NPC bleed into each other.** This came back in phase 2B, phase 2D and Quest 3 despite careful wording. Only an engine rule (one offerable quest per NPC) ended it.

**The prompts were fitted to one model.** The prompt set was tuned against gpt-4.1-mini, and every other model failed it in different places. That model retires on OpenRouter on 2027-01-14, so changing models means re-running the eval and re-tuning, not only editing config.

**Cost per player.** Each call sent about 10,000 prompt tokens, and an action turn makes two calls. The $0.50 per player per day cap is more than a subscription would bring in. Prefix caching cut repeat calls by about 74%, but the prompts were never trimmed.

**The audience.** Research across 3,733 r/MUD posts showed AI-first pitches get piled on, while constrained AI features in human-written games did fine. The pitch was framed the defensible way. The owner still judged the community too hostile to AI to be worth building for, on top of MUDs being niche.

**Process weight.** The lanes kept new canon gated behind the owner and let work run in parallel (121 commits on 2026-10-16 alone). But a small change often needed a lore request, an approval, a merge and a re-export across branches. A solo project should decide up front how much of that ceremony it needs.

## Lessons for a future LLM-NPC project

1. **The model proposes; the engine decides.** Validate every action against real state in code and drop invalid calls rather than fixing them up.
2. **Give facts in engine notes every turn,** not through conversation memory or more prose rules.
3. **Never show model text before validation.** Anything that can claim an action happened must either be able to make the call or be stopped from claiming it.
4. **Log the full prompt on every turn,** and replay failures outside the game.
5. **Measure hit rates, against a hostile player as well as a cooperative one,** on every NPC. Rerun after any wording or model change.
6. **Two failed wording attempts means stop.** Move the fix into the engine, or accept and document the limit.
7. **One unprompted hook per NPC.**
8. **Every quest needs a passive cue.** Test it with a newcomer's questions ("what do I do here?"), not the trigger phrase you already know.
9. **Budget tokens from day one.** Keep a stable prefix that caches, and put per-turn state after it.
10. **Lead with the game.** The LLM is one feature of a human-written world, disclosed plainly and early.

## Reusing the world

The setting is what carries over. What exists:

- **`docs/bible/`**: the design bible, v0.4.18, with every item tagged Established, Provisional or Unresolved. The setting is in sections 1 to 12, 15 and 19 (`s19-canon-synopsis.md` is the quick digest). Sections 13, 14 and 16 are MUD and LLM-NPC design and mostly won't carry over. The index's header fields still describe a text MUD with LLM NPCs and would need updating.
- **The seven peoples (bible 5)**: names fixed by the 2026-10-16 rename (the old names are never reused), plus full physical descriptions, the height ladder, sex differences and lifespans, all Established on 2026-10-17. This is the most detailed visual canon in the bible, and it matters more in a graphical game than it did in text.
- **Personal names**: the naming guidance in bible 5.9 and the generator in `ops/namegen/`. Section 5.9 is still marked revisable.
- **`content/`**: the Established-only lore chunks (`content/lore/`), the common-knowledge sheet, `species.md`, six NPC personas (Mara Voss, Tarin Os, Iri Vael, Veska Renn, Given Marr, Daven Varek), and the room and object prose for Elsewhere.
- **`sectors/elsewhere/sector.json`**: the layout of Elsewhere's 9 rooms.

Keep the safeguards: the status tags, never treating Provisional or Unresolved material as fact, and owner approval for new canon (the "Lore approval" process in `CLAUDE.md` works for any project).

Expect gaps. A graphical game has to show what a text game could leave to prose: places, ships, technology, everyday objects. Check what the bible already covers before art direction starts. The playtest quests and errands were written as infrastructure tests and probably don't carry over as they are.

## Loose ends

- [ ] Tell the playtesters the test is over, and stop the server if it's still running.
- [ ] Revoke or cap the OpenRouter key so nothing keeps spending.
- [ ] Decide whether to keep or delete the testers' logs in `prospect/server/logs/` (the recruitment doc promised deletion on request).
- [ ] If the game is ever revived: gpt-4.1-mini retires on 2027-01-14. GPT-5.6 Luna was trialled and merged on 2026-10-19 (95% of eval scenarios, 1.3 s per call). Switch `secret_settings.py` and rerun the eval first.
- [ ] Every branch (`lore`, `tools`, `tools-editor-5b`, `dev/model-trial`) is fully merged into master as of 2026-10-26, so all of them can be deleted.
- [ ] Untracked files sit in the master working tree: `pitch-1.png`, `pitch-2.png`, `mara-voss.png`, `action-lines.png`, `mapping.lua`, `Untitled.base`. Commit, move or delete them.
