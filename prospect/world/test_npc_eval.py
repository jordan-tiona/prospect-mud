"""
Tests for the NPC tool-call reliability eval harness (world/npc_eval.py)
itself - not the live model. Mocks world.npc_eval.chat throughout, so
this runs free and deterministic as part of the normal `evennia test`
suite: it's checking that run_scenario() builds the right messages and
tallies hits/misses correctly, not evaluating any actual model.

Run with:
    evennia test world
"""

from unittest.mock import patch

from django.test import TestCase

from world.commitments import accept_commitment, propose_commitment
from world.llm_client import LLMReply
from world.npc_eval import EvalScenario, run_scenario


def _reply(tool_calls=None, text=""):
    return LLMReply(text=text, model="test-model", raw={}, tool_calls=tool_calls or [])


class RunScenarioTests(TestCase):
    @patch("world.npc_eval.chat")
    def test_all_trials_matching_expectation_scores_full_hits(self, mock_chat):
        mock_chat.return_value = _reply([{"name": "serve_drink", "arguments": {"drink_type": "hot"}}])
        scenario = EvalScenario(
            name="t", npc_id="mara_voss", player_message="coffee please", expect_calls={"serve_drink"}
        )

        result = run_scenario(scenario, trials=3)

        self.assertEqual(result.hits, 3)
        self.assertEqual(result.trials, 3)
        self.assertEqual(result.unexpected, [])

    @patch("world.npc_eval.chat")
    def test_missing_expected_call_is_not_a_hit(self, mock_chat):
        mock_chat.return_value = _reply([])  # model never calls anything
        scenario = EvalScenario(
            name="t", npc_id="mara_voss", player_message="coffee please", expect_calls={"serve_drink"}
        )

        result = run_scenario(scenario, trials=3)

        self.assertEqual(result.hits, 0)
        self.assertEqual(result.unexpected, [set(), set(), set()])

    @patch("world.npc_eval.chat")
    def test_unwanted_call_counts_against_expect_no_calls(self, mock_chat):
        mock_chat.return_value = _reply([{"name": "accept_help", "arguments": {}}])
        scenario = EvalScenario(
            name="t", npc_id="mara_voss", player_message="a question", expect_no_calls={"accept_help"}
        )

        result = run_scenario(scenario, trials=4)

        self.assertEqual(result.hits, 0)
        self.assertEqual(result.unexpected, [{"accept_help"}] * 4)

    @patch("world.npc_eval.chat")
    def test_extra_unexpected_call_alongside_the_expected_one_is_not_a_hit(self, mock_chat):
        # expect_calls is a minimum, not an exact set - but anything
        # named in expect_no_calls still disqualifies the trial even
        # if the expected call also fired.
        mock_chat.return_value = _reply(
            [{"name": "serve_drink", "arguments": {}}, {"name": "accept_help", "arguments": {}}]
        )
        scenario = EvalScenario(
            name="t",
            npc_id="mara_voss",
            player_message="x",
            expect_calls={"serve_drink"},
            expect_no_calls={"accept_help"},
        )

        result = run_scenario(scenario, trials=1)

        self.assertEqual(result.hits, 0)

    @patch("world.npc_eval.chat")
    def test_history_and_system_prompt_are_sent(self, mock_chat):
        mock_chat.return_value = _reply()
        scenario = EvalScenario(
            name="t",
            npc_id="mara_voss",
            history=[{"role": "user", "content": "earlier line"}],
            player_message="the actual line",
        )

        run_scenario(scenario, trials=1)

        messages = mock_chat.call_args.args[0]
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("You are Mara Voss", messages[0]["content"])
        self.assertTrue(any(m.get("content") == "earlier line" for m in messages))
        self.assertEqual(messages[-1], {"role": "user", "content": "the actual line"})

    @patch("world.npc_eval.chat")
    def test_setup_seeds_commitment_state_reflected_in_context(self, mock_chat):
        mock_chat.return_value = _reply()

        def setup(actor):
            propose_commitment(actor, "verify_display_revision")
            accept_commitment(actor, "verify_display_revision")

        scenario = EvalScenario(
            name="t", npc_id="daven_varek", player_message="x", setup=setup
        )

        run_scenario(scenario, trials=1)

        messages = mock_chat.call_args.args[0]
        self.assertTrue(
            any("open, not yet acknowledged" in m.get("content", "") for m in messages)
        )

    @patch("world.npc_eval.chat")
    def test_expect_text_contains_checks_the_reply_text_case_insensitively(self, mock_chat):
        mock_chat.return_value = _reply(text="I already confirmed the Approval Mark myself.")
        scenario = EvalScenario(
            name="t", npc_id="veska_renn", player_message="x", expect_text_contains=["approval mark"]
        )

        result = run_scenario(scenario, trials=2)

        self.assertEqual(result.hits, 2)

    @patch("world.npc_eval.chat")
    def test_expect_text_contains_missing_is_not_a_hit(self, mock_chat):
        mock_chat.return_value = _reply(text="It's been taken care of.")
        scenario = EvalScenario(
            name="t", npc_id="veska_renn", player_message="x", expect_text_contains=["approval mark"]
        )

        result = run_scenario(scenario, trials=2)

        self.assertEqual(result.hits, 0)
        # The failure is about wording, not a tool call - the actual
        # text should be kept alongside the called-action set so it's
        # visible in the report, not just a useless empty set.
        self.assertEqual(result.unexpected, [(set(), "It's been taken care of.")] * 2)

    @patch("world.npc_eval.chat")
    def test_expect_text_absent_present_is_not_a_hit(self, mock_chat):
        mock_chat.return_value = _reply(text="I took it down and withdrew it from the board.")
        scenario = EvalScenario(
            name="t", npc_id="veska_renn", player_message="x", expect_text_absent=["withdr"]
        )

        result = run_scenario(scenario, trials=1)

        self.assertEqual(result.hits, 0)

    @patch("world.npc_eval.chat")
    def test_actor_is_cleaned_up_after_the_scenario(self, mock_chat):
        from evennia.objects.models import ObjectDB

        mock_chat.return_value = _reply()
        scenario = EvalScenario(name="t", npc_id="mara_voss", player_message="x")

        run_scenario(scenario, trials=1)

        self.assertFalse(ObjectDB.objects.filter(db_key__startswith="EvalActor").exists())
