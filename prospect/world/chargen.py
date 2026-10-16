"""
Logic for scripted character creation (docs/prospect-initial-
playtest-design-spec.md 3, the project owner's approved cryosleep-
revival script). Pure validation/application helpers live here;
commands/chargen.py holds the actual interactive Command.

The seven playable peoples are canon (CLAUDE.md, design bible
section 5) - a fixed, validated list, not free text.
"""

from evennia import search_tag

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
