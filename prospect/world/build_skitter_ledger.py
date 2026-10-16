"""
The Civic Office's skitter log (project owner, 2026-10-16): the visible
half of the post-quest skitter loop. Each player sees their own logged
total on `look`/`read` (typeclasses.objects.SkitterLedgerObject); the
number only goes up when Iri logs a report (world/actions.py's
log_dead_skitters_with_iri).

Since MUD Editor Step C (docs/build-sector-proposal.md) this is a thin
wrapper: the layout lives in sectors/elsewhere/sector.json, the prose in
content/, and both reach the game through the exported manifest
(prospect/world/data/sectors/elsewhere.json) via world.build_sector.
Edit them in the editor / content files and re-export - not here.

Idempotent: safe to re-run.

Run with:
    evennia shell -c "from world.build_skitter_ledger import build; build()"
"""

from world.build_sector import build_for_wrapper

LEDGER_TAG_CATEGORY = "skitter_ledger_prop"
LEDGER_PROP_ID = "civic_office_skitter_ledger"


def build():
    """Build/update the pest log. Returns it."""
    return build_for_wrapper({"skitter_ledger"})[LEDGER_PROP_ID]
