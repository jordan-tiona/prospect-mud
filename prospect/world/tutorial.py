"""
Tutorial proactive-nudge mechanic (project owner, 2026-10-14): Given
Marr and Daven Varek are otherwise purely reactive like every NPC in
the game (commands/say.py's engage_npc only ever runs when a player
addresses one) - live playtesting showed a brand-new player sitting
in Given's or Daven's room with no idea they were expected to speak
up, or where to go next. This module adds scripted (not LLM-
generated - see below), one-time lines per NPC, so a fresh player
always gets them regardless of what they do or don't say first.

`delayed`: said NUDGE_DELAY seconds after arrival, if the player is
still there. Right now, pointing a player at Daven once they're done
with Given, and inviting a player in Daven's office to speak up.

Scripted, not an LLM call (project owner's call): Daven's destination
is one of the things that must always be said exactly, not something
to hand to the model.

Separately, `_ROOM_TANNOYS` (project owner, 2026-10-15, after watching
a brand-new player get lost navigating out of the medical bay) covers
basic command mechanics (SAY, movement) with a room announcement
rather than an NPC line, so it's clearly OOC framing rather than
something Given says in character. Unlike the nudges above, a tannoy
fires every time a player enters that room, not once - the project
owner's explicit call: "I'd be okay with this happening every time...
I don't expect most players to be back there" once they're past
onboarding, so there's no per-player "already heard it" state to
track. `commands/tannoy.py`'s `tannoy` command repeats the same text
on demand.

Delivery is unconditional, not conversation-gated: an earlier version
of this module cancelled a pending nudge the moment the player said
*anything* to the NPC, on the theory that a real conversation makes
the scripted hint redundant. The project owner caught the real risk
in that before it shipped - a player who just says "Hi" gets back
whatever small talk the model happens to generate, which is not
guaranteed to ever mention SAY or Daven, and that one line permanently
cancelled the only mechanism that guaranteed it would be said. So
every line here only tracks "have I already said this to this
character" (one `db.*_sent` flag per line) and fires once per
character regardless of what they've said - a player who was already
told all of this in conversation just hears a harmless, brief repeat;
a player who wasn't still gets it.

Every line is still appended to the NPC's own conversation history
(the same per-player list commands/say.py's engage_npc reads and
writes via ndb.conversations) so that if the model is asked about it
later ("didn't you just say something?"), it has the line in context
rather than being blindsided by something it doesn't remember saying.
"""

from evennia.utils import utils

NUDGE_DELAY = 20  # seconds, non-blocking (evennia.utils.utils.delay) - "delayed" lines only

_ROOM_NUDGES = {
    "medical_bay": {
        "npc_id": "given_marr",
        "delayed": {
            "flag": "given_nudge_sent",
            "text": (
                "Once you're ready to go, Daven Varek can help you get further "
                "oriented - his office is just past Old Quarter Square."
            ),
        },
    },
    "daven_office": {
        "npc_id": "daven_varek",
        "delayed": {
            "flag": "daven_nudge_sent",
            "text": (
                "Go ahead and SAY something whenever you're ready - I can answer "
                "questions and point you anywhere else on Elsewhere once we've talked."
            ),
        },
    },
}

# Owner-approved wording (LR-DEV-0001, 2026-10-16). Fires every time a
# player enters the room (see module docstring), via a room
# announcement rather than an NPC line. (lead-in, spoken words): the
# spoken part is shown in bright cyan with its quotes, like any other
# dialogue (owner, 2026-10-16).
_ROOM_TANNOYS = {
    "medical_bay": (
        "A tannoy near the ceiling crackles to life:",
        "Attention, new arrivals. To talk to someone, type SAY and then what "
        "you want to say. To move, type a direction, such as NORTH or "
        "SOUTHWEST. To look at something you can see, type LOOK and then its "
        "name. To study it more closely, type PROBE and then its name. To "
        "hear this again, type TANNOY.",
    ),
}


def _room_has_tag(room, tag):
    from world.build_rooms import BUILD_TAG_CATEGORY

    return bool(room.tags.get(tag, category=BUILD_TAG_CATEGORY))


def _find_npc(room, npc_id):
    for obj in room.contents:
        if getattr(obj.db, "npc_id", None) == npc_id:
            return obj
    return None


def _speak(character, npc, text):
    character.msg("\n" + f'{npc.key} says to you, |c"{text}"|n')
    if npc.ndb.conversations is None:
        npc.ndb.conversations = {}
    npc.ndb.conversations.setdefault(character.dbref, []).append(
        {"role": "assistant", "content": text}
    )


def tannoy_text_for_room(room):
    """The announcement text for `room`, or None if it has no tannoy.
    Shared by `maybe_schedule_nudge` (fires it on every entry) and
    `commands/tannoy.py`'s `tannoy` command (repeats it on demand)."""
    if not room:
        return None
    for room_tag, (lead_in, speech) in _ROOM_TANNOYS.items():
        if _room_has_tag(room, room_tag):
            return f'{lead_in} |c"{speech}"|n'
    return None


def announce_tannoy(character):
    """Send the character's current room's tannoy text, if it has one.
    Called on every room entry (maybe_schedule_nudge) and again when a
    player takes control of the character (typeclasses/characters.py's
    at_post_puppet): character creation moves a brand-new character into
    the Medical Bay before the player is logged in to it, so the arrival
    announcement reaches nobody - the puppet call is what a new player
    actually sees (found live, 2026-10-16)."""
    tannoy_text = tannoy_text_for_room(character.location)
    if tannoy_text:
        character.msg("\n" + tannoy_text)


def maybe_schedule_nudge(character):
    """Call whenever a character enters a room (typeclasses/
    characters.py's at_post_move). Delivers this room's tannoy text,
    if any, every time - then schedules this room's `delayed` NPC
    line, for any line that hasn't already fired for this character -
    a character can collect lines from more than one room over the
    course of the tutorial, in whatever order they actually visit
    them."""
    room = character.location
    if not room:
        return

    announce_tannoy(character)

    for room_tag, config in _ROOM_NUDGES.items():
        if not _room_has_tag(room, room_tag):
            continue
        npc = _find_npc(room, config["npc_id"])
        if not npc:
            continue

        delayed = config.get("delayed")
        if delayed and not getattr(character.db, delayed["flag"], False):
            utils.delay(NUDGE_DELAY, _fire_delayed_nudge, character, npc, room_tag)


def _fire_delayed_nudge(character, npc, room_tag):
    delayed = _ROOM_NUDGES[room_tag]["delayed"]
    # Re-checked at fire time, not trusted from when this was
    # scheduled: skip if it already fired some other way (shouldn't
    # happen, nothing else sets this flag, but cheap to guard) or the
    # player has since left the room.
    if getattr(character.db, delayed["flag"], False):
        return
    if character.location != npc.location:
        return

    _speak(character, npc, delayed["text"])
    setattr(character.db, delayed["flag"], True)
