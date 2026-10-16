"""
Stock Evennia's CmdGet only aliases "grab" (not "take"), so a perfectly
natural "take <item>" phrasing falls through to "command not found" -
caught live during Quest 2 playtesting (2026-10-14). A general
vocabulary gap, not specific to any one quest or item, so it's fixed
here on the stock command itself rather than on any one object.
"""

from evennia import default_cmds


class CmdGet(default_cmds.CmdGet):
    __doc__ = default_cmds.CmdGet.__doc__

    aliases = ["grab", "take"]
