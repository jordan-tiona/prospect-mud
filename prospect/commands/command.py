"""
Commands

Commands describe the input the account can do to the game.

"""

from evennia.commands.cmdhandler import CMD_NOMATCH
from evennia.commands.command import Command as BaseCommand
from evennia.commands.default.muxcommand import MuxCommand as BaseMuxCommand
from evennia.utils.utils import inherits_from

from world.session_log import log_command, log_unknown_command, session_id_for

# from evennia import default_cmds


class _SessionCommandLoggingMixin:
    """
    Logs every command actually typed by a logged-in, puppeted
    Character to world/session_log.py's sessions.jsonl (see that
    module's docstring for why this is a separate file from world/
    conversation_log.py's conversations.jsonl).

    Deliberately gated on the caller being a Character, not a Session
    or Account: the pre-login and character-creation flows
    (commands/scripted_login.py's CmdScriptedLogin, commands/
    chargen.py's CmdScriptedCreate) run with the Session or Account as
    caller, never a Character - so this can never log a password or
    anything else typed before login. That's not a special case
    carved out here; it's simply never reached.

    This class is set as every command's base via
    settings.COMMAND_DEFAULT_CLASS - Evennia resolves every stock
    command's own parent from that setting at import time (see e.g.
    evennia.commands.default.general's own
    `COMMAND_DEFAULT_CLASS = class_from_module(settings.COMMAND_DEFAULT_CLASS)`,
    the same pattern already used in this project by commands/
    scripted_login.py and commands/chargen.py). Setting it once here
    covers every command in the game - stock (get, look, drop,
    movement/exit commands, inventory...) and custom alike - without
    editing each one individually.

    Logged from `at_pre_cmd`, not `at_post_cmd`: if a command's own
    `func()` raises, `at_post_cmd` never runs, but a crashing attempt
    is exactly the kind of thing worth having in a debugging log.
    `at_pre_cmd` only aborts the command if it returns something
    truthy, so this always returns None.
    """

    # A command that sets this False logs only the word typed, not its
    # arguments (commands/tell.py: tells are private, owner 2026-10-17).
    log_input = True

    def at_pre_cmd(self):
        caller = self.caller
        if inherits_from(caller, "typeclasses.characters.Character"):
            session_id = session_id_for(caller)
            if session_id:
                raw_input = getattr(self, "raw_string", "") or ""
                if not self.log_input:
                    raw_input = self.cmdstring
                log_command(
                    session_id=session_id,
                    actor_key=caller.key,
                    actor_dbref=caller.dbref,
                    location=caller.location.key if caller.location else "",
                    raw_input=raw_input,
                )
        return super().at_pre_cmd()


class Command(_SessionCommandLoggingMixin, BaseCommand):
    """
    Base command (you may see this if a child command had no help text defined)

    Note that the class's `__doc__` string is used by Evennia to create the
    automatic help entry for the command, so make sure to document consistently
    here. Without setting one, the parent's docstring will show (like now).

    """

    # Each Command class implements the following methods, called in this order
    # (only func() is actually required):
    #
    #     - at_pre_cmd(): If this returns anything truthy, execution is aborted.
    #     - parse(): Should perform any extra parsing needed on self.args
    #         and store the result on self.
    #     - func(): Performs the actual work.
    #     - at_post_cmd(): Extra actions, often things done after
    #         every command, like prompts.
    #
    pass


class MuxCommand(_SessionCommandLoggingMixin, BaseMuxCommand):
    """
    Same as evennia.commands.default.muxcommand.MuxCommand (all the
    switches/lhs/rhs parsing every stock default command relies on),
    with _SessionCommandLoggingMixin's logging hook mixed in. Set as
    settings.COMMAND_DEFAULT_CLASS so every stock default command
    inherits the hook too, not just this project's own custom
    commands (which already subclass `Command` above directly).
    """

    pass


class CmdNoMatch(BaseMuxCommand):
    """
    Evennia's system command for a line that matched nothing at all
    (evennia.commands.cmdhandler.CMD_NOMATCH) - by default, the engine
    only falls back to this if some cmdset actually registers it
    (cmdhandler.py: `syscmd = yield cmdset.get(CMD_NOMATCH)`); with
    none registered, an unmatched line never becomes a Command
    instance at all, so _SessionCommandLoggingMixin's hook (and this
    project's structured gameplay-event logging, game-plan.md 6.2's
    "unknown commands" signal) never sees it. This registers it
    (default_cmdsets.py's CharacterCmdSet) and logs it as its own
    `unknown_command` event instead of a generic `command` one -
    deliberately *not* built on `Command`/`MuxCommand` above, so it
    doesn't also log a redundant generic `command` event for the same
    line.

    `self.args` holds the full original line here (cmdhandler.py sets
    it from the raw string for a nomatch, not just "everything after
    the command name" like a normal command gets).
    """

    key = CMD_NOMATCH
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        if inherits_from(caller, "typeclasses.characters.Character"):
            session_id = session_id_for(caller)
            if session_id:
                log_unknown_command(
                    session_id=session_id,
                    actor_key=caller.key,
                    actor_dbref=caller.dbref,
                    location=caller.location.key if caller.location else "",
                    raw_input=self.args or "",
                )
        direction = _DIRECTIONS.get((self.args or "").strip().lower())
        if direction and caller.location:
            # A direction with no exit that way: say so, and what does
            # lead out, rather than "Huh?", which doesn't tell a player
            # (least of all through a screen reader) whether they
            # mistyped or there's just no way west (first external
            # playtest, 2026-10-20).
            exits = caller.location.get_display_exits(caller) if hasattr(caller.location, "get_display_exits") else ""
            caller.msg(f"You can't go {direction} from here." + (f" {exits}" if exits else ""))
            return
        caller.msg("Huh?")


# Every spelling of a compass or vertical direction a player might type,
# to its full name. Matching an actual exit happens before CmdNoMatch
# (the exit's own command), so a direction that reaches here has no exit.
_DIRECTIONS = {
    **{name: name for name in (
        "north", "south", "east", "west", "northeast", "northwest",
        "southeast", "southwest", "up", "down", "in", "out",
    )},
    "n": "north", "s": "south", "e": "east", "w": "west",
    "ne": "northeast", "nw": "northwest", "se": "southeast", "sw": "southwest",
    "u": "up", "d": "down",
}
