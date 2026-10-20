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

import random
import time

from evennia.utils import utils

from world.accessibility import uses_screenreader

NUDGE_DELAY = 20  # seconds, non-blocking (evennia.utils.utils.delay) - "delayed" lines only

_ROOM_NUDGES = {
    "medical_bay": {
        "npc_id": "given_marr",
        "delayed": {
            "flag": "given_nudge_sent",
            "text": (
                # "find you something useful to do": LR-DEV-0014.
                "Once you're ready to go, Daven Varek can help you get further "
                "oriented and find you something useful to do - his office is "
                "just past Old Quarter Square."
            ),
        },
    },
    "daven_office": {
        "npc_id": "daven_varek",
        "delayed": {
            "flag": "daven_nudge_sent",
            "text": (
                "Go ahead and SAY something whenever you're ready - I can answer "
                "questions, find you something useful to do, and point you "
                "anywhere else on Elsewhere once we've talked."
            ),
        },
    },
}

# Owner-approved wording (LR-DEV-0001, 2026-10-16). Fires every time a
# player enters the room (see module docstring), via a room
# announcement rather than an NPC line. (lead-in, spoken blocks): each
# block is shown in bright cyan with its quotes, like any other dialogue
# (owner, 2026-10-16).
#
# How it plays (owner, 2026-10-17): a character's first time there, the
# whole announcement, TANNOY_BLOCK_PAUSE seconds between blocks. After
# that, nothing on entry: a random block 5-10 seconds in, then each of
# the others once, TANNOY_CYCLE_GAP seconds apart, then quiet until the
# next visit. A block never lands while the player is mid-conversation
# (TANNOY_QUIET_AFTER_TALK).
_ROOM_TANNOYS = {
    "medical_bay": (
        "A tannoy near the ceiling crackles to life:",
        (
            "Attention, new arrivals. To talk to someone, type SAY and then "
            "what you want to say. To move, type a direction, such as NORTH "
            "or SOUTHWEST. To look at something, type LOOK and then its name; "
            "to study it more closely, type PROBE and then its name.",
            # LR-DEV-0014 (first external playtest, 2026-10-20): no tester
            # thought to offer help, so nobody was offered an errand.
            "People around the Old Quarter often have small jobs they'd be "
            "glad of a hand with. If you're looking for something to do, ask "
            "the people you meet whether they need any help, or SAY that "
            "you're looking for work. If you use a screen reader, type "
            "OPTION/SAVE SCREENREADER=ON once and it stays on for every "
            "later visit.",
            "To change how others see you, type DESCRIBE. To speak privately "
            "with someone, wherever they are, type TELL, then their name, "
            "then your message.",
            "To talk with the other testers and the staff running this "
            "playtest, type PLAYTEST, or PT, and then your message; to stop "
            "hearing that channel, type PLAYTEST OFF.",
        ),
    ),
}

# Ends the full announcement, and each single block.
TANNOY_LINE_FULL = "To hear this again, type TANNOY."
TANNOY_LINE_SINGLE = "To hear the whole announcement, type TANNOY."
# Narration after the last block, and after each single block (LR-DEV-0009).
TANNOY_CLOSING = "The tannoy clicks off."

TANNOY_BLOCK_PAUSE = 3  # seconds between blocks, first visit
TANNOY_FIRST_BLOCK_DELAY = (5, 10)  # seconds after entry, later visits
TANNOY_CYCLE_GAP = 45  # seconds between single blocks
TANNOY_QUIET_AFTER_TALK = 15  # seconds since the player spoke or an NPC replied
TANNOY_QUIET_RETRY = 5  # seconds to wait before trying a held block again


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


def tannoy_blocks_for_room(room):
    """The announcement for `room` as a list of blocks, the lead-in on
    the first, or None if it has no tannoy."""
    if not room:
        return None
    tannoy = _tannoy_for(room)
    if not tannoy:
        return None
    lead_in, blocks = tannoy
    blocks = list(blocks)
    blocks[-1] = f"{blocks[-1]} {TANNOY_LINE_FULL}"
    spoken = [f'|c"{block}"|n' for block in blocks]
    spoken[0] = f"{lead_in} {spoken[0]}"
    spoken[-1] = f"{spoken[-1]}\n\n{TANNOY_CLOSING}"
    return spoken


def _tannoy_for(room):
    for room_tag, tannoy in _ROOM_TANNOYS.items():
        if _room_has_tag(room, room_tag):
            return tannoy
    return None


def tannoy_text_for_room(room):
    """The whole announcement for `room` at once, blocks separated by a
    blank line, or None if it has no tannoy. `commands/tannoy.py`'s
    `tannoy` command uses this: someone asking for it wants it now."""
    blocks = tannoy_blocks_for_room(room)
    return "\n\n".join(blocks) if blocks else None


def announce_tannoy(character):
    """Start this room's tannoy for the character, if it has one: the
    whole announcement on their first visit, the single-block cycle on
    later ones (see _ROOM_TANNOYS). Called on every room entry
    (maybe_schedule_nudge) and again when a player takes control of the
    character (typeclasses/characters.py's at_post_puppet): character
    creation moves a brand-new character into the Medical Bay before the
    player is logged in to it, so the arrival announcement reaches nobody
    - the puppet call is what a new player actually sees (found live,
    2026-10-16). That's also why nothing happens without a session:
    otherwise chargen's move would use up the first visit."""
    # A new room, or a fresh puppet, ends any cycle already running.
    character.ndb.tannoy_cycle = None
    room = character.location
    if not _tannoy_for(room) or not character.sessions.count():
        return
    if not character.db.heard_full_tannoy:
        character.db.heard_full_tannoy = True
        _play_full_tannoy(character, room)
        return
    token = object()
    character.ndb.tannoy_cycle = token
    order = list(range(len(_tannoy_for(room)[1])))
    random.shuffle(order)
    utils.delay(random.uniform(*TANNOY_FIRST_BLOCK_DELAY), _play_cycle_block, character, room, token, order)


def _play_full_tannoy(character, room):
    blocks = tannoy_blocks_for_room(room)
    character.ndb.tannoy_at = time.time()  # world/idle_emotes.py holds its beats after a block
    if uses_screenreader(character):
        # All at once: a block arriving mid-sentence can cut off the
        # screen reader still reading the one before.
        character.msg("\n" + "\n\n".join(blocks))
        return
    character.msg("\n" + blocks[0])
    for index, block in enumerate(blocks[1:], start=1):
        utils.delay(TANNOY_BLOCK_PAUSE * index, _send_tannoy_block, character, room, block)


def _send_tannoy_block(character, room, block):
    # Heard only in the room it's playing in.
    if character.location == room:
        character.ndb.tannoy_at = time.time()
        character.msg("\n" + block)


def _play_cycle_block(character, room, token, order):
    if character.ndb.tannoy_cycle is not token or character.location != room:
        return
    if not _conversation_quiet(character):
        utils.delay(TANNOY_QUIET_RETRY, _play_cycle_block, character, room, token, order)
        return
    lead_in, blocks = _tannoy_for(room)
    character.ndb.tannoy_at = time.time()
    character.msg(f'\n{lead_in} |c"{blocks[order[0]]} {TANNOY_LINE_SINGLE}"|n\n\n{TANNOY_CLOSING}')
    if order[1:]:
        utils.delay(TANNOY_CYCLE_GAP, _play_cycle_block, character, room, token, order[1:])
    else:
        character.ndb.tannoy_cycle = None


def _conversation_quiet(character):
    """False while the player is waiting on an NPC's reply, or spoke or
    was answered in the last TANNOY_QUIET_AFTER_TALK seconds
    (commands/say.py records both times)."""
    now = time.time()
    for moment in (character.ndb.last_spoke_at, character.ndb.npc_reply_at):
        if moment and now - moment < TANNOY_QUIET_AFTER_TALK:
            return False
    for obj in character.location.contents:
        pending = obj.ndb.pending
        if pending and character.dbref in pending:
            return False
    return True


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
