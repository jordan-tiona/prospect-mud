# Progression ideas (parking lot)

Status: **ideas only, nothing decided.** Captured 2026-10-16 from a design conversation, for the project owner to pick up later. Progression, classes and skills are Unresolved in the bible (`docs/bible/s13-14-gameplay-and-npc-design.md`) and out of scope for the playtest (`docs/prospect-initial-playtest-design-spec.md`). Anything adopted goes into the bible through the Lore lane, not into code first.

## Leading candidate: profession levels plus teachable general skills

Inspired by IRE MUDs (Achaea, Starmourn). There, a class and level unlock skills, but advancing a skill means spending lessons with a teacher who is skilled enough.

- **Profession.** Level-based: standard stat increases and ability unlocks. Gives clear milestones and something to balance group content against.
- **General skills.** Anyone can learn them, e.g. using Fieldworks devices of different types. They advance by **training with someone** or **by use**.
- **Dynamicists** could be a profession with a gate (genetic adaptation plus extensive schooling, per bible 15). Their details are Provisional/Unresolved: owner's call.

Why it fits the bible as written:

- Elsewhere is a hub with "training, services, profession entry points" (bible 11).
- Fieldworks needs "the requisite tool and training", for any class (bible 13/15).
- The onboarding direction is "learn about professions before choosing" (bible 13).
- Species don't determine class (bible 5/13): general skills keep "anyone can learn this" structural.

Open questions:

1. **Training versus use.** Suggestion: use gets a skill to competent, and only a teacher takes it further. This limits macroing (scripted grinding stalls at the cap) and keeps teachers valuable.
2. **Where lessons come from.** Levels, quests, in-world work. Avoid IRE's sale of lessons for real money (widely criticised as pay-to-win).
3. **Engine-validated teaching.** A `teach_skill` action checks the teacher's tier, the student's prerequisites and a fixed lesson cost (CLAUDE.md hard rules 2 and 3: NPCs never set prices or invent what they can teach). The NPC supplies only the persona. A teacher NPC also serves as a passive discoverability cue (CLAUDE.md "Quest/commitment discoverability").
4. **Player teachers**, as in IRE. Good social glue. Later, but don't rule it out in the data model.
5. **Changing profession:** locked, switchable at a cost, or multiple professions (Achaea allows several classes).
6. **Scope.** Two progression systems is a lot for a solo project. Suggested order: general skills with NPC trainers first (less balance work, uses the LLM NPCs best), professions once there's play data.

## Other options discussed

1. **Pure skills (classless), Ultima Online style.** Fits "anyone can become anything".
   - Needs a total skill cap so characters keep an identity.
   - Gains only from meaningful challenges, to resist bots.
   - Per-skill ranks or titles for a sense of milestones.
2. **Tool-family proficiency**, after No Rest For The Wicked's weapon-based "classes" (going by the owner's description); Albion Online is a precedent.
   - Your abilities come from the tool you're holding, and using it advances that tool family and unlocks perks.
   - Fits Fieldworks' equipment-based framing (bible 15's examples are tools).
   - Should cover non-combat tools (repair, medical, the gardening kit), not just weapons.
   - Proficiency should persist per family when you switch, plus a few cross-cutting perks so identity isn't just "what I'm holding".
   - Dynamicist catalysts would be the one thing you can't just pick up.
   - The playtest's lent shock baton would be a natural first proficiency moment.
   - Could also serve as the general-skills half of the leading candidate.
3. **Traditional classes and levels.** Simplest to balance. Fits the setting least: the bible's Fieldworks framing is explicitly cross-class.

## Housekeeping if a classless or hybrid option is chosen

Several Established bible lines say "class" (Fieldworks usable "by any class", "across classes"). Lore should decide whether these mean "profession" and reword them.
