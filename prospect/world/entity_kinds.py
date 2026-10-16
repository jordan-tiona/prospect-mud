"""
Allowlist of entity kinds a sector file may place (docs/mud-editor-
sector-format.md Section 5).

Dev-lane owned: adding a kind, or a new allowed param value (e.g. a new
lock func), is a Dev change - the MUD editor and its exporter can only
choose from what's listed here. Drafted by the Tools lane (2026-10-16)
to mirror exactly what today's world/build_*.py scripts create; pending
Dev-lane review. Not imported by the game yet.

Plain literal data only: ops/editor reads it with ast.literal_eval,
without importing the game.

Per kind:
    typeclass         - what create_object builds
    tag_category      - existing Evennia tag category, so already-built
                        objects keep matching (never rename)
    content_dir       - where its content file lives, relative to content/
    id_field          - the content file's metadata field holding its id
    required_sections - '## Heading' sections the content file must have
    needs_heading     - content file's '# Heading' is the object's key
    params            - {name: {"values": [...], "required": bool}}
"""

ROOM_KIND = {
    "typeclass": "typeclasses.rooms.Room",
    "tag_category": "phase1_neighborhood",
    "content_dir": "rooms",
    "id_field": "room_id",
    "required_sections": ["Description"],
    "needs_heading": False,
    "params": {},
}

EXIT_TYPECLASS = "typeclasses.exits.Exit"

KINDS = {
    "talk_npc": {
        "typeclass": "typeclasses.npcs.TalkativeNPC",
        "tag_category": "phase1_npcs",
        "content_dir": "npcs",
        "id_field": "npc_id",
        "required_sections": [],
        "needs_heading": True,
        "params": {},
    },
    "ambient_npc": {
        "typeclass": "typeclasses.npcs.NPC",
        "tag_category": "phase1_ambient",
        "content_dir": "ambient/npcs",
        "id_field": "ambient_id",
        "required_sections": ["Poses", "Description"],
        "needs_heading": True,
        "params": {},
    },
    "ambient_object": {
        "typeclass": "typeclasses.objects.RoomObject",
        "tag_category": "phase1_ambient",
        "content_dir": "ambient/objects",
        "id_field": "object_id",
        "required_sections": ["Short Description", "Description"],
        "needs_heading": True,
        "params": {},
    },
    "quest_prop": {
        "typeclass": "typeclasses.objects.CommitmentHintObject",
        "tag_category": "quest_prop",
        "content_dir": "objects",
        "id_field": "object_id",
        "required_sections": ["Short Description", "Description"],
        "needs_heading": True,
        "params": {
            # server/conf/lockfuncs.py - used for both view: and search: locks
            "visibility": {
                "values": ["commitment_hint_visible", "module_exchange_hint_visible"],
                "required": True,
            },
            # commitment_hint_visible's argument
            "commitment_type": {"values": ["deliver_parcel"], "required": False},
        },
    },
    "revision_display": {
        "typeclass": "typeclasses.objects.RevisionDisplayObject",
        "tag_category": "noticeboard_prop",
        "content_dir": "objects",
        "id_field": "object_id",
        "required_sections": ["Short Description"],
        "needs_heading": True,
        "params": {},
    },
    "signpost": {
        "typeclass": "typeclasses.objects.SignpostObject",
        "tag_category": "signpost_prop",
        "content_dir": "objects",
        "id_field": "object_id",
        "required_sections": ["Short Description", "Spoke Lines"],
        "needs_heading": True,
        "params": {},
    },
    "gardening_kit": {
        "typeclass": "typeclasses.objects.GardeningKit",
        "tag_category": "garden_prop",
        "content_dir": "objects",
        "id_field": "object_id",
        "required_sections": ["Short Description", "Description"],
        "needs_heading": True,
        "params": {},
    },
    "planting_bed": {
        "typeclass": "typeclasses.objects.PlantingBed",
        "tag_category": "garden_prop",
        "content_dir": "objects",
        "id_field": "object_id",
        "required_sections": ["Short Description", "Description"],
        "needs_heading": True,
        "params": {},
    },
}
