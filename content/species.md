<!--
content_id: species_descriptions
status: Provisional
approval: Approved
bible_refs: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8
purpose: short player-facing entries shown during character creation when the player chooses a people (docs/prospect-initial-playtest-design-spec.md Section 3). Each ## heading matches an entry in world/chargen.py's SPECIES_CHOICES exactly, so code can key on it. Drafted by the Lore lane 2026-10-16 at the project owner's request; approved by the owner the same day (pronunciation notes removed at their request). The owner plans a later worldbuilding session on the peoples' physical details; the Provisional anatomy noted below is the input for that. Renamed 2026-10-16 on the owner's decision (bible 0.4.6): Kethari → Kell, Sylari → Drask, Aevyrin → Lirra, Naevari → Revari, Otheryn → Astrel, Neshyr → Selk. The ## headings must keep matching SPECIES_CHOICES, so this file only takes effect once Dev applies LR-LORE-0001 in the same merge.

Group headings (2026-10-17, LR-LORE-0002): the three `## ` headings that are not a people's name ("Ancestral peoples", "Descended from all three", "Engineered peoples") group the entries that follow them, each with a one-line note, so the picker can show the bible's classification (5, 5.8) instead of a flat list of seven names. `world/chargen.py` currently keeps only headings in SPECIES_CHOICES, so these are ignored until Dev applies LR-LORE-0002; nothing breaks meanwhile. The group wording is a reading of bible 5's opening paragraph, 5.4-5.8 and common-knowledge.md, no new facts. 2026-10-17 owner follow-ups: the property/citizenship line lives only in the Engineered group note, phrased so equality is not Elsewhere's invention (emancipation movements predate departure, bible 3, 4.4; "some" ships and settlements emancipated during the voyage and at Haven, 3, 6; Elsewhere's equal citizenship is a founding commitment, 11.2). Reworded again 2026-10-17 on the owner's decision (bible 0.4.8, 3 and 8): emancipation was complete everywhere before the Bloom, so the note says "ended generations ago, everywhere" and no longer names Elsewhere, which read as if Elsewhere alone had ended servitude. The three engineered entries no longer repeat it, and the preface's classification sentence is gone because Dev shows the group notes the first time the menu appears. Bible 18 forbids establishing that emancipation was complete at departure, and nothing here says so.

Only Established canon is used in the visible text. Where bible 5 marks anatomy as Provisional (Astrel build, Voldren build, Selk sharklike look, Lirra beak and flight structures, specific Revari traits), it is left out of the entry and noted in a comment under it, so the owner can decide whether to promote any of it. Wiring these into the chargen prompt is Dev-lane work.
-->

# The seven peoples

<!-- Optional shared preface; drop it if the picker only has room for per-entry text. -->

All seven peoples came to Prospect together, aboard the nine generation ships that left their shared home system long ago. On Elsewhere, every one of them holds the same citizenship. Your people shapes how you look, not who you are or what work you can take up.

## Ancestral peoples

The three original civilizations of the home system.

## Kell

Furred, canine-looking people who walk on the balls of their feet, with mobile, expressive ears and a wide range of coats and builds. One of the three ancestral peoples of the home system. Two Kell scientists were the first to discover the Venn–Saye field, and many Kell communities still hold that scientific tradition as a point of cultural pride.

<!-- Draft (bible 5.1 physical description, 2026-10-17; pending owner approval, then move this sentence into the entry above after the first sentence): "Most stand around two metres and are built long and lean, with a narrow muzzle, large leathery ears, a mane of long guard hairs down the spine and a full tail." The proposed starting-proficiency bonus is a mechanics question for the owner and Dev, not something this entry promises. -->

## Drask

Scaled people with a distinctly lizardlike face and elongated snout, on an otherwise upright body plan with fully capable hands. One of the three ancestral peoples of the home system. They need no special warmth or conditions, and share the same streets and rooms as everyone else.

<!-- Draft (bible 5.2 physical description, 2026-10-17; pending owner approval, then move this sentence into the entry above after the first sentence): "Broad and heavy, with larger scales shingled back from the brow, no outer ears, and a thick tail that reaches the ground." Once 5.2 is approved the third sentence rests on an established warm-blooded metabolism, not only on the design boundary. -->

## Lirra

Feathered, avian-influenced people, lighter in frame than the other ancestral peoples, with expressive plumage or crests. One of the three ancestral peoples of the home system.

<!-- Draft (bible 5.3 physical description, 2026-10-17; pending owner approval, then move this sentence into the entry above after the first sentence): "Flightless and light-boned, with a short blunt beak-like muzzle, a crest of long feathers over the head, feathered fringes along the arms and a long thin feathered tail." "Lighter in frame" in the entry is then backed by 5.3's build item. -->

## Descended from all three

A long-established people with ancestry from the Kell, Drask and Lirra alike.

## Revari

A long-established people whose ancestry draws on the Kell, Drask and Lirra alike. Most resemble the furred Kell in general build, but individuals carry varying inherited traits from all three lines, so no two families look quite the same. They are a people in their own right, not a mixture, and their name is their own.

<!-- Draft (bible 5.4 physical description, 2026-10-17; pending owner approval, then move this sentence into the entry above after the second sentence): "Those traits run in families: a patch of fine scales here, a feather crest or fringe there, a heavier tail or covered ears, never more than a few on one person." The origin of their cross-ancestry is unresolved and not mentioned. -->

## Engineered peoples

Made in the home system, long ago, for dangerous work in orbit, underground and underwater. Their ancestors were legally property there. That ended generations ago, everywhere.

## Astrel

Engineered in the home system for hazardous work in orbit and low gravity, such as construction and spacecraft maintenance, which earned them the old label "Void Walkers". Modern Astrel take up whatever work they choose.

<!-- Left out as Provisional in bible 5.5: tall or lanky build, long limbs, little or no hair, radiation resilience, possible discomfort in high gravity. If the owner wants one physical sentence here, "tall and long-limbed" is the least committal of those. -->

## Voldren

Engineered in the home system for mining, excavation and other dangerous work underground. The old label "Cave Crawlers" still follows them, and whether it is neutral or an insult depends very much on who is saying it. Modern Voldren work at whatever they choose, miners or not.

<!-- Left out as Provisional in bible 5.6: short, broad, powerful build, thick or leathery skin, recessed ears, hazard resistance. The label's society-wide meaning is unresolved (5.6, 5.8), which is why the entry says "depends on who is saying it" rather than settling it. -->

## Selk

Engineered in the home system for hazardous underwater work, such as deep construction, extraction and salvage, which earned them the old label "Sea Walkers". They breathe air and live in ordinary dry quarters alongside everyone else; the water was their work, never their home.

<!-- Left out as Provisional in bible 5.7: sharklike or shark-inspired look, webbed extremities or swimming tail, pressure and breath-holding adaptations. Air-breathing and dry accommodation are a settled constraint, so they stay in. -->
