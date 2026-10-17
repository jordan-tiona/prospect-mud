"""
`describe`: set how your character looks (project owner, 2026-10-17).
Three fields, stored and checked by world/appearance.py:

- pose (40 characters): "<name> is here, <pose>." in the room
- short description (100): what `look` shows
- long description (1,000): what `probe` shows

Takes natural phrasings as well as the terse form, the way `look at`
and `take` do (commands/look.py, commands/get.py):

    describe short tall and rangy, with a scarred jaw
    change my short description to tall and rangy
    set my pose to leaning on the counter
    clear my long description
    describe clear pose

Replaces Evennia's stock `setdesc`, which wrote db.desc with no limit
or check.
"""

import re

from evennia.utils.ansi import strip_ansi

from world import appearance

from .command import Command

_CLEAR_VERBS = ("clear my", "remove my", "delete my")

_FIELD_RE = re.compile(
    r"^(?:my\s+)?"
    r"(?P<field>short(?:\s+desc(?:ription)?)?|long(?:\s+desc(?:ription)?)?|bio(?:graphy)?|pose)\b"
    r"(?:\s+(?:to|as|is)\b|\s*[:=])?\s*(?P<text>.*)$",
    re.IGNORECASE | re.DOTALL,
)

_CLEAR_RE = re.compile(r"^(?:clear|remove|delete)\s+(?P<rest>.*)$", re.IGNORECASE | re.DOTALL)


def _field_name(word: str) -> str:
    word = word.lower()
    if word.startswith("short"):
        return "short"
    if word.startswith(("long", "bio")):
        return "long"
    return "pose"


def _parse(cmdstring: str, args: str) -> tuple[str, str, str] | None:
    """(action, field, text), action being "set", "show" or "clear";
    or None if no field could be read."""
    clearing = cmdstring.lower() in _CLEAR_VERBS
    clear_match = _CLEAR_RE.match(args)
    if clear_match:
        clearing, args = True, clear_match.group("rest")
    match = _FIELD_RE.match(args)
    if not match:
        return None
    field = _field_name(match.group("field"))
    text = match.group("text").strip()
    if clearing:
        return "clear", field, ""
    return ("set" if text else "show"), field, text


class CmdDescribe(Command):
    """
    change how your character looks

    Usage:
      describe
      describe pose <text>
      describe short <text>
      describe long <text>
      describe clear <pose|short|long>

    Your pose follows your name in the room ("Jordan is here,
    <pose>."), up to 40 characters. Your short description is what
    others see when they LOOK at you, up to 100. Your long description
    is what they see when they PROBE you, up to 1,000.

    You can also say it in plain English, such as "change my short
    description to ..." or "clear my pose".
    """

    key = "describe"
    aliases = [
        "describe myself",
        "describe me",
        "description",
        "change my",
        "set my",
        "edit my",
        "update my",
        *_CLEAR_VERBS,
    ]
    locks = "cmd:all()"
    help_category = "General"
    arg_regex = r"\s|$"

    def func(self):
        caller = self.caller
        args = self.args.strip()
        if not args:
            caller.msg(self._overview())
            return
        parsed = _parse(self.cmdstring, args)
        if parsed is None:
            caller.msg(
                "You can change your pose, your short description or your long description. "
                "Type DESCRIBE to see them."
            )
            return
        action, field, text = parsed
        label = appearance.LABELS[field]
        if action == "show":
            current = appearance.get(caller, field)
            caller.msg(
                f"Your {label}: {current}" if current else f"You don't have a {label} yet."
            )
            caller.msg(f"To change it, type DESCRIBE {field.upper()} and then the new text.")
            return
        if action == "clear":
            appearance.clear_field(caller, field)
            caller.msg(f"Your {label} is cleared.")
            return
        cleaned, error = appearance.validate(field, text)
        if error:
            caller.msg(error)
            return
        appearance.set_field(caller, field, cleaned)
        if field == "pose":
            caller.msg(f"Others now see: {caller.key} is here, {cleaned}.")
        else:
            caller.msg(f"Your {label} is now: {cleaned}")

    def _overview(self) -> str:
        caller = self.caller
        lines = ["Your descriptions:"]
        for field, how in (
            ("pose", f"after your name in the room, \"{caller.key} is here, ...\""),
            ("short", "when someone types LOOK at you"),
            ("long", "when someone types PROBE at you"),
        ):
            current = appearance.get(caller, field) or "(not set)"
            limit = appearance.LIMITS[field]
            lines.append(
                f"  |w{field.upper()}|n, shown {how}, up to {limit:,} characters:\n    {current}"
            )
        lines.append(
            "To change one, type DESCRIBE and then POSE, SHORT or LONG and the new text, "
            "for example: describe pose leaning on the counter. To remove one, type "
            "DESCRIBE CLEAR and its name."
        )
        lines.append("")
        lines.extend(self._what_others_see())
        return "\n".join(lines)

    def _what_others_see(self) -> list[str]:
        """The room line, look text and probe text as another player
        gets them, plus what NPCs are told about you."""
        from typeclasses.rooms import _presence_line

        caller = self.caller

        def plain(text):
            return " ".join(strip_ansi(text or "").split())

        look = plain(caller.get_display_desc(caller))
        probe = plain(caller.get_display_desc(caller, probe=True))
        lines = [
            "What others see:",
            f"  In the room: {plain(_presence_line(caller, caller.key, 'c'))}",
            f"  When they LOOK at you: {look}",
            f"  When they PROBE you: {probe if probe != look else '(the same as LOOK)'}",
        ]
        identity = appearance.identity_phrase(caller)
        if identity:
            lines.append(
                f"  People you talk to can see you're {identity}, along with your pose and "
                "short description."
            )
        else:
            lines.append(
                "  You have no species or sex set, so people you talk to only see your pose "
                "and short description."
            )
        return lines
