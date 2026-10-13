"""
Light formatting for what a player types with `say`, before it's
echoed to the room or sent to an NPC: capitalizes the first letter of
every sentence and every standalone "i", and appends a period if the
player left off ending punctuation, so dialogue reads naturally
without asking players to type like they're writing prose. Doesn't
touch anything else inside the text.
"""

import re

# Matches "i" as its own word, including at the start of a contraction
# ("i'm", "i've", "i'll", "i'd") - the apostrophe is a non-word
# character, so \b still lands right after the "i". Deliberately
# case-sensitive: an already-correct "I" is left alone, and this never
# touches an "i" inside a longer word ("hi", "this").
_STANDALONE_I_RE = re.compile(r"\bi\b")

# Matches a sentence-ending mark followed by whitespace and a lowercase
# letter, so that letter can be capitalized too - not just the very
# first letter of the whole message.
_SENTENCE_BOUNDARY_RE = re.compile(r"([.!?]\s+)([a-z])")


def normalize_speech(text):
    """
    Returns (normalized_text, is_question).

    `is_question` reflects whether the original text ended with "?",
    checked before a missing period gets added - used by callers that
    want to show "asks," instead of "says," for a question.
    """
    text = text.strip()
    if not text:
        return text, False

    text = _STANDALONE_I_RE.sub("I", text)

    if text[0].isalpha():
        text = text[0].upper() + text[1:]

    text = _SENTENCE_BOUNDARY_RE.sub(lambda m: m.group(1) + m.group(2).upper(), text)

    is_question = text.endswith("?")
    if text[-1] not in ".!?":
        text += "."

    return text, is_question
