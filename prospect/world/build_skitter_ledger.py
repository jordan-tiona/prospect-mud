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

# Copy of content/objects/civic_office_skitter_ledger.md (owner-approved,
# LR-0001) and the aliases in sectors/elsewhere/sector.json; this must
# match them until build_sector() replaces this script - copy changes
# across, never edit only here.
KEY = "a pest log"
ALIASES = ["log", "screen"]
ROOM_LINE = "A small screen at the end of the counter shows the office's pest log."
DESC = (
    "The office's pest log, kept on a small screen at the end of the counter: a running list of names, "
    "each with the number of skitters that person has reported putting down. Iri Vael enters the reports "
    "as people bring them in."
)


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
        ledger = create_object("typeclasses.objects.SkitterLedgerObject", key=KEY, location=room)
        ledger.tags.add(LEDGER_PROP_ID, category=LEDGER_TAG_CATEGORY)

    # Set on every run, so a rebuild renames an existing object too.
    ledger.key = KEY
    ledger.aliases.clear()
    ledger.aliases.add(ALIASES)
    ledger.db.room_line = ROOM_LINE
    ledger.db.desc = DESC
    print(f"Skitter ledger ready: {ledger.key} ({ledger.dbref}) in {room.key}")
    return ledger
