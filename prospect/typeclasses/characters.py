"""
Characters

Characters are (by default) Objects setup to be puppeted by Accounts.
They are what you "see" in game. The Character class in this module
is setup to be the "default" character type created by the default
creation commands.

"""

from evennia.objects.objects import DefaultCharacter

from world.session_log import log_room_changed, session_id_for

from .objects import ObjectParent


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

    """

    def at_post_move(self, source_location, move_type="move", **kwargs):
        if self.location.access(self, "view"):
            self.msg(text=(self.at_look(self.location, glance=True), {"type": "look"}))
        from world.tutorial import maybe_schedule_nudge

        maybe_schedule_nudge(self)

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

    def at_post_puppet(self, **kwargs):
        super().at_post_puppet(**kwargs)
        # A new character is moved into the Medical Bay by chargen before
        # anyone is logged in to it, so at_post_move's tannoy goes
        # nowhere; repeat it now that the player is actually here
        # (world/tutorial.py announce_tannoy).
        from world.tutorial import announce_tannoy

        announce_tannoy(self)
