_Part of the split design bible - see [`00-index.md`](00-index.md) for the status-label legend and the full section map._

## 17. Unresolved decisions and canon safeguards

**Status:** Unresolved unless a safeguard repeats an established constraint. The priorities below originate in the source; the added dependency notes do not settle any answer.

### Highest-priority worldbuilding decisions

The **seven working names and broad body plans are selected**; the exact physiology, comparative traits, and reproductive mechanisms still need work, but none is necessary before the three-NPC conversational prototype. The **broad Elsewhere architecture, seven working regions, representative civic philosophy and founding equality principle are also established**. What remains important is:

1. **Immediate NPC prototype:** Choose actual small room connectivity and minimal prompt/context boundaries; write the common-knowledge sheet; give each NPC one validated action; apply Mara's approved reaction to "Cave Crawler"; test the proposed three NPC profiles and review logged interactions.
2. **When needed for NPC characterization:** Refine localized cultural details and institutional vocabulary, without creating a complete constitution or simulated economy.
3. **Later worldbuilding:** Resolve the seven peoples' remaining biology (appearance settled 2026-10-17, §§5.1–5.7; sex differences, lifespans and iris colours settled the same day; teeth and diet, Drask eyes and the engineered peoples' iris colours still open), ancestral home-system geography, the hybrid-descended people's reproductive history, and commissioners' assignments.
4. **Later historical content:** Name and develop each generation ship and settlement; detail Haven's unification, legal history and government.
5. **Later game systems:** Build Elsewhere's full economy, civic offices, room map and transport; settle the Venn–Saye schools, tools, energy limits, Kell cultural bonus and mechanics.

These are scoped priorities, not an implementation roadmap with dates or deadlines.

### Questions that can remain mysterious or undecided

- What exactly caused the ancient AI crisis?
- Why did the Nine undertake their interstellar expedition?
- What were the ships' original destination and navigation circumstances?
- What exact organism or ecological mechanism initiated the Bloom?
- Could the catastrophe have been prevented?
- Did any residents survive in sealed Haven districts?
- What precise technological system maintained Haven's environmental protection?
- What are the Constellation's contemporary laws concerning advanced AI?
- How many habitats exist, and is there any common inter-habitat political authority?
- How do people talk to one another across the Constellation? The `tell` command's lines say only "your comms" (LR-DEV-0005, owner 2026-10-17); whether a Constellation-wide network exists, and what a person carries to use it, are deliberately left open.
- What are Prospect's principal biomes, native organisms, and geographical landmarks?
- What are the precise official names, electoral systems, legal procedures and jurisdiction of Elsewhere's civic institutions?
- How does traffic between the Constellation and Prospect's surface actually work, now that no shared gateway exists (Threshold rejected 2026-10-18, §11.6)? Each habitat decides for itself what it admits; who runs expeditions, from where, and how quarantine is done are open.
- Do the habitats defend themselves at all, and against what? The owner's 2026-10-18 decision rules out joint institutions but says nothing about defence.
- What subtle biological bonuses, if any, do the species carry? (Appearance and physiology settled 2026-10-17, §§5.1–5.7; sex differences and lifespans settled the same day.)
- What precise biological processes on Prospect made practical Venn–Saye dynamics possible, and when were those advances made?
- What are the exact identities and biographies of Venn and Saye?

### Important canon safeguards

Do not silently establish any of the following without a deliberate worldbuilding decision:

- A specific number of years since landfall beyond the agreed approximate history.
- That the ancestral peoples descended from Earth humans.
- That all seven peoples evolved independently.
- That the Nine consisted of seven homogeneous single-species vessels.
- That the engineered peoples were already emancipated when the Nine departed.
- That every engineered species is genetically derived directly from its commissioning ancestral species.
- That any habitat beyond the seven in §11.7 exists, or that any Constellation-wide body, treaty or jointly run facility exists (owner, 2026-10-18).
- That the Bloom was a sentient pathogen, technological plague, deliberate attack, or AI rebellion.
- That Haven was originally constructed as an orbital-refuge project.
- That every habitat shares the same government, ideology, or economy.
- That generic Fieldworks tools require genetic modification or are called catalysts.
- That Dynamicists can specialize in multiple schools or perform advanced manipulation without a catalyst.
- That particular proposed schools or devices have already been finalized.
- That Kell have inherent biological superiority in dynamics, or that their proposed cultural bonus has a settled numeric value.
- That Venn–Saye dynamics was first discovered on Prospect; only its much more powerful applications developed there.
- That *Void Walkers*, *Cave Crawlers* and *Sea Walkers* are the engineered peoples' formal names or always neutral expressions.
- That Elsewhere's working geographic names are legal/administrative district boundaries.
- That a fixed population, complete life-support model or finished public institution roster is necessary to run the first NPC test.
- That the three prototype NPC biographies or six proposed room names are permanently canonized.
- That every NPC in the prototype requires a language model, full memory, autonomous schedules or persistent inter-NPC relationships.
- That raw unreviewed conversation logs should be used indiscriminately for model fine-tuning.
- That generated NPC dialogue alone can change game state, set prices, or establish canon (all game effects go through validated tool calls; Section 16.5).
- That NPCs barter or negotiate prices.
- That Provisional or Unresolved material may be placed in NPC prompts.


---

### 17.1 Practical decision dependencies

**Proposed planning guidance:** The source's highest-priority questions remain the primary worldbuilding backlog. For implementation planning, the following dependencies help avoid accidental decisions:

| Work being prepared | Decisions needed first |
|---|---|
| Elsewhere's first conversational prototype | Minimal five-to-six-room connectivity, three lightweight NPC prompts, the common-knowledge sheet, one validated action per NPC, Mara's approved reaction to "Cave Crawler," in-universe context and reviewed logging; full economy, law and district mapping are not prerequisites. |
| Character creation and environmental mechanics (later) | Detailed species biological limits, ancestry/citizenship separation, and any Kell field-proficiency bonus; working names, body plans and full physical descriptions already settled (§§5.1–5.7). |
| Dynamicist classes, Fieldworks skills and catalyst equipment | Approved schools, genetic specialization rules, catalyst functions, limitations, resource system and skill progression. |
| Contemporary legal or political storylines | Applicable local law, emancipation history where relevant, and actual contemporary organizations. |
| Generation-ship or Nine district content | Individual names, political histories, cultural continuities, and approved physical details. |
| Surface expeditions and Haven content | Approved locations, local hazards, protection requirements, which candidate environments enter canon, and how surface access is gated (Section 13.7). |
| NPC context and training-data handling | First: concise profiles, approved lore boundaries, model/prompt metadata and curated logs. Later: richer persistent memory, event rules, shared NPC knowledge and world-state systems. |
| Content set on a habitat other than Elsewhere | Which of the six (§§11.3, 11.4, 11.8–11.11) and what local detail it needs; each habitat's constitution, offices, districts and institutions are still unnamed. |

Not every background mystery must be resolved to test three conversations on Elsewhere. Content touching an unanswered question must preserve that uncertainty. A mystery can remain unanswered; mechanics that depend on a specific answer need separate design decisions. In particular, keep the test independent of complete economy, combat, transit and governance systems.

## 18. Maintaining the living bible

**Proposed editorial workflow:** These conventions make the Markdown file maintainable without granting any proposal automatic approval.

1. Give new material an explicit status and identify the source or project decision supporting it.
2. Keep competing candidates under **Provisional** or **Unresolved** until a deliberate decision selects one.
3. When a decision is made, update the relevant main section, terminology, chronology, and open questions together. Remove obsolete alternatives or mark them superseded.
4. Check the canon safeguards before accepting new lore. Preserve approximate dates and do not silently resolve biological, legal, or political gaps.
5. Review dependent NPC, room, quest, and gameplay content when canon changes. Dialogue and rumors must not substitute for an authorial decision.
6. Keep setting canon, gameplay requirements, and implementation proposals distinct in future edits.
7. **When editing with an AI assistant**, name the sections to change and ask for every other section to be returned unchanged. Bump the version on every round trip and record in the revision history which assistant changed which sections, so drift can be caught by diffing versions.
8. **Precedence of engineering decisions:** Sections 13.5 (architecture test and phase 2), 13.7, 14.4 (in `s13-14-gameplay-and-npc-design.md`) and 16.4–16.9 (in `s16-tech-and-implementation.md`) record engineering decisions made with Claude. Where a later edit would conflict with them, flag the conflict for the project owner rather than silently overwriting.

**Planned content-authoring tool (development direction, not implemented functionality):** The project owner and Claude intend to build a dedicated MUD editor for creating, viewing and editing world content and relationships. Until that tooling exists and is integrated, the existing repository content files and their explicit approval metadata retain their authority. The editor should respect the same separation between global canon, approved local detail, provisional drafts and engine-authored state; choosing an editor does not itself approve new lore or replace the existing data model.

Suggested decision-record fields are **date**, **topic**, **previous status**, **approved decision**, **affected sections**, and **rationale or source**. No such approval records are supplied by the reference.

### Revision history

| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-10-10 | Organized the supplied worldbuilding reference into a repository-ready design bible; added explicit status guidance, a source-grounded political inventory, gameplay gaps, and clearly provisional NPC implementation guidance. No additional setting lore established. |
| 0.2 | 2026-10-10 | Added Venn–Saye field discovery and the science-fantasy design direction; distinguished unrestricted-class Fieldworks technology from genetically specialized, catalyst-dependent Dynamicists; recorded the one-school-only biological constraint, provisional schools, Ancestral A (now Kethari) scientific heritage and proposed bonus; updated chronology, glossary, gameplay, open decisions and safeguards. |
| 0.3 | 2026-10-10 | Adopted revisable names and broad features for seven peoples; recorded engineered peoples' historical nicknames and the translation convention; defined Elsewhere as an approximately 400-year-old, 30×2-km open cylinder with axial illumination, dockward-to-agricultural longitudinal expansion, seven provisional regions, diversified new-player economy and inclusive civic republic; narrowed prototype to roughly six rooms, three lightweight LLM NPCs and curated conversation logging for possible LoRA training. |
| **0.4** | **2026-10-10** | **Merged with Claude: consolidated the separate engineering design doc into this bible. Added 13.7 (on-demand ferries, gated surface access), 16.4–16.9 (Evennia/Python stack, swappable OpenAI-compatible model layer, engine-validated tool layer, no bartering with reputation-derived prices, lore store limited to Established canon with per-NPC knowledge scopes, memory rules, safety rules, roadmap, adult-content stretch goal). Conflict resolutions: prototype keeps v0.3's narrow scope but requires one validated action per NPC; memory, a quest and rumor/reputation actions move to prototype phase 2. Updated 13.3, 13.5, 14.2, 14.4, 14.6 (common-knowledge sheet; Mara's "Cave Crawler" reaction flagged), 14.7, 16.3, 17 and 18. Setting canon unchanged.** |
| 0.4.1 | 2026-10-10 | Updated Section 14.6 with the project owner’s approved, NPC-specific response to “Cave Crawler”; resolved the corresponding open prototype decision in Section 14.6 and adjusted planning references in Sections 17–18. The term’s wider social meaning remains unresolved; no setting-wide canon change. |
| **0.4.2** | **2026-10-15** | **ChatGPT editorial update, for project-owner review:** Added the game-first principle (§1), provisional name-sound ideas (§5.9), future profession-choice timing (§13.2), clarification of early vs. external-playtest scope (§§13.5 and 13.8) including Given/Daven's selected roles and species, optional terminal splash presentation notes (§16.10), and the planned dedicated MUD editor direction (§18). Preserved existing setting canon, open lore questions and earlier technical decisions. No draft scenario or presentation detail promoted to setting-wide canon. |
| 0.4.3 | 2026-10-15 | **Claude editorial update, for project-owner review:** Added one clarifying paragraph to §13.8 distinguishing the three numbered playtest quests from two other already-implemented standing commitment scenarios (Mara's misdelivered parcel, the Mara/Iri noticeboard-revision check) that run alongside them but aren't counted among the three. No other section changed; no setting canon or scope decision added. |
| 0.4.4 | 2026-10-16 | **Claude Code reorganization (docs/game-plan.md Week 0 item 5):** Split this single file into topic files under `docs/bible/` (see `00-index.md`'s layout table), verified line-for-line identical to v0.4.3's body via diff. Updated §18 item 8's section references to name the files 13.5/13.7/14.4 and 16.4–16.9 now live in. No setting canon, status label, or wording changed anywhere else. The v0.4.1–v0.4.3 single-file versions remain in `docs/` as historical snapshots. |
| 0.4.5 | 2026-10-16 | **Project-owner decisions via the Lore lane:** §14.6 - the Old Quarter cast (Mara, Tarin, Iri, Veska, Daven, Given) now know one another by name, role and workplace; previously "not yet established". Iri Vael's primary setting is the Civic Office only. No other canon changed. |
| 0.4.6 | 2026-10-16 | **Project-owner decision via the Lore lane:** §§2 and 5 - six of the seven working species names replaced for readability and phonetic distinctness (Kethari → Kell, Sylari → Drask, Aevyrin → Lirra, Naevari → Revari, Otheryn → Astrel, Neshyr → Selk; Voldren unchanged); the *ae* and “other in” pronunciation notes retired with the old names. Applied throughout the bible (revision-history rows kept as written) and to `content/`. No other canon changed. |
| 0.4.8 | 2026-10-17 | **Project-owner decision via the Lore lane (LR-LORE-0002 follow-up):** §§3 and 8 - emancipation of the engineered peoples was complete across Haven and the habitats before the Bloom; its order relative to Elsewhere's founding stays undecided, and §18's safeguard against emancipation-at-departure stands. Recorded so player-facing text (the chargen species picker) stops implying Elsewhere alone ended servitude. The owner also confirmed that emancipation advanced on "some" ships during the voyage, as §3 already says, not "most". |
| 0.4.9 | 2026-10-17 | **Project-owner decision via the Lore lane:** §5.9 rows widened after the owner judged the first `ops/namegen/` output too repetitive. Kell given names 2–3 syllables (was 1–2); Drask and Selk family names 1–2 (was 1); Voldren given names 2–3 (was 2) with plain *l, r, n, d* middles allowed beside the heavy clusters, one heavy cluster still required; a shared Length rule says to lean toward the longer end of every range. Astrel unchanged (its skew toward *s*-onsets was generator weighting). Still creative guidance, not canon; no character renamed. |
| 0.4.12 | 2026-10-17 | **Project-owner decisions via the Lore lane:** §5.8 - content and prompts say *male*/*female*, never *man*/*woman* (applied to all six personas, each `prompt_version` +1); §5.4 - the Revari trait menu widened (scale patches on shoulder blades, abdomen or hips; feathers mixed through the ruff; a Kell-sized scaled tail with a furred tip), for the admin character Ravis Vardur. `content/lore/5.4.md` and the Revari chargen sentence updated. |
| 0.4.13 | 2026-10-17 | **Lore lane, owner decision (LR-DEV-0005):** the `tell` command's comms lead-in lines approved as written in the request ("Your comms crackle..." / "Your comms click..."). A drafted §11.7 (Constellation-wide voice network plus a personal earpiece) was withdrawn unapproved: the owner dropped the earpiece and deferred the network, so §17 lists Constellation-wide communication as an open question. No canon added, no `content/` file changed, no `prompt_version` bumped. |
| 0.4.14 | 2026-10-17 | **Owner decision via the Lore lane (LR-LORE-0004):** the project is retitled *Prospect*; the initial playtest release is *Prospect: Elsewhere*, with later releases subtitled by where they put the player. Index title changed and a "Game title" row added; no setting canon changed, *the Constellation* keeps its Established status as an in-world term. |
| 0.4.15 | 2026-10-18 | **Owner design direction via the Lore lane (LR-LORE-0005):** new §13.9 on room listing density for the map build-out: a per-object flag decides whether an object's line shows in the arrival glance, and rooms with no quest cue or information object promote one or two atmospheric objects into the glance so they still read as populated. Not setting lore; no canon changed. |
| 0.4.16 | 2026-10-18 | **Owner design direction via the Lore lane (LR-LORE-0006):** §13.9 retitled and extended: every NPC built from now on carries a four-to-six-line idle emote list, consistent with its poses, implying rather than stating world facts, never reaching an LLM prompt. Not setting lore; no canon changed. |
| 0.4.17 | 2026-10-18 | **Lore lane draft at the owner's request (LR-OWNER-0001), awaiting approval:** §§11.3 and 11.4 rewritten as firm Established-track text for Freehold and Meridian, which the owner has directed become official habitats; new §11.7 holds the eight-habitat roster rule and the short names-only paragraph every NPC gets; §§11.8–11.12 propose five further major habitats (Anchorage, Threshold, Lantern, Tailings, Hermitage), one section each so a persona's `knowledge_scope` can name a single habitat (owner's knowledge model, same day). All of §§11.3, 11.4 and 11.7–11.12 are marked Draft and nothing in them is canon or reaches a prompt until the owner approves it; §§2, 12, 14.2, 17 and 19 are updated only on approval. |
| 0.4.18 | 2026-10-18 | **Owner approval via the Lore lane (LR-OWNER-0001):** all of the 0.4.17 Draft approved except Threshold, which the owner rejected because the habitats are insular, self-sufficient and self-governing and no agreement among them exists; that decision is recorded in §11.6. §§11.3, 11.4, 11.7–11.11 are Established: seven major habitats (Elsewhere, Freehold, Meridian, Anchorage, Lantern, Tailings, Hermitage), one section each so a persona's `knowledge_scope` can carry a single habitat, and a names-only roster paragraph every NPC gets. §§2, 3, 12.1, 12.2, 14.2, 14.5, 17 and 19 brought into line; the §17 safeguard now guards against habitats beyond the seven and against any Constellation-wide body. `content/common-knowledge.md` gained the roster paragraph, `content/lore/11.3`, `11.4`, `11.7`–`11.11` written, one habitat added to five personas' scopes, all six `prompt_version`s bumped. |
| 0.4.11 | 2026-10-17 | **Project-owner decisions via the Lore lane, approved the same day:** visible sex differences per people, typical lifespans with maturity and old-age ages, and Kell/Revari iris colours, proposed at the owner's request as a draft §5.10 and, on approval, folded into §§5.1–5.7 with a shared principles paragraph in §5.8 (§5.10 removed). `content/lore/5.1`–`5.7` updated to match. |
| 0.4.10 | 2026-10-17 | **Project-owner decisions via the Lore lane, approved in full the same day:** §5.1 gains the Kell's physical description decided with the owner in a worldbuilding session (rangy maned-wolf build at about 2 m / 65 kg, narrow muzzle with a dry nose plate, reflective eyes, large leathery ears, a 25–30 cm tapering dorsal ruff, full crested tail, four-fingered padded hands, bare wrapped feet, non-Earth coat colours, backless apron-like dress); §5.2 gains the Drask's (dense broad build at about 1.9 m / 95–110 kg, warm-blooded, teeth hidden at rest, large backward-shingled scales from brow to neck, no external ears, dark unforked tongue, keeled banded scales in non-Earth colours, patch shedding, ground-length tail, four-digit hands and feet with short untrimmed claws, ordinary shirts over a loincloth); §5.3 gains the Lirra's (lightest mid-height people at about 1.9 m / 50–55 kg, flightless with vestigial feather fringes on the arms, short blunt beak-like muzzle with teeth, raptor-like side-set eyes and feather-covered ear openings, head-only feather crest, true moulting feathers, long thin feathered tail, muscular scaled digitigrade legs, bare scaled hands, two-colour palettes, loose draped full-cover dress); §5.4 gains the Revari's (Kell base at about 2 m / 65–70 kg, a fixed menu of inheritable Drask and Lirra traits capped at two or three per person, traits running in families, a never-present list, Kell eyes and palette, dress mixed by family); §5.5 gains the Astrel's (tallest at 2.3–2.4 m / 70–80 kg, smooth hairless charcoal-to-grey skin, short blunt muzzle with lips, large eyes with an inner lid, small flat ears, long-jointed four-fingered hands, prehensile feet, no tail, tiring at full gravity, fitted pocketed dress); §5.6 gains the Voldren's (shortest at 1.3–1.4 m / 90–110 kg, thick leathery rock-coloured skin with keratin plating on wear surfaces, heavy brow and short broad muzzle with dust-filtering nostrils, small deep-set low-light eyes and a habitual cap or visor, recessed ears, hoof-nailed hands, thick-soled feet always booted, no tail, sturdy reinforced dress); §5.7 gains the Selk's (mid-height at 1.9–2.0 m / 85–95 kg, smooth cool countershaded skin, broad flattened head with a wide mouth and no dorsal fin, wide-set eyes with an inner lid, no external ears, sealing nostrils, a sensory line along jaw and flanks, fin-like stabilisers on forearms and calves, mildly webbed hands, fully webbed feet needing special footwear, no tail, breath and pressure adaptations, fitted water-shedding dress); §5.8 gains the height ladder (Voldren shortest, Astrel tallest, the other five close). All of it is Established as of the owner's approval; the chargen sentences moved into `content/species.md`, and `content/lore/5.1`–`5.7` written (5.6 updated). |
| 0.4.7 | 2026-10-16 | **Lore lane, approved by the owner 2026-10-16 as a working basis for a name generator:** §5.9 personal-name guidance rewritten for the renamed peoples - each row anchored to the shape of the people's own name, spread so no two rows share onset, ending and length, plus shared readability, exclusion and borrowing rules, so Tools can build a per-people name generator. Still brainstorming guidance, not canon; no character renamed. |

---

