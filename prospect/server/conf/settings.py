r"""
Evennia settings file.

The available options are found in the default settings file found
here:

https://www.evennia.com/docs/latest/Setup/Settings-Default.html

Remember:

Don't copy more from the default file than you actually intend to
change; this will make sure that you don't overload upstream updates
unnecessarily.

When changing a setting requiring a file system path (like
path/to/actual/file.py), use GAME_DIR and EVENNIA_DIR to reference
your game folder and the Evennia library folders respectively. Python
paths (path.to.module) should be given relative to the game's root
folder (typeclasses.foo) whereas paths within the Evennia library
needs to be given explicitly (evennia.foo).

If you want to share your game dir, including its settings, you can
put secret game- or server-specific settings in secret_settings.py.

"""

# Use the defaults from Evennia unless explicitly overridden
from evennia.settings_default import *

######################################################################
# Evennia base server config
######################################################################

# This is the name of your game. Make it catchy!
SERVERNAME = "prospect"


######################################################################
# LLM-driven NPC settings (phase 1 prototype, design-bible 16.4)
#
# Model name, base URL and API key come from environment, never
# hard-coded, so switching to vLLM or a hosted API later is a config
# change only. Defaults below match the local Ollama dev setup.
######################################################################
import os

LLM_BASE_URL = os.environ.get("PROSPECT_LLM_BASE_URL", "http://localhost:11434/v1")
LLM_API_KEY = os.environ.get("PROSPECT_LLM_API_KEY", "ollama")
# Purely descriptive label for structured logging (world/conversation_log.py) -
# not read anywhere else; nothing here can detect which backend
# LLM_BASE_URL actually points at, so this has to be set by hand
# alongside it.
LLM_PROVIDER = os.environ.get("PROSPECT_LLM_PROVIDER", "openrouter")
# "qwen3-8b-mud" is a local derived model (see ops/ollama/README.md),
# not the stock "qwen3:8b" tag: Ollama's OpenAI-compatible endpoint
# silently ignores any num_ctx passed in the request body (confirmed
# against Ollama 0.33.2 - only its native /api/chat endpoint honors
# it), so the only way to shrink the context window - and with it, the
# dev GPU's 12GB VRAM usage - without a model-specific call that would
# violate CLAUDE.md hard rule 8 is to bake num_ctx into the model
# itself via a Modelfile, then point LLM_MODEL at that derived tag.
# qwen3:14b's weights alone (9.3GB) left too little VRAM headroom even
# with num_ctx trimmed to 8192 (ran out of VRAM again on 2026-10-12);
# qwen3:8b's smaller weights (~5.2GB) leave real room on a 12GB card.
LLM_MODEL = os.environ.get("PROSPECT_LLM_MODEL", "qwen3-8b-mud")
LLM_TIMEOUT_SECONDS = float(os.environ.get("PROSPECT_LLM_TIMEOUT_SECONDS", "30"))

# Reasoning/"thinking" effort, passed through as the OpenAI-standard
# `reasoning_effort` field. Qwen3's extended thinking adds several
# seconds of latency with no benefit for short in-character replies,
# so the prototype default turns it off. Set to "" to omit the field
# entirely (e.g. for a model that errors on unknown params).
LLM_REASONING_EFFORT = os.environ.get("PROSPECT_LLM_REASONING_EFFORT", "none")

# Caps worst-case reply length (passed through as the OpenAI-standard
# `max_tokens` field, which Ollama's compat endpoint does honor).
# Per-NPC overrides live in that NPC's persona metadata
# (`max_reply_tokens`), read by world/npc_profile.py.
LLM_MAX_TOKENS = int(os.environ.get("PROSPECT_LLM_MAX_TOKENS", "150"))

# Cost/abuse safeguards (game-plan.md 6.2). Tuning knobs, expected to
# move during playtesting rather than being load-bearing constants.
#
# A player's `say` line only reaches the model if it's no longer than
# this many characters - checked in commands/say.py's engage_npc,
# before any model call. The ordinary (non-NPC) broadcast of the line
# to the room still happens regardless; this only gates the model call.
LLM_MAX_INPUT_CHARS = int(os.environ.get("PROSPECT_LLM_MAX_INPUT_CHARS", "300"))

# Minimum seconds between one player's model-calling turns, across all
# NPCs (not per NPC - see commands/say.py's engage_npc). Distinct from
# that same function's `pending` guard, which only blocks a genuinely
# overlapping second call before the first has replied; this blocks a
# rapid-fire sequence of separate, already-resolved turns.
LLM_COOLDOWN_SECONDS = float(os.environ.get("PROSPECT_LLM_COOLDOWN_SECONDS", "4"))

# Per-player daily spend budget in dollars (world/llm_budget.py),
# priced from each call's real token usage with the rates below. A
# quarter unlocks at UTC midnight, the rest in hourly chunks, so no
# one sitting can burn the whole day. Once exceeded, that player gets
# an in-character "come back tomorrow" fallback instead of further
# model calls until the daily reset at UTC midnight. Developer/admin
# accounts are exempt. $0.50 (project owner, 2026-10-16) is a starting
# point to watch, not a sustainable per-player cost.
LLM_PLAYER_DAILY_SPEND_USD = float(os.environ.get("PROSPECT_LLM_PLAYER_DAILY_SPEND_USD", "0.50"))

# OpenRouter's per-token rates for the configured model (openai/gpt-4.1-mini
# as of 2026-10-16: https://openrouter.ai/openai/gpt-4.1-mini-2025-04-14/api) -
# used only to compute real spend for LLM_DAILY_SPEND_LIMIT_USD below.
# Update these if the model or its pricing changes.
LLM_INPUT_COST_PER_1M_TOKENS = float(os.environ.get("PROSPECT_LLM_INPUT_COST_PER_1M_TOKENS", "0.40"))
LLM_OUTPUT_COST_PER_1M_TOKENS = float(os.environ.get("PROSPECT_LLM_OUTPUT_COST_PER_1M_TOKENS", "1.60"))
# Prompt tokens served from the provider's prompt cache (25% of the input
# rate for gpt-4.1-mini). Only used when the provider doesn't report its
# own per-call cost; OpenRouter does, so this is a fallback.
LLM_CACHED_INPUT_COST_PER_1M_TOKENS = float(os.environ.get("PROSPECT_LLM_CACHED_INPUT_COST_PER_1M_TOKENS", "0.10"))

# Server-wide daily spend circuit breaker (world/llm_budget.py), well
# below the OpenRouter key's own $25 spend limit. Deliberately set
# far above realistic playtest volume - this is a backstop against a
# bug or runaway loop, not a throttle on ordinary play. Logged at
# error level when tripped; nothing else is notified yet.
LLM_DAILY_SPEND_LIMIT_USD = float(os.environ.get("PROSPECT_LLM_DAILY_SPEND_LIMIT_USD", "2.00"))

# Invite-only account registration (game-plan.md 6.2's last
# safeguards-audit item) - see world/invites.py and
# commands/chargen.py's CmdScriptedCreate. On by default since the
# whole point is a closed beta; existing tests that don't care about
# this gate turn it off explicitly (see commands/test_chargen.py).
INVITE_ONLY_REGISTRATION = (
    os.environ.get("PROSPECT_INVITE_ONLY_REGISTRATION", "true").lower() == "true"
)

# Pure data counters with no in-game presence (evennia.GLOBAL_SCRIPTS
# singleton pattern) - the daily spend circuit breaker's server-wide
# total and the invite-code registry both have no single player or
# NPC object of their own to live on.
GLOBAL_SCRIPTS = {
    "llm_spend_tracker": {
        "typeclass": "typeclasses.scripts.Script",
        "persistent": True,
    },
    "invite_registry": {
        "typeclass": "typeclasses.scripts.Script",
        "persistent": True,
    },
    # Idle-time gameplay-event detection (world/idle_check.py,
    # game-plan.md 6.2) - ticks every 60s to check connected sessions,
    # not a data counter like the two above.
    "idle_monitor": {
        "typeclass": "typeclasses.scripts.IdleMonitor",
        "interval": 60,
        "persistent": True,
    },
}

# Every stock Evennia command resolves its own base class from this
# setting at import time (see e.g. evennia.commands.default.general's
# `COMMAND_DEFAULT_CLASS = class_from_module(settings.COMMAND_DEFAULT_CLASS)`).
# Pointing it at commands.command.MuxCommand (which mixes in
# _SessionCommandLoggingMixin on top of everything the stock
# MuxCommand already does) makes every command in the game - get,
# look, drop, movement/exit commands, inventory, as well as this
# project's own custom commands - log to world/session_log.py's
# sessions.jsonl, for playtest debugging (2026-10-15).
COMMAND_DEFAULT_CLASS = "commands.command.MuxCommand"


######################################################################
# Settings given in secret_settings.py override those in this file.
######################################################################
try:
    from server.conf.secret_settings import *
except ImportError:
    print("secret_settings.py file not found or failed to import.")
