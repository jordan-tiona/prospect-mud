"""
Stasis on logout and login (docs/prospect-initial-playtest-design-spec.md
section 8; wording from LR-DEV-0011, owner-approved 2026-10-19). A
character who logs out or loses their connection goes still in the
room and leaves the listing; one who logs back in comes out of stasis
where they were. Replaces Evennia's "has left/entered the game" lines.

Hooked from typeclasses/characters.py (at_post_unpuppet,
at_post_puppet), typeclasses/accounts.py (a session takeover shows
nothing, since the character never left) and commands/quit.py (QUIT
waits QUIT_DELAY_SECONDS so the player can read their line). Lines
go out with the character as sender, so a hidden staff member's
logout is suppressed the same way their movement is
(Character.msg / world.stealth.suppressed_for).
"""

import random

GOING_LINES = (
    "{name} goes still and unresponsive, slipping into stasis.",
    "{name} falls still, no longer responding, and slips into stasis.",
)
RETURNING_LINES = (
    "{name} stirs, coming back out of stasis.",
    "{name} stirs and is alert again, out of stasis.",
)
RETURN_SELF_LINE = "You come out of stasis where you left off."
QUIT_SELF_LINE = "You go still and slip into stasis."

QUIT_DELAY_SECONDS = 3


def _styled(text: str) -> str:
    # Gray, like engine narration and emotes (LR-LORE-0008); the words
    # carry it without colour for screen readers.
    return f"|x{text}|n"


def _to_room(character, lines):
    location = character.location
    if not location:
        return
    line = random.choice(lines)

    def message(obj, from_obj):
        obj.msg(_styled(line.format(name=character.get_display_name(obj))), from_obj=from_obj)

    location.for_contents(message, exclude=[character], from_obj=character)


def announce_going(character):
    """The room sees `character` go into stasis."""
    _to_room(character, GOING_LINES)


def announce_returning(character):
    """The room sees `character` come out of stasis."""
    _to_room(character, RETURNING_LINES)


def tell_returning(character):
    character.msg(_styled(RETURN_SELF_LINE))


def tell_quitting(character):
    character.msg(_styled(QUIT_SELF_LINE))
