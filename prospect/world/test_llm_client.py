"""
Unit tests for the LLM client's request shaping (world/llm_client.py) -
specifically settings.LLM_MAX_TOKENS and the per-NPC `max_tokens`
override. (Context-window size is handled by a derived Ollama model,
not a request parameter - see ops/ollama/README.md - since Ollama's
OpenAI-compatible endpoint ignores num_ctx in the request body.) The
OpenAI client itself is mocked; world/test_llm_connection.py remains
the manual smoke test against a live Ollama server.

Run with:
    evennia test world
"""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from world.llm_client import chat


def _mock_response():
    response = MagicMock()
    response.choices[0].message.content = "hi"
    response.choices[0].message.tool_calls = None
    response.model = "test-model"
    response.model_dump.return_value = {}
    response.usage.prompt_tokens = 10
    response.usage.completion_tokens = 5
    response.usage.total_tokens = 15
    return response


class ChatRequestShapingTests(SimpleTestCase):
    @patch("world.llm_client._get_client")
    def test_default_max_tokens_comes_from_settings(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_response()
        mock_get_client.return_value = mock_client

        chat([{"role": "user", "content": "hi"}])

        kwargs = mock_client.chat.completions.create.call_args.kwargs
        from django.conf import settings

        self.assertEqual(kwargs["max_tokens"], settings.LLM_MAX_TOKENS)

    @patch("world.llm_client._get_client")
    def test_explicit_max_tokens_overrides_the_default(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_response()
        mock_get_client.return_value = mock_client

        chat([{"role": "user", "content": "hi"}], max_tokens=42)

        kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["max_tokens"], 42)


class UsageCaptureTests(SimpleTestCase):
    """
    world/conversation_log.py and the per-player/global token budgets
    (game-plan.md 6.2) both need the model's *actual* token usage, not
    just the max_tokens cap sent with the request - this is what
    carries that number out of llm_client.chat() for them to use.
    """

    @patch("world.llm_client._get_client")
    def test_usage_is_captured_from_the_response(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_response()
        mock_get_client.return_value = mock_client

        reply = chat([{"role": "user", "content": "hi"}])

        self.assertEqual(
            reply.usage,
            {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "cached_tokens": 0},
        )

    @patch("world.llm_client._get_client")
    def test_cached_tokens_and_provider_cost_are_captured_when_reported(self, mock_get_client):
        mock_client = MagicMock()
        response = _mock_response()
        response.usage.prompt_tokens_details.cached_tokens = 8
        response.usage.cost = 0.0007
        mock_client.chat.completions.create.return_value = response
        mock_get_client.return_value = mock_client

        reply = chat([{"role": "user", "content": "hi"}])

        self.assertEqual(reply.usage["cached_tokens"], 8)
        self.assertEqual(reply.usage["cost"], 0.0007)

    @patch("world.llm_client._get_client")
    def test_missing_usage_on_the_response_yields_an_empty_dict(self, mock_get_client):
        mock_client = MagicMock()
        response = _mock_response()
        response.usage = None
        mock_client.chat.completions.create.return_value = response
        mock_get_client.return_value = mock_client

        reply = chat([{"role": "user", "content": "hi"}])

        self.assertEqual(reply.usage, {})


class PromptCacheMarkerTests(SimpleTestCase):
    """settings.LLM_PROMPT_CACHE_MARKERS: explicit cache markers for
    providers (Anthropic, via OpenRouter) that only cache marked text."""

    def _send(self, mock_get_client, messages):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_response()
        mock_get_client.return_value = mock_client
        chat(messages)
        return mock_client.chat.completions.create.call_args.kwargs

    @patch("world.llm_client._get_client")
    def test_off_by_default_sends_messages_unchanged(self, mock_get_client):
        messages = [{"role": "system", "content": "persona"}, {"role": "user", "content": "hi"}]
        kwargs = self._send(mock_get_client, messages)
        self.assertNotIn("cache_control", kwargs["extra_body"])
        self.assertEqual(kwargs["messages"], messages)

    @patch("world.llm_client._get_client")
    def test_on_marks_the_fixed_prompt_and_the_request(self, mock_get_client):
        messages = [
            {"role": "system", "content": "persona"},
            {"role": "system", "content": "quest state"},
            {"role": "user", "content": "hi"},
        ]
        with self.settings(LLM_PROMPT_CACHE_MARKERS=True):
            kwargs = self._send(mock_get_client, messages)
        self.assertEqual(kwargs["extra_body"]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(
            kwargs["messages"][0]["content"],
            [{"type": "text", "text": "persona", "cache_control": {"type": "ephemeral"}}],
        )
        self.assertEqual(kwargs["messages"][1:], messages[1:])

    @patch("world.llm_client._get_client")
    def test_on_leaves_the_callers_list_untouched(self, mock_get_client):
        # Callers keep their message lists as conversation history.
        messages = [{"role": "system", "content": "persona"}, {"role": "user", "content": "hi"}]
        with self.settings(LLM_PROMPT_CACHE_MARKERS=True):
            self._send(mock_get_client, messages)
        self.assertEqual(messages[0]["content"], "persona")


class ReasoningBudgetTests(SimpleTestCase):
    """settings.LLM_REASONING_MAX_TOKENS: a fixed, hidden thinking budget."""

    @patch("world.llm_client._get_client")
    def test_budget_replaces_effort_and_adds_to_the_reply_cap(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_response()
        mock_get_client.return_value = mock_client

        with self.settings(LLM_REASONING_MAX_TOKENS=400):
            chat([{"role": "user", "content": "hi"}], max_tokens=150)

        kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["extra_body"]["reasoning"], {"max_tokens": 400, "exclude": True})
        self.assertEqual(kwargs["max_tokens"], 550)
