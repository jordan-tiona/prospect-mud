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
    place_in_medical_bay,
    validate_sex,
    validate_species,
)


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
        apply_identity(character, sex="female", species="Kethari")
        self.assertEqual(character.db.sex, "female")
        self.assertEqual(character.db.species, "Kethari")


class PlaceInMedicalBayTests(TestCase):
    def setUp(self):
        self.rooms = build_rooms()

    def test_moves_character_into_medical_bay(self):
        character = create_object(
            "typeclasses.characters.Character", key="Tester", location=self.rooms["old_quarter_square"]
        )
        place_in_medical_bay(character)
        self.assertEqual(character.location, self.rooms["medical_bay"])
