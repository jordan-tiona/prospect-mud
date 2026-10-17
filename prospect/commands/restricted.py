"""
Stock Evennia commands kept for staff but taken away from players
(owner, 2026-10-17). `help` only lists commands the caller can run,
so these also drop out of a player's help.

- `channel`: any player could create channels (`manage:all()`);
  players have `playtest` (commands/playtest.py) instead.
- `ooc`: leaves your character for an out-of-game menu a tester
  wouldn't understand. `ic` stays open to everyone, as the way back in
  if a login ever ends up out of character.
- `quell`: does nothing for a player.

Removed outright in commands/default_cmdsets.py: `charcreate` and
`chardelete` (delete-then-create skipped chargen), `access`, `about`
and `time`.
"""

from evennia.commands.default import account, comms

STAFF = "perm(Builder)"


class CmdChannel(comms.CmdChannel):
    __doc__ = comms.CmdChannel.__doc__
    locks = f"cmd:{STAFF};admin:all();manage:all();changelocks:perm(Admin)"


class CmdOOC(account.CmdOOC):
    __doc__ = account.CmdOOC.__doc__
    locks = f"cmd:{STAFF}"


class CmdQuell(account.CmdQuell):
    __doc__ = account.CmdQuell.__doc__
    locks = f"cmd:{STAFF}"
