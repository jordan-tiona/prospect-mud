"""
Initial playtest signpost (docs/prospect-initial-playtest-design-
spec.md 4, docs/prospect-playtest-new-characters-and-rooms.md 4): a
plain, always-visible prop in Old Quarter Square that points the way
to Daven's office, parallel to world/build_noticeboard.py's café
display but computing its route dynamically
(typeclasses.objects.SignpostObject) instead of showing hand-authored
text.

Idempotent: safe to re-run. The existing prop (matched by tag) is
updated in place rather than duplicated.

Run with:
    evennia shell -c "from world.build_signpost import build; build()"
"""

from evennia import create_object, search_tag

from world.build_rooms import BUILD_TAG_CATEGORY as ROOM_TAG_CATEGORY

SIGNPOST_TAG_CATEGORY = "signpost_prop"
SIGNPOST_PROP_ID = "old_quarter_square_signpost"

# The passive one-liner the room's own description shows automatically
# (typeclasses.rooms.Room.get_display_things reads this static
# attribute directly) - kept route-free on purpose, same convention as
# build_noticeboard.py's ROOM_LINE: a deliberate `look <signpost>` is
# what reveals the actual route.
ROOM_LINE = "A signpost stands near the square's edge, listing the streets leading off it."

# Hand-authored "what's this way" flavor for the square's existing
# spokes - plain pointers to already-established room names, not new
# lore. The route to Daven's office itself is computed dynamically by
# typeclasses.objects.SignpostObject, not written here.
SPOKE_LINES = [
    "North: the Corner Café.",
    "South: the Residential Courtyard.",
    "East: the Maintenance Workshop.",
    "West: the Civic Office.",
    "Northeast: the Lift Concourse.",
]


def _get_room(room_tag):
    matches = search_tag(key=room_tag, category=ROOM_TAG_CATEGORY)
    if not matches:
        raise RuntimeError(f"Room tagged '{room_tag}' not found. Run world.build_rooms.build() first.")
    return matches[0]


def build():
    room = _get_room("old_quarter_square")

    matches = search_tag(key=SIGNPOST_PROP_ID, category=SIGNPOST_TAG_CATEGORY)
    if matches:
        signpost = matches[0]
        if not signpost.is_typeclass("typeclasses.objects.SignpostObject", exact=True):
            signpost.swap_typeclass("typeclasses.objects.SignpostObject", clean_attributes=False)
        if signpost.location != room:
            signpost.move_to(room, quiet=True)
    else:
        signpost = create_object("typeclasses.objects.SignpostObject", key="a signpost", location=room)
        signpost.tags.add(SIGNPOST_PROP_ID, category=SIGNPOST_TAG_CATEGORY)

    signpost.db.room_line = ROOM_LINE
    signpost.db.spoke_lines = SPOKE_LINES
    print(f"Signpost ready: {signpost.key} ({signpost.dbref}) in {room.key}")
    return signpost
