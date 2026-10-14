"""
Phase 2D's civic information display (docs/phase2-quest-prototype-
design.md §14, docs/phase2d-noticeboard-check-proposal.md): one
typeclasses.objects.RevisionDisplayObject in the café, always present
and visible to everyone - only its examined content is per-player
(see that class's docstring and world/noticeboard.py).

Idempotent: safe to re-run. The existing prop (matched by tag) is
updated in place rather than duplicated.

Run with:
    evennia shell -c "from world.build_noticeboard import build; build()"
"""

from evennia import create_object, search_tag

from world.build_rooms import BUILD_TAG_CATEGORY as ROOM_TAG_CATEGORY

NOTICEBOARD_TAG_CATEGORY = "noticeboard_prop"
DISPLAY_PROP_ID = "civic_information_display"

# The passive one-liner the room's own description shows (typeclasses.
# rooms.Room's get_display_things reads this static attribute
# directly, not the per-looker get_display_desc override) - kept
# number-free on purpose: a deliberate `look <display>` is what
# reveals the actual per-player revision, not a glance around the room.
ROOM_LINE = "A small civic information display cycles through local notices."


def _get_room(room_tag):
    matches = search_tag(key=room_tag, category=ROOM_TAG_CATEGORY)
    if not matches:
        raise RuntimeError(f"Room tagged '{room_tag}' not found. Run world.build_rooms.build() first.")
    return matches[0]


def build():
    room = _get_room("corner_cafe")

    matches = search_tag(key=DISPLAY_PROP_ID, category=NOTICEBOARD_TAG_CATEGORY)
    if matches:
        display = matches[0]
        if not display.is_typeclass("typeclasses.objects.RevisionDisplayObject", exact=True):
            display.swap_typeclass("typeclasses.objects.RevisionDisplayObject", clean_attributes=False)
        if display.location != room:
            display.move_to(room, quiet=True)
    else:
        display = create_object(
            "typeclasses.objects.RevisionDisplayObject", key="a civic information display", location=room
        )
        display.tags.add(DISPLAY_PROP_ID, category=NOTICEBOARD_TAG_CATEGORY)

    display.db.room_line = ROOM_LINE
    print(f"Noticeboard prop ready: {display.key} ({display.dbref}) in {room.key}")
    return display
