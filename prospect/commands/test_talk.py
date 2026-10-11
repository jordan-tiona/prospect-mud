"""
Integration tests for the `talk` command's full pipeline (step 7):
prompt builder -> LLM client -> tool validator -> output check ->
narrated reply.

The LLM call itself is mocked (world.llm_client.chat) so these run
fast and deterministically, without a live Ollama server. The manual
smoke test in world/test_llm_connection.py remains the way to confirm
actual model connectivity.

talk.py runs the model call via deferToThread so a slow model never
blocks the whole server. These tests replace deferToThread with a
version that runs synchronously (using a real, already-fired Twisted
Deferred - defer.succeed/defer.fail - so the exact same callback/
errback chain in talk.py runs, just without needing a live reactor).

Run with:
    evennia test commands
"""

from unittest.mock import patch

from django.test import TestCase
from evennia import create_object
from twisted.internet import defer

from world.build_npcs import build as build_npcs
from world.build_rooms import build as build_rooms
from world.llm_client import LLMReply, LLMUnavailableError


def _reply(text, tool_calls=None):
    return LLMReply(text=text, model="test-model", raw={}, tool_calls=tool_calls or [])


def _sync_defer_to_thread(fn, *args, **kwargs):
    try:
        result = fn(*args, **kwargs)
    except Exception as err:  # noqa: BLE001 - mirrors deferToThread's own behavior
        return defer.fail(err)
    return defer.succeed(result)


class TalkCommandTests(TestCase):
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
        self.actor.msg = lambda text="", **kw: self.messages.append(text)
        self.messages = []

        defer_patcher = patch("commands.talk.deferToThread", side_effect=_sync_defer_to_thread)
        defer_patcher.start()
        self.addCleanup(defer_patcher.stop)

        # Logging is covered by its own tests against the real
        # function (world/test_conversation_log.py); here we just
        # need it not to hit the filesystem.
        log_patcher = patch("commands.talk.log_turn")
        self.mock_log_turn = log_patcher.start()
        self.addCleanup(log_patcher.stop)

    def _talk(self, target_name, message):
        self.actor.execute_cmd(f"talk {target_name} = {message}")

    @patch("commands.talk.chat")
    def test_ordinary_reply_shown_and_recorded_in_history(self, mock_chat):
        mock_chat.return_value = _reply('Afternoon. What can I get you?')
        self._talk("Mara Voss", "hello there")

        self.assertTrue(any("Mara Voss says" in m for m in self.messages))
        self.assertTrue(any("Afternoon" in m for m in self.messages))

        history = self.mara.ndb.conversations[self.actor.dbref]
        self.assertEqual(len(history), 2)
        self.assertIn("hello there", history[0]["content"])
        self.assertEqual(history[1]["content"], "Afternoon. What can I get you?")

    @patch("commands.talk.chat")
    def test_valid_tool_call_is_applied_and_narrated(self, mock_chat):
        mock_chat.return_value = _reply(
            "Here you go.", tool_calls=[{"name": "serve_drink", "arguments": {"drink_type": "hot"}}]
        )
        self._talk("Mara Voss", "can I get a hot drink")

        self.assertTrue(any("serves" in m and "hot drink" in m for m in self.messages))

    @patch("commands.talk.chat")
    def test_invalid_tool_call_is_dropped_silently(self, mock_chat):
        # drink_type outside the enum: validator drops it, no action
        # narration is shown, but the spoken reply still goes through.
        mock_chat.return_value = _reply(
            "Sure thing.", tool_calls=[{"name": "serve_drink", "arguments": {"drink_type": "lukewarm"}}]
        )
        self._talk("Mara Voss", "surprise me")

        self.assertTrue(any("Sure thing" in m for m in self.messages))
        self.assertFalse(any("serves" in m for m in self.messages))

    @patch("commands.talk.chat")
    def test_action_not_granted_to_this_npc_is_dropped(self, mock_chat):
        # Mara's persona doesn't grant hand_over_item - even if the
        # model proposes it, it must never be applied.
        mock_chat.return_value = _reply(
            "Here.", tool_calls=[{"name": "hand_over_item", "arguments": {"item_type": "spare part"}}]
        )
        self._talk("Mara Voss", "got any spare parts?")

        self.assertFalse(any("hands" in m for m in self.messages))

    @patch("commands.talk.chat")
    def test_flagged_reply_is_not_shown_to_player(self, mock_chat):
        mock_chat.return_value = _reply("As an AI, I don't have personal opinions about coffee.")
        self._talk("Mara Voss", "what do you think of this place")

        self.assertFalse(any("As an AI" in m for m in self.messages))
        self.assertTrue(any("loss for words" in m for m in self.messages))
        # history lookup creates the (empty) list but a flagged reply
        # must never be recorded into it
        self.assertEqual(self.mara.ndb.conversations.get(self.actor.dbref), [])

    @patch("commands.talk.chat")
    def test_llm_unavailable_falls_back_gracefully(self, mock_chat):
        mock_chat.side_effect = LLMUnavailableError("timed out")
        self._talk("Mara Voss", "hello?")

        self.assertTrue(any("doesn't answer right away" in m for m in self.messages))

    @patch("commands.talk.chat")
    def test_empty_text_with_valid_tool_call_shows_only_action(self, mock_chat):
        # The model can propose a tool call with no accompanying text;
        # the action's own narration should speak for itself with no
        # separate (and misleadingly empty) "says" line.
        mock_chat.return_value = _reply(
            "", tool_calls=[{"name": "serve_drink", "arguments": {"drink_type": "hot"}}]
        )
        self._talk("Mara Voss", "hot drink please")

        self.assertFalse(any("says" in m for m in self.messages))
        self.assertTrue(any("serves" in m and "hot drink" in m for m in self.messages))

    @patch("commands.talk.chat")
    def test_empty_text_with_no_tool_calls_falls_back(self, mock_chat):
        mock_chat.return_value = _reply("", tool_calls=[])
        self._talk("Mara Voss", "...")

        self.assertTrue(any("doesn't seem to have anything to say" in m for m in self.messages))

    @patch("commands.talk.chat")
    def test_emote_shown_as_separate_line_before_dialogue(self, mock_chat):
        mock_chat.return_value = _reply("*smiles and nods* Welcome in.")
        self._talk("Mara Voss", "hello")

        emote_index = next(i for i, m in enumerate(self.messages) if m == "Mara Voss smiles and nods.")
        dialogue_index = next(i for i, m in enumerate(self.messages) if "says" in m)
        self.assertLess(emote_index, dialogue_index)
        self.assertNotIn("*", self.messages[dialogue_index])

    @patch("commands.talk.chat")
    def test_dialogue_and_action_both_shown_together(self, mock_chat):
        # When the model provides both spoken text and a tool call,
        # the player should see the NPC say something AND see the
        # action happen - not just a silent mechanical action.
        mock_chat.return_value = _reply(
            "Here you go!", tool_calls=[{"name": "serve_drink", "arguments": {"drink_type": "hot"}}]
        )
        self._talk("Mara Voss", "hot drink please")

        self.assertTrue(any("Here you go" in m for m in self.messages))
        self.assertTrue(any("serves" in m and "hot drink" in m for m in self.messages))

    @patch("commands.talk.chat")
    def test_player_line_echoes_before_model_call_runs(self, mock_chat):
        # func() must send the player's own line and return *before*
        # kicking off the model call, not after it resolves - that's
        # what keeps a slow model from blocking the whole server and
        # from hiding the player's own input until the reply arrives.
        def slow_chat(*args, **kwargs):
            self.assertIn('You say to Mara Voss, "hi"', self.messages)
            return _reply("Hello there.")

        mock_chat.side_effect = slow_chat
        self._talk("Mara Voss", "hi")

    @patch("commands.talk.chat")
    def test_scenery_object_rejected_before_any_llm_call(self, mock_chat):
        # "square" is the exit back to the hub, present in Corner Cafe -
        # a real object, but not a TalkativeNPC.
        self._talk("square", "hello")
        mock_chat.assert_not_called()

    # -- conversation logging (step 8) --------------------------------

    @patch("commands.talk.chat")
    def test_ordinary_turn_is_logged(self, mock_chat):
        mock_chat.return_value = _reply("Afternoon.")
        self._talk("Mara Voss", "hello there")

        self.mock_log_turn.assert_called_once()
        kwargs = self.mock_log_turn.call_args.kwargs
        self.assertEqual(kwargs["npc_id"], "mara_voss")
        self.assertEqual(kwargs["player_message"], "hello there")
        self.assertEqual(kwargs["npc_response"], "Afternoon.")
        self.assertEqual(kwargs["model"], "test-model")
        self.assertEqual(kwargs["prompt_version"], "1")
        self.assertEqual(kwargs["flagged"], False)
        self.assertEqual(kwargs["tool_calls"], [])
        self.assertIn("prompt_messages", kwargs)
        self.assertTrue(kwargs["conversation_id"])
        self.assertEqual(kwargs["turn_id"], 1)

    @patch("commands.talk.chat")
    def test_tool_call_outcomes_are_logged(self, mock_chat):
        mock_chat.return_value = _reply(
            "Here you go!", tool_calls=[{"name": "serve_drink", "arguments": {"drink_type": "hot"}}]
        )
        self._talk("Mara Voss", "hot drink please")

        kwargs = self.mock_log_turn.call_args.kwargs
        self.assertEqual(
            kwargs["tool_calls"],
            [{"name": "serve_drink", "arguments": {"drink_type": "hot"}, "applied": True, "reason": ""}],
        )

    @patch("commands.talk.chat")
    def test_dropped_tool_call_outcome_is_logged(self, mock_chat):
        mock_chat.return_value = _reply(
            "Sure.", tool_calls=[{"name": "serve_drink", "arguments": {"drink_type": "lukewarm"}}]
        )
        self._talk("Mara Voss", "surprise me")

        kwargs = self.mock_log_turn.call_args.kwargs
        self.assertEqual(len(kwargs["tool_calls"]), 1)
        self.assertFalse(kwargs["tool_calls"][0]["applied"])
        self.assertTrue(kwargs["tool_calls"][0]["reason"])

    @patch("commands.talk.chat")
    def test_flagged_turn_is_logged_with_reason(self, mock_chat):
        mock_chat.return_value = _reply("As an AI, I don't have personal opinions.")
        self._talk("Mara Voss", "what do you think")

        kwargs = self.mock_log_turn.call_args.kwargs
        self.assertTrue(kwargs["flagged"])
        self.assertTrue(kwargs["flag_reason"])
        self.assertEqual(kwargs["npc_response"], "As an AI, I don't have personal opinions.")

    @patch("commands.talk.chat")
    def test_llm_unavailable_turn_is_logged(self, mock_chat):
        mock_chat.side_effect = LLMUnavailableError("timed out")
        self._talk("Mara Voss", "hello?")

        self.mock_log_turn.assert_called_once()
        kwargs = self.mock_log_turn.call_args.kwargs
        self.assertIsNone(kwargs["npc_response"])
        self.assertEqual(kwargs["flag_reason"], "llm_unavailable")

    @patch("commands.talk.chat")
    def test_turn_id_increments_within_same_conversation(self, mock_chat):
        mock_chat.return_value = _reply("Afternoon.")
        self._talk("Mara Voss", "hi")
        self._talk("Mara Voss", "hi again")

        first_kwargs = self.mock_log_turn.call_args_list[0].kwargs
        second_kwargs = self.mock_log_turn.call_args_list[1].kwargs
        self.assertEqual(first_kwargs["turn_id"], 1)
        self.assertEqual(second_kwargs["turn_id"], 2)
        self.assertEqual(first_kwargs["conversation_id"], second_kwargs["conversation_id"])
