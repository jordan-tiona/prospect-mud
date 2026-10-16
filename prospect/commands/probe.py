"""
`probe <thing>`: the closer, longer look (project owner, 2026-10-16).
`look <thing>` is unchanged; `probe` shows the thing's db.probe_desc
(authored as `## Probe Description`, or a persona's `probe_desc:`
metadata line) and falls back to exactly what `look` shows when there
isn't one - see typeclasses.objects.ObjectParent.get_display_desc.

Finds its target the same way `look` does (same search, same `view`
lock via at_look, same leading-article stripping), so nothing `look`
can't see - e.g. a quest prop hidden from this player - is probeable.
Rooms, and objects with per-looker text, show their `look` text.

Later, extra detail lines (condition, size, skill-check reveals) go
after the description here; they're the only place out-of-character
text may appear (owner, 2026-10-16). No hints about `probe` are shown
anywhere else - the Medical Bay tannoy teaches it.
"""

from commands.look import _LEADING_ARTICLE_RE

from .command import Command


class CmdProbe(Command):
    """
    take a closer look at something

    Usage:
      probe <thing>

    Studies something nearby in more detail than look.
    """

    key = "probe"
    locks = "cmd:all()"
    arg_regex = r"\s|$"

    def func(self):
        caller = self.caller
        args = _LEADING_ARTICLE_RE.sub("", self.args.strip())
        if not args:
            caller.msg("Probe what?")
            return
        target = caller.search(args)
        if not target:
            return
        desc = caller.at_look(target, probe=True)
        self.msg(text=(desc, {"type": "look"}), options=None)
