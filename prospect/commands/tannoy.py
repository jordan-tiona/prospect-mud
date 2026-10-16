"""
`tannoy` - repeats the current room's tannoy announcement, if it has
one (world/tutorial.py's `_ROOM_TANNOYS`), for a player who missed it
or wants a refresher.
"""

from world.tutorial import tannoy_text_for_room

from .command import Command


class CmdTannoy(Command):
    """
    Repeat this room's tannoy announcement, if it has one.

    Usage:
      tannoy
    """

    key = "tannoy"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        text = tannoy_text_for_room(self.caller.location)
        if not text:
            self.caller.msg("There's no tannoy here.")
            return
        self.caller.msg("\n" + text)
