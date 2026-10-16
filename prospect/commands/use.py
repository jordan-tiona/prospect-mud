"""
Quest 2's "use kit on bed" world action (docs/prospect-initial-
playtest-design-spec.md §6, Quest 2; §7's command-language table:
"use kit on planting bed" / "tend the planting bed with the kit"). A
plain world command, not an NPC tool call - no LLM involved, same
category as the stock `get`/`drop` commands. The actual completion
fact (world/garden.py's per-player flag) is only ever set here; Iri's
own `confirm_bed_tended` action (world/actions.py) just reads it.

Accepts two equivalent phrasings:
    use <item> on <target>
    tend <target> with <item>
"""

import re

from commands.command import Command
from world.garden import is_bed_tended, mark_bed_tended

_USE_ON_RE = re.compile(r"^(?P<item>.+?)\s+on\s+(?P<target>.+)$", re.IGNORECASE)
_TEND_WITH_RE = re.compile(r"^(?P<target>.+?)\s+with\s+(?P<item>.+)$", re.IGNORECASE)


class CmdUse(Command):
    """
    Use an item on something in the room.

    Usage:
      use <item> on <target>
      tend <target> with <item>
    """

    key = "use"
    aliases = ["tend"]
    locks = "cmd:all()"
    help_category = "General"

    def parse(self):
        args = self.args.strip()
        pattern = _TEND_WITH_RE if self.cmdstring.lower() == "tend" else _USE_ON_RE
        match = pattern.match(args)
        self.item_name = match.group("item").strip() if match else ""
        self.target_name = match.group("target").strip() if match else ""

    def func(self):
        caller = self.caller
        if not self.item_name or not self.target_name:
            caller.msg("Use what on what? Usage: use <item> on <target>")
            return

        item = caller.search(self.item_name, location=caller, quiet=True)
        item = item[0] if item else None
        if item is None or not item.is_typeclass("typeclasses.objects.GardeningKit", exact=False):
            caller.msg(f"You don't have a {self.item_name!r} to use like that.")
            return

        target = caller.search(self.target_name, location=caller.location, quiet=True)
        target = target[0] if target else None
        if target is None or not target.is_typeclass("typeclasses.objects.PlantingBed", exact=False):
            caller.msg(f"You can't use that on {self.target_name!r}.")
            return

        if is_bed_tended(caller):
            caller.msg(f"{target.get_display_name(caller)} already looks well tended; no need to go over it again.")
            return

        mark_bed_tended(caller)
        caller.msg(f"You tend to {target.get_display_name(caller)} with {item.get_display_name(caller)}.")
