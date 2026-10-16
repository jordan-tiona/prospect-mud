"""
Characters

Characters are (by default) Objects setup to be puppeted by Accounts.
They are what you "see" in game. The Character class in this module
is setup to be the "default" character type created by the default
creation commands.

"""

from evennia.objects.objects import DefaultCharacter

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

    """

    def at_post_move(self, source_location, move_type="move", **kwargs):
        if self.location.access(self, "view"):
            self.msg(text=(self.at_look(self.location, glance=True), {"type": "look"}))
        from world.tutorial import maybe_schedule_nudge

        maybe_schedule_nudge(self)

    at_after_move = at_post_move
