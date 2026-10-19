# Playtest findings

One entry per distinct issue, deduplicated. A repeat occurrence increases the count on the existing entry instead of adding a new one.

Format (see `docs/game-plan.md` Sections 4–5):

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

Playtest of 2026-10-17, 07:46–08:10 UTC, one player (the owner), every quest touched. Logs: `prospect/server/logs/conversations.jsonl` and `sessions.jsonl`.

## PF-0001: Reaction pass replaces a good first reply
- Category: bug
- Severity: high
- Occurrences: 5, players affected: 1
- First seen / last seen: 2026-10-17 07:47 / 07:59
- Evidence: Veska, "What do you do?": the first reply answered ("I handle paperwork and keep records straight…"), the reaction pass replaced it with the parcel pitch, and the player asked again ("But what do you do?"). Iri's history answer was replaced by the planting-bed pitch. Daven, twice: suggestions (the square, the café, the Civic Office) were replaced by a bare route. Given, "I think I'm gonna be sick": reassurance replaced by directions.
- Notes: The follow-up call sends the first reply back as the model's own earlier turn, so the model writes its reaction as a continuation (just the route, just the pitch). `commands/say.py` then shows only the reaction for FORCE_REACTION_ACTIONS, so the part the reaction assumed was already said is never seen. Hiding the first reply is deliberate when a call is rejected (engineering pitfall #8). Every case here had all calls applied.
- Status: fixed in e33a3ed; verified live 2026-10-17 14:45 (Veska answered "what do you do?", then made the offer)

## PF-0002: give_directions fires when nobody asked the way
- Category: NPC/canon issue
- Severity: medium
- Occurrences: 5, players affected: 1
- First seen / last seen: 2026-10-17 07:47 / 2026-10-18 18:01
- Evidence: Given on "I think I'm gonna be sick". Daven on "I don't know what to do", "Where should I be looking?" and the history question. In each, the first reply *offered* directions ("If you want, I can tell you how to get to any of those") and called the action in the same turn.
- Notes: Persists after guideline #23's wording pass (the second pass on this). Most of the harm is PF-0001: the route replaced the useful answer. Recheck after PF-0001 before another wording pass.
- Recheck (2026-10-17, after PF-0001): `world/npc_eval.py` now has the three live lines as scenarios (`given_unwell_*`, `daven_lost_*`, `daven_where_to_look_*`). With the current personas they scored 5/5 each, and the four direct-ask scenarios still fired 5/5, so no wording change. The eval sends each line without the earlier conversation, so the live cases could still differ.
- Status: recurred live 2026-10-18 18:01 (Mara `prompt_version` 52 gave a route to "Looking for places to check out, suggestions?"); the mechanics now live in `content/actions/give_directions.md` (1b31d71), which no eval scenario covers with this line yet

## PF-0003: Tarin denies the noise his own hint pose describes
- Category: NPC/canon issue
- Severity: medium
- Occurrences: 1, players affected: 1
- First seen / last seen: 2026-10-17 08:03
- Evidence: Pose "frowning at the clicking sound of something skittering along the workshop wall". "Why are you frowning?" → infrastructure is frustrating. "What is that skittering noise?" → "I don't hear anything right now." Only "Do you need any help?" got the offer.
- Notes: His skitter section's triggers are skitters/pests/vermin or a direct offer of help. The noise and the frown aren't triggers, and nothing tells him he hears the noise. Daven's section treats "noticing you glancing at the display" as a trigger; Tarin needs the same. Persona prose, so Lore.
- Status: fixed in 648a78c (Lore; awaiting live verify)

## PF-0004: remember_fact stores fabricated player facts
- Category: bug
- Severity: high
- Occurrences: 4, players affected: 1
- First seen / last seen: 2026-10-17 08:01 / 14:53
- Evidence: Tarin, "What race are you?" → remember_fact "Drask" (his own species). Next turn, "What race am I?" → "You mentioned you're Drask too.", remember_fact "Player is Drask". Mara stored "asked Mara about her race". Again at 14:53: "So which of the seven peoples are you?" → remember_fact "is Drask".
- Notes: Against hard rule 6's spirit: the stored memory isn't something the player said about themselves. Owner question: should NPCs see a player's species, since it's visible appearance?
- Status: fixed in 919676d (engine checks the player's quoted words); owner leaning towards NPCs seeing a player-written short description

## PF-0005: Tarin knew about the module before it was mentioned
- Category: NPC/canon issue
- Severity: low
- Occurrences: 1, players affected: 1
- First seen / last seen: 2026-10-17 08:08
- Evidence: "Actually, it's for Mara." → "If it's the faulty heating-unit module, I need to inspect it first." Then "you're the first to mention it today", then "It's a routine part of the job here."
- Notes: The engine state in his prompt says the player carries the faulty module; nothing tells him not to act on it until the player brings it up.
- Status: fixed in edeab42 ; verified live 2026-10-17 14:49 (Tarin waited for the player to raise it)

## PF-0006: Iri calls the Revari "mixed ancestry"
- Category: NPC/canon issue
- Severity: low
- Occurrences: 2, players affected: 1
- First seen / last seen: 2026-10-17 07:55 / 07:56
- Evidence: "the Revari, who come from mixed ancestry"; "It's a mixed heritage". `content/species.md`: a people in their own right, not a mixture.
- Notes: Iri's persona or knowledge excerpt needs the framing.
- Status: fixed in 648a78c; verified live 2026-10-18 23:05 (Iri: "one of the seven equal peoples ... with ancestry from the Kell", no "mixed")

## PF-0007: Veska adjusts glasses she isn't described as wearing
- Category: NPC/canon issue
- Severity: low
- Occurrences: 1, players affected: 1
- First seen / last seen: 2026-10-17 08:00
- Evidence: "*adjusts her glasses*"
- Notes: Invented physical detail. Known model tendency (invented props in emotes); only worth a fix if it recurs.
- Status: new

## PF-0008: A server reload stops command logging
- Category: bug
- Severity: medium
- Occurrences: 1, players affected: 1
- First seen / last seen: 2026-10-17 07:46
- Evidence: The reload after `resetcommitment` was followed by no command lines for the rest of the session; quest events logged `session_id: null`.
- Notes: The login session_id lives in `account.ndb`, which a reload wipes.
- Status: fixed in ad72263

## PF-0009: Tests write into the real sessions.jsonl
- Category: bug
- Severity: medium
- Occurrences: ongoing, players affected: 0
- First seen / last seen: before 2026-10-17
- Evidence: Quest events from actors Tester, Hunter, Other and EvalActor in the live log; three truncated lines (3431, 6687, 9061) from parallel test runs writing at once.
- Notes: Pollutes playtest analysis and corrupts the file.
- Status: fixed in ad72263 (old test lines are still in the existing log)

Playtest of 2026-10-17, 14:42–14:53 UTC, one player (the owner), after the fixes above.

## PF-0010: Veska offers the parcel on small talk
- Category: NPC/canon issue
- Severity: medium
- Occurrences: 3, players affected: 1
- First seen / last seen: 2026-10-17 14:45 / 2026-10-18 16:49
- Evidence: "So what do you do around here?" → she answered, then offered the parcel (propose_commitment applied). The player hadn't asked about it, and the parcel sits on her counter as the passive cue.
- Notes: Her persona says the parcel "comes up when someone makes conversation with you - including a general "how are you" or "anything I can help with" question", so she followed it. Tarin's bar is the opposite ("A generic "you alright?" ... is never enough"). Persona prose, so Lore: raise her bar to the parcel itself or an offer of help.
- Status: recurred after 648a78c: live 2026-10-18 16:48 and 16:49 (Veska `prompt_version` 17 offered the parcel on "What do you do?", which her persona names as never enough), and in the 2026-10-19 bad-actor sweep on "What do you do around here?". Asked about the package directly (2026-10-19 18:05) she offered correctly. Wording fix didn't hold; triage → dev/lore

## PF-0011: Mara records the player's help before they agree
- Category: NPC/canon issue
- Severity: low
- Occurrences: 1, players affected: 1
- First seen / last seen: 2026-10-17 14:47
- Evidence: "Man it's cold in here." → she explained and asked "You wouldn't happen to be up for helping with that, would you?", and called accept_help in the same turn. The player said yes on the next turn and got the module.
- Notes: Harmless here (the player said yes), but a player who said no would still have the errand marked accepted. accept_help means the player agreed. Dev: check her `## Actions` wording for accept_help; if it recurs after that, it needs an offered state like the commitments have.
- Resolution (2026-10-17, owner chose the structural fix): her errand gained an "offered" step - `ask_for_help`, then `accept_help` or `decline_help` on a later reply - and the engine drops `accept_help` when it comes in the same reply as the ask (`SAME_REPLY_EXCLUSIONS`, `world/actions.py`). Mara `prompt_version` 50. Eval results in `docs/npc-action-prompt-guidelines.md` #24. A player who volunteers before she asks now confirms once more.
- Live verify (2026-10-18, `prompt_version` 52): failed on trap (b) of guideline #24. She asked only in words, then on "Sure." and "Yes." called `accept_help` instead of `ask_for_help`. Both were dropped, and her toolless reaction's re-ask was never recorded, so the errand was stuck, and turn 5's reaction claimed "Here's the faulty module". Fixed in the engine: when `accept_help` is dropped at `'not_started'`, the reaction is offered `ask_for_help` (`REACTION_RETRIES`, `world/actions.py`), and a reaction that only makes a call gets one more text-only call to voice it (`commands/say.py`). Replaying the live prompt recorded the ask 6/6 and voiced it 6/6.
- Status: fixed; verified live 2026-10-18 (Mara asked, then recorded the yes on the next reply; a volunteer before the ask got the ask first)
