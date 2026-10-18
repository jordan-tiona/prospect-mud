"""
GMCP out-of-band messages (owner, 2026-10-18). Every GMCP message the
game sends goes through this module, so the package list in
docs/gmcp.md stays the whole story.

Evennia does the transport: a session.msg keyword `Room_Info` goes out
as GMCP `Room.Info` over telnet (portal/gmcp_utils.py turns
underscores into dots), and as an OOB message to the webclient. A
telnet client that didn't negotiate GMCP gets nothing.

Package names follow the common IRE/Mudlet ones, so client mapper and
status scripts written for other games need little change. GMCP is an
extra channel: nothing may reach a player only through it (same rule
as colour-only output, world/accessibility.py).

Messages go to the character's sessions directly rather than through
Character.msg, which is for text a character receives in the world.

Out-of-character interface data, not setting content.
"""

from collections.abc import Mapping

from world.entity_kinds import ROOM_KIND

SECTOR_TAG_CATEGORY = "sector"  # world/build_sector.py's tag for a room's sector

# Exit keys as the short direction names mapper scripts expect.
_SHORT_DIRECTIONS = {
    "north": "n", "south": "s", "east": "e", "west": "w",
    "northeast": "ne", "northwest": "nw", "southeast": "se", "southwest": "sw",
    "up": "u", "down": "d", "in": "in", "out": "out",
}


def _send(character, package, payload):
    """`package` is the GMCP name, e.g. "Room.Info"."""
    sessions = getattr(character, "sessions", None)
    if sessions is None:
        return
    cmdname = package.replace(".", "_")
    for session in sessions.all():
        session.msg(**{cmdname: ((), payload)})


def _map_coords(room):
    """db.map_coords as {"x", "y", "z"} ints, or None if unset or malformed.
    Grid units: x grows east, y grows north, z grows up (Mudlet's
    convention). Set by the sector build; see docs/gmcp.md."""
    coords = room.attributes.get("map_coords")
    if not isinstance(coords, Mapping):  # Evennia saves dicts as _SaverDict
        return None
    try:
        return {axis: int(coords[axis]) for axis in ("x", "y", "z")}
    except (KeyError, TypeError, ValueError):
        return None


def room_info(room, looker):
    """The Room.Info payload for `room` as `looker` sees it."""
    exits = {}
    for exit_obj in room.exits:
        if exit_obj.destination is None or not exit_obj.access(looker, "view"):
            continue
        direction = exit_obj.key.lower()
        exits[_SHORT_DIRECTIONS.get(direction, direction)] = exit_obj.destination.id
    payload = {
        "num": room.id,
        "id": room.tags.get(category=ROOM_KIND["tag_category"]) or "",
        "name": room.key,
        "area": room.tags.get(category=SECTOR_TAG_CATEGORY) or "",
        "environment": room.db.room_type or "",
        "exits": exits,
    }
    coords = _map_coords(room)
    if coords is not None:
        payload["coords"] = coords
    return payload


def send_room_info(character):
    room = character.location
    if room is None:
        return
    _send(character, "Room.Info", room_info(room, character))


def char_status(character):
    """The Char.Status payload. Fields chargen hasn't set yet are left out."""
    payload = {"name": character.key}
    species = character.db.species
    if species:
        payload["species"] = species
    return payload


def send_char_status(character):
    _send(character, "Char.Status", char_status(character))
