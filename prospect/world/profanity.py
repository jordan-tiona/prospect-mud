"""
Profanity handling for everything a player writes that others see
(owner, 2026-10-19), built on the better-profanity package so every
path shares one set of rules:

- mask_speech: speech, poses, tells, whispers and channel lines go
  through with each profane word shown as ****. Mild words (MILD_WORDS)
  pass in speech, so ordinary grumbling isn't starred out. NPCs hear
  the masked line, so a model can't repeat the word back.
- name_is_profane / description_is_profane: character names and
  appearance text are rejected rather than masked, because they're
  permanent and shown everywhere. Names use the full list, mild words
  included; descriptions follow the speech rules. The library only
  matches whole words, so both also look for STRONG_ROOTS inside a
  word ("Fuckyourself") and with letters stretched out ("Fuuuck").
  Shorter roots that turn up inside real names (cock in Hancock, dick
  in Dickens, ass in Cassandra, fuk in Fukuda) are left to the
  whole-word check. Known false positives: Scunthorpe, Shitara.

Not applied to bug/feedback reports, which only staff read, or to NPC
replies (world/output_check.py), where approved persona content like
"Cave Crawler" has to reach the player.
"""

import re

from better_profanity import profanity

profanity.load_censor_words()

MASK = "*"

# In the library's list, but fine in ordinary speech. Still rejected
# in names and appearance text.
MILD_WORDS = {"hell", "damn", "damned", "crap", "piss", "pissed", "bastard", "bloody", "arse"}

# Searched for inside a word, for names only. Each must be rare enough
# inside real names that a hit is almost always deliberate.
STRONG_ROOTS = (
    "fuck", "shit", "cunt", "nigg", "bitch", "whore", "slut", "twat",
    "wank", "faggot", "dildo", "penis", "vagina", "retard", "jizz",
)

_speech_filter = profanity.__class__()
_speech_filter.load_censor_words(whitelist_words=sorted(MILD_WORDS))

_STRETCHED_RE = re.compile(r"(.)\1+")


def mask_speech(text: str) -> str:
    """`text` with each profane word replaced by ****, mild words kept."""
    if not text:
        return text
    return _speech_filter.censor(text, censor_char=MASK)


def _squeezed(text: str) -> str:
    return _STRETCHED_RE.sub(r"\1", text.lower())


def _has_strong_root(text: str) -> bool:
    letters = re.sub(r"[^a-z]", "", text.lower())
    squeezed = _squeezed(letters)
    return any(root in letters or root in squeezed for root in STRONG_ROOTS)


def name_is_profane(text: str) -> bool:
    """True if a character name holds profanity anywhere: a whole word
    on the library's full list, mild words included, or a strong root
    inside a word, stretched letters squeezed first."""
    if not text:
        return False
    if profanity.contains_profanity(text) or profanity.contains_profanity(_squeezed(text)):
        return True
    return _has_strong_root(text)


def description_is_profane(text: str) -> bool:
    """True if appearance text holds anything speech would mask, or a
    strong root inside a word. Mild words pass, as in speech."""
    if not text:
        return False
    return mask_speech(text) != text or _has_strong_root(text)
