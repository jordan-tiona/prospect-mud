"""
The `say` command: how players address talk-capable NPCs, per
design-bible 16.5's addressing rule (adopted 2026-10-11). There is no
separate `talk` command; a plain `say` reaches an NPC when the player
names it (explicitly with "to <name>," or by mentioning its name) or,
with no name at all, when exactly one player and one talk-capable NPC
share the room. Anything else is ambient speech - no model call. See
world/npc_addressing.py for the matching logic.

Once an NPC is addressed, the rest of the pipeline is unchanged from
the old `talk` command: prompt builder -> LLM client -> tool validator
-> output check -> narrated reply, logging every turn per
design-bible 14.7. Player text is always labeled as player speech in
the prompt (CLAUDE.md hard rule 6) and is never treated as fact.
Conversation history is kept in memory only (ndb), lost on
reload/restart - persistent memory is a phase 2 feature (design-bible
13.5), not built here.

Tool-calling models reliably return an empty reply alongside a tool
call - the call *is* the whole turn, nothing else fits in it. So when
that happens, _handle_llm_reply makes a second model call reporting
back what the engine actually did and asking the model to react, per
the standard OpenAI tool-calling pattern (see its own docstring).

The model call runs in a background thread (deferToThread), not
inline in func(): Evennia's single-threaded reactor would otherwise
block on that multi-second network call for the *entire server*, not
just this player. func() does the synchronous say/addressing work and
returns immediately; everything that depends on the model's reply
happens in _handle_llm_reply() once the deferred fires.
"""

import json
import uuid

from evennia.commands.default.general import CmdSay as DefaultCmdSay
from evennia.utils import logger
from twisted.internet.threads import deferToThread

from world.actions import get_tool_schemas, quest_context_for, validate_and_apply
from world.commitments import commitment_context_for
from world.conversation_log import log_turn
from world.emotes import format_emote, parse_reply
from world.llm_client import LLMUnavailableError, chat
from world.npc_addressing import present_talkative_npcs, resolve_addressee
from world.npc_profile import parse_persona
from world.output_check import is_flagged
from world.prompt_builder import build_system_prompt
from world.speech_format import normalize_speech

MAX_HISTORY_EXCHANGES = 8  # player+NPC message pairs kept per player per NPC

# Actions whose generic engine narration duplicates what the NPC's own
# in-character reaction says once it arrives (see _handle_action_reaction) -
# showing it immediately reads as a redundant system message layered on
# top of the NPC's own dialogue. Suppressed on the happy path; still
# shown by _handle_action_reaction_error as a fallback, since otherwise
# a slow/unavailable model would leave the player with no response at
# all for these actions.
SUPPRESS_IMMEDIATE_NARRATION = {"give_directions"}

# Actions whose result is useless without the NPC's own follow-up
# reaction - a drink or a part is self-explanatory once handed over,
# but directions are meaningless as a bare acknowledgment ("Sure, I
# can help with that!") with no route in it. Normally the follow-up
# call (see below) only fires when the model leaves its text empty on
# the tool-call turn, to avoid a second round-trip when the model
# already said something substantive - but confirmed live, this model
# reliably fills that slot with a short ack instead, for
# give_directions specifically, leaving the player with no route
# until they ask again. So for actions in this set, always get the
# follow-up reaction, regardless of what the model said on the
# tool-call turn itself.
#
# Phase 2B's commitment actions (docs/phase2b-records-discrepancy-
# proposal.md) are added here for a different reason: these have more
# rejectable preconditions than any action phase 1/2A had, and a
# rejected call is exactly the case where the model's own same-turn
# text is most likely to already claim a success the engine didn't
# grant. Forcing the follow-up reaction every time gives the model a
# chance to correct itself against the real result rather than
# leaving that claim as the final thing the player reads.
FORCE_REACTION_ACTIONS = {
    "give_directions",
    "propose_commitment",
    "accept_commitment",
    "decline_commitment",
    "report_commitment_outcome",
}


def _player_turn(message: str) -> dict:
    # Labeled as player speech at the data level, not just by
    # instruction, per CLAUDE.md hard rule 6.
    return {"role": "user", "content": f'The player says: "{message}"'}


def _get_history(npc, actor) -> list:
    if npc.ndb.conversations is None:
        npc.ndb.conversations = {}
    return npc.ndb.conversations.setdefault(actor.dbref, [])


def _trim_history(history: list) -> None:
    # A plain fixed-length cut can land between an assistant message's
    # tool_calls and the "tool"-role result message(s) that must
    # immediately follow it in the OpenAI message format - leaving an
    # orphaned tool-result message at the front of history with no
    # matching tool_calls before it. Some backends tolerate that;
    # OpenAI's own (via OpenRouter) rejects the whole request with a
    # 400 ("No tool call found for function call output..."), and
    # since the error path doesn't append anything new to history,
    # that orphan never ages out on its own - every retry replays the
    # same broken history and fails the same way (confirmed live
    # against gpt-4.1-mini, 2026-10-13). So after the fixed-length
    # cut, also drop any leading run of orphaned "tool" messages.
    max_messages = MAX_HISTORY_EXCHANGES * 2
    del history[:-max_messages]
    while history and history[0]["role"] == "tool":
        del history[0]


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


def _get_pending(npc) -> set:
    if npc.ndb.pending is None:
        npc.ndb.pending = set()
    return npc.ndb.pending


def _assistant_turn_messages(raw_text, calls, tool_results):
    """
    OpenAI-style assistant message for one reply - with its `tool_calls`
    attached when it made any - plus a matching `tool` message reporting
    each call's real outcome.

    Used both to build a one-off follow-up chat() call (see
    _build_followup_messages) and, critically, to persist what actually
    happened into the conversation's own stored history (see
    _handle_llm_reply / _handle_action_reaction): a plain
    {"role": "assistant", "content": raw_text} entry is indistinguishable
    from a turn where nothing happened, which left the model with no
    record in its own history that an action had genuinely occurred -
    only prose that looked the same whether it had or hadn't. Confirmed
    live: once a few tool-less turns (e.g. a correctly declined
    off-menu request) entered history this way, the model stopped
    calling the action at all for turns that should have used it,
    apparently pattern-matching the all-prose shape of its own recent
    replies rather than anything in the current request.
    """
    if not calls:
        return [{"role": "assistant", "content": raw_text or None}]

    assistant_message = {
        "role": "assistant",
        "content": raw_text or None,
        "tool_calls": [
            {
                "id": call.get("id") or f"call_{i}",
                "type": "function",
                "function": {"name": call["name"], "arguments": json.dumps(call["arguments"])},
            }
            for i, call in enumerate(calls)
        ],
    }
    tool_messages = []
    for call, result in zip(calls, tool_results):
        if result["applied"]:
            outcome = f"(The action happened: {result['narration']})"
        else:
            outcome = f"(The action did not happen: {result['reason']})"
        tool_messages.append(
            {"role": "tool", "tool_call_id": call.get("id") or "call_0", "content": outcome}
        )
    return [assistant_message] + tool_messages


def _build_followup_messages(messages, raw_text, calls, tool_results):
    """
    Appends the assistant's tool-call turn and the engine's outcome for
    each call, OpenAI-style, so a follow-up chat() call can ask the
    model to react in words to what it just did (see
    _handle_llm_reply's docstring for why this is needed at all).
    """
    return messages + _assistant_turn_messages(raw_text, calls, tool_results)


def _msg_with_lead_blank(caller, text):
    """Send `text` with a blank line ahead of it.

    A separate caller.msg("") call for the blank line, immediately
    followed by caller.msg(text), does not reliably render as a blank
    line in every client - confirmed live in Mudlet 5.0.1 (2026-10-13):
    `py self.msg(""); self.msg("END-MARKER")` showed no gap at all
    before "END-MARKER", even though Evennia's own session/telnet
    layer does send a genuine empty line for msg(""). Embedding the
    newline inside a single message's own text instead (so it's one
    "\\r\\n...\\r\\n" telnet line rather than two separate messages)
    renders correctly everywhere tested.
    """
    caller.msg("\n" + text)


def _render_reply_segments(target, caller, segments, pronouns, lead_blank=False):
    """Show an NPC's parsed reply (world.emotes.parse_reply) in the
    order its dialogue and actions actually appear - content/npc-
    shared-rules.md now invites occasionally splitting dialogue around
    an action (project owner's call), e.g.:

        Mara Voss says to you, "xxx"
        Mara Voss crosses her arms.
        Mara Voss says to you, "yyy"

    `lead_blank` puts a blank line ahead of the first message sent -
    see _msg_with_lead_blank for why that's embedded in the message's
    own text rather than sent as a separate caller.msg("").
    """
    for i, (kind, content) in enumerate(segments):
        prefix = "\n" if lead_blank and i == 0 else ""
        if kind == "dialogue":
            caller.msg(f'{prefix}{target.key} says to you, |c"{content}"|n')
        else:
            caller.msg(prefix + format_emote(target.key, content, pronouns))


def _handle_llm_reply(
    reply, target, caller, history, player_message, log_context, pending, messages, max_tokens,
    pronouns="",
):
    """
    Runs once the model has responded, back on the main thread (a
    Twisted callback always fires on the reactor thread, so this is
    safe to touch the database from). Separated from engage_npc() so
    it's directly unit-testable without any threading involved.

    Tool-calling models (confirmed empirically against the local
    Qwen3 model) reliably return an empty `text` whenever they use a
    tool call - the call *is* the whole turn, with no room for a
    spoken line alongside it, even though content/npc-shared-rules.md
    tells every NPC to always say something when using an action. A
    wording fix alone can't override that: it's the model's
    tool-calling template, not a prompting failure. So when that
    happens, a second model call is made (see
    _build_followup_messages) reporting back what the engine actually
    did, and asking the model to react - the standard OpenAI
    tool-calling pattern. This costs extra latency, but only on turns
    where an action was actually used.
    """
    # A blank line ahead of the NPC's reply - it arrives well after the
    # player's own "You say, ..." echo (the model call isn't instant),
    # so without this the reply runs up visually against that older
    # line. Project owner's call: this gap, but not one between every
    # individual emote/dialogue line within the reply itself. See
    # _msg_with_lead_blank for why every branch below embeds it in the
    # first real message instead of sending it as its own caller.msg("").
    raw_text = reply.text.strip()
    flagged, flag_reason = is_flagged(raw_text)

    if flagged:
        pending.discard(caller.dbref)
        _msg_with_lead_blank(
            caller, f"{target.key} seems momentarily at a loss for words and changes the subject."
        )
        log_turn(
            **log_context,
            model=reply.model,
            npc_response=raw_text,
            tool_calls=[],
            flagged=True,
            flag_reason=flag_reason,
        )
        return

    segments = parse_reply(raw_text)

    if not segments and not reply.tool_calls:
        pending.discard(caller.dbref)
        _msg_with_lead_blank(caller, f"{target.key} doesn't seem to have anything to say.")
        log_turn(
            **log_context,
            model=reply.model,
            npc_response=raw_text,
            tool_calls=[],
            flagged=False,
        )
        return

    # segments may be empty here (tool_calls present, no dialogue/emote
    # text) - in that case nothing below sends anything until the
    # first applied tool's narration, so the leading blank line has to
    # wait for that instead of being attached to a segment that never
    # renders.
    _render_reply_segments(target, caller, segments, pronouns, lead_blank=bool(segments))

    tool_call_records = []
    tool_results = []
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
        tool_results.append(
            {"applied": result.applied, "reason": result.reason, "narration": result.narration}
        )
        if result.applied and call["name"] not in SUPPRESS_IMMEDIATE_NARRATION:
            # A blank line ahead of this - when the model gives
            # dialogue/an action *and* a tool call in the same turn,
            # this mechanical narration line would otherwise run
            # straight into the NPC's own last line with nothing to
            # mark it as a distinct, engine-reported event (e.g. "Mara
            # Voss agrees to help" easy to miss right under her own
            # dialogue). Also separates multiple narrations from each
            # other, for a turn with more than one applied tool call.
            _msg_with_lead_blank(caller, result.narration)

    tool_call_names = {call["name"] for call in reply.tool_calls}
    needs_reaction = reply.tool_calls and (
        not segments or tool_call_names & FORCE_REACTION_ACTIONS
    )

    if needs_reaction:
        # Ask the model to react now that it's seen the outcome,
        # rather than leaving the action to speak for itself in total
        # silence (or, for FORCE_REACTION_ACTIONS, leaving its own
        # tool-call-turn text as the only thing the player ever
        # hears). Still counts as "pending" until this resolves too.
        followup_messages = _build_followup_messages(messages, raw_text, reply.tool_calls, tool_results)
        deferred = deferToThread(chat, followup_messages, max_tokens=max_tokens)
        deferred.addCallback(
            _handle_action_reaction, target, caller, history, player_message, log_context, pending,
            tool_call_records, pronouns, raw_text, reply.tool_calls, tool_results,
        )
        deferred.addErrback(
            _handle_action_reaction_error, target, caller, history, player_message, log_context, pending,
            tool_call_records, raw_text, reply.tool_calls, tool_results,
        )
        return

    if segments:
        # Store the model's own words (including its *action* markup)
        # *and* whether it actually called an action this turn - a
        # plain content-only entry would look identical to a turn
        # where nothing happened, which is what let tool-calling
        # quietly stop working mid-conversation (see
        # _assistant_turn_messages).
        history.append(_player_turn(player_message))
        history.extend(_assistant_turn_messages(raw_text, reply.tool_calls, tool_results))
        _trim_history(history)

    pending.discard(caller.dbref)
    log_turn(
        **log_context,
        model=reply.model,
        npc_response=raw_text,
        tool_calls=tool_call_records,
        flagged=False,
    )


def _handle_action_reaction(
    reply, target, caller, history, player_message, log_context, pending, tool_call_records,
    pronouns, original_raw_text, original_calls, tool_results,
):
    """
    Runs once the follow-up call (asking the model to react to its own
    action) has resolved. The action itself already happened and was
    narrated by _handle_llm_reply before this was even dispatched.

    `original_raw_text`/`original_calls`/`tool_results` are what that
    earlier, action-only reply actually was - needed here so history
    can record the real tool-call turn (see _assistant_turn_messages),
    not just this follow-up reaction, which on its own would once again
    look like plain prose with no action behind it.
    """
    pending.discard(caller.dbref)
    raw_text = reply.text.strip()
    flagged, flag_reason = is_flagged(raw_text)

    if flagged:
        log_turn(
            **log_context,
            model=reply.model,
            npc_response=raw_text,
            tool_calls=tool_call_records,
            flagged=True,
            flag_reason=flag_reason,
        )
        return

    segments = parse_reply(raw_text)
    _render_reply_segments(target, caller, segments, pronouns, lead_blank=bool(segments))

    # The action turn itself (with its tool_calls) is recorded
    # regardless of whether the model went on to say anything about
    # it - the engine's own record of what happened shouldn't depend
    # on the model's follow-up reply.
    history.append(_player_turn(player_message))
    history.extend(_assistant_turn_messages(original_raw_text, original_calls, tool_results))
    if segments:
        history.append({"role": "assistant", "content": raw_text})
    _trim_history(history)

    log_turn(
        **log_context,
        model=reply.model,
        npc_response=raw_text,
        tool_calls=tool_call_records,
        flagged=False,
    )


def _handle_action_reaction_error(
    failure, target, caller, history, player_message, log_context, pending, tool_call_records,
    original_raw_text, original_calls, tool_results,
):
    pending.discard(caller.dbref)
    if not failure.check(LLMUnavailableError):
        logger.log_err(f"say command: unexpected error getting {target.key}'s reaction: {failure}")
    # The action already happened. For most actions it was already
    # narrated up front (see _handle_llm_reply), so don't also tell the
    # player the NPC "seems distracted" after the fact - just leave that
    # earlier narration to speak for itself. For actions in
    # SUPPRESS_IMMEDIATE_NARRATION, that narration was held back
    # specifically because the NPC's own reaction was expected to cover
    # it - so if the reaction never arrives, show it now rather than
    # leaving the player with no response at all.
    for call, result in zip(original_calls, tool_results):
        if result["applied"] and call["name"] in SUPPRESS_IMMEDIATE_NARRATION:
            caller.msg(result["narration"])
    # Still record the action turn in history, same as the non-error
    # path, so a failed reaction call doesn't also erase the action
    # from the model's own memory of the conversation.
    history.append(_player_turn(player_message))
    history.extend(_assistant_turn_messages(original_raw_text, original_calls, tool_results))
    _trim_history(history)

    log_turn(
        **log_context,
        model="",
        npc_response=None,
        tool_calls=tool_call_records,
        flagged=False,
        flag_reason=f"llm_unavailable: {failure.value}",
    )


def _handle_llm_error(failure, target, caller, log_context, pending):
    pending.discard(caller.dbref)
    if not failure.check(LLMUnavailableError):
        # Not the expected failure mode - log it so it's not silently
        # lost, but still give the player the same graceful fallback
        # rather than a traceback.
        logger.log_err(f"say command: unexpected error from {target.key}: {failure}")
    _msg_with_lead_blank(
        caller, f"{target.key} seems distracted and doesn't answer right away. (try again in a moment)"
    )
    log_turn(
        **log_context,
        model="",
        npc_response=None,
        tool_calls=[],
        flagged=False,
        flag_reason=f"llm_unavailable: {failure.value}",
    )


def engage_npc(target, caller, message):
    """
    Runs the full NPC conversation pipeline once `say` has resolved
    `target` as the NPC being addressed and `message` as what it
    hears. The player's line has already been broadcast to the room
    as an ordinary `say` by the time this runs.

    Guards against overlapping calls: if this player already has a
    model call in flight for this NPC (they said something else before
    the first reply came back), a second deferToThread call isn't
    queued on top of it - that just piles latency onto an already-slow
    local model and produces replies in a confusing, possibly
    out-of-order sequence. The player is told to wait instead.
    """
    pending = _get_pending(target)
    if caller.dbref in pending:
        caller.msg(f"{target.key} is still thinking about what you said - give them a moment.")
        return

    profile = parse_persona(target.db.npc_id)
    system_prompt = build_system_prompt(target.db.npc_id)
    history = _get_history(target, caller)
    tools = get_tool_schemas(profile.actions)

    messages = [{"role": "system", "content": system_prompt.text}]
    quest_context = quest_context_for(profile.actions, caller)
    if quest_context:
        messages.append({"role": "system", "content": quest_context})
    commitment_context = commitment_context_for(profile.npc_id, profile.actions, caller)
    if commitment_context:
        messages.append({"role": "system", "content": commitment_context})
    messages += history + [_player_turn(message)]

    log_context = {
        "conversation_id": _get_conversation_id(target, caller),
        "turn_id": _next_turn_id(target, caller),
        "npc_id": target.db.npc_id,
        "location": target.location.key if target.location else "",
        "actor_key": caller.key,
        "actor_dbref": caller.dbref,
        "player_message": message,
        "prompt_messages": messages,
        "prompt_version": profile.prompt_version,
    }

    pending.add(caller.dbref)
    deferred = deferToThread(chat, messages, tools=tools, max_tokens=profile.max_reply_tokens)
    deferred.addCallback(
        _handle_llm_reply, target, caller, history, message, log_context, pending,
        messages, profile.max_reply_tokens, profile.pronouns,
    )
    deferred.addErrback(_handle_llm_error, target, caller, log_context, pending)


class CmdSay(DefaultCmdSay):
    """
    Speak as your character.

    Usage:
      say <message>
      say to <npc>, <message>

    Talk to those in your current location. A talk-capable NPC
    answers when you name it ("say to Mara, hello" or just mentioning
    its name), when you're alone with exactly one such NPC, or when
    you keep talking to whoever you were just addressing without
    naming them again. Otherwise it's just heard, not answered.
    """

    def func(self):
        caller = self.caller

        if not self.args:
            caller.msg("Say what?")
            return

        # The NPC this player was last addressing in this same room,
        # if any - cleared implicitly by the room check below the
        # moment they're somewhere else, so a stale focus from a
        # previous room can never carry over.
        stored_focus = caller.ndb.addressing_focus
        focus = stored_focus[1] if stored_focus and stored_focus[0] == caller.location else None

        target, message = resolve_addressee(self.args, caller.location, focus=focus)
        if target is not None:
            caller.ndb.addressing_focus = (caller.location, target)
        # An explicit "to <name>" prefix is addressing syntax, not
        # something the character actually says aloud - strip it from
        # what the room hears too, not just what the NPC hears. A bare
        # name mention or ambient speech has message == self.args, so
        # this is a no-op for those cases.
        broadcast_text = message or self.args
        broadcast_text, is_question = normalize_speech(broadcast_text)

        speech = caller.at_pre_say(broadcast_text)
        if not speech:
            return
        # Naming the addressee in both the speaker's own echo and what
        # the room sees - not just what the NPC hears - distinguishes
        # separate conversations when more than one player is talking
        # to NPCs in the same room (or more than one talk-capable NPC
        # is present, as in the Civic Office since phase 2B).
        if target is not None:
            if is_question:
                msg_self = '{self} ask {all_receivers}, "|n{speech}|n"'
                msg_location = '{object} asks {all_receivers}, "{speech}"'
            else:
                msg_self = '{self} say to {all_receivers}, "|n{speech}|n"'
                msg_location = '{object} says to {all_receivers}, "{speech}"'
        elif is_question:
            msg_self = '{self} ask, "|n{speech}|n"'
            msg_location = '{object} asks, "{speech}"'
        else:
            msg_self = '{self} say, "|n{speech}|n"'
            msg_location = '{object} says, "{speech}"'
        caller.at_say(
            speech, msg_self=msg_self, msg_location=msg_location,
            receivers=[target] if target is not None else None,
        )

        if target is None:
            # With two or more talk-capable NPCs present, an
            # unaddressed line that doesn't name one of them resolves
            # to ambient speech - correct per design-bible 16.5, but
            # silently so, which reads exactly like "they stopped
            # responding" if the player had been naming one of them a
            # moment ago and drops the name on a follow-up line (a
            # perfectly natural thing to do in real conversation).
            # This nudge is sent only to the speaker, not broadcast.
            if len(present_talkative_npcs(caller.location)) > 1:
                caller.msg(
                    "(More than one person here might answer that - say who you mean, "
                    "e.g. 'say to Veska, ...', or just use their name.)"
                )
            return
        if not message:
            caller.msg(f"Say what to {target.key}?")
            return

        engage_npc(target, caller, broadcast_text)
