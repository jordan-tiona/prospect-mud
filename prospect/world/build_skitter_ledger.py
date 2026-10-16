"""
The Civic Office's skitter log (project owner, 2026-10-16): the
visible half of the post-quest skitter loop. Each player sees their own
logged total on `look`/`read` (typeclasses.objects.SkitterLedgerObject);
the number only goes up when Iri logs a report
(world/actions.py's log_dead_skitters_with_iri).

Idempotent: safe to re-run. The existing prop (matched by tag) is
updated in place rather than duplicated.

Run with:
    evennia shell -c "from world.build_skitter_ledger import build; build()"
"""

from evennia import create_object, search_tag

from world.build_rooms import BUILD_TAG_CATEGORY as ROOM_TAG_CATEGORY

LEDGER_TAG_CATEGORY = "skitter_ledger_prop"
LEDGER_PROP_ID = "civic_office_skitter_ledger"

# TODO(lore): placeholder wording - the ledger's physical description
# and room line are authored content (docs/lore-requests.md LR-0001).
# Kept deliberately plain and functional until the Lore lane replaces
# them; nothing here should be read as establishing how the Civic
# Office actually keeps records.
ROOM_LINE = "A ledger of pest reports lies open on a side table."
DESC = "A plain ledger for logging reported skitter kills, one line per name."


def _get_room(room_tag):
    matches = search_tag(key=room_tag, category=ROOM_TAG_CATEGORY)
    if not matches:
        raise RuntimeError(f"Room tagged '{room_tag}' not found. Run world.build_rooms.build() first.")
    return matches[0]


def build():
    room = _get_room("civic_office")

    matches = search_tag(key=LEDGER_PROP_ID, category=LEDGER_TAG_CATEGORY)
    if matches:
        ledger = matches[0]
        if not ledger.is_typeclass("typeclasses.objects.SkitterLedgerObject", exact=True):
            ledger.swap_typeclass("typeclasses.objects.SkitterLedgerObject", clean_attributes=False)
        if ledger.location != room:
            ledger.move_to(room, quiet=True)
    else:
        ledger = create_object("typeclasses.objects.SkitterLedgerObject", key="a ledger", location=room)
        ledger.tags.add(LEDGER_PROP_ID, category=LEDGER_TAG_CATEGORY)

    ledger.db.room_line = ROOM_LINE
    ledger.db.desc = DESC
    print(f"Skitter ledger ready: {ledger.key} ({ledger.dbref}) in {room.key}")
    return ledger
