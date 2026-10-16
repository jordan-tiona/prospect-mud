"""
Logic for scripted character creation (docs/prospect-initial-
playtest-design-spec.md 3, the project owner's approved cryosleep-
revival script). Pure validation/application helpers live here;
commands/chargen.py holds the actual interactive Command.

The seven playable peoples are canon (CLAUDE.md, design bible
section 5) - a fixed, validated list, not free text.
"""

import re

from evennia import search_tag

from world.content_files import read_content_file, strip_html_comments

SPECIES_CONTENT_FILE = "species.md"

SPECIES_CHOICES = [
    "Kethari",
    "Sylari",
    "Aevyrin",
    "Naevari",
    "Otheryn",
    "Voldren",
    "Neshyr",
]

SEX_CHOICES = ["male", "female"]


def validate_species(raw: str) -> str | None:
    """Match free input against the seven canon peoples, by number
    (1-7, matching the displayed list order) or by name
    (case-insensitive). Returns the canonical name, or None if no
    match."""
    raw = (raw or "").strip()
    if not raw:
        return None

    if raw.isdigit():
        index = int(raw) - 1
        if 0 <= index < len(SPECIES_CHOICES):
            return SPECIES_CHOICES[index]
        return None

    lowered = raw.lower()
    for species in SPECIES_CHOICES:
        if species.lower() == lowered:
            return species
    return None


_APPROVAL_RE = re.compile(r"^\s*approval:\s*(\S+)", re.MULTILINE)
_FIRST_COMMENT_RE = re.compile(r"<!--(.*?)-->", re.DOTALL)
_SECTION_RE = re.compile(r"^## +(.+?)\s*$", re.MULTILINE)
_TITLE_RE = re.compile(r"^# +.*$", re.MULTILINE)


def parse_species_text(raw: str) -> tuple[str, dict[str, str]]:
    """Parse content/species.md into (preface, {species: entry}).

    Only an `approval: Approved` file is shown to players; anything else
    parses to ("", {}). All HTML comments are stripped (CLAUDE.md's
    content-file rule) - species.md's comments hold Provisional anatomy
    notes that must never be displayed. Entries are keyed by their
    `## ` heading, kept only when it's one of SPECIES_CHOICES."""
    header = _FIRST_COMMENT_RE.search(raw or "")
    approval = _APPROVAL_RE.search(header.group(1)) if header else None
    if not approval or approval.group(1) != "Approved":
        return "", {}

    text = _TITLE_RE.sub("", strip_html_comments(raw), count=1)
    parts = _SECTION_RE.split(text)
    preface = parts[0].strip()
    entries = {}
    for heading, body in zip(parts[1::2], parts[2::2]):
        if heading in SPECIES_CHOICES and body.strip():
            entries[heading] = re.sub(r"\n{3,}", "\n\n", body).strip()
    return preface, entries


def load_species_entries() -> tuple[str, dict[str, str]]:
    """(preface, {species: entry}) from content/species.md, read fresh on
    every call so content edits apply without a reload. A missing file
    gives ("", {}) - creation still works, just without descriptions."""
    try:
        raw = read_content_file(SPECIES_CONTENT_FILE)
    except OSError:
        return "", {}
    return parse_species_text(raw)


def validate_sex(raw: str) -> str | None:
    """Match free input against male/female, accepting the first
    letter as a shorthand. Returns "male"/"female", or None."""
    lowered = (raw or "").strip().lower()
    if lowered in ("m", "male"):
        return "male"
    if lowered in ("f", "female"):
        return "female"
    return None


def apply_identity(character, sex: str, species: str) -> None:
    """Record the player's confirmed, permanent identity choices on
    their new character. Called once, right after creation - nothing
    else in this project should ever change these."""
    character.db.sex = sex
    character.db.species = species


def place_in_medical_bay(character) -> None:
    """Move a freshly created character into the Medical Bay
    (world/build_rooms.py), where it becomes fully conscious at the
    end of the revival sequence."""
    from world.build_rooms import BUILD_TAG_CATEGORY as ROOM_TAG_CATEGORY

    matches = search_tag(key="medical_bay", category=ROOM_TAG_CATEGORY)
    if not matches:
        raise RuntimeError("Room tagged 'medical_bay' not found. Run world.build_rooms.build() first.")
    character.move_to(matches[0], quiet=True, move_type="teleport")
