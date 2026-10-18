"""
Splits a reply's `*action*` markup (content/npc-shared-rules.md invites
NPCs to write brief physical actions this way) out of the spoken
dialogue, preserving the order dialogue and actions actually appear in
so a reply like '"xxx" *crosses her arms* "yyy"' renders as:

    Mara Voss says, "xxx"
    Mara Voss crosses her arms.
    Mara Voss says, "yyy"

rather than collapsing every action to the front of the reply.
"""

import re

_EMOTE_RE = re.compile(r"\*(.*?)\*")

# content/npc-shared-rules.md tells the model to write its own actions
# in third person with its own pronouns, never first person - but a
# local model doesn't always follow that (confirmed live: Qwen3 wrote
# "wiping my hands" for a she/her NPC). This is a deterministic
# backstop: rewrite first-person self-reference inside *action* text
# to the NPC's own pronouns, regardless of what the model wrote.
_PRONOUN_FORMS = {
    "she/her": ("she", "her", "her", "herself"),
    "he/him": ("he", "him", "his", "himself"),
    "they/them": ("they", "them", "their", "themself"),
    "it/its": ("it", "it", "its", "itself"),
}
_SELF_PRONOUN_RE = re.compile(r"\b(myself|I|me|my)\b", re.IGNORECASE)


def _fix_self_pronouns(text: str, pronouns: str) -> str:
    forms = _PRONOUN_FORMS.get(pronouns)
    if not forms:
        return text
    subject, obj, possessive, reflexive = forms
    replacements = {"myself": reflexive, "i": subject, "me": obj, "my": possessive}

    def _replace(match):
        replacement = replacements[match.group(0).lower()]
        return replacement.capitalize() if match.start() == 0 else replacement

    return _SELF_PRONOUN_RE.sub(_replace, text)


_ESCAPED_QUOTE_RE = re.compile(r'\\(["\'])')


def _clean_dialogue(text: str) -> str:
    # Deterministic backstop for a model quirk confirmed live
    # (2026-10-14, gpt-4.1-mini): the raw reply content sometimes
    # contains literal backslash-escaped quotes (`\"like this\"`),
    # as if it were being embedded in a JSON string rather than
    # written as plain chat text - real spoken dialogue should never
    # contain a raw backslash, so this is always safe to strip.
    text = _ESCAPED_QUOTE_RE.sub(r"\1", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text.strip(" \"'")


def parse_reply(text: str) -> list:
    """Return an ordered list of ("dialogue", text) / ("emote", text)
    segments, in the order they appear in `text`. Consecutive spoken
    fragments split by an action stay separate segments (so each gets
    its own "says" line); empty fragments (no words before/between/
    after actions) are dropped."""
    segments = []
    pos = 0
    for match in _EMOTE_RE.finditer(text):
        dialogue = _clean_dialogue(text[pos:match.start()])
        if dialogue:
            segments.append(("dialogue", dialogue))
        emote = match.group(1).strip()
        if emote:
            segments.append(("emote", emote))
        pos = match.end()
    tail = _clean_dialogue(text[pos:])
    if tail:
        segments.append(("dialogue", tail))
    return segments


# NPC actions are written to the player they're talking to ("*puts a
# cold beer in front of you*"). Others in the room see the same action
# with that player's name in place of "you" - a word-level swap, so a
# rare "you" as the subject of a verb ("as you leave") comes out
# ungrammatical ("as Alice leave") rather than wrong.
_LISTENER_RE = re.compile(r"\b(you['’](?:re|ve|ll|d)|yourself|yours|your|you)\b", re.IGNORECASE)
_LISTENER_FORMS = {
    "re": "{name} is",
    "ve": "{name} has",
    "ll": "{name} will",
    "d": "{name} would",
    "yourself": "{name}",
    "yours": "{name}'s",
    "your": "{name}'s",
    "you": "{name}",
}


def name_the_listener(emote_text: str, listener_name: str) -> str:
    """`emote_text` with its second-person references to the player
    being spoken to replaced by `listener_name`, for everyone else in
    the room."""

    def _replace(match):
        word = match.group(0).lower()
        key = word[4:] if word[3:4] in ("'", "’") else word
        return _LISTENER_FORMS[key].format(name=listener_name)

    return _LISTENER_RE.sub(_replace, emote_text)


def format_emote(npc_key: str, emote_text: str, pronouns: str = "") -> str:
    """One emote's text as a third-person action line, e.g. 'smiles
    and nods' -> 'Mara Voss smiles and nods.' Colored bright gray
    (Evennia's |x), per the project owner's color scheme for actions.

    `pronouns` (e.g. "she/her", from the NPC's persona file) fixes up
    any first-person self-reference the model wrote despite being told
    not to - see _fix_self_pronouns above."""
    text = _ESCAPED_QUOTE_RE.sub(r"\1", emote_text.strip())
    if pronouns:
        text = _fix_self_pronouns(text, pronouns)
    if text and text[-1] not in ".!?":
        text += "."
    return f"|x{npc_key} {text}|n"
