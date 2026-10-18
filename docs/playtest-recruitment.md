# Playtest recruitment: pitches, research and pre-posting TODOs

**Status:** Draft. Pitch text needs the project owner's editing pass before it goes anywhere.
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

TODO after the owner's own playtesting: have Claude mine the conversation logs for exchanges fitting slots 1–3, then recreate and screenshot them.

## 5. Pitch drafts

Setting facts below come from bible §19 (canon synopsis), §13.1 (planned directions) and the playtest spec. No new lore. Species names are "working selections" and are deliberately omitted.

### 5.1 r/MUD post (long)

> **Title:** Looking for 4–5 playtesters: a tiny sci-fi Evennia MUD where the NPCs are LLM-voiced, but the engine and the writing are not
>
> Hi r/MUD,
>
> I'm a solo developer building **Prospect and the Constellation**, a sci-fi MUD on Evennia. I'm looking for a handful of people to break the first playable prototype.
>
> **Up front, since it's the first question people ask:** some NPCs speak through a large language model. That's the experiment. What the LLM does *not* do:
> - **It doesn't write the world.** Rooms, characters, lore and quests are written by me. Each NPC only knows what someone in their position would know, from material I wrote.
> - **It doesn't control the game.** The engine owns all state. If an NPC wants to hand you an item or mark a job done, that's a request the engine checks against the actual game state. Telling an NPC "I already fixed it" doesn't fix it.
> - **It can't set prices or be talked out of the rules.**
>
> The question I'm testing is whether the AI-voiced NPCs are actually *fun* to talk to inside a real MUD, or whether they're just a gimmick.
>
> **The setting**
> Prospect is a dangerous, biologically rich world, settled centuries ago by nine generation ships carrying seven humanoid peoples from a single home system. Three of those peoples were engineered and were legally property when the ships left. The planet's great city, Haven, fell about 150 years ago when native alien life breached its defenses. Its layered ruins are still down there. Civilization now lives in the Constellation, a ring of independent orbital habitats with their own politics and competing interests. The influences are Alastair Reynolds' *Revelation Space* and science fantasy grounded in consistent speculative science.
>
> **What's in this test (it's very small)**
> - You wake from cryosleep in a medical bay on **Elsewhere**, the oldest habitat, a 30 km rotating cylinder. Character creation happens in-world: name, sex, and one of the seven peoples.
> - About **nine rooms** of one neighborhood, the Old Quarter.
> - **Five LLM-voiced NPCs**: a medical tech, a mentor for newly woken people, a café owner, a maintenance tech and a community volunteer. Talk to them however you like.
> - **Three small quests**: an item errand, a gardening job, and some light combat clearing vermin out of the neighborhood.
> - Persistent characters, multiplayer, and a parser that tries to accept natural phrasing as well as standard MUD commands.
>
> No classes, no economy, no crafting, no other habitats yet. Planned later: the other Constellation habitats (ferries between them), expeditions and salvage on the planet's surface and in Haven's ruins, and the field-based technologies that let some people manipulate the world through engineered devices or genetic specialization.
>
> **What I want from you**
> - Could you find your way around and figure out what to do without help outside the game?
> - Did the NPCs feel like people with jobs, or like a chatbot in a costume?
> - Did quests come up naturally, or did you feel like you had to guess magic words?
> - Which commands did you try that didn't work? (I log failed commands.)
> - **When you finished, did you want to keep talking and exploring?** This is the one I care about most.
> - Try to break the NPCs. I'd rather you find the holes than a later player.
>
> **Logistics**
> - Invite-only for now, because every NPC line costs me real money and I'm reading every session log. Comment or DM me, or join [DISCORD LINK]. If the slots fill, you're on the list for the next round.
> - Play whenever during [DATES], plus a group session on [DATE/TIME] to test multiplayer.
> - Connect by [WEB CLIENT URL] or telnet at [HOST:PORT].
> - **Logging notice:** conversations with the NPCs are logged. I may review and curate some of them, with names stripped and passwords never recorded, to improve the NPCs, possibly including fine-tuning a model. You'll see this notice before you play, and you can ask to have your logs deleted.
>
> Happy to answer anything in the comments, including skeptical AI questions.

### 5.2 Discord short version

> **Prospect and the Constellation**: a tiny sci-fi Evennia MUD testing LLM-voiced NPCs. The world, lore and quests are written by me, and the engine checks every NPC action. Wake from cryosleep on an orbital habitat, explore a 9-room neighborhood, talk to 5 NPCs however you like, and do 3 small quests (including light combat). Looking for **4–5 testers** for [DATES] + a group session [DATE]. I want blunt feedback on whether the NPCs are fun or just a gimmick. NPC chats are logged for review. DM me or [LINK].

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
