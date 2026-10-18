"""
Integration tests for the `say` command's NPC-addressing and
conversation pipeline (per CLAUDE.md's prototype scope and
design-bible 16.5's addressing rule, adopted 2026-10-11).

The LLM call itself is mocked (world.llm_client.chat) so these run
fast and deterministically, without a live Ollama server. The manual
smoke test in world/test_llm_connection.py remains the way to confirm
actual model connectivity.

say.py runs the model call via deferToThread so a slow model never
blocks the whole server. These tests replace deferToThread with a
version that runs synchronously (using a real, already-fired Twisted
Deferred - defer.succeed/defer.fail - so the exact same callback/
errback chain in say.py runs, just without needing a live reactor).

Run with:
    evennia test commands
"""

import json
import time
from unittest.mock import patch

from django.test import TestCase, override_settings
from evennia import create_object
from twisted.internet import defer

from commands.say import (
    FIRST_PASS_HIDDEN_NOTE,
    FIRST_PASS_SHOWN_NOTE,
    MAX_HISTORY_EXCHANGES,
    _build_followup_messages,
    _trim_history,
)
from world.actions import get_quest_state
from world.build_npcs import build as build_npcs
from world.build_rooms import build as build_rooms
from world.emotes import name_the_listener, parse_reply
from world.llm_budget import call_cost_usd
from world.llm_client import LLMReply, LLMUnavailableError
from world.npc_profile import parse_persona
from world.overheard import OVERHEARD_SECONDS


def _reply(text, tool_calls=None):
    return LLMReply(text=text, model="test-model", raw={}, tool_calls=tool_calls or [])


def _sync_defer_to_thread(fn, *args, **kwargs):
    try:
        result = fn(*args, **kwargs)
    except Exception as err:  # noqa: BLE001 - mirrors deferToThread's own behavior
        return defer.fail(err)
    return defer.succeed(result)


def _record_text(text="", **kwargs):
    # Evennia's default at_say() passes text as a (string, {"type":
    # ...}) tuple, not a bare string - unwrap it so assertions below
    # can do plain substring checks.
    if isinstance(text, (tuple, list)):
        text = text[0]
    return text


class BuildFollowupMessagesTests(TestCase):
    """Pure-function tests for the OpenAI-style follow-up turn shape."""

    def test_appends_assistant_tool_call_and_tool_result(self):
        base = [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}]
        calls = [{"id": "call_1", "name": "serve_drink", "arguments": {"drink_type": "hot"}}]
        results = [{"applied": True, "reason": "", "narration": "serves a hot drink"}]

        followup = _build_followup_messages(base, "", calls, results)

        self.assertEqual(followup[:2], base)
        assistant_msg = followup[2]
        self.assertEqual(assistant_msg["role"], "assistant")
        self.assertEqual(assistant_msg["tool_calls"][0]["id"], "call_1")
        self.assertEqual(assistant_msg["tool_calls"][0]["function"]["name"], "serve_drink")
        tool_msg = followup[3]
        self.assertEqual(tool_msg["role"], "tool")
        self.assertEqual(tool_msg["tool_call_id"], "call_1")
        self.assertIn("happened", tool_msg["content"])

    def test_reports_a_dropped_call_as_not_happening(self):
        calls = [{"id": "call_1", "name": "serve_drink", "arguments": {"drink_type": "lukewarm"}}]
        results = [{"applied": False, "reason": "invalid drink_type", "narration": ""}]

        followup = _build_followup_messages([], "", calls, results)

        tool_msg = followup[-2]
        self.assertIn("did not happen", tool_msg["content"])
        self.assertIn("invalid drink_type", tool_msg["content"])

    def test_closing_note_says_whether_the_player_saw_the_first_pass(self):
        # PF-0001: without this the model assumes its first-pass text
        # was seen and writes only a continuation of it.
        calls = [{"id": "call_1", "name": "serve_drink", "arguments": {"drink_type": "hot"}}]
        results = [{"applied": True, "reason": "", "narration": "serves a hot drink"}]

        shown = _build_followup_messages([], "Here.", calls, results, first_pass_shown=True)[-1]
        hidden = _build_followup_messages([], "Here.", calls, results)[-1]

        self.assertEqual(shown, {"role": "system", "content": FIRST_PASS_SHOWN_NOTE})
        self.assertEqual(hidden, {"role": "system", "content": FIRST_PASS_HIDDEN_NOTE})


class NameTheListenerTests(TestCase):
    """What others in the room see of an NPC action written to the
    player it's talking to."""

    def test_replaces_each_second_person_form(self):
        cases = {
            "slides a mug toward you": "slides a mug toward Alice",
            "taps your shoulder": "taps Alice's shoulder",
            "nods, as if you're right": "nods, as if Alice is right",
            "smiles, glad you’ve come": "smiles, glad Alice has come",
            "You get a nod": "Alice get a nod",
        }
        for emote, expected in cases.items():
            self.assertEqual(name_the_listener(emote, "Alice"), expected)

    def test_leaves_words_that_only_contain_you_alone(self):
        self.assertEqual(name_the_listener("looks youthful", "Alice"), "looks youthful")


class ParseReplyTests(TestCase):
    def test_an_action_naming_a_tool_is_dropped(self):
        # Live 2026-10-18: Mara's reaction wrote *calls give_faulty_module*.
        segments = parse_reply('"I\'ll get the module ready." *calls give_faulty_module*')
        self.assertEqual(segments, [("dialogue", "I'll get the module ready.")])

    def test_ordinary_actions_are_kept(self):
        segments = parse_reply('*wipes down the counter* "Morning."')
        self.assertEqual(segments, [("emote", "wipes down the counter"), ("dialogue", "Morning.")])


class TrimHistoryTests(TestCase):
    """
    _trim_history must never leave a leading orphaned "tool"-role
    message with no preceding assistant tool_calls message - some
    OpenAI-compatible backends reject the whole request with a 400 if
    it does (confirmed live against gpt-4.1-mini via OpenRouter,
    2026-10-13: "No tool call found for function call output...").
    Since the error path doesn't append to history, an orphan like
    that is a permanent deadlock for that player+NPC conversation
    once it happens, not just a one-off glitch.
    """

    def test_cut_landing_on_a_tool_message_also_drops_it(self):
        # Fixed-length cut would land exactly on the "tool" message,
        # stranding it with no assistant tool_calls message before it.
        pairs_to_keep = MAX_HISTORY_EXCHANGES
        history = []
        for i in range(pairs_to_keep + 1):
            history.append({"role": "user", "content": f"msg {i}"})
            history.append(
                {"role": "assistant", "content": None, "tool_calls": [{"id": f"call_{i}"}]}
            )
            history.append({"role": "tool", "tool_call_id": f"call_{i}", "content": "ok"})

        _trim_history(history)

        self.assertNotEqual(history[0]["role"], "tool")

    def test_normal_trim_without_a_split_pair_is_unaffected(self):
        history = []
        for i in range(MAX_HISTORY_EXCHANGES + 3):
            history.append({"role": "user", "content": f"msg {i}"})
            history.append({"role": "assistant", "content": f"reply {i}"})

        _trim_history(history)

        self.assertEqual(len(history), MAX_HISTORY_EXCHANGES * 2)
        self.assertEqual(history[0]["role"], "user")


@override_settings(LLM_COOLDOWN_SECONDS=0)
class _SayTestBase(TestCase):
    """
    Shared fixture for every say-command test class below. Holds no
    tests itself, so subclasses don't re-run each other's tests (which
    subclassing a concrete test class would do).

    LLM_COOLDOWN_SECONDS is forced to 0: most tests say several lines in
    a row to exercise addressing/history/logging behavior, not the
    cooldown gate itself (CostSafeguardTests overrides it per test).
    """

    def setUp(self):
        rooms = build_rooms()
        npcs = build_npcs()
        self.cafe = rooms["corner_cafe"]
        self.workshop = rooms["maintenance_workshop"]
        self.mara = npcs["mara_voss"]
        self.tarin = npcs["tarin_os"]
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=self.cafe
        )
        self.messages = []
        self.actor.msg = lambda text="", **kw: self.messages.append(_record_text(text, **kw))

        defer_patcher = patch("commands.say.deferToThread", side_effect=_sync_defer_to_thread)
        defer_patcher.start()
        self.addCleanup(defer_patcher.stop)

        # Logging is covered by its own tests against the real
        # function (world/test_conversation_log.py); here we just
        # need it not to hit the filesystem.
        log_patcher = patch("commands.say.log_turn")
        self.mock_log_turn = log_patcher.start()
        self.addCleanup(log_patcher.stop)

    def _say(self, message):
        self.actor.execute_cmd(f"say {message}")

    def _add_other_player(self, location=None):
        other = create_object(
            "typeclasses.characters.Character", key="Other", location=location or self.cafe
        )
        other.msg = lambda text="", **kw: None
        return other


class SayCommandTests(_SayTestBase):
    # -- other players present: one hint per room visit -----------------

    @patch("commands.say.chat")
    def test_unaddressed_line_with_other_players_hints_once(self, mock_chat):
        self._add_other_player()
        self._say("hello")
        self._say("anyone here?")
        hints = [m for m in self.messages if "won't assume you mean them" in m]
        self.assertEqual(len(hints), 1)
        self.assertIn("say to Mara", hints[0])
        mock_chat.assert_not_called()

    @patch("commands.say.chat")
    def test_hint_comes_back_in_a_new_room(self, mock_chat):
        self._add_other_player()
        self._add_other_player(location=self.workshop)
        self._say("hello")
        self.actor.location = self.workshop
        self._say("hello")
        hints = [m for m in self.messages if "won't assume you mean them" in m]
        self.assertEqual(len(hints), 2)
        self.assertIn("say to Tarin", hints[1])

    @patch("commands.say.chat")
    def test_two_npc_hint_names_someone_present_once_per_visit(self, mock_chat):
        self.actor.location = build_rooms()["civic_office"]
        self._say("hello")
        self._say("anyone?")
        hints = [m for m in self.messages if "More than one person" in m]
        self.assertEqual(len(hints), 1)
        self.assertTrue("say to Iri" in hints[0] or "say to Veska" in hints[0])
        mock_chat.assert_not_called()

    @patch("commands.say.chat")
    def test_hints_stop_once_the_player_names_an_npc(self, mock_chat):
        mock_chat.return_value = _reply("Afternoon.")
        self._add_other_player()
        self._add_other_player(location=self.workshop)
        self._say("to Mara, hello")
        self.actor.location = self.workshop
        self._say("hello")
        self.assertTrue(self.actor.db.say_hint_learned)
        self.assertFalse(any("won't assume you mean them" in m for m in self.messages))

    @patch("commands.say.chat")
    def test_implicit_addressing_does_not_count_as_naming(self, mock_chat):
        mock_chat.return_value = _reply("Afternoon.")
        self._say("hello")  # alone with Mara: implicit, no name used
        self.assertFalse(self.actor.db.say_hint_learned)

    @patch("commands.say.chat")
    def test_hints_stop_after_the_limit(self, mock_chat):
        self._add_other_player()
        self._add_other_player(location=self.workshop)
        for room in (self.cafe, self.workshop, self.cafe, self.workshop, self.cafe):
            self.actor.location = room
            self._say("hello")
        hints = [m for m in self.messages if "won't assume you mean them" in m]
        self.assertEqual(len(hints), 3)

    # -- addressing: lone player, lone NPC -----------------------------

    @patch("commands.say.chat")
    def test_lone_player_lone_npc_is_implicitly_addressed(self, mock_chat):
        mock_chat.return_value = _reply('Afternoon. What can I get you?')
        self._say("hello there")

        self.assertTrue(any("Afternoon" in m for m in self.messages))
        history = self.mara.ndb.conversations[self.actor.dbref]
        self.assertIn("Hello there.", history[0]["content"])

    @patch("commands.say.chat")
    def test_say_still_broadcasts_as_ordinary_speech(self, mock_chat):
        mock_chat.return_value = _reply("Afternoon.")
        self._say("hello there")

        # Evennia's default at_say() wraps the echo with |n ANSI-reset
        # markup around the spoken text; check loosely rather than
        # pin to its exact template.
        self.assertTrue(any("You say" in m and "Hello there." in m for m in self.messages))

    @patch("commands.say.chat")
    def test_implicitly_addressed_broadcast_names_the_npc(self, mock_chat):
        # Even with no name typed, the player resolved a real
        # conversational partner - naming it in the broadcast (not
        # just a bare "You say, ...") distinguishes this from ambient
        # speech once there's more than one NPC/player to tell apart.
        mock_chat.return_value = _reply("Afternoon.")
        self._say("hello there")

        self.assertTrue(any("You say to Mara" in m for m in self.messages))

    @patch("commands.say.chat")
    def test_own_speech_is_bright_cyan_like_npc_speech(self, mock_chat):
        # Owner, 2026-10-17: the player's own lines get the same colour
        # as NPC replies so they stand out when scrolling back.
        mock_chat.return_value = _reply("Afternoon.")
        self._say("hello there")

        self.assertTrue(any('|c"Hello there."|n' in m for m in self.messages))

    @patch("commands.say.chat")
    def test_npc_reply_is_addressed_to_the_player(self, mock_chat):
        mock_chat.return_value = _reply("Afternoon.")
        self._say("hello there")

        self.assertTrue(any("Mara Voss says to you" in m for m in self.messages))

    @patch("commands.say.chat")
    def test_others_in_the_room_see_the_npc_reply_addressed_by_name(self, mock_chat):
        # Owner, 2026-10-17: bystanders used to hear only the player's
        # half of the conversation.
        mock_chat.return_value = _reply('"Afternoon." *puts a cold beer in front of you*')
        other = self._add_other_player()
        heard = []
        other.msg = lambda text="", **kw: heard.append(_record_text(text, **kw))

        self._say("to Mara, hello there")

        self.assertTrue(any('Mara Voss says to Tester, |c"Afternoon."|n' in m for m in heard))
        self.assertTrue(any("Mara Voss puts a cold beer in front of Tester." in m for m in heard))
        self.assertFalse(any("says to you" in m for m in heard))
        self.assertTrue(any("Mara Voss says to you" in m for m in self.messages))

    def _system_notes(self, mock_chat):
        messages = mock_chat.call_args.args[0]
        return [m["content"] for m in messages if m["role"] == "system"]

    @patch("commands.say.chat")
    def test_a_bystander_prompt_names_who_the_npc_was_talking_to(self, mock_chat):
        mock_chat.return_value = _reply('"Afternoon." *taps your shoulder*')
        other = self._add_other_player()
        self._say("to Mara, my secret is the password swordfish")

        other.execute_cmd("say to Mara, what did you tell Tester?")

        notes = self._system_notes(mock_chat)
        overheard = [n for n in notes if "while this person was nearby" in n]
        self.assertEqual(len(overheard), 1)
        self.assertIn("talking with Tester", overheard[0])
        # Names only: nothing either side said reaches another player's prompt.
        prompt = json.dumps(mock_chat.call_args.args[0])
        self.assertNotIn("swordfish", prompt)
        self.assertNotIn("Afternoon", prompt)

    @patch("commands.say.chat")
    def test_the_speaker_own_prompt_gets_no_overheard_note(self, mock_chat):
        mock_chat.return_value = _reply("Afternoon.")
        self._add_other_player()
        self._say("to Mara, hello")
        self._say("to Mara, how's business?")

        self.assertFalse(any("while this person was nearby" in n for n in self._system_notes(mock_chat)))

    @patch("commands.say.chat")
    def test_someone_who_arrives_later_gets_no_overheard_note(self, mock_chat):
        mock_chat.return_value = _reply("Afternoon.")
        self._add_other_player()
        self._say("to Mara, hello")
        latecomer = create_object("typeclasses.characters.Character", key="Late", location=self.cafe)
        latecomer.msg = lambda text="", **kw: None

        latecomer.execute_cmd("say to Mara, what did you tell Tester?")

        self.assertFalse(any("while this person was nearby" in n for n in self._system_notes(mock_chat)))

    @patch("commands.say.chat")
    def test_the_overheard_note_expires(self, mock_chat):
        mock_chat.return_value = _reply("Afternoon.")
        other = self._add_other_player()
        self._say("to Mara, hello")

        later = time.time() + OVERHEARD_SECONDS + 1
        with patch("world.overheard.time.time", return_value=later):
            other.execute_cmd("say to Mara, what did you tell Tester?")

        self.assertFalse(any("while this person was nearby" in n for n in self._system_notes(mock_chat)))

    @patch("commands.say.chat")
    def test_npc_reply_is_preceded_by_a_blank_line(self, mock_chat):
        # The reply arrives well after the "You say" echo above it (the
        # model call isn't instant) - project owner's call for a blank
        # line marking where the NPC's reply block starts. The blank
        # line is embedded in the reply's own message text (a leading
        # "\n") rather than sent as a separate caller.msg("") - some
        # clients (confirmed live: Mudlet 5.0.1) don't reliably render
        # a lone empty message as a visible gap, see
        # commands.say._msg_with_lead_blank.
        mock_chat.return_value = _reply("Afternoon.")
        self._say("hello there")

        you_say_index = next(i for i, m in enumerate(self.messages) if "You say" in m)
        reply_msg = self.messages[you_say_index + 1]
        self.assertTrue(reply_msg.startswith("\n"))
        self.assertIn("Afternoon.", reply_msg)

    @patch("commands.say.chat")
    def test_say_capitalizes_and_punctuates_player_speech(self, mock_chat):
        mock_chat.return_value = _reply("Afternoon.")
        self._say("hello there")

        kwargs = self.mock_log_turn.call_args.kwargs
        self.assertEqual(kwargs["player_message"], "Hello there.")

    @patch("commands.say.chat")
    def test_say_broadcasts_asks_for_a_question(self, mock_chat):
        mock_chat.return_value = _reply("Afternoon.")
        self._say("how are you?")

        self.assertTrue(any("You ask" in m and "How are you?" in m for m in self.messages))

    # -- addressing: multiple players -----------------------------------

    @patch("commands.say.chat")
    def test_multiple_players_no_name_is_ambient(self, mock_chat):
        self._add_other_player()
        self._say("hello there")

        mock_chat.assert_not_called()

    @patch("commands.say.chat")
    def test_multiple_players_with_name_mention_addresses_npc(self, mock_chat):
        self._add_other_player()
        mock_chat.return_value = _reply("Hi there!")
        self._say("Mara, how are you?")

        mock_chat.assert_called_once()
        kwargs = self.mock_log_turn.call_args.kwargs
        # The mentioned name is part of the player's actual speech and
        # is not stripped out.
        self.assertEqual(kwargs["player_message"], "Mara, how are you?")

    @patch("commands.say.chat")
    def test_whole_word_match_avoids_false_positive(self, mock_chat):
        self._add_other_player()
        self._say("Maranatha is a word that isn't her name")

        mock_chat.assert_not_called()

    # -- addressing: explicit "say to <name>" ---------------------------

    @patch("commands.say.chat")
    def test_explicit_to_syntax_with_comma_strips_prefix(self, mock_chat):
        self._add_other_player()
        mock_chat.return_value = _reply("Afternoon.")
        self._say("to Mara Voss, hello there")

        kwargs = self.mock_log_turn.call_args.kwargs
        self.assertEqual(kwargs["player_message"], "Hello there.")

    @patch("commands.say.chat")
    def test_explicit_to_syntax_names_addressee_once_not_echoed_in_speech(self, mock_chat):
        # The "to Mara Voss," addressing prefix is command syntax, not
        # something the character actually says - it's stripped from
        # the spoken words, but the broadcast now names the addressee
        # itself in its own grammar ("You say to Mara Voss, ...") so
        # observers can tell which NPC the conversation is with.
        self._add_other_player()
        mock_chat.return_value = _reply("Afternoon.")
        self._say("to Mara Voss, hello there")

        broadcasts = [m for m in self.messages if "You say" in m]
        self.assertTrue(broadcasts)
        self.assertTrue(any("to Mara Voss" in m for m in broadcasts))
        self.assertTrue(any("Hello there." in m for m in broadcasts))
        # Only named once - not also still prefixed onto the quoted speech.
        self.assertTrue(all(m.count("Mara Voss") == 1 for m in broadcasts))

    @patch("commands.say.chat")
    def test_explicit_to_syntax_without_comma_strips_prefix(self, mock_chat):
        self._add_other_player()
        mock_chat.return_value = _reply("Afternoon.")
        self._say("to Mara Voss hello there")

        kwargs = self.mock_log_turn.call_args.kwargs
        self.assertEqual(kwargs["player_message"], "Hello there.")

    @patch("commands.say.chat")
    def test_explicit_to_syntax_with_alias(self, mock_chat):
        self._add_other_player()
        mock_chat.return_value = _reply("Afternoon.")
        self._say("to Mara, hello there")

        kwargs = self.mock_log_turn.call_args.kwargs
        self.assertEqual(kwargs["player_message"], "Hello there.")

    @patch("commands.say.chat")
    def test_explicit_to_syntax_naming_absent_npc_is_ambient(self, mock_chat):
        self._add_other_player()
        self._say("to Tarin, hello there")

        mock_chat.assert_not_called()

    # -- addressing: multiple NPCs in the same room ----------------------

    @patch("commands.say.chat")
    def test_multiple_npcs_present_requires_a_name_even_for_lone_player(self, mock_chat):
        self.tarin.move_to(self.cafe, quiet=True)
        self._say("hello there")

        mock_chat.assert_not_called()

    @patch("commands.say.chat")
    def test_multiple_npcs_present_with_name_resolves_correctly(self, mock_chat):
        self.tarin.move_to(self.cafe, quiet=True)
        mock_chat.return_value = _reply("Hey.")
        self._say("Tarin, got a minute?")

        kwargs = self.mock_log_turn.call_args.kwargs
        self.assertEqual(kwargs["npc_id"], "tarin_os")

    # -- addressing: conversational focus (sticky addressing) -------------

    @patch("commands.say.chat")
    def test_unaddressed_followup_continues_the_same_npc(self, mock_chat):
        self.tarin.move_to(self.cafe, quiet=True)
        mock_chat.return_value = _reply("Hey.")
        self._say("Tarin, got a minute?")
        mock_chat.reset_mock()

        mock_chat.return_value = _reply("Sure, go ahead.")
        self._say("how's the workshop holding up")

        self.assertTrue(mock_chat.called)
        kwargs = self.mock_log_turn.call_args.kwargs
        self.assertEqual(kwargs["npc_id"], "tarin_os")

    @patch("commands.say.chat")
    def test_naming_a_different_npc_switches_focus(self, mock_chat):
        self.tarin.move_to(self.cafe, quiet=True)
        mock_chat.return_value = _reply("Hey.")
        self._say("Tarin, got a minute?")
        mock_chat.reset_mock()

        mock_chat.return_value = _reply("Afternoon.")
        self._say("to Mara, how are you?")

        kwargs = self.mock_log_turn.call_args.kwargs
        self.assertEqual(kwargs["npc_id"], "mara_voss")

    @patch("commands.say.chat")
    def test_focus_does_not_carry_over_to_a_different_room(self, mock_chat):
        self.tarin.move_to(self.cafe, quiet=True)
        mock_chat.return_value = _reply("Hey.")
        self._say("Tarin, got a minute?")
        mock_chat.reset_mock()

        # Civic Office already has two talk-capable NPCs (Iri and
        # Veska) by default - ambiguous on its own, with no focus of
        # its own yet. If focus wrongly carried over from the cafe,
        # this would resolve to Tarin anyway and the bug would go
        # unnoticed. It shouldn't: new room, no standing conversation.
        civic_office = build_rooms()["civic_office"]
        self.actor.move_to(civic_office, quiet=True)
        self._say("how's it going")

        mock_chat.assert_not_called()

    @patch("commands.say.chat")
    def test_no_prior_focus_with_multiple_npcs_still_needs_a_name(self, mock_chat):
        self.tarin.move_to(self.cafe, quiet=True)
        self._say("hello there")

        mock_chat.assert_not_called()
        self.assertTrue(any("more than one" in m.lower() for m in self.messages))

    # -- the rest of the pipeline, unchanged from the old `talk` command --

    @patch("commands.say.chat")
    def test_valid_tool_call_is_applied_and_narrated(self, mock_chat):
        mock_chat.return_value = _reply(
            "Here you go.", tool_calls=[{"name": "serve_drink", "arguments": {"drink_type": "hot"}}]
        )
        self._say("can I get a hot drink")

        self.assertTrue(any("serves" in m and "hot drink" in m for m in self.messages))

    @patch("commands.say.chat")
    def test_invalid_tool_call_is_dropped_silently(self, mock_chat):
        # drink_type outside the enum: validator drops it, no action
        # narration is shown, but the spoken reply still goes through.
        mock_chat.return_value = _reply(
            "Sure thing.", tool_calls=[{"name": "serve_drink", "arguments": {"drink_type": "lukewarm"}}]
        )
        self._say("surprise me")

        self.assertTrue(any("Sure thing" in m for m in self.messages))
        self.assertFalse(any("serves" in m for m in self.messages))

    @patch("commands.say.chat")
    def test_action_not_granted_to_this_npc_is_dropped(self, mock_chat):
        # Mara's persona doesn't grant exchange_module (that's Tarin's) -
        # even if the model proposes it, it must never be applied.
        mock_chat.return_value = _reply("Here.", tool_calls=[{"name": "exchange_module", "arguments": {"confirmed": True}}])
        self._say("swap the module for me?")

        self.assertFalse(any("swapped" in m for m in self.messages))

    @patch("commands.say.chat")
    def test_flagged_reply_is_not_shown_to_player(self, mock_chat):
        mock_chat.return_value = _reply("As an AI, I don't have personal opinions about coffee.")
        self._say("what do you think of this place")

        self.assertFalse(any("As an AI" in m for m in self.messages))
        self.assertTrue(any("loss for words" in m for m in self.messages))
        # history lookup creates the (empty) list but a flagged reply
        # must never be recorded into it
        self.assertEqual(self.mara.ndb.conversations.get(self.actor.dbref), [])

    @patch("commands.say.chat")
    def test_llm_unavailable_falls_back_gracefully(self, mock_chat):
        mock_chat.side_effect = LLMUnavailableError("timed out")
        self._say("hello?")

        self.assertTrue(any("doesn't answer right away" in m for m in self.messages))

    @patch("commands.say.chat")
    def test_empty_text_with_valid_tool_call_shows_only_action(self, mock_chat):
        # The model can propose a tool call with no accompanying text;
        # the action's own narration should speak for itself with no
        # separate (and misleadingly empty) "says" line.
        mock_chat.return_value = _reply(
            "", tool_calls=[{"name": "serve_drink", "arguments": {"drink_type": "hot"}}]
        )
        self._say("hot drink please")

        self.assertFalse(any("Mara Voss says" in m for m in self.messages))
        self.assertTrue(any("serves" in m and "hot drink" in m for m in self.messages))

    @patch("commands.say.chat")
    def test_empty_text_with_no_tool_calls_falls_back(self, mock_chat):
        mock_chat.return_value = _reply("", tool_calls=[])
        self._say("...")

        self.assertTrue(any("doesn't seem to have anything to say" in m for m in self.messages))

    @patch("commands.say.chat")
    def test_emote_shown_as_separate_line_before_dialogue(self, mock_chat):
        mock_chat.return_value = _reply("*smiles and nods* Welcome in.")
        self._say("hello")

        emote_index = next(
            i
            for i, m in enumerate(self.messages)
            if m.lstrip("\n") == "|xMara Voss smiles and nods.|n"
        )
        dialogue_index = next(i for i, m in enumerate(self.messages) if "Mara Voss says" in m)
        self.assertLess(emote_index, dialogue_index)
        self.assertNotIn("*", self.messages[dialogue_index])

    @patch("commands.say.chat")
    def test_dialogue_and_action_both_shown_together(self, mock_chat):
        mock_chat.return_value = _reply(
            "Here you go!", tool_calls=[{"name": "serve_drink", "arguments": {"drink_type": "hot"}}]
        )
        self._say("hot drink please")

        self.assertTrue(any("Here you go" in m for m in self.messages))
        self.assertTrue(any("serves" in m and "hot drink" in m for m in self.messages))

    @patch("commands.say.chat")
    def test_tool_narration_is_preceded_by_a_blank_line(self, mock_chat):
        # When the model gives dialogue *and* a tool call in the same
        # turn, the mechanical narration line needs its own visual
        # separation - otherwise it runs straight into the NPC's own
        # last line and is easy to miss entirely.
        mock_chat.return_value = _reply(
            "Here you go!", tool_calls=[{"name": "serve_drink", "arguments": {"drink_type": "hot"}}]
        )
        self._say("hot drink please")

        narration_msg = next(m for m in self.messages if "serves" in m and "hot drink" in m)
        self.assertTrue(narration_msg.startswith("\n"))

    # -- silent tool calls: the follow-up "react to what you did" call --

    @patch("commands.say.chat")
    def test_silent_tool_call_triggers_a_followup_for_dialogue(self, mock_chat):
        # Reproduces the real-model behavior found in testing: a
        # tool-calling model returns empty text alongside a tool call
        # (the call *is* the whole turn). A second call, reporting the
        # outcome back, should get the NPC talking.
        mock_chat.side_effect = [
            _reply("", tool_calls=[{"id": "call_1", "name": "serve_drink", "arguments": {"drink_type": "hot"}}]),
            _reply("Here you go, careful it's hot."),
        ]
        self._say("hot drink please")

        self.assertEqual(mock_chat.call_count, 2)
        self.assertTrue(any("serves" in m and "hot drink" in m for m in self.messages))
        self.assertTrue(any("Here you go" in m for m in self.messages))

    @patch("commands.say.chat")
    def test_followup_call_reports_the_real_outcome(self, mock_chat):
        # drink_type outside the enum: the validator drops it. The
        # follow-up call must be told it failed, not that it succeeded.
        mock_chat.side_effect = [
            _reply("", tool_calls=[{"id": "call_1", "name": "serve_drink", "arguments": {"drink_type": "lukewarm"}}]),
            _reply("Sorry, we don't have that."),
        ]
        self._say("surprise me")

        followup_messages = mock_chat.call_args_list[1].args[0]
        tool_message = next(m for m in followup_messages if m["role"] == "tool")
        self.assertIn("did not happen", tool_message["content"])

    @patch("commands.say.chat")
    def test_followup_failure_does_not_show_distracted_message(self, mock_chat):
        # The action already happened and was narrated; a failed
        # follow-up call shouldn't make it look like the NPC never
        # responded at all.
        mock_chat.side_effect = [
            _reply("", tool_calls=[{"id": "call_1", "name": "serve_drink", "arguments": {"drink_type": "hot"}}]),
            LLMUnavailableError("timed out"),
        ]
        self._say("hot drink please")

        self.assertTrue(any("serves" in m and "hot drink" in m for m in self.messages))
        self.assertFalse(any("distracted" in m for m in self.messages))

    @patch("commands.say.chat")
    def test_followup_pending_flag_is_cleared_after_resolving(self, mock_chat):
        mock_chat.side_effect = [
            _reply("", tool_calls=[{"id": "call_1", "name": "serve_drink", "arguments": {"drink_type": "hot"}}]),
            _reply("Here you go."),
        ]
        self._say("hot drink please")

        self.assertEqual(self.mara.ndb.pending, set())

    @patch("commands.say.chat")
    def test_player_line_echoes_before_model_call_runs(self, mock_chat):
        # func() must send the player's own line and return *before*
        # kicking off the model call, not after it resolves - that's
        # what keeps a slow model from blocking the whole server and
        # from hiding the player's own input until the reply arrives.
        def slow_chat(*args, **kwargs):
            self.assertTrue(any("You say" in m and "Hi." in m for m in self.messages))
            return _reply("Hello there.")

        mock_chat.side_effect = slow_chat
        self._say("hi")

    @patch("commands.say.chat")
    def test_overlapping_call_is_rejected_not_queued(self, mock_chat):
        # Simulate a reply still in flight for this player/NPC pair -
        # a second `say` before it resolves must not fire a second
        # model call (that piles latency onto an already-slow local
        # model and can return replies out of order).
        self.mara.ndb.pending = {self.actor.dbref}
        self._say("hello again")

        mock_chat.assert_not_called()
        self.assertTrue(any("still thinking" in m for m in self.messages))

    @patch("commands.say.chat")
    def test_pending_flag_is_cleared_after_reply(self, mock_chat):
        mock_chat.return_value = _reply("Afternoon.")
        self._say("hello there")

        self.assertEqual(self.mara.ndb.pending, set())

    @patch("commands.say.chat")
    def test_pending_flag_is_cleared_after_error(self, mock_chat):
        mock_chat.side_effect = LLMUnavailableError("timed out")
        self._say("hello there")

        self.assertEqual(self.mara.ndb.pending, set())

    @patch("commands.say.chat")
    def test_say_with_no_npc_present_is_ordinary_speech(self, mock_chat):
        self.mara.location = None
        self._say("hello, is anyone here?")

        mock_chat.assert_not_called()

    # -- conversation logging (unchanged behavior from `talk`) -----------

    @patch("commands.say.chat")
    def test_ordinary_turn_is_logged(self, mock_chat):
        mock_chat.return_value = _reply("Afternoon.")
        self._say("hello there")

        self.mock_log_turn.assert_called_once()
        kwargs = self.mock_log_turn.call_args.kwargs
        self.assertEqual(kwargs["npc_id"], "mara_voss")
        self.assertEqual(kwargs["player_message"], "Hello there.")
        self.assertEqual(kwargs["npc_response"], "Afternoon.")
        self.assertEqual(kwargs["model"], "test-model")
        self.assertEqual(kwargs["prompt_version"], parse_persona("mara_voss").prompt_version)
        self.assertEqual(kwargs["flagged"], False)
        self.assertEqual(kwargs["tool_calls"], [])
        self.assertIn("prompt_messages", kwargs)
        self.assertTrue(kwargs["conversation_id"])
        self.assertEqual(kwargs["turn_id"], 1)

    @patch("commands.say.chat")
    def test_ordinary_turn_logs_usage_cost_and_latency(self, mock_chat):
        reply = _reply("Afternoon.")
        reply.usage = {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}
        mock_chat.return_value = reply
        self._say("hello there")

        kwargs = self.mock_log_turn.call_args.kwargs
        self.assertEqual(kwargs["usage"], reply.usage)
        self.assertGreater(kwargs["cost_usd"], 0)
        self.assertIsInstance(kwargs["latency_ms"], float)
        self.assertGreaterEqual(kwargs["latency_ms"], 0)

    @patch("commands.say.chat")
    def test_reaction_turn_logs_usage_and_cost_from_both_calls(self, mock_chat):
        first = _reply(
            "", tool_calls=[{"id": "call_1", "name": "serve_drink", "arguments": {"drink_type": "hot"}}]
        )
        first.usage = {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110}
        second = _reply("Here you go, careful it's hot.")
        second.usage = {"prompt_tokens": 150, "completion_tokens": 15, "total_tokens": 165}
        mock_chat.side_effect = [first, second]

        self._say("hot drink please")

        kwargs = self.mock_log_turn.call_args.kwargs
        self.assertEqual(
            kwargs["usage"],
            {"prompt_tokens": 250, "completion_tokens": 25, "total_tokens": 275},
        )
        self.assertGreater(kwargs["cost_usd"], 0)

    @patch("commands.say.chat")
    def test_reaction_error_turn_logs_only_the_first_calls_usage(self, mock_chat):
        first = _reply(
            "", tool_calls=[{"id": "call_1", "name": "serve_drink", "arguments": {"drink_type": "hot"}}]
        )
        first.usage = {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110}
        mock_chat.side_effect = [first, LLMUnavailableError("timed out")]

        self._say("hot drink please")

        kwargs = self.mock_log_turn.call_args.kwargs
        self.assertEqual(kwargs["usage"], first.usage)
        self.assertGreater(kwargs["cost_usd"], 0)

    @patch("commands.say.chat")
    def test_llm_unavailable_turn_logs_no_usage_and_zero_cost(self, mock_chat):
        mock_chat.side_effect = LLMUnavailableError("timed out")
        self._say("hello?")

        kwargs = self.mock_log_turn.call_args.kwargs
        self.assertIsNone(kwargs["usage"])
        self.assertEqual(kwargs["cost_usd"], 0.0)
        self.assertIsInstance(kwargs["latency_ms"], float)

    @patch("commands.say.chat")
    def test_tool_call_outcomes_are_logged(self, mock_chat):
        mock_chat.return_value = _reply(
            "Here you go!", tool_calls=[{"name": "serve_drink", "arguments": {"drink_type": "hot"}}]
        )
        self._say("hot drink please")

        kwargs = self.mock_log_turn.call_args.kwargs
        self.assertEqual(
            kwargs["tool_calls"],
            [{"name": "serve_drink", "arguments": {"drink_type": "hot"}, "applied": True, "reason": ""}],
        )

    @patch("commands.say.chat")
    def test_dropped_tool_call_outcome_is_logged(self, mock_chat):
        mock_chat.return_value = _reply(
            "Sure.", tool_calls=[{"name": "serve_drink", "arguments": {"drink_type": "lukewarm"}}]
        )
        self._say("surprise me")

        kwargs = self.mock_log_turn.call_args.kwargs
        self.assertEqual(len(kwargs["tool_calls"]), 1)
        self.assertFalse(kwargs["tool_calls"][0]["applied"])
        self.assertTrue(kwargs["tool_calls"][0]["reason"])

    @patch("commands.say.chat")
    def test_flagged_turn_is_logged_with_reason(self, mock_chat):
        mock_chat.return_value = _reply("As an AI, I don't have personal opinions.")
        self._say("what do you think")

        kwargs = self.mock_log_turn.call_args.kwargs
        self.assertTrue(kwargs["flagged"])
        self.assertTrue(kwargs["flag_reason"])
        self.assertEqual(kwargs["npc_response"], "As an AI, I don't have personal opinions.")

    @patch("commands.say.chat")
    def test_llm_unavailable_turn_is_logged(self, mock_chat):
        mock_chat.side_effect = LLMUnavailableError("timed out")
        self._say("hello?")

        self.mock_log_turn.assert_called_once()
        kwargs = self.mock_log_turn.call_args.kwargs
        self.assertIsNone(kwargs["npc_response"])
        self.assertTrue(kwargs["flag_reason"].startswith("llm_unavailable"))
        self.assertIn("timed out", kwargs["flag_reason"])

    # -- module-exchange quest state (revived as Quest 1, 2026-10-14) -----
    # Mara's and Tarin's personas grant the heating-module actions again
    # (docs/prospect-initial-playtest-design-spec.md §6, Quest 1), so
    # quest_context_for has something to inject for Mara once more.

    @patch("commands.say.chat")
    def test_quest_context_injected_for_mara(self, mock_chat):
        mock_chat.return_value = _reply("Afternoon.")
        self._say("hello there")

        messages = mock_chat.call_args.args[0]
        self.assertTrue(
            any("heating-unit module errand" in m.get("content", "") for m in messages)
        )

    @patch("commands.say.chat")
    def test_quest_context_not_injected_for_npc_without_quest_actions(self, mock_chat):
        iri = build_npcs()["iri_vael"]
        self.actor.move_to(iri.location, quiet=True)
        mock_chat.return_value = _reply("Hello.")
        # Civic Office now also has Veska (phase 2B) - address Iri
        # explicitly rather than relying on implicit lone-NPC addressing.
        self._say("to Iri, hello there")

        messages = mock_chat.call_args.args[0]
        self.assertFalse(
            any("heating-unit module errand" in m.get("content", "") for m in messages)
        )

    # -- per-player NPC memory --------------------------------------------

    @patch("commands.say.chat")
    def test_remembered_fact_is_injected_on_a_later_turn(self, mock_chat):
        mock_chat.return_value = _reply(
            "Noted.", tool_calls=[{"name": "remember_fact", "arguments": {"fact": "grew up near the Docks", "player_words": "I grew up near the Docks"}}]
        )
        self._say("I grew up near the Docks, actually.")
        mock_chat.reset_mock()

        mock_chat.return_value = _reply("Good to see you again.")
        self._say("hey there")

        messages = mock_chat.call_args.args[0]
        self.assertTrue(any("grew up near the Docks" in m.get("content", "") for m in messages))

    @patch("commands.say.chat")
    def test_player_appearance_reaches_the_prompt(self, mock_chat):
        # PF-0004 follow-up: NPCs see the player's species and their own
        # short description, labelled as written by the player.
        self.actor.db.species = "Kell"
        self.actor.db.sex = "female"
        self.actor.db.desc = "tall and rangy"
        mock_chat.return_value = _reply("Afternoon.")
        self._say("hello there")

        contents = [m.get("content") or "" for m in mock_chat.call_args.args[0]]
        self.assertTrue(any("What you can see of the player: a Kell woman." in c for c in contents))
        self.assertTrue(any('"tall and rangy"' in c and "The player wrote" in c for c in contents))

    @patch("commands.say.chat")
    def test_no_memory_context_when_nothing_remembered(self, mock_chat):
        mock_chat.return_value = _reply("Afternoon.")
        self._say("hello there")

        messages = mock_chat.call_args.args[0]
        self.assertFalse(any("no way to verify" in m.get("content", "") for m in messages))

    @patch("commands.say.chat")
    def test_memory_debug_off_shows_nothing(self, mock_chat):
        mock_chat.return_value = _reply(
            "Noted.", tool_calls=[{"name": "remember_fact", "arguments": {"fact": "grew up near the Docks", "player_words": "I grew up near the Docks"}}]
        )
        self._say("I grew up near the Docks, actually.")

        self.assertFalse(any("[memory]" in m for m in self.messages))

    @patch("commands.say.chat")
    def test_memory_debug_on_shows_the_fact(self, mock_chat):
        self.actor.attributes.add("memory_debug_enabled", True)
        mock_chat.return_value = _reply(
            "Noted.", tool_calls=[{"name": "remember_fact", "arguments": {"fact": "grew up near the Docks", "player_words": "I grew up near the Docks"}}]
        )
        self._say("I grew up near the Docks, actually.")

        self.assertTrue(any("[memory]" in m and "grew up near the Docks" in m for m in self.messages))

    @patch("commands.say.chat")
    def test_hallucinated_action_outside_npcs_grant_is_dropped_not_applied(self, mock_chat):
        # exchange_module is Tarin's action, not Mara's - if the model
        # ever hallucinates the call on the wrong NPC, it must be
        # rejected as not-permitted, not silently honored.
        mock_chat.return_value = _reply(
            "Let me swap that for you.", tool_calls=[{"name": "exchange_module", "arguments": {}}]
        )
        self._say("want me to take that module to Tarin?")

        self.assertEqual(get_quest_state(self.actor), "not_started")
        kwargs = self.mock_log_turn.call_args.kwargs
        self.assertFalse(kwargs["tool_calls"][0]["applied"])
        self.assertIn("not a permitted action", kwargs["tool_calls"][0]["reason"])

    @patch("commands.say.chat")
    def test_mara_asking_and_accepting_in_one_reply_only_records_the_ask(self, mock_chat):
        # PF-0011: she asked "would you?" and called accept_help in the
        # same reply, so a player who then said no had agreed anyway.
        mock_chat.side_effect = [
            _reply(
                "It's the module. You wouldn't be up for taking it to Tarin, would you?",
                tool_calls=[
                    {"name": "ask_for_help", "arguments": {"confirmed": True}},
                    {"name": "accept_help", "arguments": {"confirmed": True}},
                ],
            ),
            _reply("You wouldn't be up for taking it over to Tarin, would you?"),
        ]
        self._say("Man it's cold in here.")

        self.assertEqual(get_quest_state(self.actor), "offered")
        calls = self.mock_log_turn.call_args.kwargs["tool_calls"]
        self.assertEqual([c["applied"] for c in calls], [True, False])
        self.assertIn("haven't answered yet", calls[1]["reason"])

    @patch("commands.say.chat")
    def test_an_unrecorded_ask_is_recorded_by_the_reaction_and_the_next_yes_lands(self, mock_chat):
        # Live 2026-10-18 (Mara prompt_version 52): she asked only in
        # words, so "Sure." was dropped at 'not_started'; her reaction
        # asked again, but with no tools that ask wasn't recorded either,
        # so "Yes." was dropped too.
        accept_and_hand_over = [
            {"name": "accept_help", "arguments": {"confirmed": True}},
            {"name": "give_faulty_module", "arguments": {"confirmed": True}},
        ]
        mock_chat.side_effect = [
            _reply("Glad to hear it.", tool_calls=accept_and_hand_over),
            # A reaction that calls a tool comes back with no words
            # (live-prompt replay, 8/8), so one more call voices it.
            _reply("", tool_calls=[{"name": "ask_for_help", "arguments": {"confirmed": True}}]),
            _reply("Would you be up for taking it to Tarin?"),
            _reply("Here's the module.", tool_calls=accept_and_hand_over),
            _reply("Tarin's at the workshop."),
        ]
        self._say("Sure.")

        reaction_kwargs = mock_chat.call_args_list[1].kwargs
        self.assertEqual([t["function"]["name"] for t in reaction_kwargs["tools"]], ["ask_for_help"])
        self.assertNotIn("tools", mock_chat.call_args_list[2].kwargs)
        self.assertTrue(any("Would you be up for taking it to Tarin?" in m for m in self.messages))
        self.assertFalse(any("Glad to hear it." in m for m in self.messages))
        self.mock_log_turn.assert_called_once()
        self.assertEqual(
            self.mock_log_turn.call_args.kwargs["npc_response"], "Would you be up for taking it to Tarin?"
        )
        self.assertEqual(get_quest_state(self.actor), "offered")
        calls = self.mock_log_turn.call_args.kwargs["tool_calls"]
        self.assertEqual(calls[-1]["name"], "ask_for_help")
        self.assertTrue(calls[-1]["applied"])
        self.assertTrue(calls[-1]["in_reaction"])
        history = self.mara.ndb.conversations[self.actor.dbref]
        recorded = [c["function"]["name"] for m in history for c in m.get("tool_calls") or []]
        self.assertIn("ask_for_help", recorded)
        ask_outcome = next(
            m["content"] for m in history if m["role"] == "tool" and "asks Tester" in m["content"]
        )
        self.assertIn("The action happened", ask_outcome)

        self._say("Yes.")

        self.assertEqual(get_quest_state(self.actor), "has_faulty_module")
        self.assertTrue(any("Tarin's at the workshop." in m for m in self.messages))

    @patch("commands.say.chat")
    def test_an_accept_without_the_hand_over_lets_the_reaction_hand_it_over(self, mock_chat):
        # Live 2026-10-18 (v52): "Umm... Okay." got accept_help alone, and
        # the reaction said "Here's the faulty module" with nothing handed over.
        self.actor.attributes.add("quest_module_exchange", "offered")
        mock_chat.side_effect = [
            _reply("", tool_calls=[{"name": "accept_help", "arguments": {"confirmed": True}}]),
            _reply("", tool_calls=[{"name": "give_faulty_module", "arguments": {"confirmed": True}}]),
            _reply("Here's the faulty module. Tarin's the one to see."),
        ]
        self._say("Umm... Okay.")

        reaction_tools = mock_chat.call_args_list[1].kwargs["tools"]
        self.assertEqual([t["function"]["name"] for t in reaction_tools], ["give_faulty_module"])
        self.assertEqual(get_quest_state(self.actor), "has_faulty_module")
        self.assertTrue(any("Here's the faulty module." in m for m in self.messages))

    @patch("commands.say.chat")
    def test_the_reaction_gets_no_tools_when_nothing_needs_retrying(self, mock_chat):
        mock_chat.side_effect = [
            _reply(
                "Sure, I'll point you there.",
                tool_calls=[{"name": "give_directions", "arguments": {"destination": "Maintenance Workshop"}}],
            ),
            _reply("Head out and you'll find it."),
        ]
        self._say("How do I get to the workshop?")

        self.assertIsNone(mock_chat.call_args_list[1].kwargs["tools"])

    @patch("commands.say.chat")
    def test_a_shown_and_recorded_ask_gets_no_reaction_or_engine_line(self, mock_chat):
        # Live 2026-10-18: after her shown ask, the reaction read the
        # recorded ask as a yes ("I'm glad you're up for it"), under an
        # engine line repeating what she'd just said.
        mock_chat.return_value = _reply(
            "Would you take the module over to Tarin for me?",
            tool_calls=[{"name": "ask_for_help", "arguments": {"confirmed": True}}],
        )
        self._say("Man it's cold in here.")

        self.assertEqual(mock_chat.call_count, 1)
        self.assertEqual(get_quest_state(self.actor), "offered")
        self.assertTrue(any("Would you take the module over to Tarin" in m for m in self.messages))
        self.assertFalse(any("explains the heating unit" in m for m in self.messages))
        history = self.mara.ndb.conversations[self.actor.dbref]
        self.assertEqual(history[-1]["role"], "tool")

    @patch("commands.say.chat")
    def test_a_reaction_call_it_wasnt_offered_is_dropped(self, mock_chat):
        mock_chat.side_effect = [
            _reply("Glad to hear it.", tool_calls=[{"name": "accept_help", "arguments": {"confirmed": True}}]),
            _reply(
                "Here, take it.",
                tool_calls=[{"name": "give_faulty_module", "arguments": {"confirmed": True}}],
            ),
        ]
        self._say("Sure.")

        self.assertEqual(get_quest_state(self.actor), "not_started")
        calls = self.mock_log_turn.call_args.kwargs["tool_calls"]
        self.assertFalse(calls[-1]["applied"])
        self.assertIn("wasn't available", calls[-1]["reason"])

    # -- reaction-triggering turns (FORCE_REACTION_ACTIONS) ---------------

    @patch("commands.say.chat")
    def test_reaction_turn_logs_both_the_original_and_reaction_text(self, mock_chat):
        # propose_commitment is in FORCE_REACTION_ACTIONS, so this
        # always makes a second model call to react to the applied
        # result - the original turn's own text (what the player
        # actually saw first) was previously never logged at all; only
        # the reaction's text landed in npc_response, under the
        # original turn's tool_calls - a mismatch between the two.
        mock_chat.side_effect = [
            _reply(
                "Actually, I've got a parcel for Tarin.",
                tool_calls=[{"name": "propose_commitment", "arguments": {"commitment_type": "deliver_parcel"}}],
            ),
            _reply("Could use a hand getting it to him, if you're headed that way."),
        ]
        self._say("anything I can help with today?")

        self.assertEqual(mock_chat.call_count, 2)
        self.mock_log_turn.assert_called_once()
        kwargs = self.mock_log_turn.call_args.kwargs
        self.assertEqual(kwargs["initial_response"], "Actually, I've got a parcel for Tarin.")
        self.assertEqual(kwargs["npc_response"], "Could use a hand getting it to him, if you're headed that way.")
        self.assertEqual(kwargs["tool_calls"][0]["name"], "propose_commitment")

    @patch("commands.say.chat")
    def test_reaction_turn_never_shows_the_player_the_pre_validation_text(self, mock_chat):
        # Confirmed live 2026-10-14 (phase 3 notice scenario): Tarin
        # blurted out a detail about the notice on a plain "how's
        # work?" - propose_commitment's own first-pass text - and then
        # visibly backtracked once the call was actually rejected for
        # an unmet prerequisite. That happened because this first-pass
        # text used to be rendered to the player unconditionally
        # (_render_reply_segments at the top of this function), before
        # validate_and_apply even ran - defeating the whole point of
        # FORCE_REACTION_ACTIONS, whose own comment already says the
        # reaction's text is meant to be "the final thing the player
        # reads". It must never reach the player when a call is
        # rejected (when every call applies it's shown - next test).
        self.actor.location = self.workshop
        mock_chat.side_effect = [
            _reply(
                "There's a parcel I'm not supposed to mention yet.",
                tool_calls=[{"name": "propose_commitment", "arguments": {"commitment_type": "deliver_parcel"}}],
            ),
            _reply("Let me rephrase - never mind, forget I said anything."),
        ]
        self._say("how's work?")

        # Tarin isn't the parcel's proposer, so the call is rejected.
        self.assertFalse(self.mock_log_turn.call_args.kwargs["tool_calls"][0]["applied"])
        self.assertFalse(any("parcel I'm not supposed to mention yet" in m for m in self.messages))
        self.assertTrue(any("forget I said anything" in m for m in self.messages))
        followup = mock_chat.call_args_list[1].args[0]
        self.assertEqual(followup[-1]["content"], FIRST_PASS_HIDDEN_NOTE)

    @patch("commands.say.chat")
    def test_applied_reaction_turn_shows_the_first_pass_then_the_reaction(self, mock_chat):
        # PF-0001 (playtest 2026-10-17): with every call applied the
        # first-pass text is true, and the reaction is written as its
        # continuation - hiding it replaced Daven's suggestions with a
        # bare route and Veska's answer with a bare offer.
        mock_chat.side_effect = [
            _reply(
                "You could start at the square, or the Civic Office.",
                tool_calls=[{"name": "give_directions", "arguments": {"destination": "Old Quarter Square"}}],
            ),
            _reply("Head south, and you're there."),
        ]
        self._say("I don't know what to do.")

        self.assertTrue(self.mock_log_turn.call_args.kwargs["tool_calls"][0]["applied"])
        first = next(i for i, m in enumerate(self.messages) if "start at the square" in m)
        second = next(i for i, m in enumerate(self.messages) if "Head south" in m)
        self.assertLess(first, second)
        followup = mock_chat.call_args_list[1].args[0]
        self.assertEqual(followup[-1]["content"], FIRST_PASS_SHOWN_NOTE)

    @patch("commands.say.chat")
    def test_report_parcel_delivery_forces_reaction_on_rejection(self, mock_chat):
        # docs/phase2e-word-gets-around-design.md: confirmed live
        # 2026-10-14 - without this, a rejected report_parcel_delivery
        # call (e.g. no fulfilled commitment on record yet) left the
        # model's own same-turn text as the final thing the player
        # read, and that text had already thanked them as if the
        # report succeeded. Adding this action to FORCE_REACTION_ACTIONS
        # gives the model a second pass against the real (rejected)
        # result, the same fix already in place for
        # report_commitment_outcome/verify_revision_report.
        mock_chat.side_effect = [
            _reply(
                "Thanks for letting me know it got to Tarin. That's a weight off my mind.",
                tool_calls=[{"name": "report_parcel_delivery", "arguments": {"confirmed": True}}],
            ),
            _reply("I can't confirm that yet - there's no record of it being handed off."),
        ]
        self._say("Good news, the package has been delivered to Tarin.")

        self.assertEqual(mock_chat.call_count, 2)
        kwargs = self.mock_log_turn.call_args.kwargs
        self.assertEqual(
            kwargs["npc_response"], "I can't confirm that yet - there's no record of it being handed off."
        )
        self.assertFalse(kwargs["tool_calls"][0]["applied"])

    @patch("commands.say.chat")
    def test_report_notice_outcome_forces_reaction_on_rejection(self, mock_chat):
        # docs/phase3-unverified-notice-design.md: the same fix as
        # report_parcel_delivery above, for a different action with
        # the same rejectable-precondition shape - without this, a
        # rejected report_notice_outcome call (nothing fulfilled on
        # record yet) would leave the model's own same-turn text as
        # the final thing the player reads, even though it already
        # thanked them as if the report succeeded.
        self.actor.location = self.workshop
        mock_chat.side_effect = [
            _reply(
                "Relieved to hear it checked out and stayed up.",
                tool_calls=[{"name": "report_notice_outcome", "arguments": {"reported_resolution": "verified"}}],
            ),
            _reply("Actually, I haven't heard anything about it yet - don't think that's settled."),
        ]
        self._say("Veska checked the notice, it's staying up.")

        self.assertEqual(mock_chat.call_count, 2)
        kwargs = self.mock_log_turn.call_args.kwargs
        self.assertEqual(
            kwargs["npc_response"],
            "Actually, I haven't heard anything about it yet - don't think that's settled.",
        )
        self.assertFalse(kwargs["tool_calls"][0]["applied"])

    @patch("commands.say.chat")
    def test_non_reaction_turn_leaves_initial_response_unset(self, mock_chat):
        # No FORCE_REACTION_ACTIONS tool call and real dialogue text -
        # only one model call happens, so there's no separate initial
        # vs. reaction text to distinguish.
        mock_chat.return_value = _reply(
            "Here you go.", tool_calls=[{"name": "serve_drink", "arguments": {"drink_type": "hot"}}]
        )
        self._say("hot drink please")

        self.assertEqual(mock_chat.call_count, 1)
        kwargs = self.mock_log_turn.call_args.kwargs
        # Not passed at all on this path (log_turn's own default
        # applies) - not asserting a literal None, since the mock only
        # records what was actually passed.
        self.assertIsNone(kwargs.get("initial_response"))
        self.assertEqual(kwargs["npc_response"], "Here you go.")

    @patch("commands.say.chat")
    def test_reaction_error_still_logs_the_original_text(self, mock_chat):
        mock_chat.side_effect = [
            _reply(
                "Here's an offer.",
                tool_calls=[{"name": "propose_commitment", "arguments": {"commitment_type": "deliver_parcel"}}],
            ),
            LLMUnavailableError("timed out"),
        ]
        self._say("anything I can help with today?")

        kwargs = self.mock_log_turn.call_args.kwargs
        self.assertEqual(kwargs["initial_response"], "Here's an offer.")
        self.assertIsNone(kwargs["npc_response"])
        self.assertTrue(kwargs["flag_reason"].startswith("llm_unavailable"))

    @patch("commands.say.chat")
    def test_turn_id_increments_within_same_conversation(self, mock_chat):
        mock_chat.return_value = _reply("Afternoon.")
        self._say("hi")
        self._say("hi again")

        first_kwargs = self.mock_log_turn.call_args_list[0].kwargs
        second_kwargs = self.mock_log_turn.call_args_list[1].kwargs
        self.assertEqual(first_kwargs["turn_id"], 1)
        self.assertEqual(second_kwargs["turn_id"], 2)
        self.assertEqual(first_kwargs["conversation_id"], second_kwargs["conversation_id"])


class CostSafeguardTests(_SayTestBase):
    """
    The pre-model-call gates added for game-plan.md 6.2: input length
    cap, per-player cooldown, same-message dedup, and the token
    budgets. Each test overrides LLM_COOLDOWN_SECONDS back to whatever
    it actually needs to exercise, since the base class default of 0
    would otherwise mask the cooldown gate entirely.
    """

    @override_settings(LLM_MAX_INPUT_CHARS=10)
    @patch("commands.say.chat")
    def test_message_over_the_length_cap_skips_the_model_call(self, mock_chat):
        self._say("this message is definitely longer than ten characters")

        mock_chat.assert_not_called()
        self.assertTrue(any("too much" in m.lower() for m in self.messages))

    @override_settings(LLM_MAX_INPUT_CHARS=10)
    @patch("commands.say.chat")
    def test_message_within_the_length_cap_still_goes_through(self, mock_chat):
        mock_chat.return_value = _reply("Hi!")
        self._say("hi there")

        mock_chat.assert_called_once()

    @override_settings(LLM_COOLDOWN_SECONDS=100)
    @patch("commands.say.chat")
    def test_second_call_within_the_cooldown_is_rejected(self, mock_chat):
        mock_chat.return_value = _reply("Afternoon.")
        self._say("hello there")
        mock_chat.reset_mock()

        self._say("how are you")

        mock_chat.assert_not_called()
        self.assertTrue(any("a moment" in m.lower() for m in self.messages))

    @override_settings(LLM_COOLDOWN_SECONDS=100)
    @patch("commands.say.chat")
    def test_cooldown_is_not_per_npc_but_global_to_the_player(self, mock_chat):
        # A player can't dodge the cooldown by pestering a different
        # NPC instead - the whole point is limiting how often this
        # player triggers *any* model call.
        self.tarin.move_to(self.cafe, quiet=True)
        mock_chat.return_value = _reply("Afternoon.")
        self._say("to Mara, hello there")
        mock_chat.reset_mock()

        self._say("to Tarin, got a minute?")

        mock_chat.assert_not_called()

    @override_settings(LLM_COOLDOWN_SECONDS=4)
    @patch("commands.say.time")
    @patch("commands.say.chat")
    def test_call_after_the_cooldown_elapses_is_allowed(self, mock_chat, mock_time):
        # A plain growing sequence rather than a fixed-length list -
        # _handle_llm_reply also calls time.time() now (for
        # latency_ms), and pinning an exact call count here would
        # make this test break again on the next unrelated timing
        # read added anywhere in the chain.
        mock_time.time.side_effect = (1000.0 + i * 10 for i in range(100))
        mock_chat.return_value = _reply("Afternoon.")
        self._say("hello there")
        mock_chat.reset_mock()

        mock_chat.return_value = _reply("Doing well.")
        self._say("how are you")

        mock_chat.assert_called_once()

    @patch("commands.say.chat")
    def test_identical_message_to_the_same_npc_is_rejected(self, mock_chat):
        mock_chat.return_value = _reply("Afternoon.")
        self._say("hello there")
        mock_chat.reset_mock()

        self._say("hello there")

        mock_chat.assert_not_called()
        self.assertTrue(any("already" in m.lower() for m in self.messages))

    @patch("commands.say.chat")
    def test_different_message_after_a_duplicate_still_goes_through(self, mock_chat):
        mock_chat.return_value = _reply("Afternoon.")
        self._say("hello there")
        mock_chat.reset_mock()

        mock_chat.return_value = _reply("Doing well.")
        self._say("how are you")

        mock_chat.assert_called_once()

    @patch("commands.say.player_over_budget", return_value=True)
    @patch("commands.say.chat")
    def test_player_over_budget_skips_the_model_call(self, mock_chat, mock_over_budget):
        self._say("hello there")

        mock_chat.assert_not_called()
        self.assertTrue(any("another day" in m.lower() for m in self.messages))

    @patch("commands.say.global_daily_limit_reached", return_value=True)
    @patch("commands.say.chat")
    def test_global_spend_limit_skips_the_model_call(self, mock_chat, mock_limit_reached):
        self._say("hello there")

        mock_chat.assert_not_called()
        self.assertTrue(any("too busy" in m.lower() for m in self.messages))

    @patch("commands.say.chat")
    def test_usage_is_recorded_against_the_player_and_global_totals(self, mock_chat):
        mock_chat.return_value = _reply("Afternoon.")
        mock_chat.return_value.usage = {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
        }

        self._say("hello there")

        self.assertAlmostEqual(self.actor.db.llm_spend_today_usd, call_cost_usd(mock_chat.return_value.usage))

    @patch("commands.say.chat")
    def test_duplicate_check_is_scoped_per_npc(self, mock_chat):
        # Unlike the cooldown gate above, saying the exact same line to
        # a *different* NPC right after is a legitimate new question,
        # not a duplicate. Both use the explicit "to <name>," form so
        # the addressing prefix is stripped the same way on both calls
        # and the NPC actually hears the identical remainder text.
        self.tarin.move_to(self.cafe, quiet=True)
        mock_chat.return_value = _reply("Hey.")
        self._say("to Tarin, got a minute?")
        mock_chat.reset_mock()

        mock_chat.return_value = _reply("Afternoon.")
        self._say("to Mara, got a minute?")

        mock_chat.assert_called_once()


class SkitterLogTests(_SayTestBase):
    """
    The post-quest skitter loop through the real say pipeline: Iri gets
    the logged total as per-turn context, and log_dead_skitters_with_iri
    is a FORCE_REACTION action, so a rejected log never shows the
    player the first-pass text written before the engine decided
    (docs/engineering-pitfalls.md #8).
    """

    def setUp(self):
        super().setUp()
        npcs = build_npcs()
        self.iri = npcs["iri_vael"]
        civic_office = build_rooms()["civic_office"]
        self.actor.move_to(civic_office, quiet=True)

    def _finish_hunt(self):
        from world.commitments import accept_commitment, fulfill_commitment_with_precondition, propose_commitment
        from world.skitters import record_kill

        propose_commitment(self.actor, "hunt_skitters")
        accept_commitment(self.actor, "hunt_skitters")
        for _ in range(3):
            record_kill(self.actor)
        fulfill_commitment_with_precondition(self.actor, "hunt_skitters", "tarin_os", True)

    @patch("commands.say.chat")
    def test_iri_gets_the_logged_total_as_context(self, mock_chat):
        from world.skitters import bank_kills

        self._finish_hunt()
        bank_kills(self.actor)
        mock_chat.return_value = _reply("Hello!")
        self._say("to Iri, hi")

        messages = mock_chat.call_args.args[0]
        self.assertTrue(any("3 skitters logged" in m.get("content", "") for m in messages))

    @patch("commands.say.chat")
    def test_rejected_log_never_shows_the_first_pass_text(self, mock_chat):
        # Nothing new to log: the first-pass text claims a success the
        # engine then denies. Only the reaction may reach the player.
        from world.skitters import bank_kills

        self._finish_hunt()
        bank_kills(self.actor)
        mock_chat.side_effect = [
            _reply(
                "Great, I've logged five more for you!",
                tool_calls=[{"id": "call_1", "name": "log_dead_skitters_with_iri", "arguments": {"confirmed": True}}],
            ),
            _reply("Hm, nothing new on record since last time."),
        ]
        self._say("to Iri, I killed some more skitters")

        self.assertFalse(any("logged five more" in m for m in self.messages))
        self.assertTrue(any("nothing new on record" in m for m in self.messages))

    @patch("commands.say.chat")
    def test_successful_log_banks_the_kills(self, mock_chat):
        from world.skitters import banked_kills_for

        self._finish_hunt()
        mock_chat.side_effect = [
            _reply(
                "",
                tool_calls=[{"id": "call_1", "name": "log_dead_skitters_with_iri", "arguments": {"confirmed": True}}],
            ),
            _reply("Three, all logged."),
        ]
        self._say("to Iri, put me down for some skitter kills")

        self.assertEqual(banked_kills_for(self.actor), 3)
        self.assertTrue(any("Total on record: 3" in m for m in self.messages))
