"""
Elsewhere's rooms and exits (originally the six-room Old Quarter
test neighborhood from design-bible 13.6, plus the playtest's Medical
Bay, Old Quarter Street and Daven's Office).

Since MUD Editor Step C (docs/build-sector-proposal.md) this is a thin
wrapper: the layout lives in sectors/elsewhere/sector.json, the prose in
content/, and both reach the game through the exported manifest
(prospect/world/data/sectors/elsewhere.json) via world.build_sector.
Edit them in the editor / content files and re-export - not here.

Idempotent: safe to re-run. Existing rooms/exits (matched by tag) are
updated in place rather than duplicated.

Run with:
    evennia shell -c "from world.build_rooms import build; build()"
"""

from world.build_sector import build_for_wrapper

BUILD_TAG_CATEGORY = "phase1_neighborhood"


def build():
    """Build/update every room and exit. Returns {room_id: room}."""
    return build_for_wrapper(set())
