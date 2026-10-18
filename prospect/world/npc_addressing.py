"""
Resolves whether a player's `say` addresses a talk-capable NPC, per
design-bible 16.5's addressing rule (adopted 2026-10-11): explicit
naming (`say to <name>, ...` or the name mentioned anywhere in the
message), or - with no name at all - the lone-player/lone-NPC case, or
(2026-10-13, phase 2B) a per-player "conversational focus": once a
player has addressed a particular NPC, an unaddressed follow-up in the
same room defaults back to that same NPC, as long as it's still
present. Without this, a room with more than one talk-capable NPC
(the Civic Office, since Veska joined Iri) required re-naming the NPC
on *every* line - a real person naturally drops the name mid-
conversation, and silently getting no reply reads exactly like the
NPC stopped responding. Anything that still doesn't resolve is
ambient speech: no NPC, no model call.

Kept separate from commands/say.py so the matching logic (words,
regexes, present NPCs/players) is unit-testable without a command or a
live room.
"""

import re

from evennia.utils.utils import inherits_from

from world.stealth import is_hidden


def _candidate_names(npc):
    names = [npc.key] + list(npc.aliases.all())
    return [name for name in names if name]


def present_talkative_npcs(room):
    """Public wrapper - also used by commands/say.py to detect when a
    room has more than one talk-capable NPC, so it can tell a player
    their unaddressed `say` didn't reach anyone instead of leaving
    them wondering why nobody answered."""
    if room is None:
        return []
    return [obj for obj in room.contents if inherits_from(obj, "typeclasses.npcs.TalkativeNPC")]


_present_talkative_npcs = present_talkative_npcs


def _present_players(room, speaker=None):
    """Players who count toward the lone-player rule. Hidden staff other
    than the speaker don't (world/stealth.py): a tester who can't see
    them is alone with the NPC as far as they know. Visible staff count
    like anyone (owner, 2026-10-17): the tester can see them and may be
    talking to them, so a plain `say` mustn't go to the NPC. A speaker
    always counts themselves."""
    if room is None:
        return []
    return [
        obj
        for obj in room.contents
        if inherits_from(obj, "typeclasses.characters.Character") and (obj is speaker or not is_hidden(obj))
    ]


def _name_pattern(name, anchored):
    words = r"\s+".join(re.escape(word) for word in name.split())
    if anchored:
        return r"^" + words + r"\b,?\s*"
    return r"(?<!\w)" + words + r"(?!\w)"


def _match_explicit_name(npcs, rest):
    """Matches the longest present NPC name at the start of `rest`.

    Longest-first so "Mara Voss" wins over "Mara" when both are valid
    candidate names for the same NPC.
    """
    candidates = [(name, npc) for npc in npcs for name in _candidate_names(npc)]
    candidates.sort(key=lambda pair: -len(pair[0].split()))
    for name, npc in candidates:
        match = re.match(_name_pattern(name, anchored=True), rest, re.IGNORECASE)
        if match:
            return npc, rest[match.end():]
    return None, None


def _match_mentioned_name(npcs, speech):
    """Finds the present NPC whose name appears earliest in `speech`."""
    best = None
    for npc in npcs:
        for name in _candidate_names(npc):
            match = re.search(_name_pattern(name, anchored=False), speech, re.IGNORECASE)
            if match and (best is None or match.start() < best[0]):
                best = (match.start(), npc)
    return best[1] if best else None


def names_a_present_npc(speech, room) -> bool:
    """True if `speech` names a present talk-capable NPC, by "to <name>"
    or a mention - the two ways resolve_addressee lets a player choose
    who they mean, as opposed to the lone-NPC rule or `focus`."""
    npcs = _present_talkative_npcs(room)
    if not npcs:
        return False
    to_match = re.match(r"^to\s+(.*)$", speech.strip(), re.IGNORECASE | re.DOTALL)
    if to_match and _match_explicit_name(npcs, to_match.group(1))[0] is not None:
        return True
    return _match_mentioned_name(npcs, speech) is not None


def resolve_addressee(speech, room, focus=None, speaker=None):
    """
    `room` is the room the `say` happened in, used to find present
    talk-capable NPCs and players. `focus` is the NPC this same
    player was last addressing in this room (commands/say.py tracks
    this per player, cleared whenever they change rooms), or None.
    `speaker` is the player talking, so staff in the room can be left
    out of the lone-player count without leaving out the speaker.

    Returns (npc, message): `npc` is the talk-capable NPC this `say`
    addresses, or None for ambient speech. `message` is what the NPC
    actually hears - the player's words, with an explicit "to <name>"
    addressing prefix stripped (it's command syntax, not speech).

    Explicit naming or a name mentioned anywhere always wins over
    `focus` - if a player names a *different* present NPC, that's a
    deliberate switch, not a continuation.
    """
    npcs = _present_talkative_npcs(room)
    if not npcs:
        return None, speech

    stripped = speech.strip()
    to_match = re.match(r"^to\s+(.*)$", stripped, re.IGNORECASE | re.DOTALL)
    if to_match:
        npc, remainder = _match_explicit_name(npcs, to_match.group(1))
        if npc is not None:
            return npc, remainder

    npc = _match_mentioned_name(npcs, speech)
    if npc is not None:
        return npc, speech

    if len(npcs) == 1 and len(_present_players(room, speaker)) == 1:
        return npcs[0], speech

    if focus is not None and focus in npcs:
        return focus, speech

    return None, speech
