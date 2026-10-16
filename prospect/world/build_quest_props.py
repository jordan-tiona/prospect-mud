"""
Discoverable quest-prop objects: the project owner's discoverability
rule (2026-10-13) that every quest/commitment should have some
passive, in-world cue a player can stumble onto, not just a
conversational trigger they have to think to ask about.
world.commitments.hint_pose_for already does this for an NPC's own
pose (Tarin "frowning over a shipment manifest"); this module is the
equivalent for a room object.

Each prop is a real typeclasses.objects.CommitmentHintObject - not pickable
(get:false(), same as any other scenery) - whose `view`/`search` locks are
wired to a per-player lock func (usually server/conf/lockfuncs.py's
commitment_hint_visible, keyed on a generic commitment_type; a quest with
its own bespoke state instead uses its own lock func - see
module_exchange_hint_visible), so it's genuinely per-player: visible only
to a looker who hasn't engaged with the errand yet. Once a player's been
offered it, declined it, accepted it, or finished it, the object quietly
stops existing for them (on every future look, not just once) - a
different player who hasn't touched it yet still sees it fresh. No
separate timer, despawn, or respawn logic is needed; it falls out of the
lock check alone.

Idempotent: safe to re-run. Existing props (matched by tag) are
updated in place rather than duplicated.

Run with:
    evennia shell -c "from world.build_quest_props import build; build()"
"""

from evennia import create_object, search_tag

from world.build_rooms import BUILD_TAG_CATEGORY as ROOM_TAG_CATEGORY

QUEST_PROP_TAG_CATEGORY = "quest_prop"

# (prop_id, room_tag, key, room_line, desc, lock_func_call)
# room_line is the one-liner shown as part of the room's own
# description (typeclasses.rooms.Room's get_display_things); desc is
# the longer text shown on an explicit `look <prop>`. Kept deliberately
# mundane - "nothing suspicious here" is the scenario's own framing
# (content/npcs/mara_voss.md), not something to dramatize. lock_func_call
# is the view/search lock func call (e.g. "commitment_hint_visible
# (deliver_parcel)") - most props key off a generic commitment_type via
# server/conf/lockfuncs.py's commitment_hint_visible, but a quest with its
# own bespoke state (the heating-unit module exchange below) uses its own
# lock func instead (module_exchange_hint_visible), same per-player
# "not started yet" bar, just a different state source.
QUEST_PROPS = [
    (
        "misdelivered_parcel_hint",
        "corner_cafe",
        "a small parcel",
        "A small parcel sits on the counter, unopened.",
        "A small, plainly wrapped parcel. The shipping label reads: "
        '"Tarin Os, Maintenance Workshop." It was clearly meant to go '
        "there, not here.",
        "commitment_hint_visible(deliver_parcel)",
    ),
    (
        "faulty_heating_module_hint",
        "corner_cafe",
        "a faulty heating module",
        "A small temperature-control module sits pulled loose from the heating unit, clearly not seated right.",
        "A removable temperature-control module, worked free of the café's heating unit. It looks like the kind "
        "of ordinary part Tarin Os at the Maintenance Workshop would know how to deal with.",
        "module_exchange_hint_visible()",
    ),
]


def _get_room(room_tag):
    matches = search_tag(key=room_tag, category=ROOM_TAG_CATEGORY)
    if not matches:
        raise RuntimeError(f"Room tagged '{room_tag}' not found. Run world.build_rooms.build() first.")
    return matches[0]


def _get_or_create_prop(prop_id, key, room, room_line, desc, lock_func_call):
    lock_string = f"view:{lock_func_call};search:{lock_func_call};get:false()"

    matches = search_tag(key=prop_id, category=QUEST_PROP_TAG_CATEGORY)
    if matches:
        prop = matches[0]
        if not prop.is_typeclass("typeclasses.objects.CommitmentHintObject", exact=True):
            # Upgrades an existing prop created before this typeclass
            # existed (confirmed live, 2026-10-13: plain RoomObject's
            # access() doesn't defeat Evennia's superuser bypass, which
            # made the hint invisible-to-everyone-except-actually-
            # effective-for-no-one on a solo dev's own superuser account).
            prop.swap_typeclass("typeclasses.objects.CommitmentHintObject", clean_attributes=False)
        if prop.location != room:
            prop.move_to(room, quiet=True)
        prop.db.room_line = room_line
        prop.db.desc = desc
        prop.locks.add(lock_string)
        return prop

    prop = create_object("typeclasses.objects.CommitmentHintObject", key=key, location=room)
    prop.db.room_line = room_line
    prop.db.desc = desc
    prop.locks.add(lock_string)
    prop.tags.add(prop_id, category=QUEST_PROP_TAG_CATEGORY)
    return prop


def build():
    props = {}
    for prop_id, room_tag, key, room_line, desc, lock_func_call in QUEST_PROPS:
        room = _get_room(room_tag)
        prop = _get_or_create_prop(prop_id, key, room, room_line, desc, lock_func_call)
        props[prop_id] = prop
        print(f"Quest prop ready: {prop.key} ({prop.dbref}) in {room.key}")
    return props
