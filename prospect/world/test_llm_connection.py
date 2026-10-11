"""
Manual connectivity smoke test for the LLM client (phase 1 step 3).

This is not a unit test: it requires a live Ollama server and is meant
to be run by hand to confirm the client module can actually reach the
configured model. Automated tests for the prompt builder and tool
validator come in later steps, per CLAUDE.md.

Run with:
    evennia shell -c "from world.test_llm_connection import run; run()"
"""

import time

from world.llm_client import LLMUnavailableError, chat


def run():
    messages = [
        {"role": "system", "content": "Reply with exactly one short sentence."},
        {"role": "user", "content": "Say hello and name one color."},
    ]
    start = time.monotonic()
    try:
        reply = chat(messages)
    except LLMUnavailableError as err:
        print(f"FAILED after {time.monotonic() - start:.1f}s: {err}")
        return

    elapsed = time.monotonic() - start
    print(f"OK ({elapsed:.1f}s, model={reply.model})")
    print(f"Reply: {reply.text}")
