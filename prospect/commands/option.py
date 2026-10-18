"""
`option`, with one setting of ours on top of Evennia's client options:
AMBIENCE, the switch for idle NPC emotes (world/idle_emotes.py,
LR-LORE-0006). Stored as a session protocol flag like SCREENREADER, so
`option/save ambience=off` sticks across logins the same way.

Evennia's own command keeps its validators in a local dict, so this
handles AMBIENCE itself and passes everything else through.
"""

from evennia.commands.default.account import CmdOption as EvenniaCmdOption

from world.idle_emotes import AMBIENCE_FLAG

_ON = ("on", "true", "1", "yes")
_OFF = ("off", "false", "0", "no")


class CmdOption(EvenniaCmdOption):
    __doc__ = EvenniaCmdOption.__doc__.rstrip() + """

    AMBIENCE (on by default) shows small things NPCs do now and then,
    such as wiping a counter. Turn it off with:
      option/save ambience=off
    """

    def func(self):
        if self.session is None or not self.rhs or self.lhs.strip().upper() != AMBIENCE_FLAG:
            super().func()
            return

        value = self.rhs.strip().lower()
        if value not in _ON + _OFF:
            self.msg(f"|rCould not set option |w{AMBIENCE_FLAG}|r:|n use on or off.")
            return
        new_val = value in _ON
        old_val = self.session.protocol_flags.get(AMBIENCE_FLAG, True)
        if old_val == new_val:
            self.msg(f"Option |w{AMBIENCE_FLAG}|n was kept as '|w{old_val}|n'.")
        else:
            self.msg(f"Option |w{AMBIENCE_FLAG}|n was changed from '|w{old_val}|n' to '|w{new_val}|n'.")
        saved = self.account.attributes.get("_saved_protocol_flags", default={})
        if "save" in self.switches:
            saved[AMBIENCE_FLAG] = new_val
            self.account.attributes.add("_saved_protocol_flags", saved)
            self.msg(f"|gSaved option {AMBIENCE_FLAG}.|n")
        if "clear" in self.switches:
            saved.pop(AMBIENCE_FLAG, None)
            self.account.attributes.add("_saved_protocol_flags", saved)
            self.msg(f"|gCleared saved {AMBIENCE_FLAG}.")
        self.session.update_flags(**{AMBIENCE_FLAG: new_val})
