"""
Tests for world/tutorial.py: the scripted proactive lines Given Marr
and Daven Varek give a new player (project owner, 2026-10-14 - see
that module's docstring for why delivery is unconditional rather than
cancelled by conversation), plus the medical-bay tannoy announcement
(project owner, 2026-10-15) that fires on every room entry rather than
once.

`maybe_schedule_nudge` sends the room's tannoy text synchronously (if
any) every time, and schedules any NPC `delayed` line via
`evennia.utils.utils.delay`, once per character; the delayed behavior
is tested by calling `_fire_delayed_nudge` directly with a zero wait
so these tests don't need to sleep or mock Twisted's reactor.

Run with:
    evennia test world
"""

from django.test import TestCase
from evennia import create_object

from world.build_npcs import build as build_npcs
from world.build_rooms import build as build_rooms
from world.tutorial import _fire_delayed_nudge, maybe_schedule_nudge, tannoy_text_for_room


class TannoyTests(TestCase):
    def setUp(self):
        self.rooms = build_rooms()
        self.npcs = build_npcs()
        self.given = self.npcs["given_marr"]
        # ndb isn't DB-backed, so it survives across test methods via
        # Evennia's object cache even though db.* attributes roll back
        # cleanly - reset it explicitly (same pattern as
        # commands/test_admin.py) rather than assume it starts empty.
        self.given.ndb.conversations = None
        # Created with no location, then placed below: create_object()
        # with a location already fires the real at_post_move hook
        # (correctly - that's what makes this feature work live), which
        # would otherwise fire maybe_schedule_nudge before the ndb
        # reset above even ran, and get wiped out by it.
        self.character = create_object("typeclasses.characters.Character", key="Tester")
        self.character.location = self.rooms["medical_bay"]
        self.sent = []
        self.character.msg = lambda text="", **kw: self.sent.append(text)

    def test_tannoy_text_for_room_matches_medical_bay(self):
        self.assertIn("SAY", tannoy_text_for_room(self.rooms["medical_bay"]))

    def test_tannoy_text_for_room_none_elsewhere(self):
        self.assertIsNone(tannoy_text_for_room(self.rooms["old_quarter_square"]))

    def test_tannoy_fires_on_arrival(self):
        maybe_schedule_nudge(self.character)
        self.assertTrue(any("SAY" in text for text in self.sent))

    def test_tannoy_fires_every_time_not_just_once(self):
        maybe_schedule_nudge(self.character)
        sent_before = len(self.sent)
        maybe_schedule_nudge(self.character)
        self.assertEqual(len(self.sent), sent_before + 1)

    def test_tannoy_is_not_attributed_to_given_as_dialogue(self):
        maybe_schedule_nudge(self.character)
        history = self.given.ndb.conversations
        self.assertFalse(history and history.get(self.character.dbref))


class DelayedNudgeTests(TestCase):
    def setUp(self):
        self.rooms = build_rooms()
        self.npcs = build_npcs()
        self.given = self.npcs["given_marr"]
        self.daven = self.npcs["daven_varek"]
        # See TannoyTests.setUp's comment - ndb leaks across
        # test methods via the object cache, so reset it explicitly,
        # and place the character after that reset rather than via
        # create_object(location=...), which would otherwise fire the
        # real at_post_move hook (and its immediate nudge) first.
        self.given.ndb.conversations = None
        self.daven.ndb.conversations = None
        self.character = create_object("typeclasses.characters.Character", key="Tester")
        self.character.location = self.rooms["medical_bay"]

    def test_fires_and_sets_the_flag(self):
        _fire_delayed_nudge(self.character, self.given, "medical_bay")
        self.assertTrue(self.character.db.given_nudge_sent)

    def test_mentions_daven_so_the_next_step_is_never_silent(self):
        _fire_delayed_nudge(self.character, self.given, "medical_bay")
        history = self.given.ndb.conversations[self.character.dbref]
        self.assertIn("Daven", history[0]["content"])

    def test_still_fires_even_if_the_player_already_talked(self):
        self.given.ndb.conversations = {
            self.character.dbref: [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello there."},
            ]
        }
        _fire_delayed_nudge(self.character, self.given, "medical_bay")
        self.assertTrue(self.character.db.given_nudge_sent)
        history = self.given.ndb.conversations[self.character.dbref]
        self.assertEqual(len(history), 3)

    def test_noop_if_player_left_the_room(self):
        self.character.location = self.rooms["old_quarter_square"]
        _fire_delayed_nudge(self.character, self.given, "medical_bay")
        self.assertFalse(self.character.db.given_nudge_sent)

    def test_noop_if_already_sent(self):
        self.character.db.given_nudge_sent = True
        _fire_delayed_nudge(self.character, self.given, "medical_bay")
        history = self.given.ndb.conversations or {}
        self.assertNotIn(self.character.dbref, history)

    def test_given_and_daven_nudges_are_independent(self):
        self.character.location = self.rooms["daven_office"]
        _fire_delayed_nudge(self.character, self.daven, "daven_office")
        self.assertTrue(self.character.db.daven_nudge_sent)
        self.assertFalse(self.character.db.given_nudge_sent)
