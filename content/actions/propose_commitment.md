<!--
How propose_commitment works, for every NPC that has it. Engine mechanics in prompt form (Dev lane): world/prompt_builder.py adds this file only for NPCs whose `actions` list it. The errand itself - its `commitment_type`, what it's about, and when it comes up - stays in the persona's `## Actions` bullet. Check docs/npc-action-prompt-guidelines.md (#10, #11, #12, #19) before changing it.
-->

- Only call it when the errand's state is `"not offered"`, and only with the `commitment_type` your own bullet names - never any other value.
- Describing the problem *is* the offer. The moment you decide to mention the errand to this player at all - even just explaining what's wrong, before you've asked them anything - call this in that same turn. Don't split "telling them about it" and "making the offer" into two replies.
