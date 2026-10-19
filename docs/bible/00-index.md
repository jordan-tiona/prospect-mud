# Prospect

**Living Project Design Bible**

| Field | Value |
|---|---|
| Document version | 0.4.18 |
| Last organized | 2026-10-18 |
| Development stage | Early development |
| Project | Text-based multiplayer science-fiction MUD |
| Game title | *Prospect*. The initial playtest release is *Prospect: Elsewhere*; later releases take a subtitle from wherever they put the player. Owner decision 2026-10-17 (LR-LORE-0004); the project and this bible were titled *Prospect and the Constellation* through v0.4.13. *The Constellation* remains an Established in-world term. |
| Creative direction | Science fantasy grounded in consistent speculative science; atmosphere and political/technological influences from Alastair Reynolds' *Revelation Space* universe |
| Initial playable location | Elsewhere |
| NPC direction | LLM-driven in-universe dialogue; small conversational proof of concept with curated logging for potential future LoRA fine-tuning |
| Source of setting material | *Prospect and the Constellation — Worldbuilding Reference and Design Source*, version 0.1, supplied by the project owner |
| Engineering stack | Evennia (Python) game engine; LLM reached through one swappable OpenAI-compatible API layer; local open-weight model for prototyping |

This living bible organizes the original worldbuilding reference and subsequent decisions, including the initial NPC prototype plan, the adopted engineering architecture (Section 16), and subsequent gameplay and authoring directions through 2026-10-15. It preserves established facts and uncertainty. New organizational guidance and implementation suggestions are explicitly identified as proposals; they do not add setting canon or claim that any game system has been implemented.

## How to read this bible

| Label | Meaning |
|---|---|
| **Established canon** | A setting fact affirmed in the source. It can be used consistently in world content. |
| **Established design direction** | An affirmed creative or gameplay requirement. This is a development intention, not a claim about completed software. |
| **Provisional** | A candidate name, physical concept, historical explanation, location, or gameplay possibility. It is not approved canon. |
| **Unresolved** | The source leaves the answer undecided. Do not fill the gap with an authoritative invention. |
| **Proposed implementation guidance** | Practical guidance added in this organization of the bible. It requires a project decision before becoming an implementation requirement. |

Sections marked **mixed status** contain settled foundations alongside explicitly qualified possibilities. Words such as *may*, *might*, *could*, *potential*, *possible*, and *not necessarily* retain their original uncertainty. Examples illustrate an option; they do not establish a named place, organization, event, or mechanic. Approximate dates stay approximate. A working name does not make every fact about the people it describes provisional, and an established place name does not settle that place's undeveloped institutions.

An **unresolved author decision** is distinct from an **in-world mystery**. The reference permits some questions to remain mysterious, but this document does not invent secret answers. Likewise, an NPC's belief or prejudice need not be objective world truth.

## Bible layout (split 2026-10-16)

This bible is organized as a set of topic files under `docs/bible/`, grouped from the original single-file `docs/prospect-constellation-design-v0.4.3.md` (kept in `docs/` as a historical snapshot, not updated further). Splitting was a pure reorganization - verified line-for-line against that file - no setting canon or status label changed. Section numbering inside each file is unchanged, so "bible 14.6" still means the same thing; only which file holds it changed.

| Sections | File | Covers |
|---|---|---|
| 19 | [`s19-canon-synopsis.md`](s19-canon-synopsis.md) | Canonical setting synopsis - the condensed canon digest; read this first for a quick Established-canon refresher |
| 1–3 | [`s01-03-premise-terminology-chronology.md`](s01-03-premise-terminology-chronology.md) | Core premise and creative principles, names and terminology, relative chronology |
| 4 | [`s04-home-system-origins.md`](s04-home-system-origins.md) | Home system and historical foundations: pre-interstellar civilization, the AI crisis, the Genetic Revolution and Three Commissions |
| 5 | [`s05-peoples.md`](s05-peoples.md) | The seven peoples |
| 6–10 | [`s06-10-exodus-and-haven.md`](s06-10-exodus-and-haven.md) | The Nine generation ships, Prospect, the founding of Haven, Haven's architecture and historical geography, the Bloom and the ruined city |
| 11–12 | [`s11-12-constellation-and-factions.md`](s11-12-constellation-and-factions.md) | The Constellation and its seven habitats (Elsewhere, Freehold, Meridian, Anchorage, Lantern, Tailings, Hermitage; §11.7 is the shared roster, one section per habitat for scoping), factions and institutions |
| 13–14 | [`s13-14-gameplay-and-npc-design.md`](s13-14-gameplay-and-npc-design.md) | Gameplay concepts and prototype scope, LLM-driven NPC design - CLAUDE.md's engineering callouts (13.5–13.7, 14.2/14.4/14.6/14.7) live here |
| 15 | [`s15-dynamicism-fieldworks.md`](s15-dynamicism-fieldworks.md) | Venn–Saye dynamics, Fieldworks, and Dynamicism |
| 16 | [`s16-tech-and-implementation.md`](s16-tech-and-implementation.md) | Technology and implementation boundaries - stack, request flow, lore store, safety, roadmap (CLAUDE.md's 16.4–16.8) |
| 17–18 | [`s17-18-unresolved-and-maintenance.md`](s17-18-unresolved-and-maintenance.md) | Unresolved decisions and canon safeguards; maintaining the living bible (editorial workflow, revision history) |

Read only the file(s) a task actually needs - that's the point of the split; don't load the whole bible into context.
