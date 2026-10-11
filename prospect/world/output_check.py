"""
Output check (design-bible 16.7 / CLAUDE.md "Output check for
out-of-character/offensive replies"): a simple filter run on a reply
before it reaches the player.

Deliberately narrow for phase 1. It targets the failure mode an LLM
voicing an NPC is actually likely to produce - breaking character to
talk like an AI assistant - rather than a general profanity/offensive-
language filter. A blanket word-list filter would risk flagging a
persona's own approved in-character language (e.g. Mara being called
"Cave Crawler", design-bible 14.6), which is meant to reach the
player. CLAUDE.md allows this: "a simple filter is fine at first."
"""

import re

_ASSISTANT_LEAK_PATTERNS = [
    r"\bas an ai\b",
    r"\bi('m| am) an ai\b",
    r"\blanguage model\b",
    r"\bi cannot assist\b",
    r"\bas a large language model\b",
    r"\bi don't have (a body|feelings|personal experiences)\b",
    r"\bi'm just an? (ai|assistant|language model)\b",
]
_ASSISTANT_LEAK_RE = re.compile("|".join(_ASSISTANT_LEAK_PATTERNS), re.IGNORECASE)


def is_flagged(text: str) -> tuple:
    """
    Return (flagged: bool, reason: str) for an assistant-voice leak.

    Deliberately does not flag empty text: a model proposing a tool
    call will often return no spoken text alongside it (the action
    speaks for itself), which is normal, not a failure. The talk
    command handles the "nothing to say and nothing to do" case
    itself, since that's a different kind of problem than this filter
    is for.
    """
    if not text:
        return False, ""
    if _ASSISTANT_LEAK_RE.search(text):
        return True, "broke character as an AI assistant"
    return False, ""
