"""
`stealth`: staff-only toggle for being in the game unseen during a
playtest (world/stealth.py has the mechanics).

Also overrides the stock `pose`/`emote` so posing while hidden reveals
you first, the same as `say` (commands/say.py) - the owner's call
(2026-10-17) was a reveal with a reminder, not a block.
"""

from evennia import default_cmds

from commands.command import Command
from world.stealth import hide, is_hidden, reveal, reveal_for_speech


class CmdStealth(Command):
    """
    Hide from players, or show yourself again. While hidden, players
    don't see you in the room and your arrivals, departures and logins
    aren't announced to them. Other staff still see you. Speaking
    (say, pose) reveals you.

    Usage:
      stealth          - toggle
      stealth on|off
    """

    key = "stealth"
    locks = "cmd:perm(Builder)"
    help_category = "Admin"

    def func(self):
        caller = self.caller
        arg = self.args.strip().lower()
        if arg not in ("", "on", "off"):
            caller.msg("Usage: stealth [on|off]")
            return

        want_hidden = not is_hidden(caller) if not arg else arg == "on"
        if want_hidden:
            hide(caller)
            caller.msg(
                "You are hidden. Players can't see you, and your comings and goings "
                "aren't announced to them. Speaking (say, pose) reveals you."
            )
        else:
            reveal(caller)
            caller.msg("You are visible again.")


class CmdPose(default_cmds.CmdPose):
    __doc__ = default_cmds.CmdPose.__doc__

    def func(self):
        if self.args:
            reveal_for_speech(self.caller)
            self.args = punctuate_pose(self.args)
        super().func()


def punctuate_pose(text):
    """Ends a pose with a period when the player left it off ("emote
    smiles" -> "Ravis smiles."), like say does for speech. Anything
    already ending in punctuation, a quote or a bracket is left alone."""
    text = text.rstrip()
    if text and text[-1].isalnum():
        return text + "."
    return text
