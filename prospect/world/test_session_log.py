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

from django.test import SimpleTestCase

from world.session_log import log_command, log_session_end, log_session_start


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
