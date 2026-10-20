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
    locks             - optional lock string template, formatted from params
    probe             - False for kinds whose look text is per-player and that
                        ignore db.probe_desc (commands/probe.py); default True
    glance            - False for kinds whose room line is left out of the
                        arrival glance (shown only on an explicit `look`);
                        default True. A content file's `glance: show | hide`
                        metadata line overrides it per object, and the export
                        writes the result as the `in_glance` attribute
                        (typeclasses/rooms.py; LR-LORE-0005). NPC kinds
                        ignore it: their presence lines always show.
    container         - True for kinds other entities can be placed
                        inside (a sector entity's optional `inside`
                        field names one; docs/mud-editor-sector-
                        format.md Section 4). Default False
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

# Rooms game code finds by tag, per sector. ops/editor/check.py reports a
# sector missing one as an error (so export refuses), and world.build_sector
# never prunes one. Drafted by the Tools lane from the Dev review of
# docs/build-sector-proposal.md (Section 8, item 3); pending Dev confirmation.
REQUIRED_ROOM_IDS = {
    "elsewhere": [
        "medical_bay",  # world/chargen.py place_in_medical_bay; world/tutorial.py tannoy + nudge
        "daven_office",  # typeclasses/objects.py SignpostObject route; world/tutorial.py nudge
        # world/skitters.py ELIGIBLE_ROOM_TAGS (skitter spawn rooms):
        "lift_concourse",
        "old_quarter_square",
        "corner_cafe",
        "maintenance_workshop",
        "residential_courtyard",
        "old_quarter_street",
    ],
}

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
        "glance": False,  # the room prose carries their atmosphere
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
        # Filled from params (a missing param formats as ""); see
        # world/build_quest_props.py's lock_string.
        "locks": "view:{visibility}({commitment_type});search:{visibility}({commitment_type});get:false()",
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
        "probe": False,  # per-looker look text; probe shows it too
        "typeclass": "typeclasses.objects.RevisionDisplayObject",
        "tag_category": "noticeboard_prop",
        "content_dir": "objects",
        "id_field": "object_id",
        "required_sections": ["Short Description"],
        "needs_heading": True,
        "params": {},
    },
    "signpost": {
        "probe": False,  # per-looker look text; probe shows it too
        "typeclass": "typeclasses.objects.SignpostObject",
        "tag_category": "signpost_prop",
        "content_dir": "objects",
        "id_field": "object_id",
        "required_sections": ["Short Description", "Spoke Lines"],
        "needs_heading": True,
        "params": {},
    },
    "skitter_ledger": {
        "probe": False,  # per-looker look text; probe shows it too
        "typeclass": "typeclasses.objects.SkitterLedgerObject",
        "tag_category": "skitter_ledger_prop",
        "content_dir": "objects",
        "id_field": "object_id",
        "required_sections": ["Short Description", "Description"],
        "needs_heading": True,
        "params": {},
    },
    "gardening_kit": {
        "typeclass": "typeclasses.objects.GardeningKit",
        "tag_category": "garden_prop",
        "content_dir": "objects",
        "id_field": "object_id",
        # No room line once it sits inside the communal locker
        # (LR-DEV-0013); a kit left loose in a room still wants one.
        "required_sections": ["Description"],
        "needs_heading": True,
        "params": {},
    },
    "container": {
        # A fixture players take things out of (`get <item> from <it>`,
        # or just `get <item>` in its room); what it holds is placed in
        # the sector with `inside` (LR-DEV-0013's communal locker).
        "typeclass": "typeclasses.objects.Container",
        "tag_category": "container",
        "content_dir": "objects",
        "id_field": "object_id",
        "required_sections": ["Short Description", "Description"],
        "needs_heading": True,
        "params": {},
        "container": True,
    },
    "planting_bed": {
        "glance": False,  # playtest spec: keep the beds out of the listing
        "probe": False,  # per-looker look text; probe shows it too
        "typeclass": "typeclasses.objects.PlantingBed",
        "tag_category": "garden_prop",
        "content_dir": "objects",
        "id_field": "object_id",
        "required_sections": ["Short Description", "Description"],
        "needs_heading": True,
        "params": {},
    },
}
