"""
Phase 2D (docs/phase2-quest-prototype-design.md §14, docs/phase2d-
noticeboard-check-proposal.md): the civic information display's
per-player expected revision number - the "hashed password" the
model never sees. Generated lazily, the first time a given player
examines the display (typeclasses.objects.RevisionDisplayObject),
and stable after that until a builder reset - not tied to accepting
the commitment, since the display is ordinary café furniture, not a
quest-gated prop.

CLAUDE.md hard rule 2 applies: the actual pass/fail comparison
(world/actions.py's _validate_verify_revision_report) happens here,
in Python, against this stored value - the model only ever proposes
a `reported_revision` argument; it never sees whether that's correct
until the engine's result tells it.
"""

import random

REVISION_KEY = "noticeboard_revision"


def get_or_create_expected_revision(actor) -> str:
    """The four-digit revision this player's own copy of the display
    shows - generated once, stable afterward. Always exactly four
    digits (1000-9999), so there's no leading-zero ambiguity to
    normalize when comparing against a reported value."""
    revision = actor.attributes.get(REVISION_KEY, default=None)
    if revision is None:
        revision = str(random.randint(1000, 9999))
        actor.attributes.add(REVISION_KEY, revision)
    return revision


def reset_expected_revision(actor) -> str | None:
    """Builder-only reset: clears this player's generated revision so
    their next examination generates a fresh one. Returns the
    previous value (for the admin command to report), or None if
    they'd never examined the display at all."""
    previous = actor.attributes.get(REVISION_KEY, default=None)
    actor.attributes.remove(REVISION_KEY)
    return previous


def revision_matches(actor, reported_revision) -> bool:
    """The actual check - world/actions.py's validator calls this and
    relays only the boolean, never the real value, to the model."""
    expected = get_or_create_expected_revision(actor)
    return str(reported_revision).strip() == expected
