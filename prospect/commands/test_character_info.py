"""
Tests for commands/character_info.py's `score`, `exits` and `save`.

Run with:
    evennia test commands.test_character_info
"""

from django.test import TestCase
from evennia import create_object

from world.actions import QUEST_MODULE_EXCHANGE_KEY
from world.commitments import (
    accept_commitment,
    decline_commitment,
    fulfill_commitment_with_precondition,
    propose_commitment,
)


class _CommandTestBase(TestCase):
    def setUp(self):
        self.room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.other = create_object("typeclasses.rooms.Room", key="Other Room")
        self.actor = create_object("typeclasses.characters.Character", key="Ana Pell", location=self.room)
        self.messages = []
        self.actor.msg = lambda text="", **kw: self.messages.append(text)

    def _run(self, line):
        self.messages.clear()
        self.actor.execute_cmd(line)
        return "\n".join(str(m[0] if isinstance(m, tuple) else m) for m in self.messages)


class ScoreTests(_CommandTestBase):
    def test_shows_name_and_species(self):
        self.actor.db.species = "Kell"
        text = self._run("score")
        self.assertIn("Name: Ana Pell", text)
        self.assertIn("Species: Kell", text)

    def test_no_errands_points_at_asking_for_work(self):
        text = self._run("score")
        self.assertIn("You haven't taken on any errands yet", text)
        self.assertIn("whether they need any help", text)
        self.assertNotIn("Errands:", text)

    def test_the_aliases_testers_typed_all_work(self):
        for alias in ("sc", "stats", "info", "errands", "quests"):
            self.assertIn("Name: Ana Pell", self._run(alias), alias)

    def test_offered_open_and_fulfilled_errands_listed_in_progress_first(self):
        propose_commitment(self.actor, "deliver_parcel")
        accept_commitment(self.actor, "deliver_parcel")
        fulfill_commitment_with_precondition(self.actor, "deliver_parcel", "tarin_os", True)
        propose_commitment(self.actor, "verify_display_revision")
        propose_commitment(self.actor, "hunt_skitters")
        accept_commitment(self.actor, "hunt_skitters")

        text = self._run("score")
        self.assertIn("Errands:", text)
        skitters = text.index("Thin out the skitters for Tarin Os: in progress.")
        display = text.index("Daven Varek's display with Iri Vael: offered")
        parcel = text.index("from Veska Renn to Tarin Os: done.")
        self.assertLess(skitters, display)
        self.assertLess(display, parcel)

    def test_a_declined_errand_is_not_listed(self):
        propose_commitment(self.actor, "tend_planting_bed")
        decline_commitment(self.actor, "tend_planting_bed")
        self.assertIn("You haven't taken on any errands yet", self._run("score"))

    def test_heating_errand_states(self):
        for state, status in (
            ("offered", "offered"),
            ("has_faulty_module", "in progress"),
            ("completed", "done"),
        ):
            self.actor.attributes.add(QUEST_MODULE_EXCHANGE_KEY, state)
            self.assertIn(f"heating module to Tarin Os and bring the working one back: {status}", self._run("score"))

    def test_heating_not_started_is_not_listed(self):
        self.actor.attributes.add(QUEST_MODULE_EXCHANGE_KEY, "not_started")
        self.assertNotIn("heating", self._run("score"))

    def test_no_colour_codes(self):
        # Read aloud by screen readers; nothing may rely on colour.
        propose_commitment(self.actor, "hunt_skitters")
        self.assertNotIn("|", self._run("score"))


class ExitsTests(_CommandTestBase):
    def test_lists_exits(self):
        create_object("typeclasses.exits.Exit", key="north", location=self.room, destination=self.other)
        self.assertIn("north", self._run("exits"))

    def test_no_exits(self):
        self.actor.location = self.other
        self.assertIn("You don't see any way out of here.", self._run("exits"))


class SaveTests(_CommandTestBase):
    def test_says_saving_is_automatic(self):
        self.assertIn("saved automatically", self._run("save"))
