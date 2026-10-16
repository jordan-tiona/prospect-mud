"""
Phase 2D's civic information display (docs/phase2-quest-prototype-
design.md §14): one typeclasses.objects.RevisionDisplayObject in the
café, visible to everyone - only its examined content is per-player
(see that class and world/noticeboard.py).

Since MUD Editor Step C (docs/build-sector-proposal.md) this is a thin
wrapper: the layout lives in sectors/elsewhere/sector.json, the prose in
content/, and both reach the game through the exported manifest
(prospect/world/data/sectors/elsewhere.json) via world.build_sector.
Edit them in the editor / content files and re-export - not here.

Idempotent: safe to re-run.

Run with:
    evennia shell -c "from world.build_noticeboard import build; build()"
"""

from world.build_sector import build_for_wrapper

NOTICEBOARD_TAG_CATEGORY = "noticeboard_prop"
DISPLAY_PROP_ID = "civic_information_display"


def build():
    """Build/update the display. Returns it."""
    return build_for_wrapper({"revision_display"})[DISPLAY_PROP_ID]
