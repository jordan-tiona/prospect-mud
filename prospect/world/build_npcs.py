"""
Talk-capable (LLM-voiced) NPCs, each with its `npc_id` pointer to
content/npcs/<npc_id>.md and its first name as an alias so players can
address it by that alone (world.npc_addressing).

Since MUD Editor Step C (docs/build-sector-proposal.md) this is a thin
wrapper: the layout lives in sectors/elsewhere/sector.json, the prose in
content/, and both reach the game through the exported manifest
(prospect/world/data/sectors/elsewhere.json) via world.build_sector.
Edit them in the editor / content files and re-export - not here.

Idempotent: safe to re-run. Existing NPCs (matched by tag) are updated
in place rather than duplicated.

Run with:
    evennia shell -c "from world.build_npcs import build; build()"
"""

from world.build_sector import build_for_wrapper

NPC_TAG_CATEGORY = "phase1_npcs"


def build():
    """Build/update every talk-capable NPC. Returns {npc_id: npc}."""
    return build_for_wrapper({"talk_npc"})
