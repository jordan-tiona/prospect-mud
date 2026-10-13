"""
Adds "look at <obj>" and "l at <obj>" as aliases for Evennia's default
`look`, since "look at the notice board" is the phrasing players will
reach for naturally. The alias text already includes "at " as part of
the matched command name, so by the time func() sees self.args, "at "
is already gone - no extra parsing needed for that part.

Also strips a leading article ("a"/"an"/"the") from whatever's left,
so "look at the board" and "look board" both resolve to an object
actually named "board" - object names aren't authored with articles
in front, so a literal "the board" would otherwise fail to match.
"""

import re

from evennia.commands.default.general import CmdLook as DefaultCmdLook

_LEADING_ARTICLE_RE = re.compile(r"^(a|an|the)\s+", re.IGNORECASE)


class CmdLook(DefaultCmdLook):
    aliases = ["l", "ls", "look at", "l at"]

    def func(self):
        self.args = _LEADING_ARTICLE_RE.sub("", self.args.strip())
        super().func()
