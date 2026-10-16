"""
Discoverable quest-prop objects: the project owner's discoverability
rule (2026-10-13) that every quest/commitment should have some passive,
in-world cue a player can stumble onto (CLAUDE.md, "Quest/commitment
discoverability").

Each prop is a typeclasses.objects.CommitmentHintObject - not pickable -
whose `view`/`search` locks are wired to a per-player lock func
(server/conf/lockfuncs.py's commitment_hint_visible(<commitment_type>),
or a quest's own lock func such as module_exchange_hint_visible), so
it's visible only to a looker who hasn't engaged with the errand yet.
No timer or respawn logic: it falls out of the lock check alone. The
lock string comes from the `quest_prop` kind in world/entity_kinds.py,
filled from each prop's params in the sector file.

Since MUD Editor Step C (docs/build-sector-proposal.md) this is a thin
wrapper: the layout lives in sectors/elsewhere/sector.json, the prose in
content/, and both reach the game through the exported manifest
(prospect/world/data/sectors/elsewhere.json) via world.build_sector.
Edit them in the editor / content files and re-export - not here.

Idempotent: safe to re-run.

Run with:
    evennia shell -c "from world.build_quest_props import build; build()"
"""

from world.build_sector import build_for_wrapper

QUEST_PROP_TAG_CATEGORY = "quest_prop"


def build():
    """Build/update every quest prop. Returns {prop_id: prop}."""
    return build_for_wrapper({"quest_prop"})
