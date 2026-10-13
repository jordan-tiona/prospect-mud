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
