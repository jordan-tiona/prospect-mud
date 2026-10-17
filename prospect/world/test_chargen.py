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
    apply_identity,
    load_species_entries,
    parse_species_text,
    place_in_medical_bay,
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
