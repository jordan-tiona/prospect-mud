"""
Room

Rooms are simple containers that has no location of their own.

Overrides `return_appearance`'s display hooks (per CLAUDE.md's
preference for Evennia's own patterns over custom frameworks) to read
the way the project owner wants, after Achaea: a room's scenery
fixtures (typeclasses.objects.RoomObject) and background characters
(typeclasses.npcs.NPC and real players) are woven into the room's own
description as one-liner sentences, rather than Evennia's default
"You see: X and Y." / "Characters: X and Y." summary lines. The exits
line becomes a single natural-language sentence instead of
"Exits: ...".

Scenery that isn't meant to be interacted with stays as plain prose in
a room's own `desc` - these hooks only add sentences for *inspectable*
RoomObjects and present characters.

Color scheme (project owner's choice, Evennia markup - see
world/llm_client.py's sibling note in commands/say.py for the rest of
it): room name + exits = dark yellow (|Y), room description = gray
(|W), talk-capable NPCs + real players "is here" lines = bright cyan
(|c), ambient (non-LLM) NPCs + RoomObject one-liners = dark cyan (|C).

Two-tier room description (project owner's call, so walking around
doesn't bombard the player with full prose every step): `db.glance` is
a short (~25-40 word) blurb shown when a player walks into the room
(typeclasses.characters.Character.at_post_move passes `glance=True`
into `at_look`/`return_appearance`); `db.desc` is the full description
shown on an explicit `look`. If `db.glance` isn't set, falls back to
`db.desc` for both - rooms without an authored glance blurb yet still
work.
"""

from evennia.objects.objects import DefaultRoom
from evennia.utils.utils import inherits_from, iter_to_str

from world.commitments import hint_pose_for

from .objects import PARAGRAPH_INDENT, ObjectParent, indent_paragraphs

# Counted phrasing ("a single exit", "two exits") only for one or two
# exits; three or more switch to a plain leading-list instead (see
# get_display_exits) - project owner's call over counting exits past 2.
_COUNT_WORDS = {1: "a single", 2: "two"}

# Canonical compass order for listing exits, matching how a person
# would actually recite them - not alphabetical. Anything not in this
# list (a future non-cardinal exit) sorts after it, alphabetically.
_DIRECTION_ORDER = [
    "north", "south", "east", "west",
    "northeast", "northwest", "southeast", "southwest",
    "up", "down", "in", "out",
]


def _presence_line(entity, name, color, looker=None):
    """'<name> is here[, <pose>].' - shared by NPCs and player characters.
    `color` is an Evennia color-markup letter: bright cyan (c) for
    talk-capable NPCs and real players, dark cyan (C) for ambient
    (non-LLM) NPCs, per the project owner's color scheme.

    `looker` lets a talk-capable NPC with an open commitment
    (world.commitments.hint_pose_for) show a per-player hint pose in
    place of its normal static one - e.g. Tarin looking preoccupied
    with a shipment manifest only to a player he hasn't yet offered
    that errand to, phase 2B's docs/phase2b-records-discrepancy-
    proposal.md discoverability fix. Falls back to the static pose
    for anyone else, and for entities with no npc_id at all (player
    characters, ambient NPCs)."""
    npc_id = getattr(entity.db, "npc_id", None)
    hint_pose = hint_pose_for(npc_id, looker) if npc_id and looker is not None else None
    pose = hint_pose or entity.db.ambient_pose
    line = f"{name} is here, {pose}." if pose else f"{name} is here."
    return f"|{color}{line}|n"


class Room(ObjectParent, DefaultRoom):
    """
    Rooms are like any Object, except their location is None
    (which is default). They also use basetype_setup() to
    add locks so they cannot be puppeted or picked up.
    (to change that, use at_object_creation instead)

    See mygame/typeclasses/objects.py for a list of
    properties and methods available on all Objects.
    """

    appearance_template = """
{header}
|Y{name}{extra_name_info}|n
|W{desc}|n
{things}
{characters}
{exits}
{footer}
    """

    def get_display_name(self, looker=None, **kwargs):
        name = super().get_display_name(looker, **kwargs)
        room_type = self.db.room_type
        return f"{name} ({room_type})" if room_type else name

    def get_display_desc(self, looker, **kwargs):
        if kwargs.get("glance"):
            text = self.db.glance or self.db.desc or self.default_description
        else:
            text = self.db.desc or self.default_description
        return indent_paragraphs(text)

    def get_display_things(self, looker, **kwargs):
        things = self.filter_visible(self.contents_get(content_type="object"), looker, **kwargs)

        lines = []
        for thing in things:
            name = thing.get_display_name(looker, **kwargs)
            if inherits_from(thing, "typeclasses.npcs.TalkativeNPC"):
                lines.append(_presence_line(thing, name, "c", looker=looker))
            elif inherits_from(thing, "typeclasses.npcs.NPC"):
                lines.append(_presence_line(thing, name, "C", looker=looker))
            else:
                line = thing.db.room_line or thing.db.desc or f"There is {name} here."
                lines.append(f"|C{line}|n")
        joined = " ".join(lines)
        return f"{PARAGRAPH_INDENT}{joined}" if joined else ""

    def get_display_characters(self, looker, **kwargs):
        characters = self.filter_visible(
            self.contents_get(content_type="character"), looker, **kwargs
        )
        lines = [
            _presence_line(char, char.get_display_name(looker, **kwargs), "c")
            for char in characters
        ]
        joined = " ".join(lines)
        return f"{PARAGRAPH_INDENT}{joined}" if joined else ""

    def get_display_exits(self, looker, **kwargs):
        exits = self.filter_visible(self.contents_get(content_type="exit"), looker, **kwargs)
        names = [exi.get_display_name(looker, **kwargs) for exi in exits]
        order_index = {name: i for i, name in enumerate(_DIRECTION_ORDER)}
        names.sort(key=lambda name: (order_index.get(name, len(_DIRECTION_ORDER)), name))
        if not names:
            return ""

        count = len(names)
        direction_list = iter_to_str(names, endsep=", and")
        if count <= 2:
            noun = "exit" if count == 1 else "exits"
            line = f"You see {_COUNT_WORDS[count]} {noun} leading {direction_list}."
        else:
            line = f"You see exits leading {direction_list}."
        return f"|Y{line}|n"
