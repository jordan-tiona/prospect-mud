"""
Quest 3's ("Unwelcome Guests") combat command (docs/prospect-initial-
playtest-design-spec.md §7's command-language table: "attack skitter",
"kill skitter", "k skitter", "hit the skitter with my baton"). A plain
world command, not an NPC tool call - no LLM involved, same category
as commands/use.py.

Targeting goes through Evennia's own lock-respecting search(), so an
ineligible player's `attack skitter` fails exactly like `look skitter`
would ("you don't see that here") - no special-casing needed on top
of typeclasses.creatures.Skitter's own view/search lock.

Accepts two equivalent phrasings:
    attack <target>
    attack <target> with <item>
If no `with <item>` clause is given and the player is holding exactly
one Weapon, that weapon is used automatically.
"""

import re

from commands.command import Command

_WITH_RE = re.compile(r"^(?P<target>.+?)\s+with\s+(?P<item>.+)$", re.IGNORECASE)


class CmdAttack(Command):
    """
    Attack a creature.

    Usage:
      attack <target>
      attack <target> with <item>
    """

    key = "attack"
    aliases = ["kill", "k", "hit"]
    locks = "cmd:all()"
    help_category = "General"

    def parse(self):
        args = self.args.strip()
        match = _WITH_RE.match(args)
        if match:
            self.target_name = match.group("target").strip()
            self.item_name = match.group("item").strip()
        else:
            self.target_name = args
            self.item_name = ""

    def func(self):
        caller = self.caller
        if not self.target_name:
            caller.msg("Attack what?")
            return

        matches = caller.search(self.target_name, location=caller.location, quiet=True)
        target = matches[0] if matches else None
        if target is None or not target.is_typeclass("typeclasses.creatures.Creature", exact=False):
            caller.msg(f"You don't see {self.target_name!r} here to attack.")
            return

        weapon = self._find_weapon(caller)
        if weapon is None:
            caller.msg("You don't have anything to fight it with.")
            return

        target_name = target.get_display_name(caller)
        weapon_name = weapon.get_display_name(caller)
        defeated = target.take_damage(weapon.db.damage or 1, attacker=caller)
        if defeated:
            caller.msg(f"You defeat {target_name}.")
            return

        descriptor = target.health_descriptor()
        if descriptor:
            caller.msg(f"You hit {target_name} with {weapon_name}. It {descriptor}.")
        else:
            caller.msg(f"You hit {target_name} with {weapon_name}.")

    def _find_weapon(self, caller):
        if self.item_name:
            matches = caller.search(self.item_name, location=caller, quiet=True)
            item = matches[0] if matches else None
            if item is not None and item.is_typeclass("typeclasses.objects.Weapon", exact=False):
                return item
            return None
        for obj in caller.contents:
            if obj.is_typeclass("typeclasses.objects.Weapon", exact=False):
                return obj
        return None
