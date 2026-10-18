"""
Who an NPC was talking to while someone else was in earshot (project
owner, 2026-10-17). Others in the room see an NPC's replies
(commands/say.py's _render_reply_segments), so a bystander can ask the
NPC about them - but each conversation is private to its own player,
and an NPC with no sign of the other conversation denied it outright
and guessed at what it had been about (seen live, Mara prompt_version
51).

So the NPC is told who it was talking to near this player, and how to
handle being asked about it. Names only, never what was said: no
player's words reach another player's prompt (design-bible 16.x's
shared-room rule). The note is only added when it applies, rather
than as a standing rule in content/npc-shared-rules.md that every
prompt would carry.

Kept in ndb, so a reload forgets it.
"""

import time

OVERHEARD_SECONDS = 10 * 60


def record_overheard(npc, speaker, bystanders):
    """Note that each of `bystanders` saw `npc` talking with `speaker`."""
    if npc.ndb.overheard is None:
        npc.ndb.overheard = {}
    now = time.time()
    for obj in bystanders:
        npc.ndb.overheard.setdefault(obj.dbref, {})[speaker.key] = now


def overheard_context_for(npc, listener):
    """The prompt note for `listener` talking to `npc`, or "" if they
    haven't seen it talking with anyone else in the last
    OVERHEARD_SECONDS."""
    seen = (npc.ndb.overheard or {}).get(listener.dbref)
    if not seen:
        return ""
    cutoff = time.time() - OVERHEARD_SECONDS
    for name, when in list(seen.items()):
        if when < cutoff:
            del seen[name]
    names = [name for name, _ in sorted(seen.items(), key=lambda item: -item[1])]
    if not names:
        return ""
    return (
        f"In the last few minutes, while this person was nearby, you were talking with "
        f"{_join(names)} (player character names). You don't have the details of that in mind. "
        "If this person asks what you said, or claims you said something, brush it off curtly in your own "
        "words, a little put out that they were listening. Don't confirm, deny or repeat it, "
        "don't guess at what it was about, and don't say you weren't talking to them. Refer to "
        "them by name, not as he or she. Anything else they ask, answer as usual."
    )


def _join(names):
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f" and {names[-1]}"
