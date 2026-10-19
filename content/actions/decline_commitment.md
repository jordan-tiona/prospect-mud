<!--
How decline_commitment works, for every NPC that has it. Engine mechanics in prompt form (Dev lane): world/prompt_builder.py adds this file only for NPCs whose `actions` list it.
-->

- Record that the player has turned the errand down. Only valid while the state is `"offered, awaiting the player's answer"`, and only with your errand's `commitment_type`.
- Asking a question or changing the subject isn't a decline - don't call this on anything short of an actual "no."
- Nothing is owed afterward, and you're free to bring it up again another time.
