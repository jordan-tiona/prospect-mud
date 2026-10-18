"""
Tests for world/chargen.py: the pure identity-validation/application
helpers behind the scripted character-creation command
(commands/chargen.py). The interactive Q&A flow itself isn't covered
here - these are the pieces a silent bug could actually corrupt state
in (an unvalidated species, a character stranded outside the Medical
Bay).

Run with:
    evennia test world
"""

from django.test import TestCase
from evennia import create_object

from world.build_rooms import build as build_rooms
from world.chargen import (
    SPECIES_CHOICES,
    account_name_for,
    apply_identity,
    character_name_taken,
    load_species_entries,
    load_species_groups,
    parse_species_groups,
    parse_species_text,
    login_username,
    place_in_medical_bay,
    validate_character_name,
    validate_sex,
    validate_species,
)

_SPECIES_FIXTURE = """<!--
content_id: species_descriptions
approval: {approval}
-->

# Title line

<!-- a note -->

Preface text.

## Kell

Entry one.

<!-- Provisional note that must not show -->

## Drask

Entry two.

Second paragraph.

## Not A Listed People

Ignored.
"""


class SpeciesEntriesTests(TestCase):
    def test_parses_preface_and_entries_without_comments(self):
        preface, entries = parse_species_text(_SPECIES_FIXTURE.format(approval="Approved"))
        self.assertEqual(preface, "Preface text.")
        self.assertEqual(entries, {"Kell": "Entry one.", "Drask": "Entry two.\n\nSecond paragraph."})

    def test_unapproved_file_shows_nothing(self):
        self.assertEqual(parse_species_text(_SPECIES_FIXTURE.format(approval="Draft")), ("", {}))
        self.assertEqual(parse_species_text("## Kell\n\nNo header."), ("", {}))

    def test_real_file_covers_every_people_with_no_comment_text(self):
        preface, entries = load_species_entries()
        self.assertTrue(preface)
        self.assertEqual(sorted(entries), sorted(SPECIES_CHOICES))
        for text in [preface, *entries.values()]:
            self.assertNotIn("<!--", text)
            self.assertNotIn("-->", text)

    def test_group_headings_are_not_entries(self):
        _preface, entries = parse_species_text(_GROUPED_FIXTURE.format(approval="Approved"))
        self.assertEqual(sorted(entries), sorted(SPECIES_CHOICES))


# LR-LORE-0002's shape: non-species `## ` headings group the species
# headings that follow them. Built from SPECIES_CHOICES so the fixture
# can't drift from the code's order.
_GROUPED_FIXTURE = (
    "<!--\napproval: {approval}\n-->\n\n# Title\n\nPreface.\n\n"
    "## First group\n\nFirst note. <!-- hidden -->\n\n"
    + "".join(f"## {name}\n\nAbout {name}.\n\n" for name in SPECIES_CHOICES[:3])
    + "## Second group\n\nSecond note.\n\n"
    + "".join(f"## {name}\n\nAbout {name}.\n\n" for name in SPECIES_CHOICES[3:])
)


class SpeciesGroupsTests(TestCase):
    def test_parses_groups_in_order_with_notes(self):
        groups = parse_species_groups(_GROUPED_FIXTURE.format(approval="Approved"))
        self.assertEqual(
            groups,
            [
                ("First group", "First note.", SPECIES_CHOICES[:3]),
                ("Second group", "Second note.", SPECIES_CHOICES[3:]),
            ],
        )

    def test_unapproved_file_has_no_groups(self):
        self.assertEqual(parse_species_groups(_GROUPED_FIXTURE.format(approval="Draft")), [])

    def test_species_before_any_group_falls_back_to_flat(self):
        # The original ungrouped fixture: Kell and Drask with no group heading.
        self.assertEqual(parse_species_groups(_SPECIES_FIXTURE.format(approval="Approved")), [])

    def test_order_out_of_step_with_species_choices_falls_back_to_flat(self):
        first, second = SPECIES_CHOICES[0], SPECIES_CHOICES[1]
        swapped = (
            _GROUPED_FIXTURE.format(approval="Approved")
            .replace(f"## {first}\n", "## @@\n")
            .replace(f"## {second}\n", f"## {first}\n")
            .replace("## @@\n", f"## {second}\n")
        )
        self.assertEqual(parse_species_groups(swapped), [])

    def test_missing_people_falls_back_to_flat(self):
        last = SPECIES_CHOICES[-1]
        raw = _GROUPED_FIXTURE.format(approval="Approved").replace(f"## {last}\n\nAbout {last}.\n\n", "")
        self.assertEqual(parse_species_groups(raw), [])

    def test_empty_group_falls_back_to_flat(self):
        raw = _GROUPED_FIXTURE.format(approval="Approved") + "## Empty group\n\nNobody here.\n"
        self.assertEqual(parse_species_groups(raw), [])

    def test_real_file_groups_cover_every_people(self):
        groups = load_species_groups()
        self.assertEqual(len(groups), 3)
        self.assertEqual([name for _t, _n, names in groups for name in names], SPECIES_CHOICES)
        for title, note, _names in groups:
            self.assertTrue(note, title)
            self.assertNotIn("<!--", note)


class ValidateSpeciesTests(TestCase):
    def test_accepts_every_canon_name_case_insensitively(self):
        for species in SPECIES_CHOICES:
            self.assertEqual(validate_species(species.upper()), species)
            self.assertEqual(validate_species(species.lower()), species)

    def test_accepts_list_number(self):
        for i, species in enumerate(SPECIES_CHOICES, start=1):
            self.assertEqual(validate_species(str(i)), species)

    def test_rejects_out_of_range_number(self):
        self.assertIsNone(validate_species("0"))
        self.assertIsNone(validate_species(str(len(SPECIES_CHOICES) + 1)))

    def test_rejects_unknown_name(self):
        self.assertIsNone(validate_species("Human"))

    def test_rejects_empty(self):
        self.assertIsNone(validate_species(""))
        self.assertIsNone(validate_species(None))


class ValidateSexTests(TestCase):
    def test_accepts_full_words_and_initials(self):
        self.assertEqual(validate_sex("male"), "male")
        self.assertEqual(validate_sex("MALE"), "male")
        self.assertEqual(validate_sex("m"), "male")
        self.assertEqual(validate_sex("female"), "female")
        self.assertEqual(validate_sex("F"), "female")

    def test_rejects_anything_else(self):
        self.assertIsNone(validate_sex("other"))
        self.assertIsNone(validate_sex(""))
        self.assertIsNone(validate_sex(None))


class CharacterNameTests(TestCase):
    # Owner, 2026-10-18: letters only, at most one space.
    def test_accepts_one_or_two_parts_and_capitalizes(self):
        self.assertEqual(validate_character_name("Jordan"), "Jordan")
        self.assertEqual(validate_character_name("jordan tiona"), "Jordan Tiona")
        self.assertEqual(validate_character_name("  Jordan  "), "Jordan")

    def test_leaves_the_rest_of_each_part_as_typed(self):
        self.assertEqual(validate_character_name("deVries"), "DeVries")

    def test_rejects_digits_symbols_and_extra_spaces(self):
        for bad in ("Jordan2", "J@ck", "O'Brien", "Jordan_Tiona", "Jordan-Tiona",
                    "Jordan  Tiona", "Ann Marie Tiona", "Jördan", "", None):
            self.assertIsNone(validate_character_name(bad), bad)

    def test_account_name_swaps_the_space_for_an_underscore(self):
        self.assertEqual(account_name_for("Jordan Tiona"), "Jordan_Tiona")
        self.assertEqual(account_name_for("Jordan"), "Jordan")

    def test_character_name_taken_ignores_case(self):
        room = create_object("typeclasses.rooms.Room", key="Room")
        create_object("typeclasses.characters.Character", key="Jordan Tiona", location=room, home=room)
        self.assertTrue(character_name_taken("jordan tiona"))
        self.assertFalse(character_name_taken("Jordan"))


class LoginUsernameTests(TestCase):
    def test_a_space_finds_the_underscore_account(self):
        self.assertEqual(login_username("Jordan Tiona"), "Jordan_Tiona")

    def test_no_space_is_unchanged(self):
        self.assertEqual(login_username("Jordan"), "Jordan")

    def test_an_old_account_with_a_real_space_still_matches(self):
        from evennia.utils.create import create_account

        create_account("Ravis Vardur", None, "SomePass123!")
        self.assertEqual(login_username("ravis vardur"), "ravis vardur")


class ApplyIdentityTests(TestCase):
    def setUp(self):
        self.rooms = build_rooms()

    def test_sets_both_fields(self):
        character = create_object(
            "typeclasses.characters.Character", key="Tester", location=self.rooms["medical_bay"]
        )
        apply_identity(character, sex="female", species="Kell")
        self.assertEqual(character.db.sex, "female")
        self.assertEqual(character.db.species, "Kell")


class MigrateLegacySpeciesTests(TestCase):
    def setUp(self):
        room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.old = create_object("typeclasses.characters.Character", key="Old", location=room)
        self.old.db.species = "Neshyr"
        self.current = create_object("typeclasses.characters.Character", key="Current", location=room)
        self.current.db.species = "Voldren"
        self.unset = create_object("typeclasses.characters.Character", key="Unset", location=room)

    def test_remaps_only_old_names(self):
        from world.chargen import migrate_legacy_species

        self.assertEqual(migrate_legacy_species(), [("Old", "Neshyr", "Selk")])
        self.assertEqual(self.old.db.species, "Selk")
        self.assertEqual(self.current.db.species, "Voldren")
        self.assertIsNone(self.unset.db.species)

    def test_is_idempotent(self):
        from world.chargen import migrate_legacy_species

        migrate_legacy_species()
        self.assertEqual(migrate_legacy_species(), [])

    def test_every_new_name_is_a_current_choice(self):
        from world.chargen import LEGACY_SPECIES_NAMES, SPECIES_CHOICES

        self.assertTrue(set(LEGACY_SPECIES_NAMES.values()) <= set(SPECIES_CHOICES))
        self.assertFalse(set(LEGACY_SPECIES_NAMES) & set(SPECIES_CHOICES))


class PlaceInMedicalBayTests(TestCase):
    def setUp(self):
        self.rooms = build_rooms()

    def test_moves_character_into_medical_bay(self):
        character = create_object(
            "typeclasses.characters.Character", key="Tester", location=self.rooms["old_quarter_square"]
        )
        place_in_medical_bay(character)
        self.assertEqual(character.location, self.rooms["medical_bay"])
