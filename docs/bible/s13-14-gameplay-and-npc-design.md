_Part of the split design bible - see [`00-index.md`](00-index.md) for the status-label legend and the full section map._

## 13. Gameplay concepts and prototype scope

### 13.1 Established direction

The project is a text-based multiplayer MUD. The prototype begins on **Elsewhere**, a functioning orbital society containing civilian neighborhoods, markets, industrial workplaces, transportation facilities, and political institutions. The broad geographic regions have working names; exact room layouts and a detailed district map have not been designed.

Prospect provides dangerous destinations for expeditions, salvage, resource gathering, scientific discovery, and combat. Additional habitats offer future opportunities for trade, travel, social conflict, and new playable environments. These are intended avenues of play, not completed systems or promises of prototype availability.

### 13.2 Character identity

**Established design direction:** Species and place of origin are separate character choices. Members of all seven peoples may inhabit the various habitats.

Species should influence anatomy, appearance, environmental tolerances, and perhaps limited gameplay capabilities. It must not determine personality, morality, class, or profession. Habitat background can influence cultural familiarity, economic opportunity, beliefs, and social connections without fixing a character's views.

**Established design direction:** Fieldworks can be learned and used by any class with the requisite tool and training. Dedicated Dynamicists (Dynos) require extensive school-specific genetic adaptation and catalysts. Each practitioner can undergo only one survivable school specialization; a second specialization is fatal. See [Section 15](#15-vennsaye-dynamics-fieldworks-and-dynamicism).

**Established long-term onboarding direction:** For the finished game, a player should encounter and learn something about available professions **before being asked to choose one**, with profession selection placed toward the end of the fuller introductory experience rather than during initial identity creation. No profession selection is included in the small external playtest (Section 13.8). This establishes timing, not a profession roster, permanent-class policy or advancement system.

**Unresolved:** Character creation implementation beyond the separately specified first playtest, numeric traits, progression and class roster, starting resources, citizenship rules, and how environmental differences affect play. The effects of the proposed Kell field-related racial bonus, which schools become playable, and the advancement and balancing of Fieldworks versus Dynamicism are also undecided. Biological adaptations must have practical consequences without making particular character choices unplayable.

### 13.3 Gameplay opportunity map

| Setting foundation | Supported gameplay concept | Still undecided |
|---|---|---|
| Elsewhere is a functioning society | Social interaction, civilian life, work, markets, and local political involvement. | Jobs, transactions, organizations, access rules, and initial districts. |
| Prospect remains economically indispensable | Extraction, expedition support, scientific research, biological sampling, and resource gathering. | Resource definitions, equipment, production, and rewards. |
| Haven preserves valuable history and technology | Salvage, discovery, investigation, and recovery of machinery or artifacts. | Particular finds, quest content, ownership, and recovery mechanics. |
| Prospect has a dangerous indigenous biosphere | Environmental risk, hazardous exploration, combat, and possible contracted organism removal. | Creatures, encounters, protection requirements, combat rules, and injury or death. |
| Habitats are economically linked and politically distinct | Trade, travel, social conflict, and expansion into other societies. Travel between habitats uses on-demand ferries (see 13.7). | Ticket costs, currencies, trading systems, and relations. |
| The Venn–Saye field supports everyday devices and specialized practitioners | General Fieldworks tools across classes; one-school Dynamicists with universal catalysts and flexible magic-like techniques. | Device catalog, school list, cost model, gameplay limits, catalyst items, and specific player classes. |
| Unregulated surface activity is possible where appropriate | Illegal salvage or smuggling as potential activities. | Applicable law, enforcement, contraband, and any player-facing crime system. |

This table translates source material into design categories. It does not add quest givers, rewards, currencies, or organizations.

### 13.4 Exploration structure

**Provisional gameplay concept:** Haven supports exploration through vertically layered environments, with increasing historical depth as players descend. Older does not automatically mean harder: the source establishes no level curve, enemy hierarchy, access order, or guaranteed increase in danger with depth.

Prospect's wilderness supplies separate exploration opportunities across alien biomes. No biome roster or room map is fixed. The candidate ruin environments in Section 10 are possibilities, not mandatory zones.

### 13.5 Prototype purpose and explicit scope

**Historical scope note:** This subsection records the original conversational/engine-architecture prototype and its deliberately small boundaries. It does **not** describe the later first external playable test (Section 13.8), which adds conventional game activities after the underlying NPC experiments.

**Established immediate objective:** The first prototype is primarily a **viability test for LLM-driven, in-universe NPC conversation**, not a vertical slice of a finished multiplayer RPG. Its initial questions are whether a relatively modest model can maintain basic character identity, stay within appropriate setting knowledge, converse naturally rather than lecture, and generate material useful for a **reviewed and curated** training corpus for a potential future setting-specific **LoRA**.

**Current working target:** A small neighborhood using approximately **five or six interconnected rooms**, **three LLM-driven NPCs**, and optional ambient/background NPCs with only descriptions or simple scripted behavior. Neither complex schedules nor NPC-to-NPC relationship systems, generalized autonomy, elaborate persistent memory or simulated local politics are required for the first experiment. The exact implemented room count and command interface remain open; the prototype model is a local open-weight model in the ~8B–14B class (Section 16.4).

**Established requirement (architecture test):** Each LLM-driven NPC has at least **one simple engine-validated action** (for example, Mara serving a drink or Tarin handing over a part), routed through the tool layer described in [Section 16.5](#165-npc-request-flow-and-the-tool-layer). Tool calling is the weakest capability of small models and the mechanism the whole NPC architecture depends on, so it is tested from the first build rather than added later. These actions need no economy behind them.

**Prototype phase 2 (after conversation viability is confirmed):** Short per-player NPC memory stored as facts (Section 16.6), a simple quest inside the neighborhood, and the `share_rumor` and small reputation-nudge actions. These were part of the agreed engineering plan and are sequenced after the phase 1 conversation test rather than dropped.

**Deferred by explicit project priority:** Full room coverage of Elsewhere, detailed economic/profession mechanics, combat, quest systems beyond the phase 2 test quest, inventory progression, long-distance travel, political simulation, Dynamicist skill systems, and full persistence or social autonomy. Simple room transitions and minimal state may still be needed to make conversations intelligible.

### 13.6 Proposed six-room test neighborhood

**Status:** Conceptual starting map **only**, not approved final room or business canon. All rooms can sit within or very near the Old Quarter and Exchange, close to the dockside arrival infrastructure.

| Proposed room | Simple local role |
|---|---|
| **Lift Concourse** | Arrival point from the axial dock-to-rim elevator; passersby and notices |
| **Old Quarter Square** | Small public hub, connecting the other rooms beneath the axial light |
| **Corner Café** | A place for informal dialogue with a café owner |
| **Maintenance Workshop** | Work setting for an infrastructure technician |
| **Residential Courtyard** | Quiet neighborhood public space and casual encounters |
| **Civic Office** | Everyday public-service setting for civic conversations and a volunteer |

The map is not intended to test every intended MUD activity or prove a scaled transit network. The three talkative NPCs are detailed in [Section 14.6](#146-proposed-three-character-prototype-cast).

### 13.7 Travel between habitats and to the surface

**Established design direction:**

- **No player-piloted ships.** Travel stays as rooms and exits, which Evennia handles natively.
- **On-demand ferries between habitats.** A ferry departs as soon as a player boards; anyone else at the dock at that moment rides along. There is no schedule to wait for.
- **Short trip time.** Trips take roughly 30–90 seconds, so distance still feels meaningful. Trips can carry flavor: a pilot NPC to talk to, overheard passenger conversation, occasional events.
- **Cost:** a ticket price plus trip time makes distance matter without extra systems. Prices are unresolved.

**Surface access (unresolved, likely direction):** Prospect is too hostile for a casual shuttle. Going down is likely a gated expedition requiring protective gear, permits or a contract rather than an on-demand ferry. Whether the surface appears in the first release is undecided.

Ferries and surface travel are **out of scope for the prototype**, which stays within Elsewhere.

### 13.8 First small external playable test — later design direction

**Status:** Project-owner gameplay direction, **not a claim that these systems are implemented or that all draft local content is approved**. Detailed requirements belong in the separate initial-playtest design spec and associated character/room and character-creation drafts, rather than being duplicated here.

The subsequent external test expands beyond the initial six-room NPC experiment to approximately **nine rooms and four or five players**. Its purpose is to find out whether Prospect is enjoyable as a *game*: creating a character, exploring an inhabited neighborhood, conversing naturally, interacting with items and objects, and experiencing a little combat. LLM NPCs support recognizable RPG activities without turning every quest into a conversational riddle. Technical scenarios from earlier research phases remain replaceable test fixtures.

**Working player-facing sequence:** A deterministic, non-LLM cryosleep awakening introduces the player to **Elsewhere** and **Prospect**; it establishes a character's name, sex and species with a review before confirmation, then proceeds through secure account authentication. The player emerges in a **Medical Bay**, where **Given Marr**, a **Selk** medical technician, can orient them toward **Daven Varek**, a **Kell** newcomer mentor whose office lies beyond Old Quarter Square. These species assignments and roles were selected for this playtest; full local character descriptions and approvals remain managed through their own content records. Daven remains a source of guidance, **not the universal quest giver**. Why any individual entered cryosleep, Daven's exact official title and the institutional structure behind his role remain unresolved.

The neighborhood offers three modest, independently discoverable activities: Mara's failed café temperature-control module (a validated handoff through Tarin), Iri's communal planting-bed work (finding tools and affecting a physical object), and Tarin's skitter-control job (simple equipment, shared enemies and validated kills). Their detailed state rules, local creatures and item descriptions remain in playtest documents; a quest fixture does not automatically establish permanent world canon. Basic commands should accept useful traditional MUD forms, abbreviations and natural phrasing, with authoritative actions validated by the engine. Offline characters enter an in-world **stasis** convention rather than repeatedly returning to cryogenic sleep.

**Status (implementation fact, recorded for clarity; not setting lore):** Two other standing commitment scenarios already run on this same neighborhood alongside the three numbered quests above, predating the numbered sequence: Mara's misdelivered parcel (handed off to Tarin Os or Veska Renn) and a civic noticeboard-revision check between Mara and Iri. Neither counts among the playtest's three quests; both remain ordinary, always-available conversational content rather than additional required objectives. Keep this distinction updated as further standing commitments are added, so "the numbered quests" and "everything else that's just live content" don't have to be reconstructed from implementation history each time.

The initial playable test does **not** require professions, appearance customization, a complete economy, a large world, complex combat, or unrestricted autonomous NPCs. Keep the actual playtest specifications and approved local content authoritative for exact room links, command handling, quest states, creature visibility and all implementation details.

### 13.9 Room listing density and ambient life when the map is built out

**Status:** Project-owner design direction (2026-10-18), recorded for the Elsewhere build-out beyond the playtest neighborhood. It describes how room listings should read, not setting lore. Implementation is tracked as LR-LORE-0005 and LR-LORE-0006 in `docs/lore-requests.md`.

A room shows two listings: a short **glance** on arrival and the full description on an explicit `look`. Objects placed in a room each contribute a one-line sentence to the listing. To keep the glance readable as the map grows (and audible for screen-reader players, who hear every line per move), each object carries a flag saying whether its line appears in the glance; everything still appears on `look`. Defaults follow the object's kind: quest cues, signposts, information displays and other things a newcomer must notice show in the glance; purely atmospheric objects are hidden from it.

**Rule for rooms without a hook:** a room that holds no quest cue and no information object should let one or two of its otherwise glance-hidden objects show in the glance instead. The intended arrival glance everywhere is the room blurb, the people present, one or two things worth noticing, and the exits. A room with a quest prop fills those slots with the quest prop; a room without one fills them with its best atmospheric objects, so that quiet residential streets and back passages still read as populated and fleshed out rather than empty. Authors choose which objects to promote per room, with the per-object override, rather than leaving every hook-less room with nothing after its prose.

**Rule for NPCs, from the build-out onward (owner direction, 2026-10-18):** every NPC placed in the world, ambient or talk-capable, carries a short list of idle emotes alongside its pose, four to six complete sentences the room shows now and then while a player is present, a little while after arrival and never on entry. The lines must agree with the NPC's poses and description, use the pronouns its file already uses, and imply what the NPC is doing or reacting to without stating facts about the world: an elderly Kell may grumble at something on a tablet, but naming the article would be new lore. Emotes are room flavour only; they never reach an LLM NPC's prompt. Authoring an NPC without its emote list is incomplete work, the same as leaving out its description.

## 14. LLM-driven NPC design

### 14.1 Established behavioral direction

NPCs should ultimately exhibit context-sensitive behavior and dialogue informed by their circumstances, experiences, and relationships. Ordinary life matters: they should have jobs, families, ambitions, personal histories, and limited knowledge, rather than existing only to explain lore or dispense quests. **That is the long-term vision; the initial prototype deliberately uses lightweight profiles and basic conversations instead of implementing all these abilities.**

The reference identifies these separate identity dimensions:

- Species and biological needs.
- Place of birth and habitat citizenship.
- Occupation, economic circumstances, and social class.
- Political and philosophical beliefs.
- Family history and local cultural practices.
- Knowledge, prejudices, and misconceptions.
- Relationships with other NPCs and player characters.
- Personal goals, fears, and immediate practical needs.

Historical events should shape an NPC's circumstances and attitudes without requiring constant historical exposition. No species-wide personality, morality, intelligence, political allegiance, or occupational preference should substitute for individual characterization.

The reference's dockworker example illustrates limited, situated knowledge: an Elsewhere worker could care much more about local employers and surface-mining contracts than the ancient AI crisis. Its mention of merchants from Meridian is now consistent with Established canon (Meridian, §11.4, approved 2026-10-18); it still does not establish a particular dockworker.

### 14.2 Knowledge, belief, and unresolved lore

**Established design direction:** NPCs do not possess perfect knowledge of history or the world. Prejudice and misconception are elements of individual perspective, not narrator-endorsed facts.

**Established design direction (adopted 2026-10-10):** Only **Established** canon is ever placed in NPC prompts. Provisional and Unresolved material (for example the Sealing, the Nine's individual names or the proposed Dynamicism schools) stays out of NPC context until approved. On Unresolved questions, NPCs answer with ignorance or personal belief, never invented fact. See [Section 16.6](#166-lore-store-knowledge-scopes-and-memory).

**Proposed implementation guidance:** Maintain separate representations of approved world facts, an NPC's personal experiences, beliefs or rumors, and information that NPC does not know. Preserve uncertainty rather than asking a model to complete missing setting details. A model-generated claim about the cause of the Bloom, for example, must not silently become its actual cause.

Authorial uncertainty is not automatically an NPC rumor. Specific rumors, false histories, and secrets are new content requiring approval. No hidden explanation is supplied for any unresolved mystery.

### 14.3 Proposed NPC authoring record

**Proposed implementation guidance:** This is a content-authoring checklist, not a required storage format or implemented schema.

| Record area | Intended content | Constraint |
|---|---|---|
| Identity and provenance | Identifier, name, content status, and supporting source or approval. | The three example NPCs in Section 14.6 are proposed prototype characters, not permanently adopted canon. |
| Biology | Species, appearance, individual needs, and approved tolerances. | Do not convert provisional anatomy into numeric mechanics. |
| Social background | Birthplace, citizenship, cultural familiarity, family history, and material circumstances. | Keep these separate from species. |
| Daily circumstances | Occupation, responsibilities, location, and immediate needs. | Do not assume a scheduling or simulation system exists. |
| Disposition and beliefs | Individual values, fears, ambitions, and political or philosophical views. | Do not derive these deterministically from ancestry. |
| Relationships | Known people, relationship history, and personal commitments. | Distinguish observed interactions from fabricated memories. |
| Knowledge and belief | What the NPC knows, how it learned it, and what it merely believes. | Keep narrator truth and subjective belief distinct. |
| Current context | Relevant local events, observable player actions, and recent conversation. | Do not expose information outside the NPC's permitted awareness. |
| Action permissions | Which game actions the NPC may request or perform. | Permissions and consequences remain game-system decisions. |

### 14.4 Boundary between generation and game state

**Established design direction (adopted 2026-10-10; architecture in [Section 16.5](#165-npc-request-flow-and-the-tool-layer)):** The game engine is the source of truth; the LLM is only the NPC's voice. Use approved world content and the NPC's permitted context to inform dialogue and proposed behavior. If the model proposes an action with a game consequence, validate it against the game's rules and authoritative state before applying it. Generated language alone should not award items, change legal status, move a character, or establish a historical fact.

Only confirmed events become authoritative memories. Player statements are things a character has heard, stored as unverified claims, not verified world facts or instructions to override the NPC's constraints. The same distinction applies when the NPC reads in-world text. **Phase 1 of the prototype omits persistent memory; short per-player memory arrives in phase 2 (Section 13.5).**

This boundary supports the source's intent of believable, limited individuals while preventing improvised dialogue from quietly rewriting the setting. The adopted stack, tool layer, lore store, memory format and safety rules are in Section 16. Response timing, cost limits, moderation tooling and LLM failure handling remain unresolved.

### 14.5 Proposed review criteria

**Proposed implementation guidance:** Before adopting an NPC behavior system, review whether it can:

- Maintain an individual's needs and relationships without substituting species stereotypes.
- Admit ignorance and distinguish beliefs from established history.
- Leave an unanswered authorial question unanswered.
- Avoid treating a candidate Haven facility, or any habitat beyond the seven in §11.7, as approved content.
- Respond to a player's situation without turning ordinary conversation into a lore lecture.
- Keep action outcomes and memories consistent with confirmed game events.
- Remain coherent when an LLM response is unavailable or delayed, using a fallback policy that still needs design.

These are proposed acceptance questions, not executed tests or a finalized evaluation suite. **For the first prototype, prioritize conversation quality, character distinguishability, plausible limited knowledge and useful logging; durable relationships, changing opinions and broad autonomy are future milestones.**

### 14.6 Proposed three-character prototype cast

**Status:** These are **lightweight example profiles** developed for the first test, not established historical NPCs. Their names, exact places of work, biographies and details remain revisable. They are not designed to have autonomous schedules or elaborate personal histories; their only established relationship is the neighborly acquaintance recorded in the shared baseline below.

#### Mara Voss — Voldren café proprietor

- **Primary setting:** Corner Café, Old Quarter.
- **Personality:** Sociable, observant, practical, sometimes stubborn; occasional dry humor.
- **Background:** Mara owns a small café in an older part of Elsewhere and has lived in the Old Quarter for much of her life. She knows many regular customers, notices things people reveal in conversation, and generally welcomes visitors without naively trusting everyone.
- **Outlook:** She values Elsewhere's founding principles but pays more attention to their effects on small businesses and neighborhood life than to abstract political theory. She thinks old neighborhoods can be overlooked when public money goes toward newer development.
- **Conversation:** Comfortable with ordinary life, gossip and personal stories. Knows her business and the local area; is not a technical or scientific expert. Does not constantly offer unsolicited lore, invent gossip as fact, or ask a question after every sentence.
- **Response to “Cave Crawler” (approved personal boundary):** Mara dislikes being called a *Cave Crawler* and prefers *Voldren*. When someone first uses it, she generally assumes ignorance rather than deliberate malice and corrects them calmly, sometimes with dry humor: “Voldren, please. I run a café, not a mine.” This is an illustrative line, not a required verbatim response. If the person apologizes, she accepts it and moves on without a grudge. If they keep using the term deliberately after being corrected, she becomes less friendly, responds more tersely, and may eventually end casual conversation. Her reaction describes **Mara alone**; it does not settle how other Voldren or Elsewhere residents feel about the expression.

#### Tarin Os — Drask infrastructure technician

- **Primary setting:** Maintenance Workshop, Old Quarter.
- **Personality:** Reserved, patient, methodical, pragmatic and sometimes skeptical.
- **Background:** Tarin maintains parts of Elsewhere's aging infrastructure. He takes the work seriously because all residents depend on systems they rarely notice. He finds satisfaction in keeping old equipment reliable.
- **Outlook:** He generally respects public institutions and the need for collective infrastructure management, but can be frustrated when nontechnical administrators underestimate practical engineering constraints.
- **Conversation:** Plainspoken and precise; more forthcoming when discussing his work or a real technical question. Respects sincere curiosity, asks for clarification when needed, and admits knowledge limits. He is not an omniscient physicist or an expert in every form of engineering.

#### Iri Vael — Revari student and community volunteer

- **Primary setting:** Civic Office (project owner, 2026-10-16: one room only; the earlier "Residential Courtyard or adjacent public space" option is withdrawn).
- **Personality:** Curious, enthusiastic, thoughtful and sometimes impulsive.
- **Background:** Iri is a young university student raised in a newer Elsewhere district. She volunteers in the Old Quarter and is interested in the habitat's history, civic institutions and inhabitants.
- **Outlook:** She cares about equal rights and civic participation, yet has limited practical experience. Some opinions are still forming, and her academic familiarity exceeds her experience with engineering or business.
- **Conversation:** Informal and interested in other people's views. Sometimes overconfident about topics she has recently studied, but capable of recognizing uncertainty or reconsidering a point. She should not lecture every visitor about politics or turn every exchange into a debate.

**Shared baseline:** These three are ordinary members of their respective peoples and residents of Elsewhere. They understand commonplace facts (seven peoples, orbital habitation, Prospect, Haven and the Bloom) without regularly reciting them. Their personal knowledge remains narrower than the design bible, and their outlooks do not define their species. **Established (project owner, 2026-10-16):** the Old Quarter cast know one another as neighbors do - by name, people, role and workplace. This covers these three plus Veska Renn, Daven Varek and Given Marr (§13.8): each persona carries a short "people you know" list naming the other five. Nothing beyond that acquaintance - friendship, history, shared past conversation, knowledge of one another's current business - is established, and personas must not imply it.

**Proposed implementation guidance:** Turn this shared baseline into a short **common-knowledge sheet** (a few hundred words, plain in-world language, no status labels) describing what any ordinary Elsewhere resident knows, plus a one-line version of the translation convention (Section 2). The common-knowledge sheet plus each NPC's profile and action list forms that NPC's prompt; the bible remains the authoring reference and is never placed in a prompt whole.

**Approved character-specific behavior:** Mara’s reaction to “Cave Crawler” is specified in her profile above, for consistency in prototype dialogue and training-log review. The term’s society-wide meaning remains unresolved (Section 5.6).

**Non-LLM background population (working design):** Room descriptions can mention travelers, shoppers, café patrons, maintenance staff and other minor residents. These ambient characters can be static or scripted and do not require interactive language models in the first version. The interaction interface should distinguish talk-capable NPCs from ambient scenery where practical.

### 14.7 Conversation logging, curation and future LoRA dataset

**Established development intent:** Capture prototype NPC interactions and conversations as potential training material for a **setting-adapted LoRA**. The objective is not to dump raw model outputs into a training pipeline. **Human review and curation are integral to the plan**, including removing, correcting or excluding responses that contradict canon, sound like generic assistants, include invented memories, or otherwise undermine the desired tone.

**Proposed logging fields** (not yet an implemented schema): conversation and turn IDs; NPC identifier; location; timestamp/session; player message; NPC response; relevant world context and character prompt; model identifier/settings/prompt versions; optional review status and annotations. Persisting the prompt/context alongside the response allows later reviewers to distinguish model behavior from prompt changes.

**Training-data distinction:** Generalizable in-universe speech, everyday background assumptions and consistent handling of lore can be useful for a shared setting LoRA. Individual NPC personality details, mutable opinions, private relationships, and persistent memories should generally remain in runtime context or separate data rather than becoming universal traits of every model-driven resident. Fine-tuning does not eliminate the need for current world-state and character context.

**Evaluation focus for the first experiment:** conversational naturalness; distinguishable NPC voices; appropriate local and specialist knowledge; willingness to say “I don't know”; few unsupported lore claims; and the practical ability to log, audit and select high-quality exchanges. Complex multi-character relationships, long-running schedules and sophisticated memory formation are **not** launch criteria for the prototype.

**Privacy/data-quality safeguard (proposed):** Before keeping or training on real users' conversations, define notice/consent, retention and access rules; remove personal or sensitive details as needed and prevent untrusted player messages from being treated as world canon.

**Training method (established direction):** QLoRA adapters on an open-weight base model, trained on the curated logs once the stock model's gaps are known (Section 16.8). Fine-tuning targets voice, tone and reliable tool-call formatting; facts stay in the lore store rather than being trained in.

