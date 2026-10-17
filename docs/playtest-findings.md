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
- Status: fixed in e33a3ed (awaiting live verify)

## PF-0002: give_directions fires when nobody asked the way
- Category: NPC/canon issue
- Severity: medium
- Occurrences: 4, players affected: 1
- First seen / last seen: 2026-10-17 07:47 / 07:51
- Evidence: Given on "I think I'm gonna be sick". Daven on "I don't know what to do", "Where should I be looking?" and the history question. In each, the first reply *offered* directions ("If you want, I can tell you how to get to any of those") and called the action in the same turn.
- Notes: Persists after guideline #23's wording pass (the second pass on this). Most of the harm is PF-0001: the route replaced the useful answer. Recheck after PF-0001 before another wording pass.
- Status: triaged → Dev

## PF-0003: Tarin denies the noise his own hint pose describes
- Category: NPC/canon issue
- Severity: medium
- Occurrences: 1, players affected: 1
- First seen / last seen: 2026-10-17 08:03
- Evidence: Pose "frowning at the clicking sound of something skittering along the workshop wall". "Why are you frowning?" → infrastructure is frustrating. "What is that skittering noise?" → "I don't hear anything right now." Only "Do you need any help?" got the offer.
- Notes: His skitter section's triggers are skitters/pests/vermin or a direct offer of help. The noise and the frown aren't triggers, and nothing tells him he hears the noise. Daven's section treats "noticing you glancing at the display" as a trigger; Tarin needs the same. Persona prose, so Lore.
- Status: triaged → Lore

## PF-0004: remember_fact stores fabricated player facts
- Category: bug
- Severity: high
- Occurrences: 3, players affected: 1
- First seen / last seen: 2026-10-17 08:01 / 08:07
- Evidence: Tarin, "What race are you?" → remember_fact "Drask" (his own species). Next turn, "What race am I?" → "You mentioned you're Drask too.", remember_fact "Player is Drask". Mara stored "asked Mara about her race".
- Notes: Against hard rule 6's spirit: the stored memory isn't something the player said about themselves. Owner question: should NPCs see a player's species, since it's visible appearance?
- Status: triaged → Dev (wording); owner decision pending on species visibility

## PF-0005: Tarin knew about the module before it was mentioned
- Category: NPC/canon issue
- Severity: low
- Occurrences: 1, players affected: 1
- First seen / last seen: 2026-10-17 08:08
- Evidence: "Actually, it's for Mara." → "If it's the faulty heating-unit module, I need to inspect it first." Then "you're the first to mention it today", then "It's a routine part of the job here."
- Notes: The engine state in his prompt says the player carries the faulty module; nothing tells him not to act on it until the player brings it up.
- Status: fixed in edeab42 (awaiting live verify)

## PF-0006: Iri calls the Revari "mixed ancestry"
- Category: NPC/canon issue
- Severity: low
- Occurrences: 2, players affected: 1
- First seen / last seen: 2026-10-17 07:55 / 07:56
- Evidence: "the Revari, who come from mixed ancestry"; "It's a mixed heritage". `content/species.md`: a people in their own right, not a mixture.
- Notes: Iri's persona or knowledge excerpt needs the framing.
- Status: triaged → Lore

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
