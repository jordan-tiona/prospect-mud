"""
Scripted character creation - "First Awakening" (project-owner +
ChatGPT collaborative script, uploads/1dbe8f29-prospect-character-
creation-opening-expanded-v2.md, approved 2026-10-14; supersedes the
shorter script this module held before). Replaces Evennia's default
one-line `create <name> <password>` unloggedin command with a
cinematic, non-LLM Q&A sequence collecting identity (name, sex,
species) before a password - commands/default_cmdsets.py's
UnloggedinCmdSet adds this over the default by key, same pattern as
every other command override in this project.

Reuses Account.create() for the actual account/character creation and
its own username/password validation (world/chargen.py's docstring
has more on the reuse rationale) - this command only adds the
narrated Q&A in front of it and the one-time species/sex/location
setup after. Passwords are typed directly into this flow's own
prompts and handed straight to Account.create(); Evennia's own
default `create` command accepts a password the same way (in plain
text, not echo-masked) - this doesn't change that. Passwords never
reach world/conversation_log.py or any NPC-facing code path.

Pacing: a generator-based Command's `func()` can `yield` a plain
number instead of a prompt string - evennia.commands.cmdhandler's
`_progressive_cmd_run` reads that as a non-blocking delay (not a
request for input) and resumes the generator on its own after that
many seconds (confirmed against Evennia's source: fractional seconds
work fine, it's just handed to `utils.delay`). Yielding a *string*
instead displays it and waits for the player's response - also
confirmed against source (`_progressive_cmd_run` dispatches on
`isinstance(value, (int, float))` vs `isinstance(value, str)`).
`_block()` below sends one or more already-script's `[DISPLAY
TOGETHER]` lines as a single message (so multi-line beats appear with
no artificial delay between them, matching the script's explicit
"accumulate, don't drip-feed one line per NPC-reply pause" framing),
then optionally yields the beat's own pause length.

Two deliberate departures from a literal reading of the script, both
engineering calls rather than content:
- The player-facing wording for *which* field to correct, after
  declining the identity summary, isn't in the source script (it only
  says "return only to the relevant earlier fields") - this module
  adds a short "name/sex/species/all" sub-prompt to do that. Everything
  the recovery voice itself says is transcribed from the source
  document as written.
- "Allow players to advance a pause early" and "skip the cinematic on
  repeat attempts" (script's implementation-boundary note 7) aren't
  implemented: Evennia's generator-command mechanism offers either a
  timed, non-interactive delay (`yield <number>`) or an indefinite
  wait for input (`yield <string>`), not a race between the two, so a
  pause can't be interrupted by an early keypress without hooking the
  session's input queue directly - flagged as a known gap rather than
  attempted here.

Color: `|c"..."|n` (bright cyan) for every line the recovery voice
speaks, matching the convention already used for NPC/player speech
elsewhere (commands/say.py). `|W...|n` (gray) for narrative prose -
matching typeclasses/rooms.py's room-description color - to visually
separate "what's happening to you" from "what the voice says
to you". The faux `Darkness` title uses `|Y...|n`, the same
dark-yellow room-title color as a real room name. Plain, uncolored
text for system prompts/summaries/errors, same as before.
"""

from django.conf import settings
from evennia.utils import class_from_module, utils

from typeclasses.objects import indent_paragraphs
from world.chargen import (
    SPECIES_CHOICES,
    account_name_for,
    apply_identity,
    character_name_taken,
    load_species_entries,
    load_species_groups,
    place_in_medical_bay,
    validate_character_name,
    validate_sex,
    validate_species,
)
from world.disclosure import (
    AGREE_PROMPT,
    AGREE_WORDS,
    DISCLOSURE_TEXT,
    QUIT_WORDS,
    WELCOME_TEXT,
    agreement_record,
)
from world.invites import announce_registration, consume_code, is_valid_code, record_registration
from world.profanity import name_is_profane

COMMAND_DEFAULT_CLASS = utils.class_from_module(settings.COMMAND_DEFAULT_CLASS)


def _species_line(name):
    return f"{SPECIES_CHOICES.index(name) + 1}. {name}"


def species_menu(groups, with_notes):
    """The species picker. Without groups (content/species.md missing,
    unapproved, or out of step with SPECIES_CHOICES) it's the flat
    numbered list. With them (LR-LORE-0002) each group gets a heading
    in the room-title color, its note in the description color when
    with_notes, and its members indented below - numbered by
    SPECIES_CHOICES either way, so picking by number never changes."""
    if not groups:
        return "\n".join(f"  {_species_line(name)}" for name in SPECIES_CHOICES)
    blocks = []
    for title, note, names in groups:
        lines = [f"  |Y{title}|n"]
        if with_notes and note:
            lines.append(f"  |W{note}|n")
        lines.extend(f"    {_species_line(name)}" for name in names)
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _narration(text):
    """Narrative prose (the script's *italics*) - gray, not quoted."""
    return f"|W{text}|n"


def _voice(text):
    """A line the recovery computer actually says - bright cyan, quoted."""
    return f'|c"{text}"|n|n'


def _block(session, *lines, pause=None):
    """
    Send one `[DISPLAY TOGETHER]` beat: `lines` (each already colored
    by `_narration`/`_voice`, or plain for uncolored system text) are
    joined with a blank line between them and sent as a single
    message, so they render with no artificial delay between them but
    still read as visually separate lines. A trailing blank line is
    also appended after the whole block (project owner, 2026-10-14:
    confirmed live over Mudlet - consecutive blocks are separate
    `session.msg()` sends, and a client starts each one on its own
    fresh line but adds no gap of its own, so without this the next
    block/prompt runs on immediately with no breathing room at all).
    `pause`, if given, is the non-blocking `yield` afterward - see the
    module docstring's "Pacing" note.
    """
    session.msg("\n\n".join(lines) + "\n")
    if pause:
        yield pause


def _species_entry(name, description):
    """One people's entry, laid out like a room (typeclasses/rooms.py):
    dark-yellow title, then the gray, paragraph-indented description,
    with a blank line between them and a trailing blank line before the
    Select prompt. Further per-species details (size, lifespan, ...) can
    slot in below the description in their own colors."""
    lines = [f"|Y{name}|n"]
    if description:
        lines.append(f"|W{indent_paragraphs(description)}|n")
    return "\n\n".join(lines) + "\n"


def _title(session, title):
    """The faux `Darkness` opening title: same dark-yellow styling as
    a real room name (typeclasses/rooms.py), but not a real room -
    no exits, no room_id, nothing to `look` at afterward."""
    session.msg(f"|Y{title}|n")


class CmdScriptedCreate(COMMAND_DEFAULT_CLASS):
    """
    create a new character

    Usage (at login screen):
      create

    A guided, in-world sequence for creating a new character: your
    name, sex, and species, followed by a password to protect your
    account. If you already have a character, use `connect` instead.
    """

    key = "create"
    aliases = ["cre", "cr"]
    locks = "cmd:all()"
    arg_regex = r"\s.*?|$"

    def at_pre_cmd(self):
        if not settings.NEW_ACCOUNT_REGISTRATION_ENABLED:
            self.msg("Registration is currently disabled.")
            return True
        return super().at_pre_cmd()

    def func(self):
        session = self.caller

        code = None
        if settings.INVITE_ONLY_REGISTRATION:
            code = yield from self._ask_invite_code(session)
        agreed = yield from self._ask_disclosure(session)
        if not agreed:
            return
        if code is not None and not consume_code(code, used_by=session.address):
            # Used by someone else while this player was reading.
            session.msg("|RThat code has just been used. Please ask for a new one.|n")
            return

        yield from self._scene_1(session)
        yield from self._scene_2(session)

        name = yield from self._ask_name(session)
        sex = yield from self._ask_sex(session)
        species = yield from self._ask_species(session)

        while True:
            yield from self._show_summary(session, name, sex, species)
            action = yield from self._confirm_or_correct(session)
            if action == "confirm":
                break
            target = yield from self._ask_correction_target(session)
            if target in ("name", "all"):
                name = yield from self._ask_name(session)
            if target in ("sex", "all"):
                sex = yield from self._ask_sex(session)
            if target in ("species", "all"):
                species = yield from self._ask_species(session)

        yield from _block(
            session,
            _voice("Identity record confirmed."),
            _voice(
                "Your responses indicate that you are awake, attentive, and able to follow "
                "this procedure. The medical technician will conduct any further assessment "
                "that's needed."
            ),
            pause=3.6,
        )

        password = yield from self._ask_password(session, name)

        Account = class_from_module(settings.BASE_ACCOUNT_TYPECLASS)
        account, errors = Account.create(
            username=account_name_for(name), password=password, ip=session.address, session=session
        )
        if not account:
            session.msg("|R%s|n" % "\n".join(errors))
            return

        character = account.db._last_puppet
        if character is None and account.characters:
            character = account.characters.all()[0]
        account.db.disclosure_agreed = agreed
        if character is not None and character.key != name:
            # Evennia names the character after the account; players
            # see the name as given, space and all.
            character.key = name
        if character is not None:
            try:
                apply_identity(character, sex=sex, species=species)
                place_in_medical_bay(character)
            except Exception:
                from evennia.utils import logger

                logger.log_trace()
                session.msg(
                    "Something went wrong finishing your revival - an admin has been notified. "
                    "You can still log in; a staff member will sort out your starting location."
                )
        if code is not None:
            account.db.invite_code = code.strip().upper()
            record_registration(code, account.key, character.key if character is not None else name)
            announce_registration(code)

        yield from self._scene_5(session, name)

        session.sessionhandler.login(session, account)

    # -- Invite gate (plain administrative check, not part of the ------
    # -- authored "First Awakening" script - see world/invites.py) -----

    def _ask_invite_code(self, session):
        """Returns the code once it checks out. It's only used up after
        the disclosure is agreed to (func)."""
        while True:
            raw = yield "This playtest is invite-only. Please enter your invite code:"
            if is_valid_code(raw):
                return raw
            session.msg("|RThat code isn't valid, or has already been used.|n")

    def _ask_disclosure(self, session):
        """world/disclosure.py: returns the agreement record, or None if
        the player declined."""
        # One message, so the blank line between them shows in every client.
        session.msg(WELCOME_TEXT + "\n\n" + DISCLOSURE_TEXT)
        while True:
            answer = (yield AGREE_PROMPT).strip().lower()
            if answer in AGREE_WORDS:
                return agreement_record()
            if answer in QUIT_WORDS:
                session.msg(
                    "No problem. Nothing has been created, and your invite code is still "
                    "unused if you change your mind."
                )
                return None

    # -- Scene 1: the edge of consciousness -----------------------------

    def _scene_1(self, session):
        _title(session, "Darkness")
        yield 2.5

        yield from _block(
            session,
            _narration("At first, there is nothing."),
            _narration(
                "Then a sound, faint and regular. A low mechanical hum. Somewhere beyond it, "
                "a soft sequence of tones repeats at measured intervals."
            ),
            _narration(
                "You become aware of a distant pressure around your body, of warmth returning "
                "to places that had forgotten what warmth felt like. There is no clear sense of "
                "time. For a moment, even the difference between sleeping and waking seems "
                "uncertain."
            ),
            pause=3.8,
        )

        yield from _block(
            session,
            _narration("The tones stop. A voice takes their place, close and perfectly clear."),
            _voice("Good morning."),
            _voice(
                "Please remain calm. You are emerging from cryogenic suspension. Some "
                "disorientation is expected during recovery."
            ),
            pause=3.0,
        )

        yield from _block(
            session,
            _voice(
                "You may notice a delay between thinking about movement and being able to "
                "move. This is normal. Please do not attempt to stand until the revival "
                "procedure is complete."
            ),
            _voice("Your recovery is progressing within acceptable parameters."),
            pause=3.4,
        )

        yield from _block(
            session,
            _narration(
                "You try to place the voice. It has no obvious direction, no breath behind it, "
                "and no hesitation between words. It simply waits for you to understand."
            ),
            _voice(
                "I am the recovery system's automated attendant. I will guide you through the "
                "final steps."
            ),
            _voice("You do not need to remember anything before answering my questions."),
            pause=3.6,
        )

    # -- Scene 2: a place, and a name for it -----------------------------

    def _scene_2(self, session):
        yield from _block(
            session,
            _voice(
                "For your orientation: you are aboard Elsewhere, an orbital habitat currently "
                "in orbit around the planet Prospect."
            ),
            _voice(
                "You are in a medical recovery facility. A member of the staff will be "
                "available when the chamber opens."
            ),
            pause=4.5,
        )

        yield from _block(
            session,
            _voice(
                "If those names are unfamiliar, that is not a problem. You may ask the "
                "attending technician about your surroundings once you are fully awake."
            ),
            _voice(
                "First, however, I need to complete your identity record and confirm that you "
                "are able to understand and respond to simple questions."
            ),
            pause=2.8,
        )

        session.msg(_voice("We'll begin with something straightforward."))

    # -- Scene 3: identity verification -----------------------------------

    def _ask_name(self, session):
        Account = class_from_module(settings.BASE_ACCOUNT_TYPECLASS)
        while True:
            raw = yield _voice("What is your name?")
            raw = Account.normalize_username((raw or "").strip())
            if not raw:
                session.msg(_voice("I didn't catch that. What is your name?"))
                continue
            name = validate_character_name(raw)
            if name is None:
                session.msg(_voice("Please give your name in letters only, with at most one space."))
                continue
            if name_is_profane(name):
                session.msg(_voice("I can't record that name. Please give a different one."))
                continue
            username = account_name_for(name)
            valid, errors = Account.validate_username(username)
            if valid and character_name_taken(name):
                valid, errors = False, ["Sorry, there is already a character with that name."]
            if not valid:
                session.msg("|R%s|n" % "\n".join(errors))
                continue
            session.msg(_voice(f"Thank you, {name}. I've recorded that."))
            if username != name:
                session.msg(f"(Your account will be created as {username}. Use that name to log in.)")
            yield 2.7
            return name

    def _ask_sex(self, session):
        session.msg(_voice("Now, please confirm your sex for the record."))
        while True:
            raw = yield _voice("Male or female?")
            sex = validate_sex(raw)
            if sex is None:
                session.msg(_voice("I need either 'male' or 'female'."))
                continue
            session.msg(_voice("Understood."))
            yield 2.7
            return sex

    def _ask_species(self, session):
        """Pick a people: choosing one shows its content/species.md entry
        and asks to confirm; 'no' goes back to the list. The shared
        preface is shown once per creation, not again on a correction,
        and so are the group notes: the first menu carries them, every
        later one is headings and names only (owner's choice, 2026-10-17)."""
        preface, entries = load_species_entries()
        groups = load_species_groups()
        session.msg(
            _voice(
                "Next is your species. You may find the terminology unfamiliar, but there is "
                "no need to hurry. Review the available entries before making your selection."
            )
        )
        if preface and not getattr(self, "_species_preface_shown", False):
            session.msg(f"|W{indent_paragraphs(preface)}|n\n")
            self._species_preface_shown = True
        while True:
            with_notes = not getattr(self, "_species_notes_shown", False)
            self._species_notes_shown = True
            raw = yield species_menu(groups, with_notes)
            species = validate_species(raw)
            if species is None:
                session.msg(
                    _voice(
                        "I didn't recognize that. Please choose one of the listed peoples, by "
                        "name or number."
                    )
                )
                continue
            session.msg(_species_entry(species, entries.get(species)))
            if not (yield from self._confirm_species(session, species)):
                continue
            session.msg(_voice(f"{species}. Thank you."))
            yield 3.1
            return species

    def _confirm_species(self, session, species):
        while True:
            raw = yield f"Select {species}? [Yes/No]"
            answer = (raw or "").strip().lower()
            if answer in ("yes", "y"):
                return True
            if answer in ("no", "n"):
                return False
            session.msg("|RPlease answer 'yes' or 'no'.|n")

    def _show_summary(self, session, name, sex, species):
        yield from _block(
            session,
            _voice("Your answers are being accepted correctly. That's a good sign."),
            _voice(
                "I'll repeat the information once, so you can check it before we finalize the "
                "record."
            ),
            f"  Name: {name}\n  Sex: {sex.capitalize()}\n  Species: {species}",
            pause=2.8,
        )

    def _confirm_or_correct(self, session):
        yield from _block(
            session,
            _voice(
                "Is everything correct? Your name, sex, and species will be permanent "
                "once confirmed."
            ),
            _voice("If something is wrong, this is the time to change it."),
        )
        while True:
            raw = yield "Confirm, or make corrections? [Confirm/Correct]"
            answer = (raw or "").strip().lower()
            if answer in ("confirm", "confirmed", "yes", "y"):
                return "confirm"
            if answer in ("correct", "corrections", "no", "n"):
                return "correct"
            session.msg("|RPlease answer 'confirm' or 'correct'.|n")

    def _ask_correction_target(self, session):
        while True:
            raw = yield "What would you like to change? [Name/Sex/Species/All]"
            answer = (raw or "").strip().lower()
            if answer in ("name", "sex", "species", "all"):
                return answer
            session.msg("|RPlease choose one of: name, sex, species, all.|n")

    # -- Scene 4: stasis credentials ---------------------------------------

    def _ask_password(self, session, name):
        Account = class_from_module(settings.BASE_ACCOUNT_TYPECLASS)

        yield from _block(
            session,
            _voice("There is one final administrative step before the chamber opens."),
            _voice(
                "When you are away, your connection may enter a protected state called "
                "stasis. While in that state, you cannot interact with your surroundings."
            ),
            pause=3.0,
        )

        yield from _block(
            session,
            _voice(
                "To restore access when you return, you will need a private authentication "
                "credential. You can think of it as a key that belongs only to you."
            ),
            _voice(
                "Please choose a password now. Do not share it with other residents or "
                "medical staff."
            ),
        )

        while True:
            password = yield _voice("Password:")
            valid, error = Account.validate_password(password, account=Account(username=account_name_for(name)))
            if not valid:
                session.msg(
                    "|R%s|n" % "\n".join(error.messages if error else ["That password isn't valid."])
                )
                continue
            confirm = yield _voice("Please confirm your password:")
            if confirm != password:
                session.msg(_voice("Those passwords didn't match. Let's try again."))
                continue
            break

        yield from _block(
            session,
            _voice("Credentials accepted. Your access is now protected."),
            _voice("You won't need to repeat the identity questions each time you return."),
            pause=3.4,
        )
        return password

    # -- Scene 5: the chamber opens -----------------------------------------

    def _scene_5(self, session, name):
        yield from _block(
            session,
            _narration(
                "The mechanical hum changes pitch. A subtle vibration travels through "
                "whatever has been supporting you. For the first time, you notice the weight "
                "of your own hands."
            ),
            _voice(f"Thank you, {name}. The revival procedure is complete."),
            _voice("Please remain still while the recovery chamber opens."),
            pause=3.8,
        )

        yield from _block(
            session,
            _narration(
                "Something releases with a soft click. Air moves across your face. The "
                "pressure around you eases, and the quiet machinery beyond the chamber "
                "becomes a little louder."
            ),
            pause=3.3,
        )

        yield from _block(
            session,
            _voice("Welcome to Elsewhere."),
            _voice("A medical technician is nearby if you have questions. Take your time getting up."),
            pause=4.3,
        )

        session.msg(_narration("Your eyes open."))
