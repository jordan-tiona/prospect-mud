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

import time
from unittest.mock import patch

from django.test import TestCase
from evennia import create_object

from world.build_npcs import build as build_npcs
from world.build_rooms import build as build_rooms
from world.tutorial import (
    TANNOY_BLOCK_PAUSE,
    TANNOY_CYCLE_GAP,
    TANNOY_FIRST_BLOCK_DELAY,
    TANNOY_QUIET_RETRY,
    _fire_delayed_nudge,
    announce_tannoy,
    maybe_schedule_nudge,
    tannoy_text_for_room,
)


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
        self.character.ndb.last_spoke_at = None
        self.character.ndb.npc_reply_at = None
        self.sent = []
        # The tannoy only plays to a logged-in character (announce_tannoy).
        sessions = patch.object(type(self.character.sessions), "count", return_value=1)
        sessions.start()
        self.addCleanup(sessions.stop)
        self.character.msg = lambda text="", **kw: self.sent.append(text)

    def test_tannoy_text_for_room_matches_medical_bay(self):
        text = tannoy_text_for_room(self.rooms["medical_bay"])
        for command in ("SAY", "NORTH", "LOOK", "PROBE", "DESCRIBE", "TELL", "PLAYTEST", "OPTION/SAVE SCREENREADER=ON", "TANNOY"):
            self.assertIn(command, text)
        # The spoken part is bright cyan, like other dialogue; the lead-in isn't.
        self.assertTrue(text.startswith("A tannoy near the ceiling crackles to life: "))
        self.assertIn(' |c"Attention, new arrivals.', text)
        self.assertIn('To hear this again, type TANNOY."|n', text)
        self.assertTrue(text.endswith("The tannoy clicks off."))

    def test_tannoy_is_four_blocks_with_a_blank_line_between(self):
        text = tannoy_text_for_room(self.rooms["medical_bay"])
        self.assertEqual(text.count('|c"'), 4)
        # Three between the blocks, one before "The tannoy clicks off."
        self.assertEqual(text.count("|n\n\n"), 4)

    def test_tannoy_tells_new_arrivals_to_ask_for_work_second(self):
        # LR-DEV-0014: second, so screen-reader players hear it early.
        blocks = tannoy_text_for_room(self.rooms["medical_bay"]).split("|n\n\n")
        self.assertIn("whether they need any help", blocks[1])
        self.assertIn("looking for work", blocks[1])

    def test_tannoy_blocks_arrive_paced_on_arrival(self):
        with patch("world.tutorial.utils.delay") as mock_delay:
            announce_tannoy(self.character)
        self.assertEqual(len(self.sent), 1)
        self.assertIn("Attention, new arrivals.", self.sent[0])
        self.assertNotIn("PLAYTEST", self.sent[0])
        waits = [call.args[0] for call in mock_delay.call_args_list]
        self.assertEqual(waits, [TANNOY_BLOCK_PAUSE, TANNOY_BLOCK_PAUSE * 2, TANNOY_BLOCK_PAUSE * 3])
        for call in mock_delay.call_args_list:
            call.args[1](*call.args[2:])
        self.assertEqual(len(self.sent), 4)
        self.assertIn("PLAYTEST", self.sent[3])

    def test_later_blocks_stop_if_the_player_leaves(self):
        with patch("world.tutorial.utils.delay") as mock_delay:
            announce_tannoy(self.character)
        self.character.location = self.rooms["old_quarter_square"]
        for call in mock_delay.call_args_list:
            call.args[1](*call.args[2:])
        self.assertEqual(len(self.sent), 1)

    def test_screen_reader_gets_the_whole_tannoy_at_once(self):
        with patch("world.tutorial.uses_screenreader", return_value=True), patch(
            "world.tutorial.utils.delay"
        ) as mock_delay:
            announce_tannoy(self.character)
        mock_delay.assert_not_called()
        self.assertEqual(len(self.sent), 1)
        self.assertIn("PLAYTEST", self.sent[0])

    def test_tannoy_text_for_room_none_elsewhere(self):
        self.assertIsNone(tannoy_text_for_room(self.rooms["old_quarter_square"]))

    def test_tannoy_fires_on_arrival(self):
        maybe_schedule_nudge(self.character)
        self.assertTrue(any("SAY" in text for text in self.sent))

    # -- later visits: single blocks, cycled once -----------------------

    def _second_visit(self):
        self.character.db.heard_full_tannoy = True
        with patch("world.tutorial.utils.delay") as mock_delay:
            announce_tannoy(self.character)
        return mock_delay

    def _run(self, call):
        with patch("world.tutorial.utils.delay") as mock_delay:
            call.args[1](*call.args[2:])
        return mock_delay

    def test_first_visit_marks_the_full_announcement_heard(self):
        with patch("world.tutorial.utils.delay"):
            announce_tannoy(self.character)
        self.assertTrue(self.character.db.heard_full_tannoy)

    def test_no_session_plays_nothing_and_keeps_the_first_visit(self):
        # Chargen moves the character in before the player is logged in.
        with patch.object(type(self.character.sessions), "count", return_value=0):
            announce_tannoy(self.character)
        self.assertEqual(self.sent, [])
        self.assertFalse(self.character.db.heard_full_tannoy)

    def test_later_visit_plays_nothing_on_entry(self):
        mock_delay = self._second_visit()
        self.assertEqual(self.sent, [])
        first_wait = mock_delay.call_args.args[0]
        self.assertTrue(TANNOY_FIRST_BLOCK_DELAY[0] <= first_wait <= TANNOY_FIRST_BLOCK_DELAY[1])

    def test_later_visit_plays_each_block_once_then_stops(self):
        call = self._second_visit().call_args
        gaps = []
        while call is not None:
            mock_delay = self._run(call)
            call = mock_delay.call_args
            if call is not None:
                gaps.append(call.args[0])
        self.assertEqual(len(self.sent), 4)
        self.assertEqual(gaps, [TANNOY_CYCLE_GAP, TANNOY_CYCLE_GAP, TANNOY_CYCLE_GAP])
        for text in self.sent:
            self.assertIn("A tannoy near the ceiling crackles to life:", text)
            self.assertIn("To hear the whole announcement, type TANNOY.", text)
            self.assertTrue(text.endswith("The tannoy clicks off."))
        joined = "\n".join(self.sent)
        for command in ("SAY", "TELL", "PLAYTEST"):
            self.assertIn(command, joined)
        self.assertIsNone(self.character.ndb.tannoy_cycle)

    def test_cycle_stops_when_the_player_leaves(self):
        call = self._second_visit().call_args
        self.character.location = self.rooms["old_quarter_square"]
        self.assertIsNone(self._run(call).call_args)
        self.assertEqual(self.sent, [])

    def test_reentering_replaces_the_old_cycle(self):
        old_call = self._second_visit().call_args
        self._second_visit()
        self.assertIsNone(self._run(old_call).call_args)
        self.assertEqual(self.sent, [])

    def test_block_waits_while_the_player_is_talking(self):
        call = self._second_visit().call_args
        self.character.ndb.last_spoke_at = time.time()
        retry = self._run(call).call_args
        self.assertEqual(self.sent, [])
        self.assertEqual(retry.args[0], TANNOY_QUIET_RETRY)

    def test_block_waits_for_a_pending_npc_reply(self):
        call = self._second_visit().call_args
        self.given.ndb.pending = {self.character.dbref}
        self.addCleanup(setattr, self.given.ndb, "pending", None)
        self._run(call)
        self.assertEqual(self.sent, [])

    def test_tannoy_fires_when_a_player_takes_control_in_the_room(self):
        # Chargen places a new character before login, so at_post_move's
        # tannoy reaches nobody; at_post_puppet is what a new player sees.
        with patch("evennia.objects.objects.DefaultCharacter.at_post_puppet"):
            self.character.at_post_puppet()
        self.assertTrue(any("SAY" in str(text) for text in self.sent))

    def test_no_tannoy_on_puppet_in_a_room_without_one(self):
        self.character.location = self.rooms["old_quarter_square"]
        with patch("evennia.objects.objects.DefaultCharacter.at_post_puppet"):
            self.character.at_post_puppet()
        self.assertFalse(any("SAY" in str(text) for text in self.sent))

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
