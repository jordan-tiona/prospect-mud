"""
Splits a reply's `*action*` markup (content/npc-shared-rules.md invites
NPCs to write brief physical actions this way) out of the spoken
dialogue, so the talk command can show:

    Mara Voss smiles and nods.
    Mara Voss says, "Welcome in."

instead of leaving the asterisks inline in the quoted speech.
"""

import re

_EMOTE_RE = re.compile(r"\*(.*?)\*")


def split_emotes(text: str) -> tuple:
    """Return (dialogue, emotes) - dialogue with all *action* spans
    removed and tidied, emotes as a list of their inner text, in
    order of appearance."""
    emotes = [m.strip() for m in _EMOTE_RE.findall(text) if m.strip()]
    dialogue = _EMOTE_RE.sub("", text)
    dialogue = re.sub(r"\s{2,}", " ", dialogue).strip()
    dialogue = dialogue.strip(" \"'")
    return dialogue, emotes


def format_emote(npc_key: str, emote_text: str) -> str:
    """One emote's text as a third-person action line, e.g. 'smiles
    and nods' -> 'Mara Voss smiles and nods.'"""
    text = emote_text.strip()
    if text and text[-1] not in ".!?":
        text += "."
    return f"{npc_key} {text}"
