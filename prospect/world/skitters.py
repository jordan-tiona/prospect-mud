"""
Quest 3 ("Unwelcome Guests" - docs/prospect-initial-playtest-design-
spec.md §6, docs/playtest-quest3-skitters-design.md): per-player kill
tracking/eligibility, plus the shared global population of skitters -
the first shared-world entity in this project, not a per-player
commitment the way every earlier quest's state has been.

Eligibility (who can see/target a skitter at all) is derived entirely
from the existing "hunt_skitters" commitment's state, via
world.commitments - there is no separate "eligible" flag to keep in
sync with it. The kill counter is separate per-player state, since a
commitment's own record has no notion of a running count.

Population management deliberately isn't a ticking Script: the
population can only change at exactly two points - the builder's
initial population, and a kill (typeclasses.creatures.Skitter.
at_defeated) - so topping it back up synchronously at each of those
two points keeps the "~2 active skitters" invariant with no timer and
nothing to test for drift between ticks.
"""

import random

from evennia import create_object, search_tag

from world.build_rooms import BUILD_TAG_CATEGORY as ROOM_TAG_CATEGORY
from world.commitments import get_state_summary

KILLS_KEY = "skitter_kills"
HUNT_COMMITMENT_TYPE = "hunt_skitters"

# docs/playtest-quest3-skitters-design.md's settled room list: every
# room except Civic Office, Daven's Office, and the Medical Bay
# (offices and the sterile recovery room are out, per the project
# owner's 2026-10-15 direction).
ELIGIBLE_ROOM_TAGS = (
    "lift_concourse",
    "old_quarter_square",
    "corner_cafe",
    "maintenance_workshop",
    "residential_courtyard",
    "old_quarter_street",
)

ACTIVE_SKITTER_COUNT = 2

# docs/prospect-initial-playtest-design-spec.md §6: "three is the
# current suggestion, so players experience respawning."
REQUIRED_KILLS = 3

SKITTER_TAG = "skitter"
SKITTER_TAG_CATEGORY = "skitter_entity"


def record_kill(actor) -> None:
    actor.attributes.add(KILLS_KEY, kills_for(actor) + 1)


def kills_for(actor) -> int:
    return int(actor.attributes.get(KILLS_KEY, default=0))


def reset_kills(actor) -> int:
    """Builder-only reset: clears this player's kill counter so a
    retest starts from zero. Returns the previous count (for the admin
    command to report) - mirrors world/noticeboard.py's
    reset_expected_revision. Without this, resetting the hunt_skitters
    commitment alone would leave an old kill count in place, letting
    report_skitter_kills succeed immediately without actually
    re-hunting anything."""
    previous = int(actor.attributes.get(KILLS_KEY, default=0))
    actor.attributes.remove(KILLS_KEY)
    return previous


def is_hunting(actor) -> bool:
    """True iff this player has an open 'hunt_skitters' commitment -
    the single source of truth both the targeting lock and the attack
    command use, so there's nothing separate to fall out of sync."""
    return get_state_summary(actor, HUNT_COMMITMENT_TYPE).startswith("open")


def _eligible_rooms():
    rooms = []
    for tag in ELIGIBLE_ROOM_TAGS:
        matches = search_tag(key=tag, category=ROOM_TAG_CATEGORY)
        if matches:
            rooms.append(matches[0])
    return rooms


def _live_skitters():
    return search_tag(key=SKITTER_TAG, category=SKITTER_TAG_CATEGORY)


def spawn_one(exclude_room=None):
    """Create one Skitter in a random eligible room, optionally
    excluding one room (the one a skitter was just defeated in, so it
    reads as "appeared elsewhere" rather than "immediately back where
    it died"). Falls back to allowing the excluded room if it's the
    only eligible room available, rather than failing to spawn at all.
    """
    rooms = _eligible_rooms()
    if not rooms:
        raise RuntimeError("No eligible rooms found. Run world.build_rooms.build() first.")

    choices = [r for r in rooms if r != exclude_room] or rooms
    room = random.choice(choices)

    skitter = create_object("typeclasses.creatures.Skitter", key="a skitter", location=room)
    # docs/playtest-quest3-skitters-design.md's approved skitter lore
    # (project owner, 2026-10-15): a small, six-legged scavenging
    # pest, roughly rat-sized - not native to Prospect, origin
    # deliberately unestablished (don't let this desc imply either).
    skitter.db.desc = (
        "A low, six-legged creature with a narrow, plated back, covered in dull gray-brown "
        "overlapping plates. Short feelers and gripping mouthparts sit on its small head. It "
        "moves in quick starts and stops, tiny claws ticking against the decking - more "
        "nuisance than real threat, but it may lunge and bite if cornered."
    )
    # Same bug class PlantingBed hit before it (typeclasses/objects.py) -
    # without this, typeclasses.rooms.Room's get_display_things falls
    # back to the full db.desc for the room listing instead of a short
    # line (confirmed live during playtesting, 2026-10-16).
    skitter.db.room_line = "A skitter scurries along the floor here, claws ticking against the decking."
    skitter.tags.add(SKITTER_TAG, category=SKITTER_TAG_CATEGORY)
    return skitter


def ensure_population(exclude_room=None):
    """Idempotent: spawns skitters until ACTIVE_SKITTER_COUNT live
    instances exist, excluding exclude_room from the first spawn only
    (a kill only ever creates a deficit of one; the builder's initial
    call passes no exclude_room at all)."""
    deficit = ACTIVE_SKITTER_COUNT - len(_live_skitters())
    for i in range(max(deficit, 0)):
        spawn_one(exclude_room=exclude_room if i == 0 else None)
