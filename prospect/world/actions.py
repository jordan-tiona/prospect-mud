"""
Tool layer and validator (design-bible 16.5; CLAUDE.md hard rule 2).

The model can only *propose* an action by name plus arguments; it
never changes game state directly. `validate_and_apply` is the one
place that checks a proposal against authoritative state (the NPC's
declared permissions, stock, the real room graph) and either applies
it or drops it. Dropped calls are never "fixed up" into something
valid - the caller (step 7's talk command) narrates the drop as the
NPC being unable to help, not as a corrected action.

Phase 1 gives each prototype NPC exactly one action, per design-bible
13.5: `serve_drink` (Mara), `hand_over_item` (Tarin), `give_directions`
(Iri).
"""

from dataclasses import dataclass

from world.build_rooms import BUILD_TAG_CATEGORY as ROOM_TAG_CATEGORY
from world.build_rooms import ROOMS as NEIGHBORHOOD_ROOMS
from world.npc_profile import parse_persona


@dataclass
class ActionResult:
    applied: bool
    # Shown to the player as the narrated outcome of a valid action
    # (design-bible 16.5 step 4). Empty when the call was dropped.
    narration: str
    # Why a call was dropped. For logs/debugging, not necessarily
    # shown to the player verbatim.
    reason: str = ""


def validate_and_apply(npc, actor, action_name: str, arguments: dict) -> ActionResult:
    """
    The engine validator. Checks that `action_name` is one of this
    NPC's declared permitted actions before running its specific
    validator, so an NPC can't be talked into an action its persona
    never granted it.
    """
    arguments = arguments or {}

    profile = parse_persona(npc.db.npc_id)
    if action_name not in profile.actions:
        return ActionResult(
            applied=False,
            narration="",
            reason=f"'{action_name}' is not a permitted action for {profile.npc_id}.",
        )

    validator = _ACTION_VALIDATORS.get(action_name)
    if validator is None:
        return ActionResult(
            applied=False,
            narration="",
            reason=f"No validator implemented for action '{action_name}'.",
        )

    return validator(npc, actor, arguments)


def _validate_serve_drink(npc, actor, arguments: dict) -> ActionResult:
    drink_type = arguments.get("drink_type")
    if drink_type not in ("hot", "cold"):
        return ActionResult(False, "", reason=f"invalid drink_type: {drink_type!r}")
    return ActionResult(True, f"{npc.key} serves {actor.key} a {drink_type} drink.")


def _validate_hand_over_item(npc, actor, arguments: dict) -> ActionResult:
    item_type = arguments.get("item_type")
    if item_type not in ("spare part", "hand tool"):
        return ActionResult(False, "", reason=f"invalid item_type: {item_type!r}")

    stock = npc.db.stock
    if stock is None:
        stock = {"spare part": 3, "hand tool": 3}

    if stock.get(item_type, 0) <= 0:
        npc.db.stock = stock
        return ActionResult(False, "", reason=f"out of stock: {item_type}")

    stock[item_type] -= 1
    npc.db.stock = stock
    return ActionResult(True, f"{npc.key} hands {actor.key} a {item_type}.")


def _find_neighborhood_room(destination_name: str):
    """Match free-text destination against the six known rooms, by
    display name, case-insensitively. Returns the room object, or
    None if it's not one of the six (per persona: "Don't describe
    routes to places outside this neighborhood")."""
    from evennia import search_tag

    destination_name = (destination_name or "").strip().lower()
    for tag, name, _desc in NEIGHBORHOOD_ROOMS:
        if name.lower() == destination_name:
            matches = search_tag(key=tag, category=ROOM_TAG_CATEGORY)
            return matches[0] if matches else None
    return None


def _find_exit_path(start_room, target_room, max_depth=4):
    """
    BFS over the *actual* exits between rooms (not an assumed map),
    so directions reflect authoritative state. Returns a list of exit
    keys to follow, [] if already there, or None if unreachable
    within max_depth.
    """
    if start_room == target_room:
        return []

    visited = {start_room}
    frontier = [(start_room, [])]
    while frontier:
        next_frontier = []
        for room, path in frontier:
            if len(path) >= max_depth:
                continue
            for exi in room.exits:
                dest = exi.destination
                if dest is None or dest in visited:
                    continue
                new_path = path + [exi.key]
                if dest == target_room:
                    return new_path
                visited.add(dest)
                next_frontier.append((dest, new_path))
        frontier = next_frontier
    return None


def _validate_give_directions(npc, actor, arguments: dict) -> ActionResult:
    destination_name = arguments.get("destination", "")
    target_room = _find_neighborhood_room(destination_name)
    if target_room is None:
        return ActionResult(False, "", reason=f"destination not in neighborhood: {destination_name!r}")

    start_room = actor.location
    if start_room is None:
        return ActionResult(False, "", reason="actor has no location")

    path = _find_exit_path(start_room, target_room)
    if path is None:
        return ActionResult(False, "", reason=f"no known path from {start_room} to {target_room}")

    if not path:
        return ActionResult(True, f"{npc.key} says you're already there.")

    route_text = ", then ".join(f'take "{step}"' for step in path)
    return ActionResult(True, f"{npc.key} explains the way: {route_text}.")


_ACTION_VALIDATORS = {
    "serve_drink": _validate_serve_drink,
    "hand_over_item": _validate_hand_over_item,
    "give_directions": _validate_give_directions,
}


# OpenAI-style tool/function definitions, offered to the model so it
# can *propose* an action by name. This is the only part of the tool
# layer the model ever sees; validate_and_apply() above is what
# actually decides whether a proposal does anything.
ACTION_SCHEMAS = {
    "serve_drink": {
        "type": "function",
        "function": {
            "name": "serve_drink",
            "description": "Serve the player a drink from the cafe's simple menu.",
            "parameters": {
                "type": "object",
                "properties": {
                    "drink_type": {
                        "type": "string",
                        "enum": ["hot", "cold"],
                        "description": "Whether to serve a hot drink or a cold drink.",
                    }
                },
                "required": ["drink_type"],
            },
        },
    },
    "hand_over_item": {
        "type": "function",
        "function": {
            "name": "hand_over_item",
            "description": "Hand the player an item from the workshop's small stock of spares.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_type": {
                        "type": "string",
                        "enum": ["spare part", "hand tool"],
                        "description": "Which kind of item to hand over.",
                    }
                },
                "required": ["item_type"],
            },
        },
    },
    "give_directions": {
        "type": "function",
        "function": {
            "name": "give_directions",
            "description": (
                "Give the player directions to one of the six rooms in this "
                "neighborhood (Lift Concourse, Old Quarter Square, Corner "
                "Cafe, Maintenance Workshop, Residential Courtyard, Civic "
                "Office). Do not use this for places outside the "
                "neighborhood - say you don't know instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "description": "The exact name of the destination room.",
                    }
                },
                "required": ["destination"],
            },
        },
    },
}


def get_tool_schemas(action_names: list) -> list:
    """Tool definitions for the action names an NPC's persona grants."""
    return [ACTION_SCHEMAS[name] for name in action_names if name in ACTION_SCHEMAS]
