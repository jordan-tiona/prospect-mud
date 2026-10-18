"""
Characters

Characters are (by default) Objects setup to be puppeted by Accounts.
They are what you "see" in game. The Character class in this module
is setup to be the "default" character type created by the default
creation commands.

"""

import time

from evennia.objects.objects import DefaultCharacter

from world.appearance import identity_phrase, tidy
from world.session_log import log_room_changed, session_id_for
from world.stealth import is_hidden, is_staff, suppressed_for

from .objects import ObjectParent, indent_paragraphs

# Movement lines (owner, 2026-10-17), instead of Evennia's "X is leaving
# <room>, heading for <room>." Keyed by the exit's direction: the one
# taken when leaving, the one leading back when arriving.
_COMPASS = {"north", "south", "east", "west", "northeast", "northwest", "southeast", "southwest"}
_LEAVE_OTHER = {"up": "heads up", "down": "heads down", "in": "heads inside", "out": "heads outside"}
_ARRIVE_OTHER = {"up": "from above", "down": "from below", "in": "from inside", "out": "from outside"}


def leave_message(direction: str) -> str:
    if direction in _COMPASS:
        return f"{{object}} leaves to the {direction}."
    if direction in _LEAVE_OTHER:
        return f"{{object}} {_LEAVE_OTHER[direction]}."
    return "{object} leaves."


def arrive_message(direction_back: str) -> str:
    if direction_back in _COMPASS:
        return f"{{object}} arrives from the {direction_back}."
    if direction_back in _ARRIVE_OTHER:
        return f"{{object}} arrives {_ARRIVE_OTHER[direction_back]}."
    return "{object} arrives."


def _exit_key_between(room, destination) -> str:
    if room is None or destination is None:
        return ""
    for obj in room.contents:
        if obj.destination is destination:
            return obj.key.lower()
    return ""


class Character(ObjectParent, DefaultCharacter):
    """
    The Character just re-implements some of the Object's methods and hooks
    to represent a Character entity in-game.

    See mygame/typeclasses/objects.py for a list of
    properties and methods available on all Object child classes like this.

    Optional `db.ambient_pose` (e.g. "resting against the wall") is read
    by typeclasses.rooms.Room to show "<name> is here, <pose>." for
    other players present in the room, same convention as NPCs.

    Overrides `at_post_move` so walking into a room shows its short
    "glance" blurb instead of the full `look` description - the
    project owner's call to avoid bombarding a player with a full
    description on every step while still giving `look` the complete
    text (typeclasses.rooms.Room.get_display_desc branches on this).

    Also the hook `world/tutorial.py`'s one-time proactive NPC nudges
    (Given/Daven speaking up unprompted a beat after a new player
    walks in) key off of - see that module for why.

    Also logs a structured `room_changed` gameplay event
    (world/session_log.py, game-plan.md 6.2) for any Character with an
    active session - a bare per-command `location` field (commands/
    command.py's logging mixin) only ever shows where a player was
    *when they typed something*, not the room they actually moved
    into if their next command happens much later, or isn't a move at
    all.

    Also where staff stealth (world/stealth.py) takes effect on the
    receiving end: `msg` drops anything a hidden character broadcast
    unless this character is staff.

    """

    def msg(self, text=None, from_obj=None, session=None, options=None, **kwargs):
        if suppressed_for(self, from_obj):
            return
        super().msg(text=text, from_obj=from_obj, session=session, options=options, **kwargs)

    def at_look(self, target, **kwargs):
        text = super().at_look(target, **kwargs)
        if text and is_hidden(self) and target is not None and target == self.location:
            text += "\n|x(You are hidden from players.)|n"
        return text

    def get_display_name(self, looker=None, **kwargs):
        name = super().get_display_name(looker, **kwargs)
        if looker is not None and looker is not self and looker.location and is_hidden(self) and is_staff(looker):
            name += " |x(hidden)|n"
        return name

    def announce_move_from(self, destination, msg=None, mapping=None, move_type="move", **kwargs):
        if msg is None:
            msg = leave_message(_exit_key_between(self.location, destination))
        super().announce_move_from(destination, msg=msg, mapping=mapping, move_type=move_type, **kwargs)

    def announce_move_to(self, source_location, msg=None, mapping=None, move_type="move", **kwargs):
        if msg is None and source_location is not None:
            msg = arrive_message(_exit_key_between(self.location, source_location))
        super().announce_move_to(source_location, msg=msg, mapping=mapping, move_type=move_type, **kwargs)

    def at_post_move(self, source_location, move_type="move", **kwargs):
        if self.location.access(self, "view"):
            self.msg(text=(self.at_look(self.location, glance=True), {"type": "look"}))
        from world.idle_emotes import start_room_emotes
        from world.tutorial import maybe_schedule_nudge

        # world/idle_emotes.py holds its beats just after an arrival glance.
        self.ndb.arrived_at = time.time()
        # A new visit: ambient NPCs react to being addressed again
        # (world/ambient_reactions.py).
        self.ndb.ambient_reacted = None
        maybe_schedule_nudge(self)
        start_room_emotes(self)

        session_id = session_id_for(self)
        if session_id:
            log_room_changed(
                session_id=session_id,
                actor_key=self.key,
                actor_dbref=self.dbref,
                from_location=source_location.key if source_location else "",
                to_location=self.location.key if self.location else "",
            )

    at_after_move = at_post_move

    def get_display_desc(self, looker, **kwargs):
        # A player who hasn't written a short description (commands/
        # describe.py) shows what character creation made them, e.g.
        # "A Kell woman.", rather than Evennia's "This is a character."
        has_probe_text = kwargs.get("probe") and self.db.probe_desc
        if not self.db.desc and not has_probe_text:
            identity = identity_phrase(self)
            if identity:
                return indent_paragraphs(identity[0].upper() + identity[1:] + ".")
        if has_probe_text:
            return indent_paragraphs(tidy(self.db.probe_desc))
        if self.db.desc:
            return indent_paragraphs(tidy(self.db.desc))
        return super().get_display_desc(looker, **kwargs)

    def at_post_puppet(self, **kwargs):
        super().at_post_puppet(**kwargs)
        # A new character is moved into the Medical Bay by chargen before
        # anyone is logged in to it, so at_post_move's tannoy goes
        # nowhere; repeat it now that the player is actually here
        # (world/tutorial.py announce_tannoy).
        from world.idle_emotes import start_room_emotes
        from world.tutorial import announce_tannoy

        announce_tannoy(self)
        start_room_emotes(self)
