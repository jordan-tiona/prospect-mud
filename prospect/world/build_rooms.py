"""
Old Quarter neighborhood world builder.

Creates the original six-room test neighborhood from design-bible
section 13.6 (Lift Concourse, Old Quarter Square, Corner Café,
Maintenance Workshop, Residential Courtyard, Civic Office), connected
hub-and-spoke with Old Quarter Square as the hub, per that section's
"connecting the other rooms" language - plus the three rooms added
for the initial playtest (docs/prospect-initial-playtest-design-
spec.md): Medical Bay, Old Quarter Street, and Daven's Office.

Room descriptions are TODO(lore) stubs quoting only the bible's stated
room *role* (not invented prose) until the project owner authors real
descriptions.

The hub-and-spoke exit topology is an inference, not settled canon: the
bible gives each room a role but no map. Exits use standard MUD
cardinal directions (north/south/east/west) plus up/down (see SPOKES
below for the compass arrangement and why the Lift Concourse sits on
up/down instead) - the project owner's preferred movement style over
this builder's original named-exit scheme (cafe/workshop/square/etc).

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
        "Corner Café",
        "TODO(lore): placeholder description. Role (design bible 13.6): "
        "a place for informal dialogue with a café owner.",
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
    (
        "medical_bay",
        "Medical Bay",
        "TODO(lore): placeholder description. Role (initial playtest spec "
        "docs/prospect-initial-playtest-design-spec.md 3): player's first "
        "fully conscious location, reached from the Lift Concourse; "
        "Given Marr's workplace.",
    ),
    (
        "old_quarter_street",
        "Old Quarter Street",
        "TODO(lore): placeholder description. Role (initial playtest spec "
        "docs/prospect-initial-playtest-design-spec.md 4-5): a short "
        "street off Old Quarter Square, leading to Daven Varek's office. "
        "Working room name pending approval.",
    ),
    (
        "daven_office",
        "Daven's Office",
        "TODO(lore): placeholder description. Role (initial playtest spec "
        "docs/prospect-initial-playtest-design-spec.md 4): Daven Varek's "
        "office, reached from Old Quarter Street.",
    ),
]

HUB = "old_quarter_square"

# (spoke_tag, exit key/aliases from hub -> spoke, exit key/aliases from spoke -> hub)
#
# Standard MUD cardinal-direction movement, including the two
# diagonals added for the initial playtest (project owner's call,
# 2026-10-14): the four ground-level cardinals and up were already
# spoken for by the original six rooms, so the Lift Concourse moved
# from up/down onto northeast/southwest (it's envisioned as the base
# of the elevator up to the low/no-gravity docking area, so "up" no
# longer describes reaching it from the square) and Old Quarter Street
# took the opposite diagonal, southwest/northeast.
SPOKES = [
    ("lift_concourse", ("northeast", ["ne"]), ("southwest", ["sw"])),
    ("corner_cafe", ("north", ["n"]), ("south", ["s"])),
    ("maintenance_workshop", ("east", ["e"]), ("west", ["w"])),
    ("residential_courtyard", ("south", ["s"]), ("north", ["n"])),
    ("civic_office", ("west", ["w"]), ("east", ["e"])),
    ("old_quarter_street", ("southwest", ["sw"]), ("northeast", ["ne"])),
]

# Secondary connections: a spoke off another spoke room, not the hub
# itself. Built after the hub spokes above (see `build()`), by then
# both rooms already exist.
#
# (from_tag, to_tag, exit key/aliases from -> to, exit key/aliases to -> from)
CHAINS = [
    ("lift_concourse", "medical_bay", ("up", ["u"]), ("down", ["d"])),
    ("old_quarter_street", "daven_office", ("north", ["n"]), ("south", ["s"])),
]


def _get_or_create_room(tag, name, desc):
    matches = search_tag(key=tag, category=BUILD_TAG_CATEGORY)
    if matches:
        room = matches[0]
        if room.key != name:
            room.key = name
        return room
    room = create_object("typeclasses.rooms.Room", key=name)
    room.db.desc = desc
    room.tags.add(tag, category=BUILD_TAG_CATEGORY)
    return room


def _get_or_create_exit(source, destination, key, aliases):
    for exi in source.exits:
        if exi.destination == destination:
            if exi.key != key:
                exi.key = key
            if sorted(exi.aliases.all()) != sorted(aliases):
                exi.aliases.clear()
                exi.aliases.add(aliases)
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

    for from_tag, to_tag, (fwd_key, fwd_aliases), (back_key, back_aliases) in CHAINS:
        from_room = rooms[from_tag]
        to_room = rooms[to_tag]
        _get_or_create_exit(from_room, to_room, fwd_key, fwd_aliases)
        _get_or_create_exit(to_room, from_room, back_key, back_aliases)
        print(f"Exits ready: {from_room.key} <-> {to_room.key}")

    print("Done. Old Quarter Square dbref:", hub_room.dbref)
    return rooms
