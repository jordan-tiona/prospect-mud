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

import random

from evennia import TICKER_HANDLER
from evennia.objects.objects import DefaultObject

from .objects import ObjectParent

# How often an ambient NPC's pose silently rotates, in seconds. Project
# owner's call: background texture, not an event worth broadcasting -
# a player only notices on their next `look`. One shared default for
# now; revisit per-NPC if some should feel busier than others.
POSE_ROTATE_INTERVAL = 600


class NPC(ObjectParent, DefaultObject):
    """
    An ambient background character: static description only, no
    conversation. Not pickupable.

    Optional `db.ambient_pose` (e.g. "idly drying a glass") is read by
    typeclasses.rooms.Room to show "<name> is here, <pose>." instead of
    the bare "<name> is here." - authored content, same as everything
    else about an NPC.

    For an NPC with several possible poses that should occasionally
    switch (the project owner's idea so background characters don't
    feel frozen in place), call `set_ambient_poses([...])` instead of
    setting `db.ambient_pose` directly - this seeds an initial random
    pose and subscribes to a TickerHandler that silently swaps to
    another pose from the list every `POSE_ROTATE_INTERVAL` seconds.
    Silent and on a timer (not a real-time actor): this class is still
    static scenery, not the roaming/combat-capable NPC class the
    project owner has in mind as a separate, later class.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.locks.add("get:false()")

    def set_ambient_poses(self, poses):
        """Author a rotating set of poses for this NPC (see class
        docstring). `poses` must be non-empty."""
        self.db.ambient_poses = list(poses)
        self.db.ambient_pose = random.choice(self.db.ambient_poses)
        TICKER_HANDLER.add(
            interval=POSE_ROTATE_INTERVAL,
            callback=self.at_pose_tick,
            idstring="ambient_pose",
        )

    def at_pose_tick(self, *args, **kwargs):
        """TickerHandler callback: silently swap to a different pose
        from `db.ambient_poses`. No message is sent anywhere - a
        present player only sees the change on their next `look`."""
        poses = self.db.ambient_poses
        if not poses:
            return
        choices = [pose for pose in poses if pose != self.db.ambient_pose] or poses
        self.db.ambient_pose = random.choice(choices)


class TalkativeNPC(NPC):
    """
    A talk-capable NPC. `db.npc_id` must match a persona file at
    content/npcs/<npc_id>.md, whose HTML-comment metadata the prompt
    builder (step 5) will parse.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.npc_id = None
