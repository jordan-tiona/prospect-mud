"""
Phase 1 prototype world builder.

Creates the six-room test neighborhood from design-bible section 13.6
(Lift Concourse, Old Quarter Square, Corner Cafe, Maintenance Workshop,
Residential Courtyard, Civic Office), connected hub-and-spoke with Old
Quarter Square as the hub, per that section's "connecting the other
rooms" language.

Room descriptions are TODO(lore) stubs quoting only the bible's stated
room *role* (not invented prose) until the project owner authors real
descriptions.

The hub-and-spoke exit topology is an inference, not settled canon: the
bible gives each room a role but no map. Flagged in CLAUDE.md-facing
docs as a to-revise item.

Idempotent: safe to re-run. Existing rooms/exits (matched by tag) are
left alone rather than duplicated.

Run with:
    evennia shell -c "from world.build_rooms import build; build()"
"""

from evennia import create_object, search_tag

BUILD_TAG_CATEGORY = "phase1_neighborhood"

ROOMS = [
    (
        "lift_concourse",
        "Lift Concourse",
        "TODO(lore): placeholder description. Role (design bible 13.6): "
        "arrival point from the axial dock-to-rim elevator; passersby and "
        "notices.",
    ),
    (
        "old_quarter_square",
        "Old Quarter Square",
        "TODO(lore): placeholder description. Role (design bible 13.6): "
        "small public hub, connecting the other rooms beneath the axial "
        "light.",
    ),
    (
        "corner_cafe",
        "Corner Cafe",
        "TODO(lore): placeholder description. Role (design bible 13.6): "
        "a place for informal dialogue with a cafe owner.",
    ),
    (
        "maintenance_workshop",
        "Maintenance Workshop",
        "TODO(lore): placeholder description. Role (design bible 13.6): "
        "work setting for an infrastructure technician.",
    ),
    (
        "residential_courtyard",
        "Residential Courtyard",
        "TODO(lore): placeholder description. Role (design bible 13.6): "
        "quiet neighborhood public space and casual encounters.",
    ),
    (
        "civic_office",
        "Civic Office",
        "TODO(lore): placeholder description. Role (design bible 13.6): "
        "everyday public-service setting for civic conversations and a "
        "volunteer.",
    ),
]

HUB = "old_quarter_square"

# (spoke_tag, exit key/aliases from hub -> spoke, exit key/aliases from spoke -> hub)
SPOKES = [
    ("lift_concourse", ("lift concourse", ["lift", "concourse"]), ("old quarter square", ["square"])),
    ("corner_cafe", ("corner cafe", ["cafe"]), ("old quarter square", ["square"])),
    ("maintenance_workshop", ("maintenance workshop", ["workshop"]), ("old quarter square", ["square"])),
    ("residential_courtyard", ("residential courtyard", ["courtyard"]), ("old quarter square", ["square"])),
    ("civic_office", ("civic office", ["office"]), ("old quarter square", ["square"])),
]


def _get_or_create_room(tag, name, desc):
    matches = search_tag(key=tag, category=BUILD_TAG_CATEGORY)
    if matches:
        return matches[0]
    room = create_object("typeclasses.rooms.Room", key=name)
    room.db.desc = desc
    room.tags.add(tag, category=BUILD_TAG_CATEGORY)
    return room


def _get_or_create_exit(source, destination, key, aliases):
    for exi in source.exits:
        if exi.destination == destination and exi.key == key:
            return exi
    return create_object(
        "typeclasses.exits.Exit",
        key=key,
        aliases=aliases,
        location=source,
        destination=destination,
    )


def build():
    rooms = {}
    for tag, name, desc in ROOMS:
        room = _get_or_create_room(tag, name, desc)
        rooms[tag] = room
        print(f"Room ready: {room.key} ({room.dbref})")

    hub_room = rooms[HUB]
    for spoke_tag, (hub_to_spoke_key, hub_to_spoke_aliases), (spoke_to_hub_key, spoke_to_hub_aliases) in SPOKES:
        spoke_room = rooms[spoke_tag]
        _get_or_create_exit(hub_room, spoke_room, hub_to_spoke_key, hub_to_spoke_aliases)
        _get_or_create_exit(spoke_room, hub_room, spoke_to_hub_key, spoke_to_hub_aliases)
        print(f"Exits ready: {hub_room.key} <-> {spoke_room.key}")

    print("Done. Old Quarter Square dbref:", hub_room.dbref)
    return rooms
