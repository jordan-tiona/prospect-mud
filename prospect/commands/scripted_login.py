"""
Scripted connect screen (project owner, 2026-10-14): replaces
Evennia's default plain-text "connect <name> <password>" instructions
with the project's splash art (the .ans file at the repo root) and a
natural two-step "Who are you? / Password:" prompt, instead of
requiring a single one-line command.

This overrides `CMD_LOGINSTART` - the syscmd key Evennia's portal
fires automatically the moment a session connects (see
evennia.commands.default.unloggedin.CmdUnconnectedLook, the stock
command this replaces) - plus its "look"/"l" aliases, so typing
`look` later re-runs the same splash+prompt sequence rather than
showing Evennia's static connection-screen text. commands/chargen.py's
`CONNECTION_SCREEN` (server/conf/connection_screens.py) is no longer
shown by anything as a result, but is left in place rather than
deleted in case it's wanted again.

A blank name hands off directly into the project's existing scripted
character creation (commands/chargen.py's `CmdScriptedCreate`) -
rather than duplicating any of its logic, this instantiates that
command directly and `yield from`s its generator, the same way its
own func() is itself driven by Evennia's generator-command machinery
(see that module's docstring for how `yield`-as-prompt and `yield`-as-
pause work). `at_pre_cmd`'s registration-enabled check is reproduced
by hand here, since that hook is only invoked by Evennia's own command
dispatch, not by calling `.func()` directly like this does.

A given name instead prompts for a password and authenticates exactly
like Evennia's stock `connect` command (Account.authenticate) -
plain-text, not echo-masked, same as the rest of this project's
login/creation flow already is (see commands/chargen.py's docstring).
A failed login shows the error and loops back to "Who are you?"
rather than dropping the player back to a bare prompt.

The `connect`/`create` one-line commands themselves are untouched and
still work for anyone who types them directly out of habit - this
module also recognizes a full "connect <name> <password>" (or its
aliases con/conn/co) typed at the "Who are you?" prompt itself and
parses it the old way rather than treating the whole line as a
literal name, so it also authenticates immediately without an extra
Password: round-trip. This isn't just habit-forgiveness: some clients
(e.g. Mudlet) support pre-configuring a "connect name password" string
to auto-send right after connecting, and there's no way to tell that
apart from a player typing it - both need to keep working.

Splash art (project owner, 2026-10-14) is sent with `options={"raw":
True}` - without it, Evennia's `ansi.parse_ansi` reprocesses the text
as part of normal output handling (session.msg's default path), and
since the splash already *is* fully-formed ANSI (real ESC byte
sequences, not Evennia's own `|`-style markup - confirmed by reading
the file directly), running it back through that parser was
corrupting some of the art. `raw` sends it to the protocol layer
untouched (still gets the normal LF->CRLF telnet conversion).
"""

import os
import re

from django.conf import settings
from evennia.commands.cmdhandler import CMD_LOGINSTART
from evennia.utils import class_from_module, utils

COMMAND_DEFAULT_CLASS = utils.class_from_module(settings.COMMAND_DEFAULT_CLASS)

# The splash art lives at the repo root, one level up from settings.GAME_DIR
# (the `prospect/` game directory Evennia's commands run from) - see that
# setting's own docstring in server/conf/settings.py.
_SPLASH_PATH = os.path.join(os.path.dirname(settings.GAME_DIR), "prospect-with-stars-custom-colored.ans")

_WHO_ARE_YOU_PROMPT = '|cWho are you?|n |W(Leave blank if you\'re new)|n'

# Matches the stock CmdUnconnectedConnect's own key+aliases (commands/
# default_cmdsets.py doesn't remove that command - see module docstring).
_OLD_CONNECT_WORDS = ("connect", "conn", "con", "co")


def _show_splash(session):
    try:
        with open(_SPLASH_PATH, "r", encoding="ascii") as splash_file:
            session.msg(splash_file.read(), options={"raw": True})
    except OSError:
        # Missing splash art shouldn't block anyone from logging in.
        pass


def _parse_old_style_connect(raw):
    """If `raw` looks like a full old-style "connect <name> <password>"
    line (or one of that command's shorter aliases), return `(name,
    password)` - `password` is `None` if only a name followed it.
    Returns `None` if `raw` isn't that shape at all, same quoted-name
    handling as the stock command it mirrors."""
    first, _, rest = raw.partition(" ")
    if first.lower() not in _OLD_CONNECT_WORDS or not rest.strip():
        return None

    parts = [part.strip() for part in re.split(r"\"", rest) if part.strip()]
    if len(parts) == 1:
        parts = parts[0].split(None, 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    if len(parts) == 1:
        return parts[0], None
    return None


class CmdScriptedLogin(COMMAND_DEFAULT_CLASS):
    """
    show the connect screen and log in or create a character

    This is the unlogged-in "look" command - it's what Evennia runs
    automatically the moment a session connects, and what `look`/`l`
    re-run afterward.
    """

    key = CMD_LOGINSTART
    aliases = ["look", "l"]
    locks = "cmd:all()"

    def func(self):
        session = self.caller
        Account = class_from_module(settings.BASE_ACCOUNT_TYPECLASS)

        _show_splash(session)

        while True:
            raw_answer = ((yield _WHO_ARE_YOU_PROMPT) or "").strip()

            if not raw_answer:
                if not settings.NEW_ACCOUNT_REGISTRATION_ENABLED:
                    session.msg("Registration is currently disabled.")
                    continue

                from commands.chargen import CmdScriptedCreate

                create_cmd = CmdScriptedCreate()
                create_cmd.caller = session
                yield from create_cmd.func()
                return

            old_style = _parse_old_style_connect(raw_answer)
            name, password = old_style if old_style else (raw_answer, None)

            if password is None:
                password = yield "Password:"
            account, errors = Account.authenticate(
                username=name, password=password, ip=session.address, session=session
            )
            if account:
                session.sessionhandler.login(session, account)
                return

            session.msg("|R%s|n" % "\n".join(errors))
