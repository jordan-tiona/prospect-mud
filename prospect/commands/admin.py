"""
Builder-only testing commands - not part of the design-bible's
player-facing feature set. `forget` exists purely so a tester doesn't
have to restart the server to get a clean slate with an NPC: the
conversation history it clears (commands/say.py's
`npc.ndb.conversations`) is already wiped by every restart/reload on
its own, since it lives on `ndb`, not persisted to the database.

`restock` exists for the opposite problem: a hand_over_item NPC's
stock (world/actions.py) is a real, persistent, finite inventory with
no in-fiction way to refill it - phase 1 keeps each NPC to one action
(CLAUDE.md), so there's deliberately no player-facing restock action.
Repeated testing runs it dry for real, same as any other player
activity would; this is a manual reset for that, not a game feature.
"""

from evennia.utils.utils import inherits_from

from world.actions import DEFAULT_STOCK, QUEST_MODULE_EXCHANGE_KEY, get_quest_state
from world.commitments import SCENARIOS, reset_commitment
from world.conversation_log import log_commitment_reset, log_quest_reset, log_reset
from world.npc_profile import parse_persona

from .command import Command


class CmdForget(Command):
    """
    Clear your conversation history with an NPC, without restarting
    the server.

    Usage:
      forget <npc>
    """

    key = "forget"
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        caller = self.caller
        target_name = self.args.strip()

        if not target_name:
            caller.msg("Forget whom? Usage: forget <npc>")
            return

        target = caller.search(target_name, location=caller.location)
        if not target:
            return

        if not inherits_from(target, "typeclasses.npcs.TalkativeNPC"):
            caller.msg(f"{target.key} doesn't seem to remember anything about you.")
            return

        conversation_ids = getattr(target.ndb, "conversation_ids", None)
        old_conversation_id = conversation_ids.get(caller.dbref) if conversation_ids else None

        cleared = False
        for ndb_attr in ("conversations", "conversation_ids", "turn_counters"):
            store = getattr(target.ndb, ndb_attr, None)
            if store and store.pop(caller.dbref, None) is not None:
                cleared = True
        pending = target.ndb.pending
        if pending:
            pending.discard(caller.dbref)

        if cleared:
            log_reset(
                conversation_id=old_conversation_id,
                npc_id=getattr(target.db, "npc_id", target.key),
                actor_key=caller.key,
                actor_dbref=caller.dbref,
            )
            caller.msg(f"You clear your conversation history with {target.key}.")
        else:
            caller.msg(f"You have no conversation history with {target.key} to clear.")


class CmdRestock(Command):
    """
    Reset an NPC's hand_over_item stock back to its default amount.

    Usage:
      restock <npc>
    """

    key = "restock"
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        caller = self.caller
        target_name = self.args.strip()

        if not target_name:
            caller.msg("Restock whom? Usage: restock <npc>")
            return

        target = caller.search(target_name, location=caller.location)
        if not target:
            return

        npc_id = getattr(target.db, "npc_id", None)
        if not npc_id or "hand_over_item" not in parse_persona(npc_id).actions:
            caller.msg(f"{target.key} doesn't keep any stock to restock.")
            return

        target.db.stock = dict(DEFAULT_STOCK)
        caller.msg(f"You restock {target.key}'s supplies back to the default amount.")


class CmdResetQuest(Command):
    """
    Reset a player's heating-unit-module quest progress back to the
    start, without restarting the server.

    Usage:
      resetquest
      resetquest <player>
    """

    key = "resetquest"
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        caller = self.caller
        target_name = self.args.strip()

        if not target_name:
            target = caller
        else:
            target = caller.search(target_name, global_search=True)
            if not target:
                return

        previous_state = get_quest_state(target)
        if previous_state == "not_started":
            caller.msg(f"{target.key}'s module quest is already at the start.")
            return

        target.attributes.add(QUEST_MODULE_EXCHANGE_KEY, "not_started")
        log_quest_reset(
            quest_key=QUEST_MODULE_EXCHANGE_KEY,
            previous_state=previous_state,
            actor_key=target.key,
            actor_dbref=target.dbref,
        )
        caller.msg(f"You reset {target.key}'s module quest back to the start (was {previous_state!r}).")


class CmdResetCommitment(Command):
    """
    Reset a player's commitment progress (phase 2B, docs/phase2b-
    records-discrepancy-proposal.md) back to the start, without
    restarting the server. Clears every authored commitment type for
    that player - there's currently only one ("discrepancy_report"),
    but this stays generic rather than hard-coding it.

    A stale model reply that arrives after this reset can't revive the
    cleared commitment: every commitment action looks up the player's
    *current* state fresh each time it's called (never a commitment_id
    carried over from the model's own earlier context), so an in-flight
    reply from before the reset is rejected the same way any other
    out-of-order call would be.

    Usage:
      resetcommitment
      resetcommitment <player>
    """

    key = "resetcommitment"
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        caller = self.caller
        target_name = self.args.strip()

        if not target_name:
            target = caller
        else:
            target = caller.search(target_name, global_search=True)
            if not target:
                return

        cleared_any = False
        for commitment_type in SCENARIOS:
            snapshot = reset_commitment(target, commitment_type)
            if not snapshot["had_offer"] and not snapshot["previous_statuses"]:
                continue
            cleared_any = True
            log_commitment_reset(
                commitment_type=commitment_type,
                had_offer=snapshot["had_offer"],
                previous_statuses=snapshot["previous_statuses"],
                actor_key=target.key,
                actor_dbref=target.dbref,
            )

        if cleared_any:
            caller.msg(f"You reset {target.key}'s commitment progress back to the start.")
        else:
            caller.msg(f"{target.key} has no commitment progress to reset.")
