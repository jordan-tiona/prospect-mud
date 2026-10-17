"""
Tests for the per-session command/transcript logger (world/
session_log.py) - separate from world/conversation_log.py's
conversations.jsonl (see that module's docstring for why).

Run with:
    evennia test world
"""

import json
import tempfile
from pathlib import Path

from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from evennia import create_account, create_object

from world.session_log import (
    log_command,
    log_feedback,
    log_idle,
    log_quest_event,
    log_room_changed,
    log_session_end,
    log_session_start,
    log_unknown_command,
    session_id_for,
    set_session_id,
)


class SessionLogTests(SimpleTestCase):
    def setUp(self):
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        self.path = Path(tmp_dir.name) / "sessions.jsonl"

    def _read_records(self):
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines()]

    def test_log_session_start_writes_expected_fields(self):
        log_session_start(session_id="abc123", account_key="Jordan", path=self.path)

        [record] = self._read_records()
        self.assertEqual(record["event"], "session_start")
        self.assertEqual(record["session_id"], "abc123")
        self.assertEqual(record["account_key"], "Jordan")
        self.assertIn("timestamp", record)

    def test_log_session_end_writes_expected_fields(self):
        log_session_end(session_id="abc123", account_key="Jordan", reason="quit", path=self.path)

        [record] = self._read_records()
        self.assertEqual(record["event"], "session_end")
        self.assertEqual(record["session_id"], "abc123")
        self.assertEqual(record["reason"], "quit")

    def test_log_command_writes_expected_fields(self):
        log_command(
            session_id="abc123",
            actor_key="Jordan",
            actor_dbref="#5",
            location="Old Quarter Square",
            raw_input="use gardening kit on planting bed",
            path=self.path,
        )

        [record] = self._read_records()
        self.assertEqual(record["event"], "command")
        self.assertEqual(record["session_id"], "abc123")
        self.assertEqual(record["actor_key"], "Jordan")
        self.assertEqual(record["actor_dbref"], "#5")
        self.assertEqual(record["location"], "Old Quarter Square")
        self.assertEqual(record["raw_input"], "use gardening kit on planting bed")

    def test_multiple_calls_append_rather_than_overwrite(self):
        log_session_start(session_id="abc123", account_key="Jordan", path=self.path)
        log_command(
            session_id="abc123",
            actor_key="Jordan",
            actor_dbref="#5",
            location="Old Quarter Square",
            raw_input="look",
            path=self.path,
        )
        log_session_end(session_id="abc123", account_key="Jordan", path=self.path)

        records = self._read_records()
        self.assertEqual([r["event"] for r in records], ["session_start", "command", "session_end"])

    def test_log_unknown_command_writes_expected_fields(self):
        log_unknown_command(
            session_id="abc123",
            actor_key="Jordan",
            actor_dbref="#5",
            location="Old Quarter Square",
            raw_input="fooble the bar",
            path=self.path,
        )

        [record] = self._read_records()
        self.assertEqual(record["event"], "unknown_command")
        self.assertEqual(record["raw_input"], "fooble the bar")

    def test_log_room_changed_writes_expected_fields(self):
        log_room_changed(
            session_id="abc123",
            actor_key="Jordan",
            actor_dbref="#5",
            from_location="Old Quarter Square",
            to_location="Corner Cafe",
            path=self.path,
        )

        [record] = self._read_records()
        self.assertEqual(record["event"], "room_changed")
        self.assertEqual(record["from_location"], "Old Quarter Square")
        self.assertEqual(record["to_location"], "Corner Cafe")

    def test_log_quest_event_writes_expected_fields(self):
        log_quest_event(
            session_id="abc123",
            actor_key="Jordan",
            actor_dbref="#5",
            event="quest_started",
            commitment_type="hunt_skitters",
            mandatory=True,
            commitment_id="xyz",
            path=self.path,
        )

        [record] = self._read_records()
        self.assertEqual(record["event"], "quest_started")
        self.assertEqual(record["commitment_type"], "hunt_skitters")
        self.assertTrue(record["mandatory"])
        self.assertEqual(record["commitment_id"], "xyz")

    def test_log_feedback_writes_expected_fields(self):
        log_feedback(
            session_id="abc123",
            actor_key="Jordan",
            actor_dbref="#5",
            location="Old Quarter Square",
            category="bug",
            message="the drink kept serving cold",
            path=self.path,
        )

        [record] = self._read_records()
        self.assertEqual(record["event"], "feedback")
        self.assertEqual(record["category"], "bug")
        self.assertEqual(record["message"], "the drink kept serving cold")

    def test_log_idle_writes_expected_fields(self):
        log_idle(
            session_id="abc123",
            actor_key="Jordan",
            actor_dbref="#5",
            location="Old Quarter Square",
            idle_seconds=720.5,
            path=self.path,
        )

        [record] = self._read_records()
        self.assertEqual(record["event"], "idle")
        self.assertEqual(record["idle_seconds"], 720.5)


class SessionIdForTests(TestCase):
    def setUp(self):
        # An explicit room/home, rather than relying on the default
        # home (settings.DEFAULT_HOME, "#2") existing - see
        # world/test_llm_budget.py's PlayerBudgetTests for the same
        # fix against the same intermittent dangling-foreign-key
        # IntegrityError (2026-10-16).
        self.room = create_object("typeclasses.rooms.Room", key="Test Room")

    def test_returns_none_for_a_character_with_no_account(self):
        character = create_object(
            "typeclasses.characters.Character", key="Tester", location=self.room, home=self.room
        )

        self.assertIsNone(session_id_for(character))

    def test_returns_the_accounts_session_id_when_set(self):
        character = create_object(
            "typeclasses.characters.Character", key="Tester", location=self.room, home=self.room
        )
        account = create_account("TesterAccount", "tester@example.com", "zqv-prospect-test-9273")
        character.account = account
        set_session_id(account, "abc123")

        self.assertEqual(session_id_for(character), "abc123")

    def test_session_id_survives_a_reload(self):
        # PF-0008: on ndb, a reload wiped it and command logging stopped
        # for every player still connected.
        character = create_object(
            "typeclasses.characters.Character", key="Tester", location=self.room, home=self.room
        )
        account = create_account("TesterAccount", "tester@example.com", "zqv-prospect-test-9273")
        character.account = account
        set_session_id(account, "abc123")
        account.nattributes.clear()

        self.assertEqual(session_id_for(character), "abc123")


class DefaultLogPathTests(SimpleTestCase):
    def test_tests_never_write_to_the_real_log(self):
        # PF-0009: quest/commitment tests were appending to the real
        # sessions.jsonl, and parallel workers truncated lines in it.
        with patch("pathlib.Path.open") as mock_open:
            log_session_start(session_id="abc", account_key="Tester")
        mock_open.assert_not_called()
