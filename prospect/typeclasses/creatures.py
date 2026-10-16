"""
Creatures

Generic, shared-world, combat-capable entities - distinct from
typeclasses.npcs.NPC (static ambient scenery, no combat concept) and
typeclasses.npcs.TalkativeNPC (LLM-voiced, conversational). NPC's own
docstring already named this as planned ("not the roaming/combat-
capable NPC class the project owner has in mind as a separate, later
class") - Quest 3 ("Unwelcome Guests," docs/playtest-quest3-skitters-
design.md) is where it's actually built, with Skitter as its first
concrete instance rather than a one-off typeclass.

Creature owns only the generic, reusable mechanics: hp tracking,
damage application, and the no_superuser_bypass lock plumbing a
per-player targeting lock needs to actually work against the one
account doing the real playtesting (docs/engineering-pitfalls.md #2 -
the same lesson typeclasses.objects.CommitmentHintObject already
learned). It deliberately knows nothing about eligibility rules,
kill-crediting, or respawning - those are quest-specific and belong on
the subclass, the same boundary typeclasses.objects.RoomObject draws
against its own specific subclasses.
"""

from .objects import ObjectParent
from evennia.objects.objects import DefaultObject


class Creature(ObjectParent, DefaultObject):
    """
    Generic shared-world, combat-capable creature base. Not pickupable
    and not an NPC (no conversation, no npc_id). Subclasses set
    max_hp and override at_defeated() for their own kill-crediting/
    respawn behavior.
    """

    max_hp = 1
    # Materia Magica-style threshold health feedback (project owner,
    # 2026-10-16): never show a number, just an ordered sequence of
    # (fraction_threshold, descriptor) pairs, *most severe first* -
    # health_descriptor() returns the first one whose threshold is
    # still >= the creature's current hp/max_hp fraction, so a lower,
    # more severe threshold that also matches takes priority over a
    # less severe one earlier in a hp range that happens to overlap
    # it. Empty by default: a subclass with nothing to say about being
    # hurt just gets no extra line, not an error.
    health_descriptors: tuple = ()

    def at_object_creation(self):
        super().at_object_creation()
        self.locks.add("get:false()")
        self.db.hp = self.max_hp

    def health_descriptor(self):
        """Flavor text for the creature's current hp fraction (read
        after take_damage() lands, while it's still alive), or None if
        this subclass has nothing to say or hp tracking isn't set up."""
        if not self.health_descriptors or not self.max_hp:
            return None
        hp = self.db.hp if self.db.hp is not None else self.max_hp
        fraction = max(hp, 0) / self.max_hp
        for threshold, text in self.health_descriptors:
            if fraction <= threshold:
                return text
        return None

    def access(self, accessing_obj, access_type="read", default=False, no_superuser_bypass=False, **kwargs):
        if access_type in ("view", "search"):
            no_superuser_bypass = True
        return super().access(
            accessing_obj,
            access_type=access_type,
            default=default,
            no_superuser_bypass=no_superuser_bypass,
            **kwargs,
        )

    def take_damage(self, amount, attacker=None):
        """
        Apply damage. Returns True if this reduces hp to 0 or below -
        at_defeated() has already run by the time this returns in that
        case. The caller (e.g. commands/attack.py's CmdAttack) should
        treat a True return as "this creature is gone now" and not act
        on it further (it may already be deleted).
        """
        current = self.db.hp if self.db.hp is not None else self.max_hp
        self.db.hp = current - amount
        if self.db.hp <= 0:
            self.at_defeated(attacker=attacker)
            return True
        return False

    def at_defeated(self, attacker=None):
        """
        Base behavior: just delete self. A subclass that needs to
        record a kill or trigger a respawn should do that work first,
        then call super().at_defeated(attacker=attacker) to actually
        remove the object.
        """
        self.delete()


class Skitter(Creature):
    """
    A small, six-legged scavenging pest, roughly rat-sized - approved
    content as of 2026-10-15 (docs/playtest-quest3-skitters-design.md).
    Origin and biology stay deliberately unestablished per the design
    spec; don't invent either here.

    max_hp is a balance number, not lore - easy to retune later
    without a design conversation. The targeting lock is set here,
    not by whatever builder/respawn code creates an instance, because
    (unlike typeclasses.objects.CommitmentHintObject's per-scenario
    commitment_type argument) skitter_targetable() takes no
    per-instance argument - every skitter uses the same eligibility
    rule, so setting it once here means every instance, including ones
    spawned later by world.skitters.ensure_population(), automatically
    carries the correct lock with nothing to remember at each call
    site.
    """

    max_hp = 3
    # Most severe first (see Creature.health_descriptors) - with
    # max_hp=3 and the starter weapon's 1 damage per hit, this lands
    # on exactly one descriptor per non-lethal hit: "scratches" after
    # the first, "badly hurt" after the second, defeated on the third.
    health_descriptors = (
        (0.34, "looks badly hurt"),
        (0.67, "has a few light scratches"),
    )

    def at_object_creation(self):
        super().at_object_creation()
        self.locks.add("view:skitter_targetable();search:skitter_targetable()")

    def at_defeated(self, attacker=None):
        from world.skitters import ensure_population, record_kill

        room = self.location
        if attacker is not None:
            record_kill(attacker)
        super().at_defeated(attacker=attacker)
        ensure_population(exclude_room=room)
