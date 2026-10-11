"""
The `talk` command: how players address talk-capable NPCs.

Wires the full pipeline from design-bible 16.5: prompt builder -> LLM
client -> tool validator -> output check -> narrated reply, logging
every turn per design-bible 14.7. Player text is always labeled as
player speech in the prompt (CLAUDE.md hard rule 6) and is never
treated as fact. Conversation history is kept in memory only (ndb),
lost on reload/restart - persistent memory is a phase 2 feature
(design-bible 13.5), not built here.

The model call runs in a background thread (deferToThread), not
inline in func(): Evennia's single-threaded reactor would otherwise
block on that multi-second network call for the *entire server*, not
just this player, and the player's own line wouldn't even echo back
until the reply arrived. func() does the synchronous validation and
echoes the player's line, then returns immediately; everything that
depends on the model's reply happens in _handle_llm_reply() once the
deferred fires.
"""

import uuid

from twisted.internet.threads import deferToThread

from evennia.utils import logger
from evennia.utils.utils import inherits_from

from .command import Command
from world.actions import get_tool_schemas, validate_and_apply
from world.conversation_log import log_turn
from world.emotes import format_emote, split_emotes
from world.llm_client import LLMUnavailableError, chat
from world.npc_profile import parse_persona
from world.output_check import is_flagged
from world.prompt_builder import build_system_prompt

MAX_HISTORY_EXCHANGES = 4  # player+NPC message pairs kept per player per NPC


def _player_turn(message: str) -> dict:
    # Labeled as player speech at the data level, not just by
    # instruction, per CLAUDE.md hard rule 6.
    return {"role": "user", "content": f'The player says: "{message}"'}


def _get_history(npc, actor) -> list:
    if npc.ndb.conversations is None:
        npc.ndb.conversations = {}
    return npc.ndb.conversations.setdefault(actor.dbref, [])


def _trim_history(history: list) -> None:
    max_messages = MAX_HISTORY_EXCHANGES * 2
    del history[:-max_messages]


def _get_conversation_id(npc, actor) -> str:
    if npc.ndb.conversation_ids is None:
        npc.ndb.conversation_ids = {}
    ids = npc.ndb.conversation_ids
    if actor.dbref not in ids:
        ids[actor.dbref] = uuid.uuid4().hex
    return ids[actor.dbref]


def _next_turn_id(npc, actor) -> int:
    if npc.ndb.turn_counters is None:
        npc.ndb.turn_counters = {}
    counters = npc.ndb.turn_counters
    counters[actor.dbref] = counters.get(actor.dbref, 0) + 1
    return counters[actor.dbref]


def _handle_llm_reply(reply, target, caller, history, player_message, log_context):
    """
    Runs once the model has responded, back on the main thread (a
    Twisted callback always fires on the reactor thread, so this is
    safe to touch the database from). Separated from func() so it's
    directly unit-testable without any threading involved.
    """
    raw_text = reply.text.strip()
    flagged, flag_reason = is_flagged(raw_text)

    if flagged:
        caller.msg(f"{target.key} seems momentarily at a loss for words and changes the subject.")
        log_turn(
            **log_context,
            model=reply.model,
            npc_response=raw_text,
            tool_calls=[],
            flagged=True,
            flag_reason=flag_reason,
        )
        return

    dialogue, emotes = split_emotes(raw_text)

    if not dialogue and not emotes and not reply.tool_calls:
        caller.msg(f"{target.key} doesn't seem to have anything to say.")
        log_turn(
            **log_context,
            model=reply.model,
            npc_response=raw_text,
            tool_calls=[],
            flagged=False,
        )
        return

    for emote in emotes:
        caller.msg(format_emote(target.key, emote))

    if dialogue:
        caller.msg(f'{target.key} says, "{dialogue}"')

    if dialogue or emotes:
        # store the model's own words (including its *action* markup)
        # as context for its next turn, not our reformatted display text
        history.append(_player_turn(player_message))
        history.append({"role": "assistant", "content": raw_text})
        _trim_history(history)

    tool_call_records = []
    for call in reply.tool_calls:
        result = validate_and_apply(target, caller, call["name"], call["arguments"])
        tool_call_records.append(
            {
                "name": call["name"],
                "arguments": call["arguments"],
                "applied": result.applied,
                "reason": result.reason,
            }
        )
        if result.applied:
            caller.msg(result.narration)

    log_turn(
        **log_context,
        model=reply.model,
        npc_response=raw_text,
        tool_calls=tool_call_records,
        flagged=False,
    )


def _handle_llm_error(failure, target, caller, log_context):
    if not failure.check(LLMUnavailableError):
        # Not the expected failure mode - log it so it's not silently
        # lost, but still give the player the same graceful fallback
        # rather than a traceback.
        logger.log_err(f"talk command: unexpected error from {target.key}: {failure}")
    caller.msg(f"{target.key} seems distracted and doesn't answer right away. (try again in a moment)")
    log_turn(
        **log_context,
        model="",
        npc_response=None,
        tool_calls=[],
        flagged=False,
        flag_reason="llm_unavailable",
    )


class CmdTalk(Command):
    """
    Talk to an NPC.

    Usage:
      talk <npc> = <message>

    Only works on talk-capable NPCs, not ambient scenery.
    """

    key = "talk"
    locks = "cmd:all()"
    help_category = "General"

    def parse(self):
        args = self.args.strip()
        if "=" in args:
            lhs, rhs = args.split("=", 1)
        else:
            lhs, rhs = args, ""
        self.target_name = lhs.strip()
        self.message = rhs.strip()

    def func(self):
        caller = self.caller

        if not self.target_name:
            caller.msg("Talk to whom? Usage: talk <npc> = <message>")
            return

        target = caller.search(self.target_name, location=caller.location)
        if not target:
            return

        if not inherits_from(target, "typeclasses.npcs.TalkativeNPC"):
            caller.msg(f"{target.key} doesn't seem interested in talking.")
            return

        if not self.message:
            caller.msg(f"Talk to {target.key} about what? Usage: talk <npc> = <message>")
            return

        caller.msg(f'You say to {target.key}, "{self.message}"')
        caller.location.msg_contents(
            f"{caller.key} talks to {target.key}.",
            exclude=[caller],
        )

        profile = parse_persona(target.db.npc_id)
        system_prompt = build_system_prompt(target.db.npc_id)
        history = _get_history(target, caller)
        tools = get_tool_schemas(profile.actions)

        messages = [{"role": "system", "content": system_prompt.text}] + history + [_player_turn(self.message)]

        log_context = {
            "conversation_id": _get_conversation_id(target, caller),
            "turn_id": _next_turn_id(target, caller),
            "npc_id": target.db.npc_id,
            "location": target.location.key if target.location else "",
            "actor_key": caller.key,
            "actor_dbref": caller.dbref,
            "player_message": self.message,
            "prompt_messages": messages,
            "prompt_version": profile.prompt_version,
        }

        deferred = deferToThread(chat, messages, tools=tools)
        deferred.addCallback(_handle_llm_reply, target, caller, history, self.message, log_context)
        deferred.addErrback(_handle_llm_error, target, caller, log_context)
