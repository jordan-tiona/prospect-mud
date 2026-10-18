"""
Idle emotes (LR-LORE-0006, owner 2026-10-18): now and then an NPC in a
room with players does something small - "Mara wipes down a stretch of
counter that was already clean." - from its authored `## Emotes` list
(db.emotes, set by the sector build from the ambient NPC file or the
persona file; world/npc_profile.py cuts the section out of the persona
body so it never reaches a prompt). Engine output, no LLM call.

How it plays, modelled on the Medical Bay tannoy (world/tutorial.py):
nothing on entry; the first line EMOTE_FIRST_DELAY seconds after a
player arrives in a quiet room, then one every EMOTE_GAP seconds, for
as long as any player is there. One timer per room, not per NPC, so
two NPCs sharing a room never emote back to back; each beat prefers a
different NPC from the last one and never repeats an NPC's last line.

A beat is held while the room is busy (EMOTE_QUIET_AFTER seconds since
anyone present arrived, spoke, got an NPC reply or heard a tannoy
block, or while a reply is pending), so an emote never lands on top of
a glance, a tannoy or a conversation. An NPC whose per-player hint
pose (world.commitments.hint_pose_for) is showing to anyone present
doesn't emote, so a quest cue is never crowded out.

Lines go to each player with msg(), never to msg_contents: they're not
part of any NPC's conversation history or overheard record, so they
never reach a prompt. A player can turn them off with
`option/save ambience=off` (commands/option.py), screen-reader users
above all, since they hear every line.

Kept in ndb: a reload stops every timer, and the next arrival or
login in a room starts it again.
"""

import random
import time

from evennia.utils import utils
from evennia.utils.utils import inherits_from

from world.commitments import hint_pose_for

EMOTE_FIRST_DELAY = (10, 30)  # seconds after a player arrives in a room with no timer running
EMOTE_GAP = (60, 120)  # seconds between beats
EMOTE_QUIET_AFTER = 15  # seconds since an arrival, speech, NPC reply or tannoy block
EMOTE_QUIET_RETRY = 5  # seconds to wait before trying a held beat again

AMBIENCE_FLAG = "AMBIENCE"  # session protocol flag; absent means on


def hears_ambience(character) -> bool:
    """False if any of the character's sessions turned idle emotes off."""
    return not any(
        session.protocol_flags.get(AMBIENCE_FLAG, True) is False for session in character.sessions.all()
    )


def _players(room):
    return [
        obj for obj in room.contents
        if inherits_from(obj, "typeclasses.characters.Character") and obj.sessions.count()
    ]


def _emoting_npcs(room):
    return [obj for obj in room.contents if inherits_from(obj, "typeclasses.npcs.NPC") and obj.db.emotes]


def _quiet(character):
    now = time.time()
    for name in ("arrived_at", "last_spoke_at", "npc_reply_at", "tannoy_at"):
        moment = getattr(character.ndb, name, None)
        if moment and now - moment < EMOTE_QUIET_AFTER:
            return False
    for obj in character.location.contents:
        pending = obj.ndb.pending
        if pending and character.dbref in pending:
            return False
    return True


def _showing_hint(npc, players):
    npc_id = npc.db.npc_id
    return bool(npc_id) and any(hint_pose_for(npc_id, player) for player in players)


def start_room_emotes(character):
    """Start the character's room's emote timer if it isn't running.
    Called on every room entry and when a player takes control of a
    character (typeclasses/characters.py)."""
    room = character.location
    if not room or not character.sessions.count() or room.ndb.emote_timer is not None:
        return
    if not _emoting_npcs(room):
        return
    token = object()
    room.ndb.emote_timer = token
    utils.delay(random.uniform(*EMOTE_FIRST_DELAY), _beat, room, token)


def _beat(room, token):
    if room.ndb.emote_timer is not token:
        return
    players = _players(room)
    npcs = _emoting_npcs(room)
    if not players or not npcs:
        room.ndb.emote_timer = None
        return
    if not all(_quiet(player) for player in players):
        utils.delay(EMOTE_QUIET_RETRY, _beat, room, token)
        return
    emote_once(room, players, npcs)
    utils.delay(random.uniform(*EMOTE_GAP), _beat, room, token)


def emote_once(room, players, npcs):
    """Send one emote to the room's listening players. Returns the line,
    or None if no NPC was eligible."""
    eligible = [npc for npc in npcs if not _showing_hint(npc, players)]
    if not eligible:
        return None
    others = [npc for npc in eligible if npc is not room.ndb.last_emoter]
    npc = random.choice(others or eligible)
    lines = list(npc.db.emotes)
    fresh = [line for line in lines if line != npc.ndb.last_emote]
    line = random.choice(fresh or lines)
    npc.ndb.last_emote = line
    room.ndb.last_emoter = npc
    for player in players:
        if hears_ambience(player):
            player.msg(f"\n|x{line}|n")  # NPC-action gray, like format_emote
    return line
