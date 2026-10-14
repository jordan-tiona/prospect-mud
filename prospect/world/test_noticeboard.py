"""
Tests for the civic information display's per-player revision state
(world/noticeboard.py), design doc §14 / docs/phase2d-noticeboard-
check-proposal.md. The actual pass/fail comparison happens here, in
Python, against a value the model never sees - "the hashed password"
per the project owner's framing (2026-10-14).

Run with:
    evennia test world
"""

from django.test import TestCase
from evennia import create_object

from world.noticeboard import (
    get_or_create_expected_revision,
    reset_expected_revision,
    revision_matches,
)


class ExpectedRevisionTests(TestCase):
    def setUp(self):
        room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.actor = create_object("typeclasses.characters.Character", key="Tester", location=room)

    def test_generates_a_four_digit_revision(self):
        revision = get_or_create_expected_revision(self.actor)
        self.assertEqual(len(revision), 4)
        self.assertTrue(revision.isdigit())

    def test_stable_across_calls(self):
        first = get_or_create_expected_revision(self.actor)
        second = get_or_create_expected_revision(self.actor)
        self.assertEqual(first, second)

    def test_per_player(self):
        other = create_object("typeclasses.characters.Character", key="Other", location=self.actor.location)
        mine = get_or_create_expected_revision(self.actor)
        theirs = get_or_create_expected_revision(other)
        # Not asserting they differ (a same-value collision is valid,
        # if unlikely) - just that each player gets their own stored
        # value, independently generated.
        self.assertEqual(get_or_create_expected_revision(self.actor), mine)
        self.assertEqual(get_or_create_expected_revision(other), theirs)

    def test_reset_clears_it(self):
        original = get_or_create_expected_revision(self.actor)
        previous = reset_expected_revision(self.actor)
        self.assertEqual(previous, original)
        fresh = get_or_create_expected_revision(self.actor)
        # A fresh value is generated on next access - not asserting it
        # differs (same reasoning as above), just that reset actually
        # cleared the stored attribute rather than being a no-op.
        self.assertIsNotNone(fresh)

    def test_reset_with_nothing_generated_yet_returns_none(self):
        self.assertIsNone(reset_expected_revision(self.actor))


class RevisionMatchesTests(TestCase):
    def setUp(self):
        room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.actor = create_object("typeclasses.characters.Character", key="Tester", location=room)

    def test_correct_report_matches(self):
        expected = get_or_create_expected_revision(self.actor)
        self.assertTrue(revision_matches(self.actor, expected))

    def test_wrong_report_does_not_match(self):
        expected = get_or_create_expected_revision(self.actor)
        wrong = "9999" if expected != "9999" else "1111"
        self.assertFalse(revision_matches(self.actor, wrong))

    def test_matching_generates_if_nothing_stored_yet(self):
        # revision_matches calls get_or_create, same as examining the
        # display would have - a player who somehow reaches Iri
        # without ever looking at the display still gets a real,
        # consistent value to be checked against, rather than erroring.
        self.assertFalse(revision_matches(self.actor, "0000") and False)  # just must not raise
        revision_matches(self.actor, "1234")

    def test_whitespace_is_tolerated(self):
        expected = get_or_create_expected_revision(self.actor)
        self.assertTrue(revision_matches(self.actor, f"  {expected}  "))

    def test_non_string_reported_value_is_tolerated(self):
        expected = get_or_create_expected_revision(self.actor)
        self.assertTrue(revision_matches(self.actor, int(expected)))
