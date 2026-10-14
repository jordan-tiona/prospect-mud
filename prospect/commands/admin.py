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

from world.actions import DEFAULT_STOCK, QUEST_MODULE_EXCHANGE_KEY, cleanup_stray_parcels, get_quest_state
from world.commitments import known_commitment_types_for, reset_commitment
from world.conversation_log import (
    log_commitment_reset,
    log_memory_reset,
    log_quest_reset,
    log_reset,
    log_rumor_reset,
)
from world.npc_memory import known_npc_ids_with_memory_for, reset_memory
from world.noticeboard import reset_expected_revision
from world.npc_profile import parse_persona
from world.reputation import reset_reputation
from world.rumors import reset_rumor

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
        # Not just SCENARIOS - also whatever's actually in this player's
        # own data, so a commitment_type since renamed or removed (e.g.
        # the 2026-10-13 parcel redesign) can still be found and cleared,
        # rather than silently staying stuck forever.
        for commitment_type in known_commitment_types_for(target):
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

        removed_parcels = cleanup_stray_parcels(target)
        previous_revision = reset_expected_revision(target)

        # Phase 2E: the parcel-rumor knowledge and reputation credit
        # are both downstream of deliver_parcel - coordinated here
        # rather than a separate `resetrumor` command, so a tester
        # resetting commitments can't forget the other half and leave
        # Mara believing the parcel arrived (or still crediting
        # reputation) from an instance that no longer exists.
        rumor_snapshot = reset_rumor(target)
        previous_mara_reputation = reset_reputation(target, "mara_voss")
        rumor_cleared = bool(rumor_snapshot["informed_commitment_ids"]) or rumor_snapshot["reputation_credited"]
        if rumor_cleared or previous_mara_reputation:
            log_rumor_reset(
                previous_informed_commitment_ids=rumor_snapshot["informed_commitment_ids"],
                previous_reputation_credited=rumor_snapshot["reputation_credited"],
                previous_mara_reputation=previous_mara_reputation,
                actor_key=target.key,
                actor_dbref=target.dbref,
            )

        if cleared_any or removed_parcels or previous_revision is not None or rumor_cleared or previous_mara_reputation:
            caller.msg(f"You reset {target.key}'s commitment progress back to the start.")
            if removed_parcels:
                caller.msg(f"Removed {removed_parcels} stray carried parcel(s) no longer tied to anything open.")
            if previous_revision is not None:
                caller.msg("Cleared their generated noticeboard revision - the display will show a fresh one.")
            if rumor_cleared or previous_mara_reputation:
                caller.msg("Cleared their parcel-delivery rumor knowledge and Mara's reputation credit.")
        else:
            caller.msg(f"{target.key} has no commitment progress to reset.")


class CmdResetMemory(Command):
    """
    Clear a player's stored NPC memory (design-bible 16.6) back to
    nothing, without restarting the server. Clears every NPC this
    player actually has memory stored under, not just NPCs that
    currently grant remember_fact - the same reasoning as
    resetcommitment's known_commitment_types_for, in case that ever
    changes later.

    Usage:
      resetmemory
      resetmemory <player>
    """

    key = "resetmemory"
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
        for npc_id in known_npc_ids_with_memory_for(target):
            snapshot = reset_memory(target, npc_id)
            if not snapshot["previous_facts"]:
                continue
            cleared_any = True
            log_memory_reset(
                npc_id=npc_id,
                previous_facts=snapshot["previous_facts"],
                actor_key=target.key,
                actor_dbref=target.dbref,
            )

        if cleared_any:
            caller.msg(f"You cleared {target.key}'s stored NPC memory.")
        else:
            caller.msg(f"{target.key} has no stored NPC memory to clear.")


class CmdMemoryDebug(Command):
    """
    Toggle a visible `[memory] <NPC> notes: "..."` line whenever
    remember_fact actually fires for a player, so you can confirm what
    got stored without having to read server/logs/conversations.jsonl.
    Off by default. Purely a testing aid - world/actions.py's
    _validate_remember_fact checks this flag, not a game feature.

    Usage:
      memorydebug
      memorydebug <player>
    """

    key = "memorydebug"
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

        enabled = not target.attributes.get("memory_debug_enabled", default=False)
        target.attributes.add("memory_debug_enabled", enabled)
        state = "on" if enabled else "off"
        caller.msg(f"Memory debug messages are now {state} for {target.key}.")
