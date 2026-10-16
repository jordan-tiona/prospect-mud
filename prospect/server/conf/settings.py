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
