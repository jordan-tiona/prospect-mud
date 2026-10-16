"""
Tests for the Civic Office's skitter ledger builder
(world/build_skitter_ledger.py) and its per-looker count
(typeclasses.objects.SkitterLedgerObject).

Run with:
    evennia test world
"""

from django.test import TestCase
from evennia import create_object, search_tag

from world.build_rooms import build as build_rooms
from world.build_skitter_ledger import LEDGER_PROP_ID, LEDGER_TAG_CATEGORY, build
from world.skitters import bank_kills, record_kill


class BuildSkitterLedgerTests(TestCase):
    def setUp(self):
        self.rooms = build_rooms()
        self.actor = create_object(
            "typeclasses.characters.Character", key="Hunter", location=self.rooms["civic_office"]
        )

    def test_builds_the_ledger_in_the_civic_office(self):
        ledger = build()
        self.assertEqual(ledger.location, self.rooms["civic_office"])
        self.assertTrue(ledger.is_typeclass("typeclasses.objects.SkitterLedgerObject", exact=True))

    def test_rerun_does_not_duplicate(self):
        build()
        build()
        self.assertEqual(len(search_tag(key=LEDGER_PROP_ID, category=LEDGER_TAG_CATEGORY)), 1)

    def test_not_pickable(self):
        ledger = build()
        self.assertFalse(ledger.access(None, "get"))

    def test_shows_nothing_logged_for_a_new_player(self):
        ledger = build()
        self.assertIn("nothing logged under your name", ledger.get_display_desc(self.actor))

    def test_shows_only_the_logged_count_not_raw_kills(self):
        ledger = build()
        for _ in range(3):
            record_kill(self.actor)
        bank_kills(self.actor)
        record_kill(self.actor)  # killed but not yet logged with Iri
        self.assertIn("3 skitters logged", ledger.get_display_desc(self.actor))

    def test_count_is_per_looker(self):
        ledger = build()
        record_kill(self.actor)
        bank_kills(self.actor)
        other = create_object(
            "typeclasses.characters.Character", key="Other", location=self.rooms["civic_office"]
        )
        self.assertIn("1 skitter logged", ledger.get_display_desc(self.actor))
        self.assertIn("nothing logged under your name", ledger.get_display_desc(other))

    def test_read_shows_the_count(self):
        # The "read" alias (commands/look.py) is how a player is most
        # likely to reach for a log; check the key and each alias reach it.
        build()
        for target in ("pest log", "log", "screen"):
            with self.subTest(target):
                messages = []
                self.actor.msg = lambda text="", **kw: messages.append(text[0] if isinstance(text, tuple) else text)
                self.actor.execute_cmd(f"read {target}")
                self.assertTrue(any("nothing logged under your name" in m for m in messages))

    def test_rebuild_renames_an_existing_object(self):
        ledger = build()
        ledger.key = "a ledger"
        ledger.aliases.add("ledger")
        build()
        self.assertEqual(ledger.key, "a pest log")
        self.assertEqual(sorted(ledger.aliases.all()), ["log", "screen"])
