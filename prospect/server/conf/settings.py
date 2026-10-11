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
LLM_MODEL = os.environ.get("PROSPECT_LLM_MODEL", "qwen3:14b")
LLM_TIMEOUT_SECONDS = float(os.environ.get("PROSPECT_LLM_TIMEOUT_SECONDS", "30"))


######################################################################
# Settings given in secret_settings.py override those in this file.
######################################################################
try:
    from server.conf.secret_settings import *
except ImportError:
    print("secret_settings.py file not found or failed to import.")
