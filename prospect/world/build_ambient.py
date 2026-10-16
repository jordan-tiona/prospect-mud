"""
Approved room prose (each room's `## Glance` / `## Description`) and
the ambient (non-LLM) NPCs and objects placed in rooms.

Only Approved content reaches the game: export refuses a sector whose
placed content isn't Approved (docs/mud-editor-sector-format.md Section 6),
so there's no per-file skip here any more.

Since MUD Editor Step C (docs/build-sector-proposal.md) this is a thin
wrapper: the layout lives in sectors/elsewhere/sector.json, the prose in
content/, and both reach the game through the exported manifest
(prospect/world/data/sectors/elsewhere.json) via world.build_sector.
Edit them in the editor / content files and re-export - not here.

Idempotent: safe to re-run.

Run with:
    evennia shell -c "from world.build_ambient import apply_all_room_content; apply_all_room_content()"
    evennia shell -c "from world.build_ambient import build_ambient_entities; build_ambient_entities()"
"""

from world.build_sector import build_for_wrapper

AMBIENT_TAG_CATEGORY = "phase1_ambient"


def apply_room_content(room_id):
    """Apply one room's prose (rooms are built from the manifest, prose included). Returns the room."""
    return build_for_wrapper(set())[room_id]


def apply_all_room_content():
    """Apply every room's prose. Returns the list of rooms."""
    return list(build_for_wrapper(set()).values())


def build_ambient_entities():
    """Build/update every ambient NPC and object. Returns the list of objects."""
    return list(build_for_wrapper({"ambient_npc", "ambient_object"}).values())
