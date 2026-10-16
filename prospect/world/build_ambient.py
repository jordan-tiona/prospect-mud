"""
Loads approved content-pipeline files (see
https://claude.ai/artifact/94ujHRXZNTcD82m14XrjDw) into the live
world: a room's `## Glance` / `## Description` onto an already-built
room (world/build_rooms.py), and ambient NPCs/objects as new
objects placed in their room.

Only `approval: Approved` files are applied; a `Draft` file is
skipped (reported, not built) so an in-progress draft can sit in
content/ without affecting the live game.

Idempotent: safe to re-run. Ambient NPCs/objects are matched by a tag
(their content id), so re-running updates the existing object instead
of duplicating it.

Run with:
    evennia shell -c "from world.build_ambient import apply_all_room_content; apply_all_room_content()"
    evennia shell -c "from world.build_ambient import build_ambient_entities; build_ambient_entities()"
"""

from evennia import create_object, search_tag

from world.ambient_content import parse_ambient_npc, parse_ambient_object
from world.build_rooms import BUILD_TAG_CATEGORY as ROOM_TAG_CATEGORY
from world.room_content import parse_room

AMBIENT_TAG_CATEGORY = "phase1_ambient"

# Old Quarter Square's ambient entities were trimmed after playtesting
# the first pass (five listed entries read as more text than the
# room's own description) to the project owner's density rule: at most
# ~2-3 always-listed entries per room - things with a navigation/
# gameplay role (signage, quest-relevant objects) plus at most one
# ambient NPC for life. Pure atmosphere (the benches, the planting
# beds) was folded into the room's own `## Description` prose instead
# of staying as separate listed objects - their drafted text is still
# in content/ambient/objects/square_{benches,planting_beds}.md, just
# not built here. The square's courier was moved to the Lift Concourse
# (concourse_otheryn_courier) rather than kept as a separate draft.
AMBIENT_NPC_IDS = [
    "square_elderly_kethari",
    "concourse_otheryn_courier",
    "courtyard_neshyr_neighbor",
]
AMBIENT_OBJECT_IDS = [
    "square_noticeboard",
    "concourse_arrival_directory",
    "workshop_parts_tray",
    "civic_services_board",
]

# All six prototype rooms (world/build_rooms.py), for batch application of
# their content files' `## Glance`/`## Description` once approved.
ROOM_IDS = [
    "old_quarter_square",
    "lift_concourse",
    "corner_cafe",
    "maintenance_workshop",
    "residential_courtyard",
    "civic_office",
    "medical_bay",
    "old_quarter_street",
    "daven_office",
]


def _room_by_tag(room_tag):
    matches = search_tag(key=room_tag, category=ROOM_TAG_CATEGORY)
    if not matches:
        raise RuntimeError(
            f"No room tagged '{room_tag}' - run world.build_rooms.build() first."
        )
    return matches[0]


def apply_room_content(room_id):
    """Apply a room content file's `## Glance`/`## Description` onto
    the already-built room with that tag. Skipped (not built) if the
    file isn't approved yet."""
    content = parse_room(room_id)
    if content.approval != "Approved":
        print(f"Skipped room '{room_id}': approval is '{content.approval}', not Approved.")
        return None

    room = _room_by_tag(content.room_id)
    room.db.desc = content.desc
    room.db.glance = content.glance
    print(f"Room content applied: {room.key} ({room.dbref})")
    return room


def _get_or_create_ambient_npc(ambient_id):
    content = parse_ambient_npc(ambient_id)
    if content.approval != "Approved":
        print(f"Skipped ambient NPC '{ambient_id}': approval is '{content.approval}', not Approved.")
        return None

    room = _room_by_tag(content.room)
    matches = search_tag(key=ambient_id, category=AMBIENT_TAG_CATEGORY)
    npc = matches[0] if matches else create_object("typeclasses.npcs.NPC", key=content.key, location=room)
    npc.key = content.key
    npc.location = room
    npc.db.desc = content.desc
    npc.set_ambient_poses(content.poses)
    npc.tags.add(ambient_id, category=AMBIENT_TAG_CATEGORY)
    print(f"Ambient NPC ready: {npc.key} ({npc.dbref}) in {room.key}")
    return npc


def _get_or_create_ambient_object(object_id):
    content = parse_ambient_object(object_id)
    if content.approval != "Approved":
        print(f"Skipped ambient object '{object_id}': approval is '{content.approval}', not Approved.")
        return None

    room = _room_by_tag(content.room)
    matches = search_tag(key=object_id, category=AMBIENT_TAG_CATEGORY)
    obj = (
        matches[0]
        if matches
        else create_object("typeclasses.objects.RoomObject", key=content.key, location=room)
    )
    obj.key = content.key
    obj.location = room
    obj.db.room_line = content.short_desc
    obj.db.desc = content.desc
    obj.tags.add(object_id, category=AMBIENT_TAG_CATEGORY)
    print(f"Ambient object ready: {obj.key} ({obj.dbref}) in {room.key}")
    return obj


def build_ambient_entities():
    """Build/update all approved ambient NPCs and objects listed above."""
    npcs = [_get_or_create_ambient_npc(ambient_id) for ambient_id in AMBIENT_NPC_IDS]
    objects = [_get_or_create_ambient_object(object_id) for object_id in AMBIENT_OBJECT_IDS]
    return [obj for obj in npcs + objects if obj is not None]


def apply_all_room_content():
    """Apply every approved room's content file onto its already-built
    room, listed above. Skipped (not built) rooms are reported, not
    built, same as apply_room_content()."""
    return [room for room_id in ROOM_IDS if (room := apply_room_content(room_id)) is not None]
