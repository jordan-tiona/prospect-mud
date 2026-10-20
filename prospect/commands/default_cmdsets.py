"""
Command sets

All commands in the game must be grouped in a cmdset.  A given command
can be part of any number of cmdsets and cmdsets can be added/removed
and merged onto entities at runtime.

To create new commands to populate the cmdset, see
`commands/command.py`.

This module wraps the default command sets of Evennia; overloads them
to add/remove commands from the default lineup. You can create your
own cmdsets by inheriting from them or directly from `evennia.CmdSet`.

"""

from evennia import default_cmds
from evennia.commands.default import account, general, system

from commands.admin import (
    CmdForget,
    CmdGenerateInvite,
    CmdInvites,
    CmdMemoryDebug,
    CmdResetCommitment,
    CmdResetMemory,
    CmdResetQuest,
)
from commands.attack import CmdAttack
from commands.chargen import CmdScriptedCreate
from commands.command import CmdNoMatch
from commands.describe import CmdDescribe
from commands.feedback import CmdFeedback
from commands.get import CmdGet
from commands.look import CmdLook
from commands.option import CmdOption
from commands.playtest import CmdPlaytest
from commands.probe import CmdProbe
from commands.quit import CmdQuit
from commands.restricted import CmdChannel, CmdOOC, CmdQuell
from commands.say import CmdSay
from commands.scripted_login import CmdScriptedLogin
from commands.stealth import CmdPose, CmdStealth
from commands.tannoy import CmdTannoy
from commands.socials import CmdSocial
from commands.tell import CmdTell
from commands.use import CmdUse


class CharacterCmdSet(default_cmds.CharacterCmdSet):
    """
    The `CharacterCmdSet` contains general in-game commands like `look`,
    `get`, etc available on in-game Character objects. It is merged with
    the `AccountCmdSet` when an Account puppets a Character.
    """

    key = "DefaultCharacter"

    def at_cmdset_creation(self):
        """
        Populates the cmdset
        """
        super().at_cmdset_creation()
        #
        # any commands you add below will overload the default ones.
        #
        self.add(CmdSay())
        self.add(CmdLook())
        self.add(CmdProbe())
        self.add(CmdGet())
        self.add(CmdForget())
        self.add(CmdResetQuest())
        self.add(CmdResetCommitment())
        self.add(CmdResetMemory())
        self.add(CmdMemoryDebug())
        self.add(CmdGenerateInvite())
        self.add(CmdInvites())
        self.add(CmdUse())
        self.add(CmdAttack())
        self.add(CmdTannoy())
        # Replaces stock setdesc, which had no limit or check.
        self.remove(default_cmds.CmdSetDesc)
        self.add(CmdDescribe())
        self.add(CmdNoMatch())
        self.add(CmdFeedback())
        self.add(CmdStealth())
        self.add(CmdTell())
        self.add(CmdSocial())
        # Stock pose, but revealing a hidden speaker first.
        self.add(CmdPose())
        # Nothing to do with the game for a player (commands/restricted.py).
        self.remove(general.CmdAccess)
        self.remove(system.CmdAbout)
        self.remove(system.CmdTime)


class AccountCmdSet(default_cmds.AccountCmdSet):
    """
    This is the cmdset available to the Account at all times. It is
    combined with the `CharacterCmdSet` when the Account puppets a
    Character. It holds game-account-specific commands, channel
    commands, etc.
    """

    key = "DefaultAccount"

    def at_cmdset_creation(self):
        """
        Populates the cmdset
        """
        super().at_cmdset_creation()
        #
        # any commands you add below will overload the default ones.
        #
        self.add(CmdPlaytest())
        # Evennia's `option`, plus AMBIENCE for idle emotes.
        self.add(CmdOption())
        # Replaced by commands/tell.py's `tell`, which stays private
        # and online-only.
        self.remove(default_cmds.CmdPage)
        # Deleting your character and making another skipped chargen;
        # MAX_NR_CHARACTERS already stops a second one.
        self.remove(account.CmdCharCreate)
        self.remove(account.CmdCharDelete)
        # Staff-only versions (commands/restricted.py).
        self.add(CmdChannel())
        self.add(CmdOOC())
        self.add(CmdQuell())
        # Stock quit, with stasis and a short delay (commands/quit.py).
        self.add(CmdQuit())


class UnloggedinCmdSet(default_cmds.UnloggedinCmdSet):
    """
    Command set available to the Session before being logged in.  This
    holds commands like creating a new account, logging in, etc.
    """

    key = "DefaultUnloggedin"

    def at_cmdset_creation(self):
        """
        Populates the cmdset
        """
        super().at_cmdset_creation()
        #
        # any commands you add below will overload the default ones.
        #
        self.add(CmdScriptedCreate())
        self.add(CmdScriptedLogin())


class SessionCmdSet(default_cmds.SessionCmdSet):
    """
    This cmdset is made available on Session level once logged in. It
    is empty by default.
    """

    key = "DefaultSession"

    def at_cmdset_creation(self):
        """
        This is the only method defined in a cmdset, called during
        its creation. It should populate the set with command instances.

        As and example we just add the empty base `Command` object.
        It prints some info.
        """
        super().at_cmdset_creation()
        #
        # any commands you add below will overload the default ones.
        #
