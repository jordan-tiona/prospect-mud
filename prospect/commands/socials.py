"""
Social shortcuts (owner, 2026-10-17): `smile` instead of `emote smiles.`,
and `smile mara` for "Ravis smiles at Mara Voss." Display-only: NPCs
don't react, so a social never costs a model call.

One command whose aliases are the verbs; `socials` on its own lists them.
"""

from commands.command import Command
from world.stealth import reveal_for_speech

# verb: (third person, preposition before a target)
SOCIALS = {
    "smile": ("smiles", "at"),
    "nod": ("nods", "to"),
    "wave": ("waves", "to"),
    "shrug": ("shrugs", "at"),
    "laugh": ("laughs", "with"),
    "grin": ("grins", "at"),
    "bow": ("bows", "to"),
    "sigh": ("sighs", "at"),
    "frown": ("frowns", "at"),
    "wink": ("winks", "at"),
    "clap": ("claps", "for"),
    "cheer": ("cheers", "for"),
}

# Third-person forms work too: "nods" was typed live (2026-10-18) and
# fell through to an unknown command.
VERB_FOR_ALIAS = {verb: verb for verb in SOCIALS}
VERB_FOR_ALIAS.update({third: verb for verb, (third, _prep) in SOCIALS.items()})


class CmdSocial(Command):
    """
    Quick gestures, seen by everyone in the room.

    Usage:
      <social>
      <social> <someone here>

    Socials: smile, nod, wave, shrug, laugh, grin, bow, sigh, frown,
    wink, clap, cheer. For example, "smile" shows "Ravis smiles.", and
    "wave mara" shows "Ravis waves to Mara Voss." For anything else,
    use EMOTE.
    """

    key = "socials"
    aliases = list(VERB_FOR_ALIAS)
    locks = "cmd:all()"
    help_category = "Comms"

    def func(self):
        caller = self.caller
        verb = VERB_FOR_ALIAS.get(self.cmdstring.strip().lower())
        if verb is None:
            caller.msg("Socials: " + ", ".join(SOCIALS) + ". Add someone's name to aim one at them.")
            return

        target = None
        name = self.args.strip()
        if name:
            target = caller.search(name)
            if not target:
                return
            if target == caller:
                target = None

        reveal_for_speech(caller)
        third_person, preposition = SOCIALS[verb]
        location = caller.location
        if target is None:
            caller.msg(f"You {verb}.")
            location.msg_contents(
                "{actor} " + f"{third_person}.", exclude=[caller], from_obj=caller, mapping={"actor": caller}
            )
            return

        caller.msg(f"You {verb} {preposition} {target.get_display_name(caller)}.")
        target.msg(f"{caller.get_display_name(target)} {third_person} {preposition} you.", from_obj=caller)
        location.msg_contents(
            "{actor} " + f"{third_person} {preposition} " + "{target}.",
            exclude=[caller, target],
            from_obj=caller,
            mapping={"actor": caller, "target": target},
        )
