"""
The playtest data disclosure (owner, 2026-10-17): shown after a valid
invite code and before character creation starts, and a player has to
type AGREE to go on. Declining ends registration and leaves the invite
code unused.

Out-of-character policy text, not setting content. Bump
DISCLOSURE_VERSION whenever the wording changes what a player agrees
to: each account records the version it agreed to
(`account.db.disclosure_agreed`), so older agreements stay
distinguishable.
"""

from datetime import datetime, timezone

DISCLOSURE_VERSION = 1

# No deletion line by design (owner, 2026-10-17): agreeing to the
# logging is the condition of playtesting. Deletion requests are for
# after the playtest phase.
# TODO(owner): confirm the model-tuning line before the public playtest.
DISCLOSURE_TEXT = """\
|wBefore you begin: what this playtest records|n

This is a playtest, and what you do here is recorded so the game can be improved.

  - Your commands, your conversations with characters, and what you say on the
    PLAYTEST channel are logged, along with bug and feedback reports.
  - Characters' replies are written by an AI model. What you say to them is sent
    to OpenRouter, which passes it to the model's provider (currently OpenAI).
  - Logs may be used to improve the game, including tuning the AI model that
    voices its characters.
  - Private messages sent with TELL are not logged.

Please don't share personal information you wouldn't want recorded."""

AGREE_PROMPT = "Type |wAGREE|n to continue, or |wQUIT|n to leave without creating a character."

AGREE_WORDS = {"agree", "i agree"}
QUIT_WORDS = {"quit", "q", "no", "disagree", "leave"}


def agreement_record() -> dict:
    return {"version": DISCLOSURE_VERSION, "at": datetime.now(timezone.utc).isoformat()}
