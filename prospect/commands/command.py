"""
Commands

Commands describe the input the account can do to the game.

"""

from evennia.commands.command import Command as BaseCommand
from evennia.commands.default.muxcommand import MuxCommand as BaseMuxCommand
from evennia.utils.utils import inherits_from

from world.session_log import log_command

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

    def at_pre_cmd(self):
        caller = self.caller
        if inherits_from(caller, "typeclasses.characters.Character"):
            account = getattr(caller, "account", None)
            session_id = account.ndb.session_id if account else None
            if session_id:
                log_command(
                    session_id=session_id,
                    actor_key=caller.key,
                    actor_dbref=caller.dbref,
                    location=caller.location.key if caller.location else "",
                    raw_input=getattr(self, "raw_string", "") or "",
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
