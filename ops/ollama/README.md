# Local Ollama model setup

`qwen3-8b-mud` is a local derived model, not the stock `qwen3:8b`
tag. Ollama's OpenAI-compatible endpoint (the only one this project's
LLM client is allowed to speak to - CLAUDE.md hard rule 8) silently
ignores `num_ctx` in the request body, so the only way to shrink the
context window is to bake it into the model itself via a Modelfile.

qwen3:14b's stock default context (40960 tokens) didn't fit in a
12GB-VRAM dev GPU and forced a 37%/63% CPU/GPU split (`ollama ps`).
Trimming it to 8192 via `qwen3-14b-mud` (see
`Modelfile.qwen3-14b-mud`) still ran out of VRAM on 2026-10-12: the
14B model's weights alone are 9.3GB, leaving too little headroom for
KV cache plus whatever else is on the GPU (desktop compositor,
browser, etc.). Switched the default to `qwen3-8b-mud`, whose ~5.2GB
weights leave real room on a 12GB card even with other things
running. 8192 tokens is still ample for this prototype's prompts
(persona + a handful of lore chunks + a few history turns).

To (re)create either tag after pulling/updating its base model:

```
ollama create qwen3-8b-mud -f ops/ollama/Modelfile.qwen3-8b-mud
ollama create qwen3-14b-mud -f ops/ollama/Modelfile.qwen3-14b-mud
```

Then confirm it's using the full GPU while actually answering a say
(not just idling): `ollama ps` should show `100% GPU` and
`CONTEXT  8192` while a request is in flight.

`server/conf/settings.py`'s `LLM_MODEL` points at `qwen3-8b-mud` by
default (override with `PROSPECT_LLM_MODEL` for a different setup,
e.g. a hosted API where this doesn't apply, or to go back to
`qwen3-14b-mud` if 8B's quality turns out not to be enough).
