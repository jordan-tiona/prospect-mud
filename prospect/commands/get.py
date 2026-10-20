"""
Stock Evennia's CmdGet only aliases "grab" (not "take"), so a perfectly
natural "take <item>" phrasing falls through to "command not found" -
caught live during Quest 2 playtesting (2026-10-14). A general
vocabulary gap, not specific to any one quest or item, so it's fixed
here on the stock command itself rather than on any one object.

It also reaches into containers (typeclasses.objects.Container, e.g.
the courtyard's communal locker, LR-DEV-0013):
    get <item> from <container>
    get <item>      - when nothing loose in the room matches, but
                      something inside a container here does
"get <item> from <somewhere>" where <somewhere> isn't a container here
drops the "from ..." part and looks in the room as usual (the playtest
spec's "grab the gardening kit from the locker" predates the locker).
"""

import re

from evennia import default_cmds

CONTAINER_TYPECLASS = "typeclasses.objects.Container"

_FROM_RE = re.compile(r"^(?P<item>.+?)\s+from\s+(?P<container>.+)$", re.IGNORECASE)


class CmdGet(default_cmds.CmdGet):
    __doc__ = default_cmds.CmdGet.__doc__

    aliases = ["grab", "take"]

    def func(self):
        caller = self.caller
        room = caller.location
        args = self.args.strip()
        if not args or room is None:
            super().func()
            return

        match = _FROM_RE.match(args)
        if match and not caller.search(args, location=room, quiet=True):
            named = caller.search(match.group("container"), location=room, quiet=True)
            containers = [obj for obj in named if obj.is_typeclass(CONTAINER_TYPECLASS, exact=False)]
            if containers:
                self._get_from(containers[:1], match.group("item"))
                return
            self.args = match.group("item")
            args = self.args

        if not caller.search(args, location=room, quiet=True):
            containers = [obj for obj in room.contents if obj.is_typeclass(CONTAINER_TYPECLASS, exact=False)]
            inside = [item for container in containers for item in container.contents]
            if inside and caller.search(args, candidates=inside, quiet=True):
                self._get_from(containers, args)
                return
        super().func()

    def _get_from(self, containers, item_name):
        """Stock CmdGet's checks and hooks, for an item inside one of
        `containers`."""
        caller = self.caller
        inside = [item for container in containers for item in container.contents]
        obj = caller.search(
            item_name,
            candidates=inside,
            nofound_string=f"There's no {item_name} in {containers[0].get_display_name(caller)}."
            if len(containers) == 1
            else None,
        )
        if not obj:
            return
        if not obj.access(caller, "get"):
            self.msg(obj.db.get_err_msg or "You can't get that.")
            return
        if not obj.at_pre_get(caller):
            return
        container = obj.location
        if obj.move_to(caller, quiet=True, move_type="get"):
            obj.at_get(caller)
            caller.location.msg_contents(
                f"$You() $conj(take) {obj.get_display_name(caller)} from {container.get_display_name(caller)}.",
                from_obj=caller,
            )
        else:
            self.msg("That can't be picked up.")
