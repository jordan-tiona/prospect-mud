"""
`tell`: a private message to another player who's online, replacing
Evennia's stock `page` (owner, 2026-10-17, after Achaea).

- `tell <name> <message>` (or `tell <name> = <message>`) finds the
  recipient by the name players see, full name or first name, among
  characters currently in the game.
- `tell <message>` with no recognised name replies to whoever last
  sent you a tell.
- Online only: unlike `page`, nothing is stored for later.
- Not logged: the session log records that a tell was sent, never who
  to or what it said (`log_input = False`, commands/command.py).

The comms lead-in line before a tell (LR-DEV-0005) is wired up but
off until the Lore lane's wording is approved.
"""

import time

from evennia.server.sessionhandler import SESSION_HANDLER

from commands.command import Command
from world.speech_format import normalize_speech

# TODO(lore): LR-DEV-0005 - the "you hear <name> over your comms" lead-in.
# A format string with {name}; None shows no lead-in.
TELL_LEAD_IN = None

# A sender's next tell gets the lead-in again after this long.
LEAD_IN_GAP_SECONDS = 10 * 60

USAGE = "Usage: tell <name> <message>, or tell <message> to reply to your last tell."


def online_characters():
    return [session.puppet for session in SESSION_HANDLER.get_sessions() if session.puppet]


def match_recipient(text, candidates):
    """
    Find the recipient named at the start of `text`. Returns
    (character, message, error): a match gives a character and the
    rest of the text; a first name shared by more than one candidate
    gives an error naming them; no match gives (None, text, None).
    Longest name first, so "Ravis Vardur" beats a "Ravis" on its own.
    """
    lowered = text.lower()
    names = []
    for char in candidates:
        names.append((char.key, char, True))
        first = char.key.split()[0]
        if first != char.key:
            names.append((first, char, False))
    names.sort(key=lambda entry: len(entry[0]), reverse=True)

    for name, char, is_full in names:
        name_l = name.lower()
        if lowered != name_l and not lowered.startswith(name_l + " "):
            continue
        if not is_full:
            sharing = [c for c in candidates if c.key.split()[0].lower() == name_l]
            if len(sharing) > 1:
                options = ", ".join(sorted(c.key for c in sharing))
                return None, text, f"More than one {name} is online: {options}. Use the full name."
        return char, text[len(name):].strip(), None
    return None, text, None


class CmdTell(Command):
    """
    Send a private message to another player who's in the game.

    Usage:
      tell <name> <message>
      tell <message>        - reply to whoever last sent you a tell
    """

    key = "tell"
    locks = "cmd:all()"
    help_category = "Comms"
    log_input = False

    def func(self):
        caller = self.caller
        args = self.args.strip()
        if not args:
            caller.msg(USAGE)
            return

        candidates = [char for char in online_characters() if char != caller]
        if "=" in args:
            name, message = (part.strip() for part in args.split("=", 1))
            target, rest, error = match_recipient(name, candidates)
            if target is not None and rest:
                target = None
        else:
            target, message, error = match_recipient(args, candidates)

        if error:
            caller.msg(error)
            return
        if target is None:
            if "=" in args:
                caller.msg("No one by that name is in the game.")
                return
            target = caller.db.last_tell_from
            message = args
            if target is None:
                caller.msg(USAGE)
                return
            if target not in candidates:
                caller.msg(f"{target.key} isn't in the game right now.")
                return
        if not message:
            caller.msg(f"Tell {target.key} what?")
            return

        message, _ = normalize_speech(message)
        caller.msg(f'You tell {target.get_display_name(caller)}, |Y"{message}"|n')
        _deliver(caller, target, message)


def _deliver(sender, target, message):
    heard = target.ndb.tells_heard_at or {}
    last = heard.get(sender.id)
    now = time.time()
    if TELL_LEAD_IN and (last is None or now - last > LEAD_IN_GAP_SECONDS):
        target.msg(TELL_LEAD_IN.format(name=sender.get_display_name(target)))
    heard[sender.id] = now
    target.ndb.tells_heard_at = heard
    target.db.last_tell_from = sender
    target.msg(f'{sender.get_display_name(target)} tells you, |Y"{message}"|n')
