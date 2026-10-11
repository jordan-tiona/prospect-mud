"""
The `talk` command: how players address talk-capable NPCs.

Wires the full pipeline from design-bible 16.5: prompt builder -> LLM
client -> tool validator -> output check -> narrated reply. Player
text is always labeled as player speech in the prompt (CLAUDE.md hard
rule 6) and is never treated as fact. Conversation history is kept in
memory only (ndb), lost on reload/restart - persistent memory is a
phase 2 feature (design-bible 13.5), not built here.
"""

from evennia.utils.utils import inherits_from

from .command import Command
from world.actions import get_tool_schemas, validate_and_apply
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

        try:
            reply = chat(messages, tools=tools)
        except LLMUnavailableError:
            caller.msg(f"{target.key} seems distracted and doesn't answer right away. (try again in a moment)")
            return

        text = reply.text.strip()
        flagged, _reason = is_flagged(text)
        if flagged:
            caller.msg(f"{target.key} seems momentarily at a loss for words and changes the subject.")
            return

        if text:
            caller.msg(f'{target.key} says, "{text}"')
            history.append(_player_turn(self.message))
            history.append({"role": "assistant", "content": text})
            _trim_history(history)
        elif not reply.tool_calls:
            caller.msg(f"{target.key} doesn't seem to have anything to say.")
            return

        for call in reply.tool_calls:
            result = validate_and_apply(target, caller, call["name"], call["arguments"])
            if result.applied:
                caller.msg(result.narration)
