"""
Staff stealth: an admin/mod can stand in the game during a playtest
without players seeing them (owner, 2026-10-17).

Hiding is a pair of ordinary `view`/`search` locks set to Builder-only,
so the room listing (typeclasses.rooms.Room's filter_visible) and
`look <name>` skip a hidden character for players. Staff lookers still
see them: Builder passes the lock, and a superuser bypasses it anyway
(engineering-pitfalls #2 - here that's the behaviour we want).

Everything a hidden character broadcasts to the room - arrivals and
departures, "has entered the game", get/drop - is dropped for non-staff
receivers in typeclasses.characters.Character.msg, keyed off the
message's `from_obj`. That's one structural check rather than an
override per announcement. Speaking (`say`, `pose`) is the deliberate
exception: it reveals the speaker first, with a reminder, and then goes
through as normal.

Hidden staff are also left out of the player count behind implicit NPC
addressing (world/npc_addressing.py), so a mod a tester can't see never
stops their plain `say` reaching the NPC. Visible staff count like any
player (owner, 2026-10-17).
"""

from evennia.utils.utils import inherits_from, is_iter

STAFF_PERMISSION = "Builder"

HIDDEN_LOCKS = f"view:perm({STAFF_PERMISSION});search:perm({STAFF_PERMISSION})"
VISIBLE_LOCKS = "view:all();search:all()"

REVEAL_REMINDER = "|x(You were hidden. Speaking has revealed you; type |wstealth|x to hide again.)|n"


def is_staff(obj):
    """True for a character (or account) whose account holds Builder or
    above. Characters without an account - NPCs, test dummies - aren't."""
    if obj is None:
        return False
    account = obj if inherits_from(obj, "evennia.accounts.accounts.DefaultAccount") else getattr(obj, "account", None)
    if account is None:
        return False
    return bool(account.is_superuser or account.check_permstring(STAFF_PERMISSION))


def is_hidden(obj):
    db = getattr(obj, "db", None)
    return bool(db is not None and db.stealth)


def hide(character):
    character.db.stealth = True
    character.locks.add(HIDDEN_LOCKS)


# Owner's wording (2026-10-17): announced to the room when staff become
# visible, in the shape of the movement lines (typeclasses/characters.py).
REVEAL_ANNOUNCEMENT = "{object} arrives from the ether."


def reveal(character):
    was_hidden = is_hidden(character)
    character.db.stealth = False
    character.locks.add(VISIBLE_LOCKS)
    if was_hidden and character.location:
        character.location.msg_contents(
            REVEAL_ANNOUNCEMENT, exclude=[character], from_obj=character, mapping={"object": character}
        )


def reveal_for_speech(character):
    """Called by speech commands before they broadcast. Returns True
    if the speaker was hidden and has just been revealed."""
    if not is_hidden(character):
        return False
    reveal(character)
    character.msg(REVEAL_REMINDER)
    return True


def suppressed_for(receiver, from_obj):
    """True when `receiver` mustn't get a message sent from `from_obj`
    because a hidden character sent it and the receiver isn't staff."""
    if from_obj is None:
        return False
    senders = from_obj if is_iter(from_obj) else [from_obj]
    return any(
        sender is not receiver and is_hidden(sender) for sender in senders
    ) and not is_staff(receiver)
