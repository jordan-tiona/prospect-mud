"""
QUIT with stasis (LR-DEV-0011): the player reads "You go still and
slip into stasis." and the room sees them go still, then the session
disconnects QUIT_DELAY_SECONDS later (world/stasis.py). QUIT/ALL, or
quitting with no character in the world, disconnects at once as
before.
"""

from evennia import default_cmds
from evennia.server.sessionhandler import SESSION_HANDLER
from evennia.utils.utils import delay

from world.stasis import QUIT_DELAY_SECONDS, announce_going, tell_quitting


class CmdQuit(default_cmds.CmdQuit):
    __doc__ = default_cmds.CmdQuit.__doc__

    def func(self):
        puppet = self.session.puppet if self.session else None
        if "all" in self.switches or puppet is None or puppet.location is None:
            super().func()
            return
        if puppet.ndb.quitting:
            return
        puppet.ndb.quitting = True
        tell_quitting(puppet)
        announce_going(puppet)
        # Character.at_post_unpuppet skips its own line, including when
        # the connection drops during the delay.
        puppet.ndb.stasis_announced = True
        delay(QUIT_DELAY_SECONDS, self._finish)

    def _finish(self):
        if self.session.sessid in SESSION_HANDLER:
            super().func()
