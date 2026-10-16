"""
Adds "look at <obj>" and "l at <obj>" as aliases for Evennia's default
`look`, since "look at the notice board" is the phrasing players will
reach for naturally. The alias text already includes "at " as part of
the matched command name, so by the time func() sees self.args, "at "
is already gone - no extra parsing needed for that part.

Also adds "read" (confirmed live, 2026-10-16: a player tried "read
signpost" on a readable room object and got nothing, since only
`look`/its aliases were registered) - treated as a plain synonym for
`look`, not a distinct reading mechanic. Nothing here distinguishes
a "readable" object from any other; every object is already just as
lookable, so there's no separate concept to introduce.

Also strips a leading article ("a"/"an"/"the") from whatever's left,
so "look at the board" and "look board" both resolve to an object
actually named "board" - object names aren't authored with articles
in front, so a literal "the board" would otherwise fail to match.
"""

import re

from evennia.commands.default.general import CmdLook as DefaultCmdLook

_LEADING_ARTICLE_RE = re.compile(r"^(a|an|the)\s+", re.IGNORECASE)


class CmdLook(DefaultCmdLook):
    aliases = ["l", "ls", "look at", "l at", "read"]

    def func(self):
        self.args = _LEADING_ARTICLE_RE.sub("", self.args.strip())
        super().func()
