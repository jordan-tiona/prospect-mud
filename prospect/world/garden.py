"""
Quest 2 ("A Little Community Work" - docs/prospect-initial-playtest-
design-spec.md §6): the per-player fact that a given player has used a
gardening kit on Old Quarter Square's planting bed. Mirrors world/
noticeboard.py's shape (a plain stored fact the model never computes
itself, only confirms or checks against) - but unlike the display's
revision number, there's nothing to guess here, so this is a plain
boolean, not a generated value.

CLAUDE.md hard rule 2 applies: the actual completion fact lives here, in
Python, set only by commands/use.py's engine-validated world action
(never by an NPC tool call or anything the model proposes) - Iri's own
`confirm_bed_tended` action (world/actions.py) only ever reads it.
"""

BED_TENDED_KEY = "garden_bed_tended"


def mark_bed_tended(actor) -> None:
    actor.attributes.add(BED_TENDED_KEY, True)


def is_bed_tended(actor) -> bool:
    return bool(actor.attributes.get(BED_TENDED_KEY, default=False))


def reset_bed_tended(actor) -> bool:
    """Builder-only reset: clears this player's tended flag so a
    retest starts from a genuinely untended bed. Returns the previous
    value (for the admin command to report) - mirrors world/
    noticeboard.py's reset_expected_revision. Not previously wired into
    `resetcommitment`, which left a tester's old tended flag in place
    across a reset - the same gap this module's own sibling fix for
    world/skitters.py's kill counter closes."""
    previous = bool(actor.attributes.get(BED_TENDED_KEY, default=False))
    actor.attributes.remove(BED_TENDED_KEY)
    return previous
