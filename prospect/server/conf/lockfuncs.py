"""

Lockfuncs

Lock functions are functions available when defining lock strings,
which in turn limits access to various game systems.

All functions defined globally in this module are assumed to be
available for use in lockstrings to determine access. See the
Evennia documentation for more info on locks.

A lock function is always called with two arguments, accessing_obj and
accessed_obj, followed by any number of arguments. All possible
arguments should be handled with *args, **kwargs. The lock function
should handle all eventual tracebacks by logging the error and
returning False.

Lock functions in this module extend (and will overload same-named)
lock functions from evennia.locks.lockfuncs.

"""

# def myfalse(accessing_obj, accessed_obj, *args, **kwargs):
#    """
#    called in lockstring with myfalse().
#    A simple logger that always returns false. Prints to stdout
#    for simplicity, should use utils.logger for real operation.
#    """
#    print "%s tried to access %s. Access denied." % (accessing_obj, accessed_obj)
#    return False


def commitment_hint_visible(accessing_obj, accessed_obj, *args, **kwargs):
    """
    view-lock func, usage: `view:commitment_hint_visible(<commitment_type>)`.

    Design rule (per project owner, 2026-10-13): every discoverable
    quest/commitment should have some passive, in-world cue, not just
    a conversational trigger a player has to think to ask about -
    world.commitments.hint_pose_for already does this for an NPC's
    pose (e.g. Tarin "frowning over a shipment manifest"); this is the
    equivalent for a room object (e.g. a parcel sitting on a counter).

    True only for a looker whose own commitment state for the given
    commitment_type is still "not offered" - the same per-player state
    hint_pose_for checks, applied as a real Evennia view lock instead
    of a text swap. This makes the object genuinely per-player: once a
    player's been offered it, declined it, accepted it, or finished
    it, it quietly isn't there for them any more on every future look,
    with no separate timer or respawn logic - and a different player
    who hasn't touched it yet still sees it fresh.
    """
    if not args:
        return False
    from world.commitments import get_state_summary

    try:
        return get_state_summary(accessing_obj, args[0]) == "not offered"
    except Exception:
        return False
