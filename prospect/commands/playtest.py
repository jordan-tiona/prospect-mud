"""
`playtest` / `pt`: talk on the playtest channel, or turn it off and
on (world/playtest_channel.py).

A thin wrapper over Evennia's channel rather than its stock `channel`
command, whose syntax (`channel/mute playtest`) is a lot to ask of a
tester. PlaytestChannel skips Evennia's per-subscriber channel nicks
for the same reason: they would rewrite `pt off` into a message
saying "off".
"""

from evennia.utils.logger import tail_log_file

from commands.command import Command
from world.playtest_channel import HISTORY_LINES, get_playtest_channel


class CmdPlaytest(Command):
    """
    Talk with everyone on the playtest channel, staff included.
    You're on it by default.

    Usage:
      playtest <message>   - say something on the channel (or: pt)
      playtest             - show the last few messages
      playtest off         - stop hearing the channel
      playtest on          - start hearing it again
    """

    key = "playtest"
    aliases = ["pt"]
    locks = "cmd:all()"
    help_category = "Comms"
    account_caller = True

    def func(self):
        account = self.account
        channel = get_playtest_channel()
        if channel is None:
            self.msg("The playtest channel isn't available right now.")
            return

        arg = self.args.strip()
        switch = arg.lower()
        if switch == "off":
            account.db.playtest_opted_out = True
            channel.disconnect(account)
            self.msg("You've left the playtest channel. Type |wplaytest on|n to rejoin it.")
            return
        if switch == "on":
            account.db.playtest_opted_out = False
            channel.connect(account)
            self.msg("You've joined the playtest channel.")
            return
        if not arg:
            lines = tail_log_file(channel.get_log_filename(), 0, HISTORY_LINES)
            if not lines:
                self.msg("Nothing has been said on the playtest channel yet.")
            else:
                self.msg("Recent playtest messages:\n" + "".join(lines).rstrip())
            return
        if not channel.has_connection(account):
            self.msg("You're not on the playtest channel. Type |wplaytest on|n to join it.")
            return

        puppet = self.session.puppet if self.session else None
        channel.msg(arg, senders=puppet or account)
