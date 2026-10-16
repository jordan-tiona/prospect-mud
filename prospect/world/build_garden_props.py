"""
Quest 2 world objects ("A Little Community Work" - docs/prospect-
initial-playtest-design-spec.md §6): a gettable typeclasses.objects.
GardeningKit in the Residential Courtyard (by the communal equipment
locker/shed the spec describes - deliberately not its own separate
object, per the spec's "smallest way to make the relevant bed
targetable without bloating the room listing") and a typeclasses.
objects.PlantingBed fixture in Old Quarter Square, the commands/use.py
target.

Idempotent: safe to re-run. Existing objects (matched by tag) are
updated in place rather than duplicated.

Run with:
    evennia shell -c "from world.build_garden_props import build; build()"
"""

from evennia import create_object, search_tag

from world.build_rooms import BUILD_TAG_CATEGORY as ROOM_TAG_CATEGORY

GARDEN_PROP_TAG_CATEGORY = "garden_prop"


def _get_room(room_tag):
    matches = search_tag(key=room_tag, category=ROOM_TAG_CATEGORY)
    if not matches:
        raise RuntimeError(f"Room tagged '{room_tag}' not found. Run world.build_rooms.build() first.")
    return matches[0]


def _get_or_create(prop_id, typeclass, key, room, desc, room_line=None, aliases=None):
    matches = search_tag(key=prop_id, category=GARDEN_PROP_TAG_CATEGORY)
    if matches:
        prop = matches[0]
        if prop.location != room:
            prop.move_to(room, quiet=True)
        prop.db.desc = desc
        if room_line is not None:
            prop.db.room_line = room_line
        if aliases:
            prop.aliases.add(aliases)
        return prop

    prop = create_object(typeclass, key=key, location=room)
    prop.db.desc = desc
    if room_line is not None:
        prop.db.room_line = room_line
    if aliases:
        prop.aliases.add(aliases)
    prop.tags.add(prop_id, category=GARDEN_PROP_TAG_CATEGORY)
    return prop


def build():
    props = {}

    courtyard = _get_room("residential_courtyard")
    props["gardening_kit"] = _get_or_create(
        "gardening_kit",
        "typeclasses.objects.GardeningKit",
        "a gardening kit",
        courtyard,
        # Copy of content/objects/gardening_kit.md (owner-approved,
        # LR-TOOLS-0001) until world.build_sector reads the manifest.
        "A worn gardening kit from the courtyard's communal equipment locker: a hand trowel, a pair of "
        "shears, and a few lengths of twine, left out where anyone who needs them can take them.",
        room_line="A gardening kit sits here, free for anyone to use.",
        aliases=["kit", "gardening kits"],
    )
    print(f"Garden prop ready: {props['gardening_kit'].key} ({props['gardening_kit'].dbref}) in {courtyard.key}")

    square = _get_room("old_quarter_square")
    props["planting_bed"] = _get_or_create(
        "planting_bed",
        "typeclasses.objects.PlantingBed",
        "a planting bed",
        square,
        # Draft (same workflow/caveat as the kit above). Singular on
        # purpose - there's only this one PlantingBed object in the
        # square, so "one of the square's... beds" (the original
        # wording) implied siblings that don't exist. Fixed after the
        # project owner caught it in playtest (2026-10-14).
        "The square's planting bed: a shallow trough of soil, overgrown with weeds and badly "
        "in need of tending.",
        room_line="A planting bed sits here, overgrown and badly needing attention.",
        aliases=["bed", "planting beds", "beds"],
    )
    print(f"Garden prop ready: {props['planting_bed'].key} ({props['planting_bed'].dbref}) in {square.key}")

    return props
