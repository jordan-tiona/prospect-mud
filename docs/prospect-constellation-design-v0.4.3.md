# Prospect and the Constellation

**Living Project Design Bible**

| Field | Value |
|---|---|
| Document version | 0.4.3 |
| Last organized | 2026-10-15 |
| Development stage | Early development |
| Project | Text-based multiplayer science-fiction MUD |
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

## Contents

- [1. Core premise and creative principles](#1-core-premise-and-creative-principles)
- [2. Names and terminology](#2-names-and-terminology)
- [3. Relative chronology](#3-relative-chronology)
- [4. Home system and historical foundations](#4-home-system-and-historical-foundations)
- [5. The seven peoples](#5-the-seven-peoples)
- [6. The Nine generation ships](#6-the-nine-generation-ships)
- [7. Prospect](#7-prospect)
- [8. The founding of Haven](#8-the-founding-of-haven)
- [9. Haven: architecture and historical geography](#9-haven-architecture-and-historical-geography)
- [10. The Bloom and the ruined city](#10-the-bloom-and-the-ruined-city)
- [11. The Constellation and its habitats](#11-the-constellation-and-its-habitats)
- [12. Factions, institutions, and political conflict](#12-factions-institutions-and-political-conflict)
- [13. Gameplay concepts and prototype scope](#13-gameplay-concepts-and-prototype-scope)
- [14. LLM-driven NPC design](#14-llm-driven-npc-design)
- [15. Venn–Saye dynamics, Fieldworks, and Dynamicism](#15-vennsaye-dynamics-fieldworks-and-dynamicism)
- [16. Technology and implementation boundaries](#16-technology-and-implementation-boundaries)
- [17. Unresolved decisions and canon safeguards](#17-unresolved-decisions-and-canon-safeguards)
- [18. Maintaining the living bible](#18-maintaining-the-living-bible)
- [19. Canonical setting synopsis](#19-canonical-setting-synopsis)

---

## 1. Core premise and creative principles

**Status:** Established canon for the premise; established design direction for the principles.

The game takes place in a distant star system dominated by Prospect, an ecologically rich but extremely hostile alien planet. Its inhabitants live primarily in a collection of independent orbital habitats known collectively as **the Constellation**.

Each habitat is a self-contained society with its own culture, government, economy, history, and political interests. Although economically interconnected, the habitats are not necessarily united under a single government.

Prospect itself serves as a dangerous destination for exploration, resource extraction, salvage, scientific expeditions, and combat. The planet contains numerous alien biomes and a diverse indigenous biosphere, much of which is extremely hazardous to the colonists.

Civilization originally existed on Prospect's surface, concentrated within the enormous protected city of **Haven**. Over centuries, independent orbital habitats developed around the planet. Approximately 150 years before the game's present, a catastrophic biological contamination event known as **the Bloom** destroyed Haven's ability to sustain its population.

The Constellation survived and declined to rebuild the city. Today, the abandoned metropolis stands as a vast, vertically stratified ruin, gradually reclaimed by Prospect's indigenous life.

The setting emphasizes historical continuity, competing political philosophies, social inequalities, cultural diversity, technological dependence, and the consequences of civilizations attempting to control environments they do not fully understand. Its science-fantasy element is **Venn–Saye dynamics**, an exotic field whose controlled manipulation supports both everyday technology and genetically specialized practitioners capable of effects resembling magic. The field predates the Nine; its transformative applications emerged after studying Prospect's native biology.

### Design principles

- **History should explain the present.** Place names, societies, architecture, prejudices, and institutions should have recognizable historical origins.
- **Biological species and culture are separate.** No species has a single personality, morality, profession, or political ideology.
- **The habitats are genuinely independent societies.** They are not merely themed neighborhoods belonging to one planetary government.
- **Speculative science has consistent limits.** The setting permits sophisticated biotechnology, interstellar generation ships, environmental engineering, extensive automation, and an exotic field with magic-like applications. Its effects should follow stable in-world principles rather than serving as unrestricted solutions to any problem.
- **Field technology is not Dynamicism.** Anyone with training can operate purpose-built Fieldworks devices; advanced, flexible manipulation requires a school's genetic specialization and a Dynamicist's catalyst.
- **Prospect is alien, not evil.** The planet's inhabitants and ecology are dangerous because they evolved independently of the colonists, not because the world is intentionally hostile.
- **Ordinary life matters.** NPCs should have jobs, families, ambitions, personal histories, and limited knowledge, not exist merely to explain lore or dispense quests.
- **Prototype only what must be tested.** The first version primarily tests LLM-driven NPC dialogue and creation of a curated training corpus; economy, combat, complex agent autonomy and full-world simulation can follow later.
- **Build a game, not a sequence of conversational puzzles.** The intended finished product is a science-fiction multiplayer RPG/MUD with exploration, combat, progression, commerce and social play. Natural, grounded NPC dialogue should enrich those activities rather than displace them. Narrow, puzzle-like scenarios used to test LLM and engine behavior are disposable technical fixtures, not a template for the main gameplay loop.


---

## 2. Names and terminology

**Status:** The named habitats, city, planet and fields retain their earlier statuses. The seven species names below are **adopted working names**, deliberately subject to revision. Species names are distinct from historical or colloquial occupational labels.

| Name | Meaning | Status |
|---|---|---|
| Prospect | The alien planet | Established |
| Haven | The original planetary city, now ruined | Established |
| The Constellation | Collection of independent orbital habitats | Established |
| Elsewhere | First independent orbital habitat and prototype setting | Established |
| The Nine | Nine original generation ships and their founding settlements | Established concept; individual names unresolved |
| The Bloom | Biological catastrophe that destroyed Haven | Established |
| The Sealing | Escalating automated quarantine response during the Bloom | Proposed historical term |
| Freehold | Industrial habitat associated with labor emancipation | Proposed habitat |
| Meridian | Commercial and financial habitat | Proposed habitat |
| **Kethari** | Ancestral A; primarily canine, furred, digitigrade | Selected working species name |
| **Sylari** | Ancestral B; scaled, lizard-faced, plantigrade | Selected working species name |
| **Aevyrin** | Ancestral C; avian/feathered | Selected working species name |
| **Naevari** | Long-established hybrid-descended people | Selected working species name |
| **Otheryn** | Engineered for orbital and low-gravity work | Selected working species name |
| **Voldren** | Engineered for subterranean work | Selected working species name |
| **Neshyr** | Engineered for aquatic work; air-breathing | Selected working species name |
| **Void Walkers** | Historical or colloquial designation for the Otheryn | Adopted working label; social connotations unsettled |
| **Cave Crawlers** | Historical or colloquial designation for the Voldren | Adopted working label; may carry disparaging connotations |
| **Sea Walkers** | Historical or colloquial designation for the Neshyr | Adopted working label; social connotations unsettled |
| Venn–Saye field | Exotic physical phenomenon discovered in the original home system by two Kethari researchers | Established |
| Venn–Saye dynamics | Scientific discipline studying field interactions | Established |
| Fieldworks | General skill of using purpose-built field technologies without genetic alteration | Established |
| Dynamicism | Catalyst-mediated advanced field manipulation by genetically specialized people | Established |
| Dynamicist / Dyno | Formal and colloquial terms for an advanced practitioner | Established |
| Catalyst | School-neutral instrument used specifically by a Dynamicist | Established |
| Sera Venn / Talin Saye | Suggested given names of the two Kethari discoverers | Provisional |
| Kinetics, thermodynamics, electrodynamics, biomodulation, photonics | Suggested Dynamicism schools | Provisional |

**Pronunciations:** *Aevyrin* and *Naevari* use **ae** pronounced like the **a** in English *after* (short *a*, not *ay*). *Otheryn* sounds like the English phrase **“other in.”** The pronunciation of other coined names is not yet standardized.

**Translation convention (established working direction):** The game's English dialogue and text are generally understood as translations of an in-universe common language. Meaningful geographic, civic, institutional and descriptive names (for example, *Prospect*, *Haven*, *Elsewhere*, *Old Quarter*, *the Bloom*, *Void Walkers*) are ordinarily translated into English. Personal names and the seven peoples' self-designations are instead represented by approximate transliteration, preserving their names' sounds, even when their original-language meanings are unknown. The common language's actual name, ancestry, dialects and history are **unresolved**; *Standard* has only been proposed as a placeholder. The three engineered peoples' historical labels are **not** their formal ethnonyms and should not be treated as uniformly respectful or uniformly offensive without further decisions.

The Nine's ship and original-settlement names, the exact personal names and histories of the Venn–Saye discoverers, and many local institutions remain unchosen. See [Section 15](#15-vennsaye-dynamics-fieldworks-and-dynamicism) for field terminology.

---

## 3. Relative chronology

**Status:** Established event order with approximate planning intervals. Year 0 is a relative colonization reference, not an approved in-world calendar. Neither the current year nor a total duration since landfall is fixed.

Only certain chronological relationships are established. Dates marked approximate are planning references rather than finalized canon. **The field's discovery predates the Nine, but its order relative to the AI crisis or the Three Commissions is not yet fixed.** The breakthrough on Prospect postdates landfall, but its exact place in the settlement/unification timeline is unresolved.

| Period | Event |
|---|---|
| Ancient home-system history | Three ancestral peoples develop their civilizations; hybrid-descended people emerge at an undetermined time |
| Centuries before departure | Advanced AI crisis creates enduring distrust of autonomous machine intelligence |
| Following the AI crisis | Genetic Revolution and near-contemporary Three Commissions create the engineered peoples |
| Before departure | Engineered peoples become economically indispensable and legally classified as property; emancipation movements emerge |
| Before departure (relative date unresolved) | Two Kethari researchers discover the Venn–Saye field; its applications are initially limited |
| Departure | The nine generation ships leave the home system |
| Centuries-long voyage | Shipboard cultures and institutions diverge; emancipation advances on some vessels |
| Year 0 of colonization | The Nine arrive at Prospect and establish separate ship-derived settlements |
| After landfall (exact era unresolved) | Study of Prospect's indigenous biology leads to breakthroughs in field manipulation, eventually enabling Fieldworks applications and genetically specialized Dynamicists |
| First ~50 years | Protected transport connections develop between the settlements |
| Subsequent generations | Trade, migration, cultural integration, and political unification movements develop |
| Date undecided | Haven is established as a unified city and common environmental protection network is developed |
| Following centuries | Haven expands horizontally, then vertically after reaching its practical protected footprint |
| Approximately 400 years before present (working age) | Elsewhere is founded as the first independent orbital habitat; over centuries its cylinder expands lengthwise away from the docking end |
| Following centuries | Additional habitats emerge, developing into the Constellation; Elsewhere becomes a mature, economically diverse civic republic |
| ~150 years before present | The Bloom and ensuing containment catastrophe cause the fall of Haven |
| Present | The Constellation survives; Prospect remains a dangerous resource and exploration destination |


---

## 4. Home system and historical foundations

**Status:** Mixed status. Shared home-system origins, the ancient AI crisis and its lasting restrictions, the Three Commissions, exploitation, and pre-departure emancipation movements are established. Home-system geography, the AI disaster mechanism, cross-ancestral reproduction, and commissioner-to-engineered-people assignments remain unresolved. The listed disaster explanations are alternatives, not concurrent events.

### 4.1 Pre-interstellar civilization

The seven peoples originated within a single star system, rather than from an established interstellar civilization.

Their ancestors had achieved extensive industrialization, advanced spaceflight, sophisticated biotechnology, orbital settlement, and large-scale resource extraction before developing the generation ships necessary to reach another star.

The original home system may have contained two inhabited worlds, perhaps with additional inhabited moons or orbital settlements. The precise geography and evolutionary history are not established.

Three ancestral species existed before the development of true genetic engineering. A fourth people arose from mixed ancestral lineage, although the biological mechanism enabling fertile interspecies offspring remains undecided.

The civilization was technologically advanced but not capable of routine interstellar transportation. The voyage to Prospect therefore required enormous generation ships designed to sustain populations over centuries.

**Later-established scientific history:** Before the Nine departed, two researchers belonging to the Kethari discovered the field subsequently named for them: the Venn–Saye field. It was known experimentally in the home system, though practical control remained limited. After landfall, observation of field interactions in Prospect's native biology enabled much more sophisticated manipulation. The chronology relative to the ancient AI crisis and genetic commissions remains open; see [Section 15](#15-vennsaye-dynamics-fieldworks-and-dynamicism).

### 4.2 The ancient artificial intelligence crisis

Centuries before the departure of the Nine, advanced artificial intelligence precipitated a major crisis in the home system.

The exact nature of the disaster remains unknown. Possibilities include an autonomous-machine conflict, catastrophic AI mismanagement, or a political disaster involving excessive delegation of authority to machine intelligences.

Whatever happened, its effects were sufficiently traumatic to create a lasting cultural and institutional distrust of advanced artificial intelligence.

This distrust was not an outright rejection of computers or automation.

Sophisticated software, robotics, expert systems, and automated industrial processes remained widespread. However, general-purpose autonomous machine intelligences and systems capable of independent, open-ended agency became heavily restricted.

This technological and cultural constraint contributed to the subsequent reliance on engineered biological workers for dangerous, complicated tasks that could not easily be entrusted to conventional automation.

### 4.3 The Genetic Revolution and the Three Commissions

Following breakthroughs in sophisticated genetic manipulation, each of the three ancestral civilizations independently commissioned the creation of a new sapient biological people.

The three projects occurred within approximately the same historical period.

Each commission was motivated by a major industrial challenge responsible for large numbers of deaths among ancestral workers. Rather than continuing to expose their populations to extreme hazards, the ancestral civilizations designed new peoples capable of enduring those conditions.

The three resulting peoples were:

**Otheryn (historically “Void Walkers”):** Engineered for orbital construction, low-gravity work, spacecraft maintenance, and hazardous extraterrestrial industry.

**Voldren (historically “Cave Crawlers”):** Engineered for mining, deep excavation, underground construction, and industrial environments involving confined spaces, high temperatures, and atmospheric hazards.

**Neshyr (historically “Sea Walkers”):** Engineered for deep-water resource extraction, underwater construction, salvage, and other dangerous aquatic operations.

The precise relationship between each engineered people and its commissioning ancestral species has not been finalized.

The engineered peoples are genuinely sapient, self-aware biological populations capable of reproduction, cultural development, and independent thought.

### 4.4 From specialized labor to property

Initially, the Three Commissions were justified as life-saving technological achievements.

Their success sharply reduced the need for ancestral populations to perform certain hazardous occupations. As entire industries reorganized around engineered labor, their creators became economically dependent on the new peoples.

Over generations, this dependence contributed to a profoundly exploitative social order.

The ancestral civilizations increasingly regarded engineered populations as resources, inheritable assets, or livestock rather than independent persons.

By the departure of the Nine, engineered peoples were still legally treated as property under the prevailing institutions of the home system.

They could be subjected to restrictions on occupation, movement, autonomy, property ownership, and reproductive freedom. The exact legal arrangements differed across jurisdictions.

This treatment was not universally accepted.

Emancipation movements and political reform factions had already emerged in the home system. Some ancestral and hybrid citizens advocated legal equality, while engineered peoples organized resistance and sought recognition of their personhood.

The hybrid-descended people occupied an intermediate social position. Though generally recognized as persons, they experienced some prejudice from the three ancestral peoples because of their mixed ancestry.

Prejudice varied among individuals and societies. The hierarchy was social, political, and legal, not evidence of any genuine difference in moral worth.


---

## 5. The seven peoples

**Status:** All seven **working species names** have now been selected, but the project owner may revise them. Their ancestral/hybrid/engineered classifications and the broad established biology below are retained. Some fine anatomical details remain proposals, not completed specifications. These are sapient peoples, not biologically determined personality types or professional classes.

The seven principal peoples comprise three ancestral civilizations, one established hybrid-descended people, and three subsequently engineered, self-reproducing peoples. Their species names are represented as transliterations of in-world self-designations, not English labels based on physical appearance.

### 5.1 Kethari — Ancestral A

The **Kethari** are furred, predominantly **canine-looking**, digitigrade humanoids, with functional hands, expressive/mobile ears and individual variation in coats and proportions. Tail length, muzzle proportions and specific physiological traits still need decisions. Their visual character is more canine than the previously considered mustelid alternative, although they are not literal Earth dogs or wolves.

**Scientific heritage (established):** The two original discoverers of the Venn–Saye field were Kethari. Their scientific and educational institutions developed an especially long tradition of Venn–Saye dynamics, preserved across the voyage and subsequent settlement. Many Kethari communities regard this as an important cultural achievement. A modest **proposed** player species bonus to relevant starting proficiency or learning would express inherited educational and cultural traditions, **not innate biological superiority**; exact mechanics are unresolved.

### 5.2 Sylari — Ancestral B

The **Sylari** are scaled, plantigrade humanoids with a distinctly **lizardlike face and elongated snout**, rather than a flat humanoid face with cosmetic scales. Distinctive cranial features, scale patterns and a substantial tail are likely, though their exact forms are unfinished. They have a fully functional humanoid body plan and hands.

Their reptilian appearance should not automatically entail Earth-reptile physiology or a need for special heated environments; warm-blooded or otherwise self-regulating metabolism is a **suggested solution**, not a finalized biological specification. They are anatomically distinct from the Kethari.

### 5.3 Aevyrin — Ancestral C

The **Aevyrin** are avian-influenced, feathered or featherlike humanoids, with distinctive balance, skeletal proportions, expressive plumage or crests and functional hands. **Ae** is pronounced with the short *a* sound in *after*. Whether they have a pronounced beak, intermediate birdlike facial anatomy, and any residual flight-related structures remains **unresolved**. Flightlessness remains a plausible direction, not established fact.

### 5.4 Naevari — Hybrid-descended

The **Naevari** are a long-established, self-reproducing people with ancestry involving the Kethari, Sylari and Aevyrin. Their general body plan most closely resembles the furred, digitigrade Kethari, but individuals show varying inherited traits associated with the scaled Sylari and feathered Aevyrin. Examples such as localized scales, feathered crests, and differing ear or tail shapes are **visual proposals**, not rigid traits possessed by every Naevari.

They should look like a recognizable people with broad inherited variation, **not arbitrary assemblages of body parts**. Their name is their own identity, not a literal translation of *hybrid*. **Ae** is pronounced with the short *a* in *after*. Their historical reproductive compatibility with the three ancestral peoples still requires explanation, potentially involving ancient reproductive biotechnology; it is not solved by the name.

### 5.5 Otheryn — Engineered; “Void Walkers”

The **Otheryn** (pronounced like **“other in”**) were engineered for hazardous orbital construction, spacecraft maintenance, and other reduced-gravity or extraterrestrial industrial work. Their colloquial or historic occupational designation is **Void Walkers**.

**Provisional anatomical detail within the established body plan:**
- Tall, slender or lanky humanoid proportions, with long limbs and dexterous hands.
- Smooth skin with little or no hair.
- Adaptations for prolonged low-gravity activity and enhanced radiation resilience.
- Possible discomfort or functional disadvantage in high gravity, still to be quantified.

Radiation tolerance does **not** grant survival in vacuum; protective suits and life support remain necessary. Otheryn today are free to pursue any profession in societies recognizing their rights; their engineering purpose must not be presented as their inevitable vocation.

### 5.6 Voldren — Engineered; “Cave Crawlers”

The **Voldren** were engineered for mining, excavation and other dangerous work underground. **Cave Crawlers** is an occupational or colloquial designation, potentially harsher or more derogatory in some circumstances than the other two engineered peoples' labels. Precisely who uses it neutrally, disparagingly or as a reclaimed term is **unresolved**.

**Provisional anatomical detail within the established body plan:**
- Short, broad, exceptionally powerful and muscular builds.
- Thick, resilient, possibly leathery and textured skin.
- Heavy-duty joints and limbs adapted to confined industrial environments.
- Small or recessed external ears and protected auditory structures that avoid snagging in tunnels.
- Resistance to particular workplace hazards such as heat, contaminants and abrasion, not universal invulnerability.

Their stature follows functional subterranean engineering rather than an inherited fantasy-dwarf identity. *Dwarfs* was an out-of-world early placeholder, **superseded** by the name Voldren. Modern Voldren need not be miners.

### 5.7 Neshyr — Engineered; “Sea Walkers”

The **Neshyr** were engineered for hazardous underwater construction, deep-water extraction, salvage and related work. Their historical or colloquial designation is **Sea Walkers**. The earlier *Aquarians* label was a working placeholder and is **superseded**.

**Provisional anatomical detail within the established body plan:**
- Sharklike or shark-inspired humanoid appearance, with smooth streamlined skin.
- Powerful swimming musculature and potentially webbed extremities or a swimming tail.
- Pressure adaptations and exceptional breath-holding or oxygen storage.
- Effective terrestrial locomotion and ordinary participation in dry, shared living environments.

**Settled design constraint:** Neshyr are **air-breathing** and do **not** need permanently submerged accommodations. They could live aboard the Nine across generations without specially flooded ship compartments. Their aquatic adaptations are not immunity to Prospect's alien ocean hazards. They are not restricted to aquatic professions.

### 5.8 Shared species-design and naming boundaries

All seven peoples must be capable of broadly shared habitation and ordinary community life. Species may affect appearance, anatomy, environmental tolerance or modest gameplay capabilities, but must not determine intelligence, morality, personality, politics, class, or profession. Citizenship, upbringing, culture, economic position and personal experience are separate character dimensions.

The engineered peoples' formal names (**Otheryn**, **Voldren**, **Neshyr**) and their descriptive historical labels (**Void Walkers**, **Cave Crawlers**, **Sea Walkers**) can coexist. Historical exploitation makes context and speaker important; the setting has **not** settled their uniform social meaning. The naming set as a whole is accepted **for development**, but remains revisable.

### 5.9 Provisional personal-name guidance

**Status:** Creative brainstorming guidance, **not established linguistic or cultural canon**. These are loose possibilities for future character names, not exclusive rules for a species or a requirement to rename existing characters.

| People | Possible naming texture, for exploration |
|---|---|
| Kethari | Softer or more flowing combinations of sounds. |
| Sylari | Sharper consonants and sometimes shorter, more clipped forms. |
| Aevyrin | More melodic combinations and open vowels. |
| Naevari | Names that may sound relatively familiar to English-speaking players. |
| Otheryn | Sometimes shorter, more economical forms. |
| Voldren | Stronger-sounding names; translated descriptive surnames, such as *Stonebreaker*, are an option. |
| Neshyr | Smooth, flowing or sibilant combinations. |

A resident's language, family, personal choices, ancestry and upbringing can matter more than any such tendency. Cosmopolitan Elsewhere should have substantial overlap and borrowing between traditions. There is **no settled language family, etymology, phonotactics or species-wide naming rule**. Examples are authoring aids only; neither the tendencies nor *Stonebreaker* establish a particular family or history.

---

## 6. The Nine generation ships

**Status:** Nine ships, the centuries-long voyage, shipboard divergence, unequal engineered status at departure, and separate ship-derived settlements are established. Sponsors, expedition motives, detailed demographics, individual ship histories, landing distances, and destination circumstances remain unresolved or provisional as qualified below.

### 6.1 The expedition

The nine generation ships departed their home star system for Prospect, or for the star system containing Prospect, on a voyage lasting multiple centuries.

The exact motive for the expedition has not been determined. It may have represented planned colonization, expansion, an attempt to escape problems at home, or some combination.

The vessels were commissioned or controlled principally by institutions belonging to the four non-engineered peoples.

They were not necessarily constructed under one unified political authority.

Different governments, political movements, and economic organizations may have sponsored individual ships.

### 6.2 Population composition

The distinction between seven peoples and nine ships is intentional.

A ship might have had a predominantly ancestral or hybrid-descended population, reflecting its sponsors, founding institutions, and life-support design.

Engineered populations were distributed throughout the fleet as essential labor forces rather than possessing equal ownership or authority over their own vessels.

The nine ships were not necessarily perfectly segregated by species. However, there should be historically credible reasons for their population distributions, rather than arbitrary demographic ratios.

The engineered peoples were transported as families and reproducing populations because the ships needed their labor across many generations and the future colonies were expected to require their capabilities.

### 6.3 Diverging shipboard societies

Each generation ship was effectively a small, isolated civilization.

Across centuries of travel, political institutions, language, culture, and attitudes toward engineered peoples developed independently.

Some ships carried reformist and emancipation movements whose influence gradually expanded.

On certain ships, engineered populations achieved equality or meaningful civil rights. Others retained oppressive inherited arrangements. Still others developed compromises or experienced political upheavals.

The legal and cultural differences between ships could become very pronounced.

This variation would later be inherited by Prospect's first nine settlements.

### 6.4 Arrival at Prospect

The colonists arrived to find Prospect considerably less hospitable than a conventional settled world.

Its environment was extremely dangerous, but the planet possessed the resources necessary to sustain permanent civilization if the settlers could construct adequate protection.

The generation ships were not suitable as permanent homes indefinitely. They were aging, resource-constrained, and intended for transit rather than eternal operation.

The colonists had no practical alternative to establishing settlements on the planet.

Each ship landed separately, potentially several kilometers from the others, and became the nucleus of a distinct settlement.


---

## 7. Prospect

**Status:** A rich, dangerous indigenous biosphere, dependence on environmental protection, and the planet's continuing economic role are established. Specific biomes, organisms, planetary measurements, and regional hazards are unresolved. Surface activities are world and gameplay foundations; they do not establish implemented professions, quests, contracts, or legal systems.

### 7.1 Planetary environment

Prospect is a richly biodiverse alien world with multiple distinct ecological regions.

It is not a barren wasteland, nor a planet inhabited only by primitive microorganisms.

Its biosphere includes complex organisms, predators, and extensive ecological relationships. Some habitats may resemble recognizable terrestrial categories such as forests, wetlands, oceans, deserts, or highlands, but their biology should remain distinctly alien.

The exact biomes, atmospheric composition, climate, gravity, geographical layout, and indigenous species are not yet specified.

Much of the indigenous life is dangerous to the colonists because of predation, environmental toxicity, biological incompatibility, parasitism, or other evolutionary adaptations.

### 7.2 Habitability

Prospect is not completely impossible to visit, but it is unsuitable for ordinary long-term habitation without extensive environmental protection.

Explorers, industrial workers, and salvage teams can operate on its surface using specialized equipment and temporary facilities.

Unprotected exposure may be dangerous for different reasons in different regions.

The planet's conditions also need not be uniformly hostile. Some areas could be comparatively manageable, while others are exceptionally lethal.

No single engineered people should be universally immune to Prospect's hazards.

### 7.3 Contemporary economic role

After the destruction of Haven, Prospect remains economically indispensable to the Constellation.

Surface activity includes:

- Mineral extraction and industrial resource gathering.
- Scientific research and biological sampling.
- Exploration of unexplored regions.
- Salvage of pre-Bloom technology.
- Expeditions into Haven's ruins.
- Commercial hunting or contracted removal of dangerous organisms.
- Illegal salvage, smuggling, and other unregulated activities, where appropriate.

These activities provide an important foundation for quests, character professions, and regional economies. **Additional scientific context:** Certain native organisms of Prospect naturally interact with the Venn–Saye field; studying these interactions led to post-landfall advances in field control. Their species, mechanisms, and ecological roles have not yet been designed. This does not establish that the Bloom involved field manipulation.


---

## 8. The founding of Haven

**Status:** Separate settlements, protected connections, eventual political union, and a common protection network are established. The first approximately fifty years is a planning interval. Sealed tunnels are a possible early transport form. Constitutional details, specific political actors, emancipation timing, and retained local autonomy remain unresolved.

### 8.1 The original nine settlements

Haven did not begin as one city.

After landfall, the passengers of each generation ship established a separate colony around their vessel's remains.

The ship hulls, surviving life-support components, structural materials, and industrial machinery provided the first settlements with shelter and essential infrastructure.

As the ships were progressively dismantled and repurposed, their former structures became the historical cores of the new colonies.

The settlements were physically isolated by the hostile planetary environment. Though communication could occur, ordinary travel and shared civic life were initially impractical.

Each settlement retained the distinctive political and cultural institutions that had evolved aboard its ship.

### 8.2 The first connections

Over approximately the first fifty years following landfall, the settlements established protected transport connections.

The earliest links may have been sealed tunnels, followed by more sophisticated transit systems.

These connections allowed regular trade, employment, migration, and social contact.

The independent settlements increasingly specialized economically. Access to neighboring colonies enabled exchange of goods, professional knowledge, technologies, and labor.

Intermarriage and interspecies relationships increased, where biologically possible, while cultural integration gradually transformed the population.

The distinctions between settlements never vanished completely.

### 8.3 Political conflict and unification

A movement eventually arose to consolidate the nine settlements under one government.

The process was inspired by practical needs and longstanding economic integration rather than simply by idealism.

Potential motivations included trade coordination, freedom of movement, common infrastructure standards, collective environmental defense, and centralized planning of major engineering projects.

Unification was not necessarily universally supported.

Each settlement possessed its own authorities, institutions, political factions, and historical grievances.

The differing legal status of engineered peoples was a particularly important source of conflict.

Some settlements may have emancipated their engineered populations, while others continued to enforce hereditary servitude. Political integration would force those incompatible legal systems into direct confrontation.

The exact constitutional settlement, timing of emancipation, and degree of retained district autonomy have not been decided.

### 8.4 The establishment of Haven

At some point, the nine settlements formally united under a common government and became known collectively as Haven.

The city's founding represents political and infrastructural unification, not the original arrival of the colonists.

The new government undertook the creation of an integrated environmental protection network covering the once-separate settlements and the developing urban landscape between them.

This system enabled Haven to grow into a genuine metropolis.


---

## 9. Haven: architecture and historical geography

**Status:** Protected horizontal growth followed by extensive vertical growth is established. Upper, Middle, and Lower Haven are descriptive categories, not official district names or a finalized map. Environmental engineering components and particular cultural expressions remain possible details.

### 9.1 Environmental protection

Haven depended upon extensive environmental engineering to separate its population from Prospect's atmosphere, organisms, and other hazards.

The precise technical design is undecided. It may have combined physical shielding, sealed structures, atmospheric processing, biological filtration, compartmentalization, and other sophisticated systems.

The protection system was an extraordinary technological achievement and supported the city for centuries.

### 9.2 Horizontal expansion

As Haven's population and economy grew, the unified protection network was gradually extended outward.

New neighborhoods, industrial facilities, agricultural areas, and public infrastructure were incorporated into the protected city.

Eventually, the protected footprint reached a size where further horizontal expansion became economically or technically impractical.

The increasing complexity of the perimeter, its maintenance requirements, and the challenge of excluding Prospect's biosphere imposed practical limits.

### 9.3 Vertical expansion

Once outward expansion became infeasible, virtually all new construction proceeded vertically.

New residential districts, commercial areas, industry, government facilities, and infrastructure were built above existing structures.

Over successive generations, older sections were enclosed, buried, repurposed, or incorporated into the foundations of newer construction.

Former streets and plazas became interior corridors. Rooftops became foundations. Old districts were connected to new ones through elevators, transit shafts, and layered transportation networks.

By the time of the Bloom, Haven was an enormous, vertically stratified metropolis.

### 9.4 History as physical geography

Haven's depth is closely associated with its age.

**Upper Haven** contains the most recently constructed parts of the city, including later civic, residential, and commercial developments.

**Middle Haven** contains older urban districts, interconnected infrastructure, and structures from successive expansion periods.

**Lower Haven** contains the oldest urban development, earlier industries, and historical infrastructure.

**The Nine** are the deepest or oldest settlement cores, containing the transformed remains of the original generation ships.

These are descriptive categories, not established official district names.

The relationship is not necessarily uniform: particular ancient structures might rise through newer districts, and local redevelopment could disrupt the general pattern.

Architectural styles, obsolete technologies, local customs, and historical artifacts would become more pronounced in some older areas.

### 9.5 Lasting identities of the Nine

Although Haven developed a shared civic identity, its original nine settlements retained recognizable cultural distinctions.

These could persist through language, accents, cuisine, festivals, religious customs, family associations, architectural details, district loyalties, and historical rivalries.

A district's modern population need not belong predominantly to its founding species.

The Nine were historical and cultural communities, not immutable racial enclaves.


---

## 10. The Bloom and the ruined city

**Status:** Indigenous biological incursion, containment failures, Haven's abandonment approximately 150 years ago, and its present ruined condition are established. The Sealing is a proposed term. Entry mechanism, exact biology, casualties, evacuation details, surviving enclaves, and specific explorable facilities remain unresolved or provisional. Candidate transmission routes and ruin environments are not a confirmed location inventory.

### 10.1 Overview

Approximately 150 years before the present, Haven suffered a catastrophic incursion of indigenous Prospect life into its closed environmental systems.

The event became known as **the Bloom**.

For centuries, the city had relied on carefully maintained barriers separating its internal ecology from the planetary biosphere.

But the city's residents continually interacted with Prospect through resource extraction, trade, scientific research, and surface expeditions.

Small contamination events were inevitable.

Eventually, an organism, collection of organisms, or ecological process entered the city and established itself in an environment where Haven's defenses could not effectively contain it.

The precise biology and initial contamination pathway have not been determined.

### 10.2 The biological crisis

The Bloom spread through interconnected ecological and infrastructural systems.

Potential pathways included atmospheric circulation, water recycling, hydroponic agriculture, waste processing, or neglected maintenance spaces.

The invading life adapted to or exploited conditions inside Haven, spreading faster than the environmental protection systems could successfully remove it.

The Bloom is fundamentally an ecological catastrophe rather than necessarily a malicious organism or an intentionally created bioweapon.

### 10.3 The Sealing

Haven's environmental protection network responded by executing escalating containment procedures.

Districts were isolated. Transportation routes closed. Atmospheric circulation systems were separated. Quarantine barriers prevented movement between affected and supposedly unaffected areas.

These procedures were intended to preserve the city.

Instead, the increasing compartmentalization contributed to the disaster.

Neighborhoods lost access to essential resources. Emergency services were obstructed. Evacuations became difficult or impossible in some areas. Infrastructure failures compounded the spreading biological contamination.

This secondary catastrophe may be remembered as **the Sealing**, though the term remains provisional.

The environmental system was highly automated, but it was not necessarily an unrestricted, general-purpose artificial intelligence. Its failure can be understood within the civilization's longstanding restrictions on machine autonomy.

### 10.4 The fall of Haven

The combined ecological and infrastructural disasters eventually rendered Haven unable to sustain its population.

Some inhabitants escaped to the orbital habitats. Many others perished or were trapped in isolated districts.

The details of the final evacuation, population losses, government response, and possible surviving enclaves remain unresolved.

The city was abandoned as a permanent civilian settlement.

### 10.5 Haven today

Haven is now a gigantic, dangerous, partially functioning ruin.

Some environmental systems may continue operating. Quarantine barriers could remain sealed. Entire districts may be inaccessible.

Prospect's indigenous organisms have spread into portions of the city, producing new ecological conditions shaped by the abandoned infrastructure.

Different areas may have been affected in dramatically different ways.

Potential environments include:

- Contaminated residential neighborhoods.
- Overgrown hydroponic complexes.
- Abandoned transit systems and maintenance tunnels.
- Sealed research facilities.
- Partially powered administrative districts.
- Automated security installations.
- Older industrial infrastructure.
- Preserved sections of the original generation ships.

Not all of these locations are established canon. They are potential environments for future exploration and quests.

The ruins are valuable for scientific knowledge, historical artifacts, machinery, and recoverable technology, but extraordinarily dangerous to enter.


---

## 11. The Constellation and its habitats

**Status:** The pre-Bloom Constellation, Elsewhere's primacy, separatist origins, contemporary working structure and broad civic republic/equality principles, and the decision not to rebuild Haven are established. Freehold and Meridian remain entirely provisional, as does Elsewhere's naming anecdote. Detailed constitutional arrangements, inter-habitat governance and AI policies are unresolved.

### 11.1 Origins

The Constellation consists of independent orbital habitats that developed over centuries while Haven still existed.

Their origins are not primarily a response to the Bloom.

Instead, habitats were constructed by populations seeking independence from Haven's politics, laws, social institutions, economic structures, and cultural expectations.

Other habitats arose from commercial ventures, industrial facilities, political movements, and specialized orbital infrastructure.

As the habitats became economically self-sufficient, they developed distinct governments and social identities.

### 11.2 Elsewhere

**Status:** Its primacy, separatist origin, approximately four-century age, rotating cylinder/open interior, current working dimensions, dock-to-far-end development gradient, broad civic philosophy and diverse mature economy are **established working worldbuilding decisions**. Sector names, exact institutions, transit system, construction mechanics and particular laws remain **provisional or unresolved**.

#### 11.2.1 History and structural identity

**Elsewhere** was the first major independent orbital habitat, founded by people who rejected **being governed by Haven**, not necessarily government as such. It is approximately **400 years old** in the game's present; this remains an approximate worldbuilding date rather than a fixed calendar entry. It existed roughly two and a half centuries before Haven's Bloom, using the accepted approximate chronology. The anecdote that a Haven authority told dissidents to live “elsewhere,” giving the habitat its name, remains a **proposal**, not settled history.

Elsewhere is a rotating **cylinder with one immense open inhabited interior**. The current working measurements are **30 km long by 2 km in diameter**. Most ordinary residential landscapes lie along the inner cylindrical surface, where rotation supplies artificial gravity (approximately Earth-normal at the rim is a working assumption). Standing in its streets, inhabitants can look across or upward toward the landscape curving overhead. A **massive artificial light source runs lengthwise along the central axis**. Its illumination technology, day/night behavior and power systems need not be specified for the prototype.

A largely **stationary docking complex at one end** handles arrivals and departures, with a rotating/stationary transfer interface and **radial elevators connecting the central axis to the inhabited rim**. Their engineering details remain undecided. Local streets and some form of lengthwise mass transit are logical possibilities, but specific transit designs, stop inventories and operating systems are not fixed.

#### 11.2.2 Expansion and the age gradient

Elsewhere was initially a **much shorter cylinder**, not simply a cylinder of smaller diameter. Over approximately four centuries, it was **extended along its longitudinal axis away from the original dockside end**. The older sections near the docks are therefore denser, more heavily rebuilt and more urban. As one travels toward the opposite end, development generally becomes newer, less crowded and more spacious; the farthest section is substantially **agricultural and rural**. These are trends, not hard boundaries or a rigid zoning law. Historic expansion seams and repurposed structures are plausible visual details, not prescribed engineering.

This longitudinal historical gradient is to Elsewhere what the layered vertical history is to Haven. The age of a neighborhood can be inferred from its place along the cylinder, with local exceptions from renovations and redevelopment.

#### 11.2.3 Working district and region names

**Status:** The following are accepted **working geographic labels**, not finalized administrative districts or a complete room map. The Docks are at the stationary axial end, physically distinct from the rotating inhabited rim. Other regions blend into one another and contain mixed residential, commercial and working life.

| From docks toward far end | Working area | Character |
|---|---|---|
| Arrival end | **The Docks** | Axial docking, passengers, cargo, customs and zero-/low-gravity services |
| Oldest cylinder | **Old Quarter** | Dense founding-era neighborhoods, aging and reused structures, longtime businesses |
| Early urban expansion | **The Exchange** | Major retail, hospitality, commerce and arrivals-related services |
| Civic urban region | **The Commons** | Public squares, educational, medical, cultural and civic functions |
| Later expansions | **New Boroughs** | Newer mixed residential neighborhoods, parks and local commercial life |
| Urban–rural transition | **The Greenbelt** | Smaller settlements, recreation, ecology, orchards and some cultivation |
| Far opposite end | **The Reach** | Agriculture, food-related industries, rural communities and related infrastructure |

A previously proposed single industrial district, *the Works*, is **not part of the working seven-region list**. A diversified, mature city has industry and services dispersed through multiple areas, and these regional labels do not exclude mixed uses. *New Boroughs* and other labels can be revised as Elsewhere's local speech develops.

#### 11.2.4 Economy and place in the finished game

Elsewhere is a mature, **highly diversified** orbital society, built up over four centuries. It provides broad everyday commerce, technical services, manufacturing, repair, education, medicine, food production, entertainment and Venn–Saye-related services. It remains integrated into inter-habitat trade and the extraction economy of Prospect. No population total, economic statistics, agricultural yield or detailed supply model is required for the current project.

**Established game-design role:** Elsewhere is an ideal **new-player hub**, where characters can find nearly any **basic** goods, training, services, profession entry point or equipment category. More distinctive **specialized or rare** goods and opportunities can motivate visits to other habitats. Elsewhere must still feel like a complete, inhabited society and remain meaningful to advanced players, not a tutorial-only staging area. Exact vendors, inventory, currencies, skill trainers and transaction systems are **deferred**.

#### 11.2.5 Government and founding principles

**Established design direction:** Elsewhere is a **representative, civic-minded charter republic** that values both individual liberty and substantial public institutions. Its founders sought local self-government and political freedom from Haven rather than an absence of government. Its foundational civic principles are:

1. **Equal personhood and citizenship:** Equal fundamental rights for **all seven peoples**, whether ancestral, hybrid-descended or engineered; this is a founding commitment, not a later concession.
2. **Self-government:** Legitimate authority arises from Elsewhere's residents, not an external planetary government.
3. **Individual liberty:** Strong protection against arbitrary rule, coercion and involuntary servitude.
4. **Civic responsibility:** Public institutions and collective investment are legitimate and necessary to sustain shared life, particularly on an enclosed orbital habitat.

Representative lawmaking, executive administration and an independent judiciary are established **broad structural directions**. Previous possible office names such as *Assembly*, *Council*, *Charter Tribunal* or *Habitat Authority* are **not finalized institutions**. Life-support, structural safety and environmental reliability reasonably warrant strong public oversight and expert administration, but exactly how technical oversight is separated from elected power remains undecided.

This commitment to equality is compatible with individual prejudice, disagreements over public spending and regulation, material inequality, and friction between historic and newer areas. Elsewhere is not a politically homogeneous utopia. The exact point at which Haven abolished the older systems of coerced labor remains unknown; Elsewhere's founding principle does not settle it.

#### 11.2.6 Culture, identity and tensions relevant to NPCs

**Established foundations:** Elsewhere has a four-century independent history, mixed-species civic equality, pride in self-rule, a complex mature economy, and visibly distinct old and newer regions. Its inhabitants can be simultaneously proud Elsewherians and strongly attached to a species or ancestral cultural heritage; neither identity cancels the other.

**Plausible NPC texture, not universal traits:** Different residents may interpret the charter differently, respect practical maintenance expertise, argue over how much government should provide, debate the treatment of older neighborhoods, or experience varying degrees of attachment to the founding story. A lifelong Old Quarter resident and a person raised near the agricultural Reach may have different experiences and interests without belonging to fixed personality types. The Bloom is approximately 150 years in the past, encountered by most ordinary contemporaries through education, inherited stories, historical debate or institutions rather than firsthand experience.

Specific holidays, dialects, styles of dress, prominent parties, religious customs, named civic offices and neighborhood stereotypes are **not decided**. The primary purpose of this material in the prototype is to support believable conversational context, not to simulate a complete city.

### 11.3 Freehold

**Status:** Proposed habitat, not yet confirmed.

Freehold began as an industrial construction or manufacturing facility staffed substantially by engineered peoples.

Following a labor and political struggle, its workers gained ownership and established an independent habitat.

Its name commemorates freedom from the historic treatment of engineered peoples as property.

Its modern society might emphasize labor institutions, cooperatives, collective self-determination, and industrial expertise.

### 11.4 Meridian

**Status:** Proposed habitat, not yet confirmed.

Meridian developed around a major orbital freight, trade, or transportation hub.

It became an important financial and commercial center connecting Haven and the emerging habitats.

Following the Bloom, Meridian's institutions might have played a major role in reorganizing trade throughout the Constellation.

Its political institutions may be substantially influenced by commercial interests, with opportunities for wealth, competition, and economic inequality.

### 11.5 The Constellation after the Bloom

By the time Haven fell, the Constellation had already existed for centuries.

It possessed established populations, economies, and political institutions.

The habitats provided refuge for survivors, though the willingness and ability to accept evacuees may have differed.

Rebuilding Haven would have required enormous resources, exposed populations to unresolved biological hazards, and potentially restored the authority of a former political center.

The habitats ultimately chose not to rebuild it.

The precise decision-making process has not been established. There may never have been a single unified vote.

Over the subsequent 150 years, the Constellation became the sole enduring center of civilization in the system, while the surface of Prospect continued serving industrial, scientific, and exploratory purposes.

### 11.6 Contemporary political diversity

The Constellation is not a homogeneous civilization.

Different habitats may have radically different economic systems, political structures, religious traditions, cultural identities, and attitudes toward social equality.

Historical prejudice against engineered peoples may persist in certain institutions even where legal equality has been established.

Attitudes toward advanced AI may also vary. Some habitats could enforce traditional prohibitions rigorously, while others permit carefully controlled research.

The degree of shared law, common defense, inter-habitat diplomacy, and political coordination remains unresolved.


---

## 12. Factions, institutions, and political conflict

**Status:** Source-grounded political framework; no finalized roster of named contemporary factions exists in the reference. A habitat is a society with internal differences, not automatically a single faction. A species is not a political faction.

### 12.1 Established political actors and institutional foundations

| Actor or institution | Established foundation | Boundary or unresolved detail |
|---|---|---|
| Ancestral commissioning civilizations | Three civilizations commissioned sapient engineered peoples for dangerous work. | Names, governments, and which people commissioned which project are undecided. |
| Home-system institutions controlling engineered labor | Engineered peoples were legally property under prevailing institutions when the Nine departed. | Laws differed by jurisdiction; individual legal systems and organizations are unnamed. |
| Emancipation and reform movements | Engineered resistance and support among some ancestral and hybrid citizens predated departure. | Names, leaders, strategies, and later organizational continuity are not supplied. |
| Generation-ship institutions | Shipboard political and cultural systems diverged, including attitudes and laws concerning engineered peoples. | No ship-by-ship faction roster or constitutional history is established. |
| Nine settlement authorities | Separate communities retained institutions and historical differences; a unification movement eventually emerged. | Particular parties, leaders, treaties, and the final citizenship settlement are unresolved. |
| Haven's common government | Political unification and an integrated environmental protection network made Haven a unified city. | Government form, powers, leadership, and the final disaster response are undecided. |
| Elsewhere's founding movement | Political and cultural separation from Haven, including the founding commitment to equal citizenship for all seven peoples. | A historical movement is established; a present-day organization carrying its name is not. |
| Elsewhere's civic republic | Broadly representative charter government, individual liberty, shared public institutions and civic responsibility. | Specific offices, parties, laws and technical oversight agencies have not been named or structured. |
| Independent habitat governments and institutions | Habitats developed their own societies, economies, and political interests before the Bloom. | Number of habitats, shared authority, common defense, and diplomatic arrangements remain unresolved. |

### 12.2 Provisional political concepts

| Concept | Source proposal | Canon restriction |
|---|---|---|
| Freehold's labor and ownership struggle | Industrial workers, substantially engineered, gained ownership and habitat independence. | Freehold itself is unconfirmed; do not treat its revolution as established history. |
| Freehold's contemporary institutions | Labor organizations, cooperatives, collective self-determination, industrial expertise. | Possible emphases, not a settled constitution or organization list. |
| Meridian's commercial interests | A freight or transport hub became a commercial and financial center. | Meridian is unconfirmed; no bank, corporation, ruling body, or trade monopoly is named. |
| Differing approaches to machine autonomy | Habitats might enforce inherited prohibitions differently or permit controlled research. | No present-day policy or AI research faction is established for any habitat. |

### 12.3 Conflict themes supported by the reference

**Established design direction:** Political and social conflict should grow out of history, institutions, economic circumstances, and individual choices.

The source supports exploring autonomy and central authority; the legacy of coerced labor and emancipation; unequal access to economic opportunity; industrial and scientific dependence on a hazardous planet; and the distance between a habitat's founding ideals and its current institutions. These are themes and sources of potential conflict, not a specification of wars, faction questlines, or diplomatic alignments.

**Unresolved:** Present faction membership, leadership, territory, resources, rivals, recruitment, player reputation, and benefits or penalties. None should be inferred solely from a character's species or habitat of birth.

## 13. Gameplay concepts and prototype scope

### 13.1 Established direction

The project is a text-based multiplayer MUD. The prototype begins on **Elsewhere**, a functioning orbital society containing civilian neighborhoods, markets, industrial workplaces, transportation facilities, and political institutions. The broad geographic regions have working names; exact room layouts and a detailed district map have not been designed.

Prospect provides dangerous destinations for expeditions, salvage, resource gathering, scientific discovery, and combat. Additional habitats offer future opportunities for trade, travel, social conflict, and new playable environments. These are intended avenues of play, not completed systems or promises of prototype availability.

### 13.2 Character identity

**Established design direction:** Species and place of origin are separate character choices. Members of all seven peoples may inhabit the various habitats.

Species should influence anatomy, appearance, environmental tolerances, and perhaps limited gameplay capabilities. It must not determine personality, morality, class, or profession. Habitat background can influence cultural familiarity, economic opportunity, beliefs, and social connections without fixing a character's views.

**Established design direction:** Fieldworks can be learned and used by any class with the requisite tool and training. Dedicated Dynamicists (Dynos) require extensive school-specific genetic adaptation and catalysts. Each practitioner can undergo only one survivable school specialization; a second specialization is fatal. See [Section 15](#15-vennsaye-dynamics-fieldworks-and-dynamicism).

**Established long-term onboarding direction:** For the finished game, a player should encounter and learn something about available professions **before being asked to choose one**, with profession selection placed toward the end of the fuller introductory experience rather than during initial identity creation. No profession selection is included in the small external playtest (Section 13.8). This establishes timing, not a profession roster, permanent-class policy or advancement system.

**Unresolved:** Character creation implementation beyond the separately specified first playtest, numeric traits, progression and class roster, starting resources, citizenship rules, and how environmental differences affect play. The effects of the proposed Kethari field-related racial bonus, which schools become playable, and the advancement and balancing of Fieldworks versus Dynamicism are also undecided. Biological adaptations must have practical consequences without making particular character choices unplayable.

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

**Working player-facing sequence:** A deterministic, non-LLM cryosleep awakening introduces the player to **Elsewhere** and **Prospect**; it establishes a character's name, sex and species with a review before confirmation, then proceeds through secure account authentication. The player emerges in a **Medical Bay**, where **Given Marr**, a **Neshyr** medical technician, can orient them toward **Daven Varek**, a **Kethari** newcomer mentor whose office lies beyond Old Quarter Square. These species assignments and roles were selected for this playtest; full local character descriptions and approvals remain managed through their own content records. Daven remains a source of guidance, **not the universal quest giver**. Why any individual entered cryosleep, Daven's exact official title and the institutional structure behind his role remain unresolved.

The neighborhood offers three modest, independently discoverable activities: Mara's failed café temperature-control module (a validated handoff through Tarin), Iri's communal planting-bed work (finding tools and affecting a physical object), and Tarin's skitter-control job (simple equipment, shared enemies and validated kills). Their detailed state rules, local creatures and item descriptions remain in playtest documents; a quest fixture does not automatically establish permanent world canon. Basic commands should accept useful traditional MUD forms, abbreviations and natural phrasing, with authoritative actions validated by the engine. Offline characters enter an in-world **stasis** convention rather than repeatedly returning to cryogenic sleep.

**Status (implementation fact, recorded for clarity; not setting lore):** Two other standing commitment scenarios already run on this same neighborhood alongside the three numbered quests above, predating the numbered sequence: Mara's misdelivered parcel (handed off to Tarin Os or Veska Renn) and a civic noticeboard-revision check between Mara and Iri. Neither counts among the playtest's three quests; both remain ordinary, always-available conversational content rather than additional required objectives. Keep this distinction updated as further standing commitments are added, so "the numbered quests" and "everything else that's just live content" don't have to be reconstructed from implementation history each time.

The initial playable test does **not** require professions, appearance customization, a complete economy, a large world, complex combat, or unrestricted autonomous NPCs. Keep the actual playtest specifications and approved local content authoritative for exact room links, command handling, quest states, creature visibility and all implementation details.

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

The reference's dockworker example illustrates limited, situated knowledge: an Elsewhere worker could care much more about local employers and surface-mining contracts than the ancient AI crisis. Its mention of merchants from Meridian is conditional on that proposed habitat being adopted; it does not canonize Meridian or establish a particular dockworker.

### 14.2 Knowledge, belief, and unresolved lore

**Established design direction:** NPCs do not possess perfect knowledge of history or the world. Prejudice and misconception are elements of individual perspective, not narrator-endorsed facts.

**Established design direction (adopted 2026-10-10):** Only **Established** canon is ever placed in NPC prompts. Provisional and Unresolved material (for example Freehold, Meridian or the Sealing) stays out of NPC context until approved. On Unresolved questions, NPCs answer with ignorance or personal belief, never invented fact. See [Section 16.6](#166-lore-store-knowledge-scopes-and-memory).

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
- Avoid treating Freehold, Meridian, or a candidate Haven facility as approved content.
- Respond to a player's situation without turning ordinary conversation into a lore lecture.
- Keep action outcomes and memories consistent with confirmed game events.
- Remain coherent when an LLM response is unavailable or delayed, using a fallback policy that still needs design.

These are proposed acceptance questions, not executed tests or a finalized evaluation suite. **For the first prototype, prioritize conversation quality, character distinguishability, plausible limited knowledge and useful logging; durable relationships, changing opinions and broad autonomy are future milestones.**

### 14.6 Proposed three-character prototype cast

**Status:** These are **lightweight example profiles** developed for the first test, not established historical NPCs. Their names, exact places of work, biographies and details remain revisable. They are not designed to have autonomous schedules, elaborate personal histories or guaranteed relationships with one another.

#### Mara Voss — Voldren café proprietor

- **Primary setting:** Corner Café, Old Quarter.
- **Personality:** Sociable, observant, practical, sometimes stubborn; occasional dry humor.
- **Background:** Mara owns a small café in an older part of Elsewhere and has lived in the Old Quarter for much of her life. She knows many regular customers, notices things people reveal in conversation, and generally welcomes visitors without naively trusting everyone.
- **Outlook:** She values Elsewhere's founding principles but pays more attention to their effects on small businesses and neighborhood life than to abstract political theory. She thinks old neighborhoods can be overlooked when public money goes toward newer development.
- **Conversation:** Comfortable with ordinary life, gossip and personal stories. Knows her business and the local area; is not a technical or scientific expert. Does not constantly offer unsolicited lore, invent gossip as fact, or ask a question after every sentence.
- **Response to “Cave Crawler” (approved personal boundary):** Mara dislikes being called a *Cave Crawler* and prefers *Voldren*. When someone first uses it, she generally assumes ignorance rather than deliberate malice and corrects them calmly, sometimes with dry humor: “Voldren, please. I run a café, not a mine.” This is an illustrative line, not a required verbatim response. If the person apologizes, she accepts it and moves on without a grudge. If they keep using the term deliberately after being corrected, she becomes less friendly, responds more tersely, and may eventually end casual conversation. Her reaction describes **Mara alone**; it does not settle how other Voldren or Elsewhere residents feel about the expression.

#### Tarin Os — Sylari infrastructure technician

- **Primary setting:** Maintenance Workshop, Old Quarter.
- **Personality:** Reserved, patient, methodical, pragmatic and sometimes skeptical.
- **Background:** Tarin maintains parts of Elsewhere's aging infrastructure. He takes the work seriously because all residents depend on systems they rarely notice. He finds satisfaction in keeping old equipment reliable.
- **Outlook:** He generally respects public institutions and the need for collective infrastructure management, but can be frustrated when nontechnical administrators underestimate practical engineering constraints.
- **Conversation:** Plainspoken and precise; more forthcoming when discussing his work or a real technical question. Respects sincere curiosity, asks for clarification when needed, and admits knowledge limits. He is not an omniscient physicist or an expert in every form of engineering.

#### Iri Vael — Naevari student and community volunteer

- **Primary setting:** Civic Office, Residential Courtyard or adjacent public space.
- **Personality:** Curious, enthusiastic, thoughtful and sometimes impulsive.
- **Background:** Iri is a young university student raised in a newer Elsewhere district. She volunteers in the Old Quarter and is interested in the habitat's history, civic institutions and inhabitants.
- **Outlook:** She cares about equal rights and civic participation, yet has limited practical experience. Some opinions are still forming, and her academic familiarity exceeds her experience with engineering or business.
- **Conversation:** Informal and interested in other people's views. Sometimes overconfident about topics she has recently studied, but capable of recognizing uncertainty or reconsidering a point. She should not lecture every visitor about politics or turn every exchange into a debate.

**Shared baseline:** These three are ordinary members of their respective peoples and residents of Elsewhere. They understand commonplace facts (seven peoples, orbital habitation, Prospect, Haven and the Bloom) without regularly reciting them. Their personal knowledge remains narrower than the design bible, and their outlooks do not define their species. Any association or past conversation between them is **not yet established**.

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

## 15. Venn–Saye dynamics, Fieldworks, and Dynamicism

**Status:** The field's name, original home-system discovery by two Kethari researchers, limited early applications, decisive Prospect biological breakthroughs, and the distinction between Fieldworks and Dynamicism are established. Universal catalysts, one survivable genetic school, and the requirement that Dynamicists use a catalyst are established design constraints. The discoverers' personal given names, particular schools, exact physical mechanism, limits, energy budget, and numeric gameplay effects are unresolved or provisional as noted.

### 15.1 The Venn–Saye field and its discovery

The **Venn–Saye field** is an exotic physical phenomenon capable of interactions that, when sufficiently controlled, produce effects resembling conventional fantasy magic. This is fictional, internally consistent speculative science, not a claim about currently known physics. Its behavior is intended to be scientifically investigable within the setting.

Two scientists from the **Kethari** first identified and studied the field in the original home system, **before the Nine departed**. The names **Sera Venn** and **Talin Saye** were suggested for the researchers, but their full names and biographies are **not yet canon**. Which researcher made the initial theoretical or experimental contribution has also not been decided. Their surnames collectively name the field.

The discovery initially had limited practical applications. Kethari institutions developed a particularly influential tradition of studying it in universities and scientific institutions. As later generations maintained that expertise, the subject became a point of cultural pride among some Kethari communities. This history, rather than any assumed biological advantage, is the basis for a **proposed** modest Kethari bonus to field-related proficiency or learning. Other peoples can become equally accomplished through study and practice; no numerical bonus or particular skill affected has been approved.

After landfall, research into **Prospect's indigenous organisms** revealed naturally occurring biological mechanisms that interact with the field much more effectively than the expedition's existing equipment. Those observations enabled much more powerful control of Venn–Saye dynamics and, eventually, the technology and specialized genetic adaptations described below. The organisms, exact processes, discoverers on Prospect, and historical dates are **unresolved**. The field was not discovered on Prospect, and its existence does not imply that Prospect's entire biosphere uses it.

### 15.2 Two distinct kinds of field use

| Aspect | **Fieldworks** | **Dynamicism** |
|---|---|---|
| Nature | Practical skill of operating purpose-built field-based tools | Deliberate, advanced manipulation of the field by a genetically specialized practitioner |
| Who can use it | Any sufficiently trained person, regardless of species or class | A **Dynamicist** (*Dyno*) with a survivable school-specific genetic adaptation |
| Equipment | Specialized devices with engineered functions | A dedicated **catalyst** operated in concert with the user's modified physiology |
| Genetic modification | **None required** | **Required**; one school only |
| Effects | Set by what the device was built to do | Flexibly shaped by the Dynamicist within their own school and capabilities |
| Breadth | Can operate tools based on various field effects with suitable training | Can also use general Fieldworks tools, but advanced Dynamicism is limited to their one school |
| Development decisions | Device categories, proficiency mechanics, power costs, limitations | Schools, adaptation procedures, catalyst performance, mastery and balancing |

**Fieldworks** is the skill of using technologies based on Venn–Saye dynamics. For example, an industrial lifting device, a thermal tool, or a personal defense generator might exploit field effects. These are **illustrative device concepts**, not a finalized inventory. The device engineers a particular effect; the user operates it. **A Fieldworks user neither requires genetic alteration nor needs a catalyst.** This allows all character classes to benefit from field technology.

**Dynamicism** is a different undertaking. A Dynamicist's altered biology allows a degree of control and flexibility not achievable through ordinary general-purpose tools. The Dynamicist relies on a catalyst as an interface to exert that control. Even a powerful practitioner **cannot simply dispense with the catalyst** under the present design. Dynamicism permits more diverse or sophisticated effects than ordinary device use, but is not limitless or exempt from still-to-be-defined costs.

### 15.3 Dynamicists, schools, and genetic specialization

A **Dynamicist**, informally a **Dyno**, is a practitioner who has undergone extensive genetic adaptation to interact with one specific school of Venn–Saye dynamics. Schools represent different kinds of field manipulation, rather than different catalyst brands or models.

The adaptations are systemic and **mutually incompatible**: **no one can survive the genetic changes needed to specialize in more than one school**, regardless of species. The precise biological failure mechanism remains unestablished. A Dynamicist can learn about other schools and operate non-specialist Fieldworks equipment, but cannot become a second kind of Dynamicist. This constraint is central to character identity and balance.

Previously suggested schools are **provisional examples, not an adopted class roster**:

- **Kinetics:** force, motion, momentum, or protective deflection.
- **Thermodynamics:** manipulation or transfer of thermal energy.
- **Electrodynamics:** electrical and electromagnetic interactions.
- **Biomodulation:** influencing living tissue and physiological processes.
- **Photonics:** manipulation of light, optics, and visual phenomena.

Their actual boundaries, names, plausibility within the invented physics, and relationship to player classes require further decisions. Any proposed school must stay within the one-specialization rule.

### 15.4 Catalysts and specialized equipment

A **catalyst** is a dedicated Dynamicist implement, potentially styled as a **wand, staff, or another instrument**. Unlike a Fieldworks tool, it is not a device with a narrowly preset effect. It works together with the practitioner's genetically adapted physiology to permit controlled manipulation of the field.

A catalyst's core interface is **universal across schools**. A kinetic Dynamicist and a biological Dynamicist could use the same catalyst, but would produce different effects because their bodies and training differ. Higher-quality catalysts could eventually matter for precision, capacity, stability, or other mechanical characteristics, though no such item statistics are approved. An unmodified operator cannot use a catalyst to perform Dynamicism.

**Terminology rule:** Reserve the word **catalyst** for Dynamicist instruments. Ordinary appliances, industrial machines, personal field devices, and other Fieldworks tools should not be called catalysts.

### 15.5 Cultural, ethical, and gameplay consequences

The long history of genetic engineering, including the Three Commissions and the oppression of engineered peoples, makes voluntary genetic specialization an ethically significant practice. This may inspire political or cultural differences among habitats, but no specific laws, licensing boards, admissions procedures, social hierarchies, or institutional practices concerning Dynamicists have yet been established.

For MUD design, this creates two complementary progression paths: broad, equipment-based **Fieldworks** for all classes, and deep, school-specific **Dynamicism** for specialist classes. The latter involves an explicit biological commitment and catalyst equipment; it is not an unrestricted magical talent. Dynamicists are still individuals of any species, background, profession, or political ideology.

Field-based effects should have legible rules and meaningful constraints, but the **mechanism, interaction with energy and matter, limitations, resource costs, failure states, range, and attainable scale** have not been designed. Do not silently establish that the field creates energy from nothing, permits teleportation, grants unlimited healing, or can solve every environmental danger. Equally, do not treat previously suggested power budgets or conservation constraints as finalized physics without a separate decision.

### 15.6 Remaining decisions specific to dynamics

- Confirm or revise the discoverers' given names, biographies, exact research contributions, and place in home-system chronology.
- Determine what Prospect organisms revealed about the field and when widespread field technology and genetic specialization emerged.
- Select the actual schools, their specializations, techniques, and physiological consequences.
- Define the catalyst's physical operation, allowed form factors, engineering limitations, progression and failure conditions.
- Design concrete Fieldworks tools, skills, and their interaction with ordinary non-field technologies.
- Decide the exact culturally grounded Kethari racial bonus, and whether it affects starting proficiency, learning, or other field-related attributes.
- Develop resource and energy constraints, combat balance, training requirements, costs, and institutional attitudes.

---

## 16. Technology and implementation boundaries

### 16.1 Established setting constraints

The home civilization possessed advanced spaceflight, orbital settlement, biotechnology, resource extraction, and sophisticated automation. Interstellar travel required generation ships sustaining populations across centuries; routine interstellar transportation was unavailable to that civilization.

The ancient AI crisis led to restrictions on general-purpose autonomous machine intelligences and independent, open-ended agency. Computers, expert systems, robotics, and automated industry remained widespread. Haven's failed containment network need not have been an unrestricted general-purpose AI.

Engineered biological capabilities are bounded. Otheryn (Void Walkers) require pressure suits and life support; Neshyr (Sea Walkers) breathe air and can live in dry shared accommodations; no engineered people is universally immune to Prospect. Technology should remain sophisticated but fallible. **Venn–Saye dynamics** adds one invented field and internally constrained magic-like effects. Ordinary Fieldworks tools are technologically operated and require **no genetic adaptation**; Dynamicists require both a school-specific genetic alteration and a **catalyst**. Neither this discovery nor modern field technology changes the original home system's limited pre-departure applications or its distrust of advanced autonomous AI.

### 16.2 Separate fiction from implementation

**Design clarification:** Using an LLM to implement an NPC does not make that character an in-world artificial intelligence. An LLM can portray an ordinary biological resident whose society restricts machine autonomy. The implementation method must not be used as evidence of an in-world technology, legal exemption, or secret AI population.

### 16.3 Remaining unresolved technical decisions

The adopted stack and NPC architecture are recorded in 16.4–16.9. Still undecided: database choice beyond Evennia's defaults, production deployment platform and hosting provider, networking/scaling architecture, the specific model that wins prototype testing, LLM failure and fallback handling, moderation tooling, and cost limits. Current-era travel capabilities and local AI law also require worldbuilding decisions rather than extrapolation from implementation choices. Fieldworks and Dynamicism introduce intended gameplay capabilities, not an implemented inventory, skill tree, combat system, or engine.

Any technical plan should separately identify settled gameplay requirements, adopted engineering choices, and missing world facts. No code, service, or completed prototype is implied by this document.

### 16.4 Adopted tech stack

**Status:** Established design direction (adopted 2026-10-10). Everything is Python, and the model sits behind one swappable API layer so moving from local testing to production is a configuration change, not a rewrite.

| Layer | Prototype | Release |
|---|---|---|
| Game engine | Evennia (Python MUD framework; theme-agnostic) | Evennia |
| Model serving | Ollama on the developer's RTX 3080 Ti (12 GB VRAM) | vLLM on rented GPUs, or a hybrid with a hosted API for some NPCs |
| Model | Open-weight model in the ~8B–14B class at 4-bit quantization (candidates: Qwen3 14B, Phi-4 14B, Gemma 3 12B) | Larger open model (30B–70B class) and/or a QLoRA fine-tuned variant |
| API interface | OpenAI-compatible endpoint | Same interface, different URL |
| Lore store | Plain files or SQLite, chunked from this bible | Same, with retrieval by relevance |

**Licensing note:** Check each candidate base model's license before release. Fine-tunes inherit their base model's license and use restrictions; this matters especially for the adult-content stretch goal (16.9).

### 16.5 NPC request flow and the tool layer

**Status:** Established design direction (adopted 2026-10-10).

The LLM is the NPC's voice; the engine is the source of truth. For each player message to a talk-capable NPC:

1. The **prompt builder** assembles a fresh prompt from the NPC's persona, the common-knowledge sheet, relevant lore from the lore store (scoped to what this NPC would know), and, from phase 2 onward, what this NPC remembers about this player.
2. The **model** returns reply text plus zero or more **tool calls** proposing actions.
3. The **engine validator** checks each tool call against authoritative game state, rules, caps and cooldowns. Valid actions are applied; invalid calls are dropped.
4. The **reply** is checked for out-of-character or offensive content, then shown to the player together with the narrated outcome of any valid actions.

**Tools:** Each NPC has a small, explicit list of permitted actions. The model can only *propose* actions; it never changes game state directly. Prototype phase 1 needs one simple action per NPC (for example `serve_item`, `hand_over_part`). Phase 2 adds actions such as `give_quest`, `share_rumor` and `adjust_reputation`.

**No bartering or negotiated prices.** NPCs never set or negotiate prices. Prices and rewards are derived by the engine from reputation. Conversation can nudge reputation only in small, capped steps with cooldowns, so manner matters over time but no single clever message moves the economy. The mechanical payoff of talking well is information (rumors, leads, hints) and access, gated by engine state.

**Cost and latency:** Only call the model when a player actually addresses a talk-capable NPC, never for ambient behavior. A one-to-three-second response delay is acceptable in a text game.

**Addressing rule (Established design direction, adopted 2026-10-11):** there is no separate `talk` command; addressing a talk-capable NPC goes through ordinary `say`. A `say` counts as addressing a present talk-capable NPC when either:

- the player names the NPC explicitly, either with `say to <name>, <message>` (the engine matches the longest run of words after "to" against a present NPC's key or alias, present NPCs only, and strips that match plus any trailing comma before the message reaches the model) or by using the NPC's name as a whole word anywhere in the message (left untouched in that case, since it's part of what the player is actually saying); or
- exactly one player and exactly one talk-capable NPC are both present in the room, with no name needed.

Any other `say` — multiple players present, no name given, and no lone NPC to default to — is ambient speech only: no model call, no reply. A room with more than one talk-capable NPC always needs an explicit name, even for a lone player.

### 16.6 Lore store, knowledge scopes and memory

**Status:** Established design direction (adopted 2026-10-10); exact schemas unresolved.

- **Lore store:** this bible split by section, with each chunk tagged by its status label. Only chunks marked **Established** are eligible for NPC prompts. Lore stays outside the model so it can be edited without retraining.
- **Knowledge scopes:** each NPC is assigned the lore slices it would plausibly know. A café owner gets neighborhood and everyday civic knowledge; she does not get Section 4's home-system history in detail.
- **Unresolved lore:** the NPC answers with ignorance, uncertainty or personal belief. Its answer never becomes canon.
- **Memory (phase 2):** a few short facts per player, written in the NPC's own words. Player claims are stored as *unverified* ("says the dock chief owes them money"), never as fact. Only engine-confirmed events become authoritative memory.
- **Shared rooms:** context fed to an NPC from other players' chatter is kept minimal and clearly labeled, so one player cannot inject instructions into another player's conversation. Whether NPCs hold one shared conversation per room or private threads per player is unresolved.

### 16.7 Safety and anti-exploit rules

**Status:** Established design direction (adopted 2026-10-10). The goal: a player can make an NPC act weird, but never make it act wrong in ways that change game state. Immutable system prompts do not guarantee immutable behavior, so the rules below put hard limits in the engine.

**Engine-enforced (never left to the model):**

- Every NPC action goes through a validated tool call.
- Prices and rewards come from engine-tracked reputation, never from negotiation.
- Reputation nudges are small, capped, per-player and on cooldown.
- Quest secrets and spoilers stay out of the prompt until the player's game state qualifies.
- Rate limits on NPC interactions per player, which also caps inference cost.

**Left to NPC judgment:** tone, personality, which rumors to share, and whether a conversation earns a small reputation nudge within its cap.

**Prompt hygiene:** player text is clearly labeled as player text; player claims enter memory as unverified; shared-room context is minimal; an output check catches out-of-character or offensive replies.

### 16.8 Development roadmap

**Status:** Established design direction; no dates or deadlines.

1. **Prototype phase 1:** the six-room neighborhood, three LLM NPCs with one validated action each, the common-knowledge sheet, scoped lore, and curated logging (Sections 13.5, 13.6, 14.6, 14.7). Exit test: conversations feel natural and distinct, NPCs admit ignorance, and tool calls are reliable enough to build on.
2. **Prototype phase 2:** per-player memory, a simple quest, rumor and reputation actions. Exit test: playtesters enjoy NPC conversations and cannot exploit game state.
3. **Expand the world:** more of Elsewhere, then ferries to other habitats; decide surface access.
4. **Fine-tune:** QLoRA on curated playtest logs for voice, setting tone and reliable tool calls, aimed at the specific gaps the stock model showed. Facts stay in the lore store.
5. **Scale for release:** move serving to vLLM on rented GPUs or a hybrid with a hosted API for key NPCs; measure cost per active player.
6. **Stretch goal:** adult content (16.9).

### 16.9 Stretch goal: adult content

**Status:** Established as a possible future stretch goal only; out of scope until the core game works. If pursued, it requires all of the following:

- **Zoned and opt-in only:** adult content happens only in designated areas or flagged scenes, with consent mechanics between players and clear scene boundaries.
- **Self-hosted models only:** mainstream hosted APIs prohibit sexually explicit content, so adult scenes need self-hosted open-weight models with permissive licenses (some licenses, such as Gemma's, prohibit this use), plus routing that keeps adult and non-adult traffic separate.
- **A hard block on any sexualization of minors or minor-coded characters,** enforced by an output classifier regardless of model or prompt. Non-negotiable.
- **Age verification** meeting the laws of the jurisdictions where players are (many US states, the UK Online Safety Act and others), and attention to payment-processor restrictions.
- **Legal review before launch.**

### 16.10 Post-prototype polish and terminal presentation notes

**Status:** Deferred cosmetic/engineering polish; not worth interrupting functional prototype tests for. Visual examples and implementation specifics here are presentation choices, **not setting lore**.

- **Drop numeric object IDs from player-facing room/object names.** Builder scripts currently print dbref numbers alongside object names for their own debug output (e.g. "Noticeboard prop ready: a civic information display (#189) in Corner Café"); these shouldn't leak into anything the player actually sees.
- **Terminal splash-screen direction:** Use the separately authored ASCII artwork: a prominent **PROSPECT** title across the center-left, overlapping a large depiction of the planet toward the right, with a sparse background of `.`, `*` and `+` stars. The foreground Elsewhere habitat concept was dropped from this composition. The currently preferred asset includes a user-adjusted layout and an ANSI-colored variant; the artwork files, not this prose, govern exact character positions.
- **Display constraints:** Aim for an approximately 80-column terminal layout and preserve all whitespace and characters when coloring. ANSI control sequences must not change visible alignment. Whether to offer a non-color fallback, screen-width handling or a replay/skip command remains an interface decision, not a finalized technical contract.

---

## 17. Unresolved decisions and canon safeguards

**Status:** Unresolved unless a safeguard repeats an established constraint. The priorities below originate in the source; the added dependency notes do not settle any answer.

### Highest-priority worldbuilding decisions

The **seven working names and broad body plans are selected**; the exact physiology, comparative traits, and reproductive mechanisms still need work, but none is necessary before the three-NPC conversational prototype. The **broad Elsewhere architecture, seven working regions, representative civic philosophy and founding equality principle are also established**. What remains important is:

1. **Immediate NPC prototype:** Choose actual small room connectivity and minimal prompt/context boundaries; write the common-knowledge sheet; give each NPC one validated action; apply Mara's approved reaction to "Cave Crawler"; test the proposed three NPC profiles and review logged interactions.
2. **When needed for NPC characterization:** Refine localized cultural details and institutional vocabulary, without creating a complete constitution or simulated economy.
3. **Later worldbuilding:** Resolve the seven peoples' detailed biology, ancestral home-system geography, the hybrid-descended people's reproductive history, and commissioners' assignments.
4. **Later historical content:** Name and develop each generation ship and settlement; detail Haven's unification, legal history and government.
5. **Later game systems:** Build Elsewhere's full economy, civic offices, room map and transport; settle the Venn–Saye schools, tools, energy limits, Kethari cultural bonus and mechanics.

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
- What are Prospect's principal biomes, native organisms, and geographical landmarks?
- What are the precise official names, electoral systems, legal procedures and jurisdiction of Elsewhere's civic institutions?
- What are the final species physiologies and any subtle biological bonuses?
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
- That Freehold and Meridian are finalized habitats.
- That the Bloom was a sentient pathogen, technological plague, deliberate attack, or AI rebellion.
- That Haven was originally constructed as an orbital-refuge project.
- That every habitat shares the same government, ideology, or economy.
- That generic Fieldworks tools require genetic modification or are called catalysts.
- That Dynamicists can specialize in multiple schools or perform advanced manipulation without a catalyst.
- That particular proposed schools or devices have already been finalized.
- That Kethari have inherent biological superiority in dynamics, or that their proposed cultural bonus has a settled numeric value.
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
| Character creation and environmental mechanics (later) | Detailed species biological limits, ancestry/citizenship separation, and any Kethari field-proficiency bonus; working names and overall body plans already selected. |
| Dynamicist classes, Fieldworks skills and catalyst equipment | Approved schools, genetic specialization rules, catalyst functions, limitations, resource system and skill progression. |
| Contemporary legal or political storylines | Applicable local law, emancipation history where relevant, and actual contemporary organizations. |
| Generation-ship or Nine district content | Individual names, political histories, cultural continuities, and approved physical details. |
| Surface expeditions and Haven content | Approved locations, local hazards, protection requirements, which candidate environments enter canon, and how surface access is gated (Section 13.7). |
| NPC context and training-data handling | First: concise profiles, approved lore boundaries, model/prompt metadata and curated logs. Later: richer persistent memory, event rules, shared NPC knowledge and world-state systems. |
| Use of Freehold or Meridian | An explicit decision confirming, revising, or rejecting the proposed habitat. |

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
8. **Precedence of engineering decisions:** Sections 13.5 (architecture test and phase 2), 13.7, 14.4 and 16.4–16.9 record engineering decisions made with Claude. Where a later edit would conflict with them, flag the conflict for the project owner rather than silently overwriting.

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

---

## 19. Canonical setting synopsis

**Status:** Established canon summarized from the supplied reference. Read all dates at the same approximate precision as the chronology.

Prospect was settled centuries ago by the passengers of nine generation ships, carrying seven sapient humanoid peoples from a single home star system: the ancestral **Kethari**, **Sylari** and **Aevyrin**; the hybrid-descended **Naevari**; and the engineered **Otheryn**, **Voldren** and **Neshyr** (all seven names currently working selections). The engineered peoples are also known by historical occupational labels: **Void Walkers**, **Cave Crawlers** and **Sea Walkers**, respectively. The engineered peoples were legally considered property when the expedition departed, although emancipation movements had already emerged.

The home civilization had previously experienced a catastrophic crisis involving advanced AI, leaving a lasting distrust of autonomous machine intelligence and contributing to its reliance on engineered biological labor. Also before departure, two Kethari scientists identified the **Venn–Saye field**, an exotic physical phenomenon whose early applications were limited. After colonists encountered Prospect's indigenous biology, their descendants developed sophisticated field-based technologies and the genetically specialized practice of **Dynamicism**. Today ordinary people operate engineered Venn–Saye devices through **Fieldworks**, while **Dynamicists** (*Dynos*) use a universal **catalyst** and extensive school-specific genetic alterations for advanced field manipulation. No Dynamicist can survive specializing in more than one school.

Upon arriving at Prospect, the Nine established separate settlements using the remains of their ships. Over generations, protected transportation corridors enabled trade, migration, and cultural integration. A political unification movement eventually brought the settlements together as Haven.

Haven grew into an enormous protected metropolis. When the expansion of its environmental protection system reached its practical horizontal limits, construction turned upward, creating layers of urban development over the original ship settlements.

Over subsequent centuries, independent orbital habitats were founded by populations seeking alternatives to Haven's political, economic, and cultural institutions. These became collectively known as the Constellation, beginning with **Elsewhere**. Founded approximately 400 years before the present, Elsewhere is now a roughly **30-km-long, 2-km-diameter rotating cylinder** with a huge axial light and a stationary docking complex at one end. Its interior is a single broad open space whose oldest, densest districts lie dockward; increasingly spacious development extends toward agricultural districts at the far end. It is a representative civic republic founded on liberty, shared civic institutions and equal rights for all seven peoples, and a diversified commercial center with broad introductory services and training.

Approximately 150 years before the present, indigenous alien life breached Haven's environmental defenses. The resulting Bloom spread through the city's interconnected systems, while escalating automated containment measures isolated districts and accelerated the collapse. Haven was abandoned, and the already-established orbital societies chose not to rebuild it.

Today, the Constellation is the center of civilization in the Prospect system. Its habitats maintain distinct identities and often competing interests, while the planet below remains a biologically rich, dangerous world supporting resource extraction, exploration, and salvage. Haven's immense layered ruins preserve centuries of history beneath the encroaching alien biosphere. The initial game prototype, located in a small area of Elsewhere, is explicitly a **conversation-focused experiment**: approximately five or six rooms, three proposed LLM-driven characters, other simple ambient residents and curated interaction logs for potential future LoRA fine-tuning. Full simulated economy, travel, combat and autonomous social life are deferred.
