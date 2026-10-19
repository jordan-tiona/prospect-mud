<!--
How accept_commitment works, for every NPC that has it. Engine mechanics in prompt form (Dev lane): world/prompt_builder.py adds this file only for NPCs whose `actions` list it. What agreeing looks like for a particular errand, and what happens after, stays in the persona's `## Actions` bullet. Check docs/npc-action-prompt-guidelines.md (#10, #21) before changing it.
-->

- Record that the player has actually, personally committed to the errand - the same test as any promise: did *they* say, in their own words, that *they* will? A plain "sure, I'll do it" is enough on its own. A question, a maybe, or sounding interested is not agreeing.
- Only valid while the state is `"offered, awaiting the player's answer"`, and only with your errand's `commitment_type`.
- Don't narrate handing anything over yourself. If something is handed over, that happens once the call succeeds.
