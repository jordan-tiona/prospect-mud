"""
NPCs

Two typeclasses so the game can tell talk-capable NPCs from ambient
scenery (CLAUDE.md: "A `talk` command ... that clearly distinguishes
talk-capable NPCs from scenery").

`NPC` is the ambient/background case: static description only, per
design-bible 14.6's "non-LLM background population." `TalkativeNPC`
adds the `npc_id` used to load that NPC's persona file.

Phase 1 step 4 only scaffolds the typeclasses and the `npc_id`
pointer; the actual persona/lore/LLM wiring behind that id arrives in
steps 5-7.
"""

from evennia.objects.objects import DefaultObject

from .objects import ObjectParent


class NPC(ObjectParent, DefaultObject):
    """
    An ambient background character: static description only, no
    conversation. Not pickupable.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.locks.add("get:false()")


class TalkativeNPC(NPC):
    """
    A talk-capable NPC. `db.npc_id` must match a persona file at
    content/npcs/<npc_id>.md, whose HTML-comment metadata the prompt
    builder (step 5) will parse.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.npc_id = None
