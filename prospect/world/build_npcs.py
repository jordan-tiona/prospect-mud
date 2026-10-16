"""
Phase 1 prototype NPC builder.

Spawns the three talk-capable NPCs from design-bible 14.6, placed per
each persona file's `room` metadata in content/npcs/<npc_id>.md. Step
4 scaffolding only: each NPC just gets its `npc_id` pointer here. The
prompt builder that actually reads the persona file arrives in step 5.

Idempotent: safe to re-run. Existing NPCs (matched by tag) are left
alone rather than duplicated.

Run with:
    evennia shell -c "from world.build_npcs import build; build()"
"""

from evennia import create_object, search_tag

from world.build_rooms import BUILD_TAG_CATEGORY as ROOM_TAG_CATEGORY
from world.npc_profile import parse_persona

NPC_TAG_CATEGORY = "phase1_npcs"

# (npc_id, display name, room tag from world.build_rooms.ROOMS)
# The first name is added as an alias so players can address the NPC
# by it alone (e.g. "say to Mara, ...") - see world.npc_addressing.
NPCS = [
    ("mara_voss", "Mara Voss", "corner_cafe"),
    ("tarin_os", "Tarin Os", "maintenance_workshop"),
    ("iri_vael", "Iri Vael", "civic_office"),
    ("veska_renn", "Veska Renn", "civic_office"),
    ("given_marr", "Given Marr", "medical_bay"),
    ("daven_varek", "Daven Varek", "daven_office"),
]


def _get_room(room_tag):
    matches = search_tag(key=room_tag, category=ROOM_TAG_CATEGORY)
    if not matches:
        raise RuntimeError(
            f"Room tagged '{room_tag}' not found. Run world.build_rooms.build() first."
        )
    return matches[0]


def _get_or_create_npc(npc_id, name, room):
    matches = search_tag(key=npc_id, category=NPC_TAG_CATEGORY)
    if matches:
        npc = matches[0]
        if npc.location != room:
            npc.move_to(room, quiet=True)
        first_name = name.split()[0]
        if first_name not in npc.aliases.all():
            npc.aliases.add(first_name)
    else:
        npc = create_object("typeclasses.npcs.TalkativeNPC", key=name, location=room)
        npc.db.npc_id = npc_id
        npc.tags.add(npc_id, category=NPC_TAG_CATEGORY)
        first_name = name.split()[0]
        npc.aliases.add(first_name)

    # Persona's optional `desc` metadata field (world/npc_profile.py) -
    # re-applied on every run so an updated persona file's desc takes
    # effect without deleting and recreating the NPC. An NPC with no
    # `desc` field yet (nothing authored) is left alone rather than
    # overwritten with a blank string.
    desc = parse_persona(npc_id).desc
    if desc:
        npc.db.desc = desc

    return npc


def build():
    npcs = {}
    for npc_id, name, room_tag in NPCS:
        room = _get_room(room_tag)
        npc = _get_or_create_npc(npc_id, name, room)
        npcs[npc_id] = npc
        print(f"NPC ready: {npc.key} ({npc.dbref}) in {room.key}")
    return npcs
