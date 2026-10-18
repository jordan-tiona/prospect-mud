"""
Screen-reader support (owner, 2026-10-17). Evennia keeps a per-session
SCREENREADER flag, set either by the client (MTTS bit 64, e.g. Mudlet's
"advertise screen reader use" setting) or by the player with
`option/save screenreader=on`. In that mode Evennia already strips
colour and table borders; this module covers what colour alone carried
in our own output.

Out-of-character interface text, not setting content.
"""

from evennia.utils.utils import inherits_from

from world.npc_profile import parse_persona

SCREENREADER_HINT = "Using a screen reader? Once you're in, type |woption/save screenreader=on|n."

_OBJECT_PRONOUNS = {"she/her": "her", "he/him": "him", "it/its": "it"}


def uses_screenreader(obj) -> bool:
    """True if `obj` (a session, or anything with sessions, e.g. a
    character or account) has any session in screen-reader mode."""
    flags = getattr(obj, "protocol_flags", None)
    if flags is not None:
        return bool(flags.get("SCREENREADER", False))
    sessions = getattr(obj, "sessions", None)
    if sessions is None:
        return False
    return any(session.protocol_flags.get("SCREENREADER", False) for session in sessions.all())


def talk_marker(npc) -> str:
    """'(You can talk to her.)' - the room display marks talk-capable
    NPCs only by colour, which a screen reader doesn't announce."""
    pronoun = "them"
    npc_id = getattr(npc.db, "npc_id", None)
    if npc_id and inherits_from(npc, "typeclasses.npcs.TalkativeNPC"):
        try:
            pronoun = _OBJECT_PRONOUNS.get(parse_persona(npc_id).pronouns, "them")
        except Exception:
            pass
    return f"(You can talk to {pronoun}.)"
