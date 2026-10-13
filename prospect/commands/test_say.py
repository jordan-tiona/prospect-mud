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

from unittest.mock import patch

from django.test import TestCase
from evennia import create_object
from twisted.internet import defer

from commands.say import MAX_HISTORY_EXCHANGES, _build_followup_messages, _trim_history
from world.actions import get_quest_state
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

        tool_msg = followup[-1]
        self.assertIn("did not happen", tool_msg["content"])
        self.assertIn("invalid drink_type", tool_msg["content"])


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


class SayCommandTests(TestCase):
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
    def test_npc_reply_is_addressed_to_the_player(self, mock_chat):
        mock_chat.return_value = _reply("Afternoon.")
        self._say("hello there")

        self.assertTrue(any("Mara Voss says to you" in m for m in self.messages))

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
        # Mara's persona doesn't grant hand_over_item - even if the
        # model proposes it, it must never be applied.
        mock_chat.return_value = _reply(
            "Here.", tool_calls=[{"name": "hand_over_item", "arguments": {"item_type": "spare part"}}]
        )
        self._say("got any spare parts?")

        self.assertFalse(any("hands" in m for m in self.messages))

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
        self.assertEqual(kwargs["prompt_version"], "12")
        self.assertEqual(kwargs["flagged"], False)
        self.assertEqual(kwargs["tool_calls"], [])
        self.assertIn("prompt_messages", kwargs)
        self.assertTrue(kwargs["conversation_id"])
        self.assertEqual(kwargs["turn_id"], 1)

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

    # -- module-exchange quest state (Mara + Tarin) -----------------------

    @patch("commands.say.chat")
    def test_quest_context_injected_for_mara(self, mock_chat):
        mock_chat.return_value = _reply("Afternoon.")
        self._say("hello there")

        messages = mock_chat.call_args.args[0]
        self.assertTrue(
            any(
                m["role"] == "system" and "heating-unit module errand" in m["content"]
                for m in messages
            )
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

    @patch("commands.say.chat")
    def test_accept_help_tool_call_updates_quest_state(self, mock_chat):
        mock_chat.return_value = _reply(
            "Oh, that'd be a help.", tool_calls=[{"name": "accept_help", "arguments": {}}]
        )
        self._say("want me to take that module to Tarin?")

        self.assertEqual(get_quest_state(self.actor), "accepted")

    @patch("commands.say.chat")
    def test_give_faulty_module_requires_prior_acceptance(self, mock_chat):
        mock_chat.return_value = _reply(
            "Here you go.", tool_calls=[{"name": "give_faulty_module", "arguments": {}}]
        )
        self._say("can I get the module")

        self.assertEqual(get_quest_state(self.actor), "not_started")

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
