"""
`score`, `exits` and `save` - three commands experienced MUD players
type by reflex. The first external playtest (2026-10-20) logged all of
them as unknown commands: one tester tried `scor`, `escore`, `stats`,
`score` and `info` in a row and then quit, another tried `exits` and
`save`.

`score` is also the playtest's quest log. Nobody was offered an errand
in that playtest, and a tester's feedback was "I don't have any
motivation to do anything"; a list of what you've taken on, plus a
pointer to ask people when it's empty, answers "what am I doing?" in
one place. Plain lines, no table or colour-only meaning, so it reads
the same through a screen reader.
"""

from world.actions import get_quest_state
from world.commitments import get_state_summary

from .command import Command

# Errands in the order the playtest's NPCs usually reach a newcomer.
# Labels from LR-DEV-0016 (Lore). Each ends on the step that closes the
# errand, since a label is the same in every state.
_ERRAND_LABELS = (
    ("verify_display_revision", "Check the number on Daven Varek's display with Iri Vael at the Civic Office, then tell Daven"),
    ("deliver_parcel", "Take the misdelivered parcel from Veska Renn to Tarin Os at the Maintenance Workshop"),
    ("hunt_skitters", "Thin out the skitters for Tarin Os, then go back and tell him"),
    ("tend_planting_bed", "Tend the overgrown planting bed in Old Quarter Square for Iri Vael, then tell her"),
)
_HEATING_LABEL = "Take Mara Voss's heating module to Tarin Os at the workshop and bring a working one back to her"

_IN_PROGRESS = "in progress"
_OFFERED = "offered, waiting for your answer"
_DONE = "done"

_HEATING_STATUS = {
    "offered": _OFFERED,
    "accepted": _IN_PROGRESS,
    "has_faulty_module": _IN_PROGRESS,
    "has_replacement_module": _IN_PROGRESS,
    "completed": _DONE,
}

# Same wording as the medical-bay tannoy's LR-DEV-0014 block.
_NO_ERRANDS = (
    "You haven't taken on any errands yet. People around the Old Quarter "
    "often have small jobs they'd be glad of a hand with: ask the people "
    "you meet whether they need any help, or SAY that you're looking for work."
)

_STATUS_ORDER = {_IN_PROGRESS: 0, _OFFERED: 1, _DONE: 2}


def _commitment_status(summary: str) -> str | None:
    if summary.startswith("open"):
        return _IN_PROGRESS
    if summary.startswith("offered"):
        return _OFFERED
    if summary == "fulfilled":
        return _DONE
    # "not offered", which is also where a declined errand goes back to.
    return None


def errand_lines(character) -> list[str]:
    """One line per errand this character has been offered, taken on or
    finished, in progress first."""
    errands = []
    for commitment_type, label in _ERRAND_LABELS:
        status = _commitment_status(get_state_summary(character, commitment_type))
        if status:
            errands.append((label, status))
    heating = _HEATING_STATUS.get(get_quest_state(character))
    if heating:
        errands.append((_HEATING_LABEL, heating))
    errands.sort(key=lambda errand: _STATUS_ORDER[errand[1]])
    return [f"  {label}: {status}." for label, status in errands]


class CmdScore(Command):
    """
    Show your character and the errands you've taken on.

    Usage:
      score

    Lists your name and species, and every errand you've been offered,
    are working on, or have finished.
    """

    key = "score"
    aliases = ["sc", "stats", "info", "sheet", "errands", "quests"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        lines = [f"Name: {caller.key}"]
        if caller.db.species:
            lines.append(f"Species: {caller.db.species}")
        errands = errand_lines(caller)
        lines.append("")
        if errands:
            lines.append("Errands:")
            lines.extend(errands)
        else:
            lines.append(_NO_ERRANDS)
        caller.msg("\n".join(lines))


class CmdExits(Command):
    """
    List the ways out of where you are.

    Usage:
      exits
    """

    key = "exits"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        line = caller.location.get_display_exits(caller) if caller.location else ""
        caller.msg(line or "You don't see any way out of here.")


class CmdSave(Command):
    """
    Your progress saves on its own.

    Usage:
      save
    """

    key = "save"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        self.caller.msg("There's no need to save: your progress is saved automatically, all the time.")
