"""
Quest 2 world objects ("A Little Community Work" - docs/prospect-
initial-playtest-design-spec.md §6): a gettable typeclasses.objects.
GardeningKit in the Residential Courtyard and a typeclasses.objects.
PlantingBed fixture in Old Quarter Square, the commands/use.py target.

A kit a player is carrying is left with them on a rebuild (Dev review,
docs/build-sector-proposal.md Section 8) - the old script took it back.

Since MUD Editor Step C (docs/build-sector-proposal.md) this is a thin
wrapper: the layout lives in sectors/elsewhere/sector.json, the prose in
content/, and both reach the game through the exported manifest
(prospect/world/data/sectors/elsewhere.json) via world.build_sector.
Edit them in the editor / content files and re-export - not here.

Idempotent: safe to re-run.

Run with:
    evennia shell -c "from world.build_garden_props import build; build()"
"""

from world.build_sector import build_for_wrapper

GARDEN_PROP_TAG_CATEGORY = "garden_prop"


def build():
    """Build/update the kit and the bed. Returns {"gardening_kit": kit, "planting_bed": bed}."""
    return build_for_wrapper({"gardening_kit", "planting_bed"})
