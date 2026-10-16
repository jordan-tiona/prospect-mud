"""
`bug`/`feedback`: a player's own explicit flag that something's wrong
or worth knowing, written as its own marker rather than left to be
inferred from other activity (game-plan.md 6's Week 0 item 4). Read
by playtest-review passes (game-plan.md 5's "Explicit feedback:
everything a player sends with the `bug`/`feedback` command").

One command, two keys - `category` in the logged record is whichever
word the player actually typed, not a fixed label, so a review pass
can tell a reported bug from general feedback without parsing the
message text.
"""

from commands.command import Command
from world.session_log import log_feedback, session_id_for


class CmdFeedback(Command):
    """
    Flag a bug or leave feedback for the project owner to review
    later. Writes a timestamped marker into the session log; nothing
    else about the game changes.

    Usage:
      bug <what went wrong>
      feedback <what you think>
    """

    key = "bug"
    aliases = ["feedback"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        message = self.args.strip()
        if not message:
            caller.msg(f"Usage: {self.cmdstring} <your message>")
            return

        category = "bug" if self.cmdstring.lower() == "bug" else "feedback"
        log_feedback(
            session_id=session_id_for(caller),
            actor_key=caller.key,
            actor_dbref=caller.dbref,
            location=caller.location.key if caller.location else "",
            category=category,
            message=message,
        )
        caller.msg("Thanks - that's been logged for review.")
