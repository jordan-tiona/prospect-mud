"""
Tests for world/idle_emotes.py (LR-LORE-0006): the per-room emote timer,
its quiet rules, NPC and line choice, the hint-pose exemption and the
AMBIENCE switch (commands/option.py).

Delays are captured rather than waited on: utils.delay is patched to
record (seconds, callback, args), and tests run the callbacks by hand.

Run with:
    evennia test world.test_idle_emotes
"""

import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase
from evennia import create_object

from world import idle_emotes
from world.idle_emotes import (
    AMBIENCE_FLAG,
    EMOTE_FIRST_DELAY,
    EMOTE_GAP,
    EMOTE_LIMIT_PER_VISIT,
    EMOTE_QUIET_RETRY,
    emote_once,
    hears_ambience,
    start_room_emotes,
)


def _session(**flags):
    return SimpleNamespace(protocol_flags=flags)


class IdleEmoteTests(TestCase):
    def setUp(self):
        self.room = create_object("typeclasses.rooms.Room", key="Cafe")
        self.room.ndb.emote_timer = None
        self.room.ndb.last_emoter = None
        self.mara = create_object("typeclasses.npcs.TalkativeNPC", key="Mara", location=self.room)
        self.mara.db.npc_id = "mara_voss"
        self.mara.db.emotes = ["Mara wipes the counter.", "Mara sighs."]
        self.mara.ndb.last_emote = None
        self.kell = create_object("typeclasses.npcs.NPC", key="An elderly Kell", location=self.room)
        self.kell.db.emotes = ["The elderly Kell yawns."]
        self.kell.ndb.last_emote = None

        self.player = create_object("typeclasses.characters.Character", key="Tester")
        self.player.location = self.room
        for name in ("arrived_at", "last_spoke_at", "npc_reply_at", "tannoy_at"):
            setattr(self.player.ndb, name, None)
        self.sent = []
        self.player.msg = lambda text="", **kw: self.sent.append(text)
        self.sessions = [_session()]
        for name, value in (("count", lambda: len(self.sessions)), ("all", lambda: self.sessions)):
            patcher = patch.object(type(self.player.sessions), name, side_effect=value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.delays = []
        patcher = patch.object(idle_emotes.utils, "delay", side_effect=lambda s, f, *a: self.delays.append((s, f, a)))
        patcher.start()
        self.addCleanup(patcher.stop)
        # No open commitments in these tests.
        patcher = patch.object(idle_emotes, "hint_pose_for", return_value=None)
        self.hint_pose_for = patcher.start()
        self.addCleanup(patcher.stop)

    def _run_next(self):
        _seconds, func, args = self.delays.pop(0)
        func(*args)

    def test_nothing_on_entry_first_beat_after_a_delay(self):
        start_room_emotes(self.player)
        self.assertEqual(self.sent, [])
        self.assertEqual(len(self.delays), 1)
        self.assertTrue(EMOTE_FIRST_DELAY[0] <= self.delays[0][0] <= EMOTE_FIRST_DELAY[1])
        self._run_next()
        self.assertEqual(len(self.sent), 1)
        self.assertTrue(EMOTE_GAP[0] <= self.delays[0][0] <= EMOTE_GAP[1])

    def test_one_timer_per_room(self):
        start_room_emotes(self.player)
        start_room_emotes(self.player)
        self.assertEqual(len(self.delays), 1)

    def test_no_timer_without_emoting_npcs(self):
        self.mara.db.emotes = []
        self.kell.db.emotes = []
        start_room_emotes(self.player)
        self.assertEqual(self.delays, [])

    def test_no_timer_without_a_session(self):
        self.sessions = []
        start_room_emotes(self.player)
        self.assertEqual(self.delays, [])

    def test_timer_stops_when_the_last_player_leaves(self):
        start_room_emotes(self.player)
        self.player.location = None
        self._run_next()
        self.assertEqual(self.delays, [])
        self.assertIsNone(self.room.ndb.emote_timer)

    def test_beat_held_while_the_room_is_busy(self):
        for name in ("arrived_at", "last_spoke_at", "npc_reply_at", "tannoy_at"):
            with self.subTest(name):
                self.delays.clear()
                self.room.ndb.emote_timer = None
                setattr(self.player.ndb, name, time.time())
                start_room_emotes(self.player)
                self._run_next()
                self.assertEqual(self.sent, [])
                self.assertEqual(self.delays[0][0], EMOTE_QUIET_RETRY)
                setattr(self.player.ndb, name, None)

    def test_beat_held_while_a_reply_is_pending(self):
        self.mara.ndb.pending = {self.player.dbref}
        self.addCleanup(setattr, self.mara.ndb, "pending", None)
        start_room_emotes(self.player)
        self._run_next()
        self.assertEqual(self.sent, [])

    def test_npcs_alternate_and_lines_never_repeat_back_to_back(self):
        lines = [emote_once(self.room, [self.player], [self.mara, self.kell]) for _ in range(6)]
        speakers = ["Mara" if line.startswith("Mara") else "Kell" for line in lines]
        self.assertTrue(all(a != b for a, b in zip(speakers, speakers[1:])))
        mara_lines = [line for line in lines if line.startswith("Mara")]
        self.assertTrue(all(a != b for a, b in zip(mara_lines, mara_lines[1:])))

    def test_npc_showing_a_hint_pose_does_not_emote(self):
        self.hint_pose_for.side_effect = lambda npc_id, looker: "frowning at a parcel" if npc_id == "mara_voss" else None
        for _ in range(4):
            self.assertEqual(emote_once(self.room, [self.player], [self.mara, self.kell]), "The elderly Kell yawns.")
        self.assertIsNone(emote_once(self.room, [self.player], [self.mara]))

    def test_ambience_off_hears_nothing(self):
        self.sessions = [_session(**{AMBIENCE_FLAG: False})]
        self.assertFalse(hears_ambience(self.player))
        emote_once(self.room, [self.player], [self.kell])
        self.assertEqual(self.sent, [])

    def test_ambience_on_by_default(self):
        self.assertTrue(hears_ambience(self.player))
        emote_once(self.room, [self.player], [self.kell])
        self.assertEqual(self.sent, ["\n|xThe elderly Kell yawns.|n"])

    def _hear_the_limit(self):
        start_room_emotes(self.player)
        for _ in range(EMOTE_LIMIT_PER_VISIT):
            self._run_next()
        self.assertEqual(len(self.sent), EMOTE_LIMIT_PER_VISIT)

    def test_limit_per_visit_then_the_timer_stops(self):
        self._hear_the_limit()
        self._run_next()
        self.assertEqual(len(self.sent), EMOTE_LIMIT_PER_VISIT)
        self.assertEqual(self.delays, [])
        self.assertIsNone(self.room.ndb.emote_timer)

    def test_coming_back_starts_a_new_visit(self):
        self._hear_the_limit()
        self._run_next()  # stops the timer
        start_room_emotes(self.player)  # walks back in, or logs in
        self._run_next()
        self.assertEqual(len(self.sent), EMOTE_LIMIT_PER_VISIT + 1)

    def test_limit_is_per_player(self):
        self._hear_the_limit()
        newcomer = create_object("typeclasses.characters.Character", key="Newcomer", home=self.room)
        newcomer.location = self.room
        for name in ("arrived_at", "last_spoke_at", "npc_reply_at", "tannoy_at"):
            setattr(newcomer.ndb, name, None)
        heard = []
        newcomer.msg = lambda text="", **kw: heard.append(text)
        newcomer.ndb.emotes_heard = 0
        self._run_next()
        self.assertEqual(len(heard), 1)
        self.assertEqual(len(self.sent), EMOTE_LIMIT_PER_VISIT)
        self.assertEqual(len(self.delays), 1)  # still someone listening

    def test_emotes_never_reach_npc_conversation_history(self):
        self.mara.ndb.conversations = None
        self.room.msg_contents = MagicMock()
        for _ in range(4):
            emote_once(self.room, [self.player], [self.mara])
        self.assertIsNone(self.mara.ndb.conversations)
        self.room.msg_contents.assert_not_called()


class OptionAmbienceTests(TestCase):
    def setUp(self):
        from commands.option import CmdOption

        self.session = MagicMock()
        self.session.protocol_flags = {}
        self.account = MagicMock()
        self.saved = {}
        self.account.attributes.get.side_effect = lambda key, default=None: self.saved
        self.messages = []
        self.cmd = CmdOption()
        self.cmd.session = self.session
        self.cmd.account = self.account
        self.cmd.caller = self.account
        self.cmd.msg = lambda text="", **kw: self.messages.append(text)

    def _run(self, args, switches=()):
        self.cmd.args = args
        self.cmd.lhs, _, rhs = args.partition("=")
        self.cmd.rhs = rhs.strip() or None
        self.cmd.switches = list(switches)
        self.cmd.func()

    def test_turns_ambience_off_and_saves(self):
        self._run("ambience=off", switches=["save"])
        self.session.update_flags.assert_called_once_with(**{AMBIENCE_FLAG: False})
        self.assertEqual(self.saved, {AMBIENCE_FLAG: False})

    def test_rejects_other_values(self):
        self._run("ambience=sometimes")
        self.session.update_flags.assert_not_called()
        self.assertIn("use on or off", self.messages[0])
