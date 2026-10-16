"""
Initial playtest signpost (docs/prospect-initial-playtest-design-
spec.md 4): a plain prop in Old Quarter Square pointing the way to
Daven's office. The route itself is computed by
typeclasses.objects.SignpostObject from the real exits; the static
spoke lines come from its content file.

Since MUD Editor Step C (docs/build-sector-proposal.md) this is a thin
wrapper: the layout lives in sectors/elsewhere/sector.json, the prose in
content/, and both reach the game through the exported manifest
(prospect/world/data/sectors/elsewhere.json) via world.build_sector.
Edit them in the editor / content files and re-export - not here.

Idempotent: safe to re-run.

Run with:
    evennia shell -c "from world.build_signpost import build; build()"
"""

from world.build_sector import build_for_wrapper

SIGNPOST_TAG_CATEGORY = "signpost_prop"
SIGNPOST_PROP_ID = "old_quarter_square_signpost"


def build():
    """Build/update the signpost. Returns it."""
    return build_for_wrapper({"signpost"})[SIGNPOST_PROP_ID]
