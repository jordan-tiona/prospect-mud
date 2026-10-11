"""
The `talk` command: how players address talk-capable NPCs.

Phase 1 step 4 scaffolding only. It finds the target, checks it's a
TalkativeNPC (not ambient scenery), and replies with a placeholder
line. The real prompt builder / LLM client / tool validator / output
check pipeline (design-bible 16.5) gets wired in behind this same
command in step 7.
"""

from evennia.utils.utils import inherits_from

from .command import Command


class CmdTalk(Command):
    """
    Talk to an NPC.

    Usage:
      talk <npc> = <message>

    Only works on talk-capable NPCs, not ambient scenery.
    """

    key = "talk"
    locks = "cmd:all()"
    help_category = "General"

    def parse(self):
        args = self.args.strip()
        if "=" in args:
            lhs, rhs = args.split("=", 1)
        else:
            lhs, rhs = args, ""
        self.target_name = lhs.strip()
        self.message = rhs.strip()

    def func(self):
        caller = self.caller

        if not self.target_name:
            caller.msg("Talk to whom? Usage: talk <npc> = <message>")
            return

        target = caller.search(self.target_name, location=caller.location)
        if not target:
            # caller.search() already sent a not-found/multimatch message
            return

        if not inherits_from(target, "typeclasses.npcs.TalkativeNPC"):
            caller.msg(f"{target.key} doesn't seem interested in talking.")
            return

        if not self.message:
            caller.msg(f"Talk to {target.key} about what? Usage: talk <npc> = <message>")
            return

        caller.msg(f'You say to {target.key}, "{self.message}"')
        caller.location.msg_contents(
            f"{caller.key} talks to {target.key}.",
            exclude=[caller],
        )
        # TODO(step 7): replace with the prompt builder + llm_client.chat()
        # + tool validator + output check pipeline (design-bible 16.5).
        caller.msg(f'{target.key} says, "(the conversation pipeline isn\'t wired up yet)"')
