"""
Ambient NPCs answer being addressed (LR-LORE-0007, owner 2026-10-18):
`say to <ambient NPC>, ...` still goes to the room as ambient speech,
then the NPC reacts with one nonverbal line from the global list in
content/ambient/addressed_responses.md. It tells the player, in-world,
that this one doesn't talk.

Once per room visit, per player and NPC: the first address in a stay
gets a reaction, later ones nothing extra; leaving and re-entering
resets it (typeclasses/characters.py clears ndb.ambient_reacted on
every move). Only the player who spoke sees it, since the lines
address them as "you" (owner, 2026-10-18).

Engine output, no LLM call, and never part of any NPC prompt.
"""

import random
import re

from world.ambient_content import addressed_responses

_LEADING_ARTICLE_RE = re.compile(r"^(?:A|An)\s+", re.IGNORECASE)


def reaction_name(npc):
    """The NPC's key with "A/An" turned to "The" ("The elderly Kell"):
    the player has just picked it out, so it's no longer "an" anything
    (owner, 2026-10-18)."""
    return _LEADING_ARTICLE_RE.sub("The ", npc.key, count=1)


def react_to_address(caller, npc):
    """Send `npc`'s reaction to `caller` if it's their first address to it
    this visit. Returns the line sent, or None."""
    reacted = caller.ndb.ambient_reacted
    if reacted is None:
        reacted = caller.ndb.ambient_reacted = set()
    if npc.dbref in reacted:
        return None
    lines = addressed_responses()
    if not lines:
        return None
    reacted.add(npc.dbref)
    line = random.choice(lines).replace("{name}", reaction_name(npc))
    caller.msg(f"|x{line}|n")  # NPC-action gray, like format_emote
    return line
