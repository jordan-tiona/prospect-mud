"""
Stock Evennia's CmdGet only aliases "grab" (not "take"), so a perfectly
natural "take <item>" phrasing falls through to "command not found" -
caught live during Quest 2 playtesting (2026-10-14). A general
vocabulary gap, not specific to any one quest or item, so it's fixed
here on the stock command itself rather than on any one object.

It also accepts "get <item> from <somewhere>" (the playtest spec's
"grab the gardening kit from the locker"): when the whole phrase names
nothing in the room, the "from ..." part is dropped and the item is
looked for in the room as usual. There are no containers to reach into.
"""

import re

from evennia import default_cmds

_FROM_RE = re.compile(r"^(?P<item>.+?)\s+from\s+.+$", re.IGNORECASE)


class CmdGet(default_cmds.CmdGet):
    __doc__ = default_cmds.CmdGet.__doc__

    aliases = ["grab", "take"]

    def func(self):
        match = _FROM_RE.match(self.args.strip())
        if match and not self.caller.search(self.args.strip(), location=self.caller.location, quiet=True):
            self.args = match.group("item")
        super().func()
