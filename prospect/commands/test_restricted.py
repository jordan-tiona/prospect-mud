"""
Tests for which stock Evennia commands players can reach
(commands/restricted.py, commands/default_cmdsets.py).

Run with:
    evennia test commands.test_restricted
"""

from django.test import TestCase
from evennia import create_account

from commands.default_cmdsets import AccountCmdSet, CharacterCmdSet


def _commands():
    found = {}
    for cls in (CharacterCmdSet, AccountCmdSet):
        cmdset = cls()
        cmdset.at_cmdset_creation()
        for cmd in cmdset.commands:
            found[cmd.key] = cmd
    return found


class RestrictedCommandTests(TestCase):
    def setUp(self):
        self.commands = _commands()
        self.player = create_account("Player", "player@example.com", "testpassword123", permissions=["Player"])
        self.staff = create_account("Staff", "staff@example.com", "testpassword123", permissions=["Builder"])

    def test_removed_commands_are_gone(self):
        for key in ("charcreate", "chardelete", "access", "@about", "@time", "page"):
            self.assertNotIn(key, self.commands)

    def test_staff_only_commands(self):
        for key in ("@channel", "ooc", "quell"):
            cmd = self.commands[key]
            self.assertFalse(cmd.access(self.player, "cmd"), key)
            self.assertTrue(cmd.access(self.staff, "cmd"), key)

    def test_ic_stays_open_as_the_way_back_in(self):
        self.assertTrue(self.commands["ic"].access(self.player, "cmd"))
