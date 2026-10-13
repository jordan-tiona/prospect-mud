"""
The one module permitted to speak to a language model (CLAUDE.md hard
rule 8). Nothing else in this codebase should import `openai` or know
the model's wire protocol; everything else calls through here.

Model name, base URL and API key come from Evennia settings (which in
turn read environment variables, see server/conf/settings.py) so that
swapping Ollama for vLLM or a hosted API later is a config change, not
a code change.
"""

import json
from dataclasses import dataclass, field

from django.conf import settings
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI


class LLMUnavailableError(Exception):
    """Raised when the model can't be reached or times out."""


@dataclass
class LLMReply:
    text: str
    model: str
    raw: dict
    # Proposed actions only - never applied here.
    # [{"id": ..., "name": ..., "arguments": {...}}] - `id` is needed
    # to report the outcome back in a follow-up call (see
    # commands/say.py's _get_action_reaction).
    tool_calls: list = field(default_factory=list)


def _get_client() -> OpenAI:
    return OpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        timeout=settings.LLM_TIMEOUT_SECONDS,
    )


def _parse_tool_calls(message) -> list:
    tool_calls = []
    for call in getattr(message, "tool_calls", None) or []:
        try:
            arguments = json.loads(call.function.arguments) if call.function.arguments else {}
        except json.JSONDecodeError:
            # Malformed arguments are not our job to fix up - the tool
            # validator (world/actions.py) will reject whatever this
            # ends up being (likely missing required fields).
            arguments = {}
        tool_calls.append({"id": call.id, "name": call.function.name, "arguments": arguments})
    return tool_calls


def chat(
    messages: list[dict],
    tools: list[dict] | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
) -> LLMReply:
    """
    Send a chat-style message list to the configured model and return
    its reply, plus any proposed tool calls.

    Args:
        messages: OpenAI-style message dicts, e.g.
            [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
        tools: OpenAI-style tool/function definitions the model may
            call. The model can only *propose* these; nothing here
            applies them (see world/actions.py).
        model: override the configured default model for this call.
        max_tokens: caps the reply length; defaults to
            settings.LLM_MAX_TOKENS when not given (e.g. by an NPC's
            own `max_reply_tokens` persona metadata).

    Raises:
        LLMUnavailableError: the model is unreachable, slow past the
            configured timeout, or returned an error status. Callers
            (e.g. the say command) are expected to catch this and
            fall back gracefully rather than let it propagate to the
            player as a traceback.
    """
    client = _get_client()
    use_model = model or settings.LLM_MODEL
    extra_body = {}
    if settings.LLM_REASONING_EFFORT:
        # Sent two ways because OpenAI-compatible backends disagree on
        # the wire shape for this: some (e.g. Ollama, matching OpenAI's
        # own o-series/gpt-5 field) read a flat `reasoning_effort`.
        # Others (e.g. OpenRouter, proxying many providers with
        # different native reasoning controls) read a nested
        # `reasoning` object instead and otherwise default reasoning
        # *on* regardless of `reasoning_effort`, which silently burns
        # the whole max_tokens budget on hidden thinking tokens and
        # leaves the NPC's actual reply empty (confirmed empirically
        # against qwen/qwen3.6-35b-a3b on OpenRouter). A backend that
        # recognizes neither field ignores both harmlessly.
        extra_body["reasoning_effort"] = settings.LLM_REASONING_EFFORT
        if settings.LLM_REASONING_EFFORT == "none":
            extra_body["reasoning"] = {"exclude": True, "enabled": False}
        else:
            extra_body["reasoning"] = {"effort": settings.LLM_REASONING_EFFORT}

    kwargs = {
        "model": use_model,
        "messages": messages,
        "extra_body": extra_body,
        "max_tokens": max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    try:
        response = client.chat.completions.create(**kwargs)
    except (APIConnectionError, APITimeoutError, APIStatusError) as err:
        raise LLMUnavailableError(f"LLM request failed: {err}") from err

    choice = response.choices[0]
    return LLMReply(
        text=choice.message.content or "",
        model=response.model,
        raw=response.model_dump(),
        tool_calls=_parse_tool_calls(choice.message),
    )
