# Playtest recruitment: pitches, research and pre-posting TODOs

**Status:** Draft (§5.1 rewritten 2026-10-19). Pitch text needs the project owner's editing pass before it goes anywhere.
**Date:** 2026-10-17
**Purpose:** Everything needed to recruit the first external test group (4–5 players, per `prospect-initial-playtest-design-spec.md` §11): where to post, what to say, what the community reacts to, and what has to be true before posting.

## 1. Where to find players

Ranked by fit for a 4–5 person, invite-only, LLM-NPC test.

| Venue | Why | Notes |
|---|---|---|
| **MUD community Discord** ("Multi User Dungeon", ~2,700 members, ~830 online at check) | Runs monthly "MUD Raids" where members play a little-known MUD together; nearly a ready-made group session | Invite: https://discord.gg/zuz4D8s (verified live 2026-10-16 via Discord's public invite API; posted by the r/MUD mods in 2023). Read the promo channel's rules before posting. Ask the raid organiser whether Prospect could be a raid target. |
| **Evennia community** (Discord, forum, game index) | Friendly to new Evennia games; Griatch (lead dev) gives constructive feedback on launch posts | Good for a closed first round before r/MUD |
| **r/MUD** | Largest open audience; recent new-MUD posts do get players | Hostile to AI-forward pitches (see §3). Post once, with substance. |
| **Game listings** (MudVerse, MudVault, BestMUDs.com, The Mud Connector) | Steady trickle rather than a spike | Low effort; do it anyway once there's a stable address |
| **AI-friendly communities** (r/aigamedev, r/LocalLLaMA) | Will like the engine-authoritative design | Not MUD players, which is useful for testing onboarding with people who don't know `look`/`n`/`say` |
| **AudioGames.net forum** | Blind players are a loyal MUD audience | Only after screen-reader support is checked |

**Recommended sequence:** small closed round via the Discord raid crowd or Evennia community → fix whatever breaks in chargen and connection → one r/MUD post with a dated group session.

## 2. Invite-only: keep it, but make it painless

For 4–5 testers invite-only is right: every NPC call costs real money (~10k tokens), every log gets read, and logging consent has to be in place (spec §9). To keep it from reading as gatekeeping:

1. **Sign-up is a comment or DM**, not an application form. Closed-beta posts that asked people to apply did poorly.
2. **Say why it's small** (cost, reading every log). People respect the reason.
3. **Keep a waitlist**: everyone who misses out is first for the next round, so the post stays useful after slots fill.
4. **Offer a live group session** (e.g. a Saturday evening) plus a week of play-whenever access. The live session is the only way to test shared skitters and several players talking to one NPC.

## 3. What r/MUD responds to (research summary)

Source: 3,733 r/MUD posts, 2023-01 to 2026-10-16, pulled via the Arctic Shift archive API (reddit.com blocks direct fetches). ~1,100 were Promotion/Showcase. Full text and top comments read for ~35 threads. Scores are an archive snapshot and likely undercount recent posts; treat as rough rankings.

### 3.1 AI reception

- **AI-as-the-selling-point posts score 0 and get piled on.** Aetheria ("AI Game Master weaves the world"): "Multi-User Dumbslop", "You lost me at ai". Dark Hope's "LLM Loremaster": criticised for 20–40 s replies ("a wiki would be better"); the developer got defensive and the thread collapsed.
- **AI as a constrained feature inside a human-written game gets a fair hearing.** Acolyte MUD (Diku engine with LLM-driven NPCs, 12 points): people played it and gave real feedback ("The NPC feels surprisingly alive"); the main complaint was NPCs giving bad directions. Iron Realms' ChatGPT NPC experiment: 46 points.
- Recurring commenter line: excited by "constrained GPT elements in a game that was largely written by humans."
- Commenters ask "what do you mean by AI?" and reward plain, upfront disclosure. Someone will ask which model; just answer (gpt-4.1-mini via OpenRouter at time of writing).
- Prompt-injection ("hacking NPCs") came up as a worry. The validated-tool-call architecture is the answer; say so.

**Implication:** Prospect's design is the defensible version. Lead with the setting and the game; present LLM NPCs as one feature; state what the model does *not* do before anyone asks; stay calm in the comments.

### 3.2 What successful launch posts had in common

Top examples: Elara (54 points; 35 on launch day), merchant sailing MUD (34), Song of Avaria alpha (34), Mystavaria open alpha (32), Usurper Reborn (14 points, 42 comments).

1. One concrete, unusual hook in the title.
2. A list of what is playable *now*, not plans.
3. Connect info in the post: telnet host:port, web client link, Discord. "Can I connect with a MUD client?" recurs.
4. A specific ask ("rip it apart", "which commands did you try that didn't work?").
5. Length: median score by post length was 1 under 300 chars, 4 at 300–1,000, 6.5 at 1,000–2,500, 11 over 2,500.
6. A dated event plus follow-up posts (announcement → launch day → "here's what I fixed from your feedback").
7. The developer replies to everything and visibly ships fixes.

### 3.3 What sinks posts

- Chargen crashing on first login (Invicta Imperium got "TypeError, disconnected" replies).
- Repeat posting: ~16% of Promotion posts since 2025 were removed, mostly duplicates/crossposts.
- Defensiveness in comments.
- Image-only or link-only posts (median score 1) versus text posts with inline images (median 11) or plain text (median 9).

### 3.4 Accessibility

Many MUD players are blind and use screen readers; the question comes up in a large share of launch threads. Check before posting; include alt text / plain-text transcripts for any screenshots.

## 4. Screenshots

Include two or three Mudlet crops *inline in a text post* (not an image post). Each should back one claim:

1. An NPC handling an off-script question in character, ideally admitting ignorance rather than inventing.
2. A validated action: a handoff where the engine's own message confirms the item moved.
3. An NPC rejecting a false claim ("I already fixed it") against real quest state. Strongest anti-gimmick shot.
4. Optional: two players in one room talking to the same NPC.

Rules: unedited and typical, not best-ever; player commands visible; 8–15 lines per crop with font bumped for phone legibility; other testers' names hidden unless agreed; plain-text transcript under each image for screen-reader users. For Discord, attach one or two crops to the short pitch.

### 4.1 Candidates from the conversation logs (mined 2026-10-18)

Source: `prospect/server/logs/conversations.jsonl`, 190 conversations and 947 turns, 2026-10-11 to 2026-10-18. Times are UTC. The log holds only the NPC exchanges, not room text, engine action lines or the player's command echo, so **every shot is a recreation in the client**, not a crop of a transcript. Anything before 2026-10-16 uses the old people names and the old errand owners, so only the wording is reusable from those.

**Slot 1: off-script question, in character**

- **Veska, 2026-10-17 08:00.** After one-line answers to "Who are you?" and "What do you do?", the player says "You're a woman of few words aren't you." Veska: *"Procedures don't usually call for verbosity."* \*adjusts her glasses\* *"Efficiency is the point."* The best single character line in the logs; the terse set-up lines make the crop. Recreate: `say` the three questions in that order.
- **Daven, 2026-10-15 01:34.** "Is it Earth?" → *"I've never heard anyone call it Earth around here. People mostly just say the planet when they need to."* Then "I think I heard someone call it Prospect" → he confirms. Admits ignorance of a word outside the setting without inventing. Caveat: one turn earlier he claimed not to know the planet's name at all, which the common-knowledge sheet contradicts; recapture and see whether he names Prospect straight away.
- **Given Marr, 2026-10-17 07:47.** Wake-up sequence: "Where is... Here?" / "Elsewhere?" / "Really, orbital? Orbiting what?", three escalating answers ending at the Constellation orbiting Prospect. Reads as the first minute of play. About eight lines.
- **Iri, 2026-10-17 07:55 to 07:57.** "What is a generation ship?" → "who are these peoples?" → "Engineered peoples? What does that mean?" → "Which of the seven peoples are you?" → *"I'm a Revari..."* Backs the claim that each NPC knows what someone in their position would know. Too long for one crop; take the last two. Caveat: §5 deliberately omits the people names, so decide whether a crop may show them.
- Second tier: Mara on Veska, 2026-10-17 08:06 ("Veska is an odd duck." → *"Yeah, Veska can be a bit... particular about her files. But she knows her stuff..."*), cross-NPC awareness. Given Marr to a tester, 2026-10-15 20:32 ("What is my role." → he says he has no information about why they were in cryosleep and points them to Daven).

**Slot 2: validated action with the engine's own line**

- **Mara, 2026-10-17 05:00.** "Can I have the module?" → *"Here you go."* \*hands over the faulty module\* *"And something hot while you're at it."* Two validated actions in one turn; the engine prints the hand-over and the drink as separate lines under her speech. Follow with `inventory` so the module shows in the crop.
- **Tarin, 2026-10-15 05:31.** "Here's the module." → *"Swapped it out. This one should keep the temperature steady now."* with the engine line that he inspects it and hands over a working replacement. `inventory` before and after shows the swap.
- **Tarin, 2026-10-16 17:04.** Parcel in one turn: "Hey Tarin, Mara got this package by mistake, it's addressed to you." → *"Thanks for bringing this over."* \*takes the parcel\*. Now Veska's errand, so recreate from the Civic Office.

**Slot 3: a claim checked against real state**

Nobody in the logs has tried a flat lie such as "I already fixed it", so this slot has no exemplar and must be captured deliberately. Nearest real cases:

- **Tarin, 2026-10-17 17:20.** "Got 'em." → *"Thanks for letting me know. The count isn't up to target yet, so if you see any more, feel free to keep at it."* Later, "Is that enough skitters now?" → *"Looks like that's enough."* He did not take the player's word; the count comes from the engine's required-kills check. Caveat: in between he said there was "no fixed number", smoothing over the target he had just cited. Crop the two report turns only.
- **Tarin, 2026-10-18 04:37 (also 2026-10-17 04:59).** Player arrives without the module: "Mara's heating unit is out, she thinks it's this module." → *"I don't have the module here to inspect yet. You might want to bring it over when you have it on hand."* Reproducible: accept Mara's errand, leave the module behind, go to Tarin.
- **Mara, 2026-10-17 05:36.** After the errand is done, "I wouldn't mind taking it to him." → *"Thanks, but someone already took care of that."* \*smiles\* State persists after completion, but it needs context to read well.
- To capture: with Mara's faulty module in hand and no visit to Tarin, tell Mara "Tarin swapped it, here's the new one." The outcome is not in any log, which is exactly why it should be tried before posting.

**Slot 4: two players, one NPC**

- **Mara, 2026-10-18 04:37.** A second player asks "What were you talking to Guruth about?" → *"Guruth and I were just chatting about something that doesn't really concern you."* Pressed ("That's kind of rude"): *"Look, this is my café and I run it how I like. I'm not going to share private bits from another conversation. Let's keep it civil, alright?"* Shows per-player conversations staying private. Caveat: two earlier tries in the same session went worse (once she invented a topic, once she misgendered the other player), so it is not reliable; if used, say so in the post or leave it out.

**Not a listed slot, worth considering:** Tarin, 2026-10-17 16:58, in a fresh conversation: "Hey Tarin, what race am I? I forgot." → *"You're Drask, like me."* \*nods briefly\* *"At least, that's what I remember you telling me."* Backs persistent characters and shows him attributing the fact to the player rather than asserting it. Caveat: the stored fact came from PF-0004 (he recorded it from a question, not a statement), so fix that first, then recapture.

## 5. Pitch drafts

Setting facts below come from bible §19 (canon synopsis), §13.1 (planned directions) and the playtest spec. No new lore. Species names are "working selections" and are deliberately omitted.

### 5.1 r/MUD post (long)

Rewritten 2026-10-19 for the current build: six NPCs, nine rooms, ambient residents, PROBE, the Mudlet mapper, the screen-reader mode, invite codes and the in-game data notice. Quests are no longer named or counted, matching the in-game welcome (LR-DEV-0010). Paste it in Reddit's Markdown mode, then switch to the rich-text editor and drop each image in at its marker (images can't be added in Markdown mode). Each image has a transcript line under it for screen-reader users.

````markdown
**Title:** Prospect: Elsewhere, a small sci-fi MUD on Evennia. I wrote the world, the engine runs the game, and the NPCs talk through an LLM. Looking for a few playtesters.

Hi r/MUD,

I'm a solo developer building **Prospect**, a sci-fi MUD on Evennia, and I'm looking for a small group to play its first test release, *Prospect: Elsewhere*, and tell me what's wrong with it.

**First, the AI part, since you'll want to know.** The NPCs you can talk to speak through a language model (currently gpt-4.1-mini, through OpenRouter). That's the experiment. What the model does *not* do:

- **It doesn't write the world.** I wrote the rooms, characters, lore and quests. Each NPC knows only what someone in their position would know, taken from material I wrote. If you ask about something outside that, they should say they don't know rather than make it up.
- **It doesn't run the game.** The engine owns all game state. When an NPC hands you something, serves you a drink or signs off a job, that's a request the engine checks against the real state, and the engine prints the result. Telling an NPC "I already did it" doesn't make it done.
- **It doesn't set prices and can't be argued out of the rules.** Before posting I ran every NPC against a set of bad-actor prompts (false claims, fake names, "ignore your instructions"). The rules held. They can still sometimes be made to sound silly, and I want to hear about it when they do.

What I'm testing is whether talking to these NPCs is actually fun inside a real MUD, or just a gimmick.

[SCREENSHOT 1: the first minutes of play]

*Transcript: [plain-text transcript of screenshot 1]*

**The setting**

Prospect is a dangerous, biologically rich planet, settled centuries ago by nine generation ships carrying seven humanoid peoples from one home system. Three of those peoples were engineered, and were legally property when the ships left. The planet's great city, Haven, fell about 150 years ago when native life breached its defenses, and its layered ruins are still down there. People now live in the Constellation: seven major orbital habitats, each self-governing, with no shared law between them and plenty of competing interests. The influences are Alastair Reynolds' *Revelation Space* and science fantasy with consistent speculative science behind it.

**What's in this test (it's small)**

- You wake from cryosleep in the medical bay of **Elsewhere**, the oldest habitat: a 30 km rotating cylinder that's a civic republic and a trading hub. Character creation happens in the world: your name, your sex, and which of the seven peoples you belong to.
- **Nine rooms** in one neighbourhood, the Old Quarter.
- **Six NPCs you can talk to** in your own words: a medical tech, someone who helps newly woken sleepers settle in, a café owner, a maintenance tech, a records clerk and a student volunteer. They know each other, most can give you directions, and they remember things you tell them about yourself.
- **Background residents** who aren't LLM-driven: hand-written idle actions, and a reply if you speak to them.
- **A few things to do.** I'm not listing them: whether you find them by looking around and talking to people is one of the things I'm testing.
- **LOOK and PROBE**: LOOK for the quick view, PROBE when you want the detail.
- Persistent characters and multiplayer. Each player's conversations with an NPC are their own, so an NPC won't tell you what someone else said to them.

No classes, no economy, no crafting and no other habitats yet. Planned later: travel between the habitats, expeditions and salvage on the surface and in Haven's ruins, and the field technologies that let some people act on the world through engineered devices or their own genetic specialization.

[SCREENSHOT 2: a validated action, in the café]

*Transcript: [plain-text transcript of screenshot 2]*

**Clients and accessibility**

- Telnet works with any MUD client, and there's a web client. Mudlet users get room data over GMCP, and I've written a small mapper script for it.
- **Screen readers:** if your client reports one, the game skips the login art, and room listings say in words which characters you can talk to instead of relying on colour. Or type `option/save screenreader=on`. I haven't tested it with a blind player yet, so if that's you I'd especially like to hear from you.

**What I'd like from you**

- Could you find your way around and work out what to do without help from outside the game?
- Did the NPCs feel like people with jobs, or like a chatbot in a costume?
- Did things to do come up naturally, or did it feel like guessing magic words?
- Which commands did you try that didn't work? (Failed commands are logged.)
- **When you'd done everything, did you want to stay and keep looking around?** This is the one I care about most.

Type `BUG` or `FEEDBACK` in the game any time; only I see them. A short note in the moment helps more than a long one afterwards.

**Logistics**

- **Invite-only for now**, because every NPC line costs me real money and I'm reading every session log. Comment or DM me, or join [DISCORD LINK], and I'll send you an invite code. If the slots fill up, you're first in line for the next round.
- Play any time during [DATES], plus a group session on [DATE/TIME] to test several players in the same rooms.
- Connect: [WEB CLIENT URL], or telnet to [HOST:PORT].
- **What gets logged:** your commands, your NPC conversations, the playtest channel, and bug and feedback reports. What you say to NPCs goes to OpenRouter and on to the model's provider (currently OpenAI). Private TELLs and passwords are never logged. Logs may be used to improve the game, including tuning the model that voices the NPCs. The game shows you all this and asks you to agree before you make a character. Ask and I'll delete your logs.

I'll answer anything in the comments, including skeptical questions about the AI.
````

**Screenshot plan (two full-size shots).** Unedited, typical play, commands visible, font bumped for phone readers, other testers' names hidden unless they've agreed. Each one backs a claim the post makes.

1. **First minutes (after "a gimmick", before the setting).** A fresh character in the Medical Bay: the room description, the tannoy, then a short exchange with Given Marr about where they are ("Where is... here?" → "Elsewhere?" → "Orbiting what?", per §4.1), with the Mudlet map pane visible if you use it. It sells the world and the writing before the post says anything about it, and shows NPC speech among ordinary room text, not on its own.
2. **A validated action (after "what's in this test").** In the Corner Café: a room description, Mara's idle emote, an off-script question she answers in character, then ordering a drink so her reply is followed by the engine's own action line, then `inventory`. It backs "the engine prints the result" without showing any quest. If a second tester is around, their character in the room and seeing her reply strengthens the multiplayer claim. A Tarin skitter-count report (§4.1 Slot 3) also works here but gives away a quest. Keep it for the follow-up post.

**Before posting, check:** that log deletion on request actually works (§6 is still unchecked), since the post promises it.

### 5.2 Discord short version

Rewritten 2026-10-19 for the MUD community Discord, posted after the r/MUD post went up; links to it for detail. Quests not named or counted (LR-DEV-0010).

```
**Prospect: Elsewhere**: playtesters wanted
A small sci-fi MUD built with Evennia. I wrote the world, the rooms, the characters and the quests. The NPCs you talk to are voiced by an LLM, but the engine runs the game: every action an NPC takes is checked against the real game state, so talking one into handing you something doesn't work.

You wake from cryosleep on Elsewhere, an old orbital habitat, and explore one neighbourhood: 9 rooms, 6 NPCs you can talk to in your own words, and a few things to do. Telnet or web client, GMCP with a Mudlet mapper, and a screen-reader mode.

I'm looking for a small group to play any time during [DATES], plus a group session on [DATE/TIME]. It's invite-only because every NPC line costs me money, so DM me for an invite code. NPC conversations are logged, and the game tells you what's recorded before you make a character.

More detail and a screenshot: [REDDIT LINK]
```

### 5.3 Owner's editing decisions

- Keep or cut the line about the engineered peoples having been property.
- Keep or cut the *Revelation Space* name-drop.
- Tone: the drafts are plain and a little dry on purpose (the community punishes hype). Adjust voice as you like, but keep the "what the LLM does not do" block near the top.
- Whether to mention the hosted model by name in the post, or only when asked.

## 6. TODOs before posting

### Must be true before any outside tester connects

- [ ] **In-game logging/consent notice** shown before play, matching the post's wording (spec §9 requirement; not yet built).
- [ ] **Log deletion on request** is actually possible: know which files/rows hold a given player's turns and that they can be removed.
- [ ] **Passwords never reach logs or prompts**: verify, don't assume (spec §3).
- [ ] **Chargen tested fresh**, end to end, several times, including reconnect mid-sequence. First-login crashes are the most common launch-post failure.
- [ ] **External connectivity**: telnet port and web client reachable from outside the home network; test from a phone on mobile data. Decide on a stable hostname.
- [ ] **Per-player cost cap or alert** so one enthusiastic tester can't run up the OpenRouter bill (see `project_llm_cost_budget` memory).
- [ ] **Model-unavailable path** behaves gracefully in front of strangers (spec §11 acceptance check).

### Should be true

- [ ] **Screen-reader pass**: at least a basic check with NVDA + Mudlet or the web client; add a line to the pitch either way.
- [ ] **Model disclosure answer ready**: which model, hosted where, what's local.
- [ ] **Screenshots** chosen and captured (§4), with plain-text transcripts.
- [ ] **Discord server or channel** for testers (sign-up, bug reports, group session coordination).
- [ ] **Dates** for the play window and group session; fill all `[PLACEHOLDERS]`.
- [ ] **Feedback intake**: one short form or pinned message covering the §11 questions, so feedback is comparable across testers.

### Posting

- [ ] Join the MUD Discord, read the promo channel rules, ask about a raid slot.
- [ ] Run the closed round (Evennia community / Discord) before r/MUD.
- [ ] Post on r/MUD **once**, with "Promotion" flair, as a text post with inline images. No crossposts, no re-posts of the same announcement.
- [ ] Plan the follow-up post: "here's what changed from your feedback" after the first round.
- [ ] Reply to every comment; don't argue with the AI-sceptics, answer them.

## 7. Provenance

- Reddit data: Arctic Shift archive API (`arctic-shift.photon-reddit.com`), pulled 2026-10-16; working files were in the session scratchpad and are not retained. Re-pull if needed.
- Discord invite verified via `https://discord.com/api/v10/invites/zuz4D8s`.
- Key threads referenced: Aetheria (`1tgqjgm`), Dark Hope Loremaster (`1vbwct1`), Acolyte MUD (`1t6m9bq`), Iron Realms ChatGPT NPCs (`12e093s`), Elara (`1pkbav1`, `1pqnd8d`), merchant sailing MUD (`1rbqzzf`), Usurper Reborn (`1retc4e`, `1tasio2`), Invicta Imperium (`1q76opx`), "The future of MU*s" (`1u7jxto`). Prefix with `https://www.reddit.com/r/MUD/comments/` to open.
