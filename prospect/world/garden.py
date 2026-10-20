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


# The kit built in the Residential Courtyard is a supply, never picked up
# itself: `get kit` hands the player their own copy, flagged with this
# attribute (typeclasses.objects.GardeningKit.at_pre_get). One shared kit
# that a single player could carry off blocked the quest for everyone
# else - caught live 2026-10-19, with the only kit sitting in a
# character's inventory (engineering-pitfalls #16).
PERSONAL_KIT_KEY = "personal_kit"
GARDENING_KIT_TYPECLASS = "typeclasses.objects.GardeningKit"


def is_personal_kit(obj) -> bool:
    return bool(obj.attributes.get(PERSONAL_KIT_KEY, default=False))


def carried_kits(actor) -> list:
    return [obj for obj in actor.contents if obj.is_typeclass(GARDENING_KIT_TYPECLASS, exact=False)]


def give_personal_kit(supply, actor):
    """Create actor's own copy of the supply kit in their inventory.
    Tags aren't copied, so world.build_sector never mistakes a copy for
    the placed entity."""
    from evennia import create_object

    kit = create_object(
        GARDENING_KIT_TYPECLASS,
        key=supply.key,
        location=actor,
        home=supply.location,
        aliases=list(supply.aliases.all()),
        attributes=[("desc", supply.db.desc), (PERSONAL_KIT_KEY, True)],
    )
    return kit


def cleanup_personal_kits(actor) -> int:
    """Reset-path counterpart to give_personal_kit (engineering-pitfalls
    #4): deletes every personal kit the player carries. Returns how many
    were deleted. A supply kit somehow in their inventory is left alone,
    since world.build_sector reports it as held instead."""
    removed = 0
    for kit in carried_kits(actor):
        if is_personal_kit(kit):
            kit.delete()
            removed += 1
    return removed
