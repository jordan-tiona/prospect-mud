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


def skitter_targetable(accessing_obj, accessed_obj, *args, **kwargs):
    """
    view/search-lock func for typeclasses.creatures.Skitter, usage:
    `view:skitter_targetable()` (no argument - every skitter uses the
    same eligibility rule, unlike commitment_hint_visible above).

    True only for a looker currently eligible to hunt skitters -
    world.skitters.is_hunting, which itself just checks the
    "hunt_skitters" commitment's open state. Same per-looker
    view/search gating pattern as commitment_hint_visible, applied to
    a shared-world creature instead of a per-player hint object:
    typeclasses.creatures.Creature.access() is what forces
    no_superuser_bypass for this to actually work against the
    solo dev's own (superuser) account, the same lesson
    docs/engineering-pitfalls.md #2 already taught for
    CommitmentHintObject.
    """
    from world.skitters import is_hunting

    try:
        return is_hunting(accessing_obj)
    except Exception:
        return False


def module_exchange_hint_visible(accessing_obj, accessed_obj, *args, **kwargs):
    """
    view-lock func for the heating-unit module-exchange quest's hint prop
    (world/build_quest_props.py). This quest predates the per-player
    discoverability rule above (world/actions.py's QUEST_MODULE_EXCHANGE_*
    state machine, phase 2) and has no generic commitment_type to key off -
    its own state lives in world.actions.get_quest_state, not
    world.commitments. True only for a looker who hasn't started the
    errand yet, the same "not offered"-equivalent bar commitment_hint_visible
    uses, so the hint quietly stops existing for a player once they engage
    with it, same discipline as that function. Mara asking ("offered")
    hides it too; declining brings it back, as for a commitment.
    """
    from world.actions import get_quest_state

    try:
        return get_quest_state(accessing_obj) == "not_started"
    except Exception:
        return False
