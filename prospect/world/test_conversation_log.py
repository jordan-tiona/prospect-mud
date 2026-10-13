"""
Tests for the conversation logger (world/conversation_log.py), per
design-bible 14.7. Writes to a temp file (via the `path` override)
rather than the real server/logs/conversations.jsonl.

Run with:
    evennia test world
"""

import json
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from world.conversation_log import log_quest_reset, log_reset, log_turn


class ConversationLogTests(SimpleTestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.log_path = Path(self._tmpdir.name) / "conversations.jsonl"

    def _log(self, **overrides):
        kwargs = dict(
            conversation_id="conv-1",
            turn_id=1,
            npc_id="mara_voss",
            location="Corner Cafe",
            actor_key="Tester",
            actor_dbref="#1",
            player_message="hello",
            prompt_messages=[{"role": "system", "content": "..."}],
            model="qwen3:14b",
            prompt_version="1",
            npc_response="hi there",
            tool_calls=[],
            flagged=False,
            path=self.log_path,
        )
        kwargs.update(overrides)
        log_turn(**kwargs)

    def _read_records(self):
        with self.log_path.open(encoding="utf-8") as f:
            return [json.loads(line) for line in f]

    def test_creates_parent_directory_and_writes_one_record(self):
        self._log()
        records = self._read_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["npc_id"], "mara_voss")
        self.assertEqual(records[0]["player_message"], "hello")
        self.assertEqual(records[0]["npc_response"], "hi there")

    def test_appends_rather_than_overwrites(self):
        self._log(turn_id=1)
        self._log(turn_id=2)
        records = self._read_records()
        self.assertEqual([r["turn_id"] for r in records], [1, 2])

    def test_never_logs_the_api_key(self):
        self._log()
        raw = self.log_path.read_text(encoding="utf-8")
        self.assertNotIn("ollama", raw.lower().split('"model_settings"')[0])  # sanity: key not in early fields
        record = self._read_records()[0]
        self.assertNotIn("api_key", record["model_settings"])
        self.assertNotIn("LLM_API_KEY", str(record))

    def test_review_fields_default_to_null(self):
        self._log()
        record = self._read_records()[0]
        self.assertIsNone(record["review_status"])
        self.assertIsNone(record["annotations"])

    def test_includes_full_prompt_for_review(self):
        prompt = [{"role": "system", "content": "common knowledge + persona + lore"}]
        self._log(prompt_messages=prompt)
        record = self._read_records()[0]
        self.assertEqual(record["prompt"], prompt)

    def test_npc_response_can_be_none(self):
        self._log(npc_response=None, flagged=False, flag_reason="llm_unavailable")
        record = self._read_records()[0]
        self.assertIsNone(record["npc_response"])
        self.assertEqual(record["flag_reason"], "llm_unavailable")


class ConversationResetLogTests(SimpleTestCase):
    """
    log_reset() marks a `forget` command in the same file as regular
    turns (commands/admin.py's CmdForget), so a reviewer scanning the
    log can tell a sudden change in behavior was a deliberate reset,
    not something the model did on its own.
    """

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.log_path = Path(self._tmpdir.name) / "conversations.jsonl"

    def _read_records(self):
        with self.log_path.open(encoding="utf-8") as f:
            return [json.loads(line) for line in f]

    def test_writes_a_forget_event_record(self):
        log_reset(
            conversation_id="conv-1",
            npc_id="mara_voss",
            actor_key="Tester",
            actor_dbref="#1",
            path=self.log_path,
        )
        records = self._read_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["event"], "forget")
        self.assertEqual(records[0]["conversation_id"], "conv-1")
        self.assertEqual(records[0]["npc_id"], "mara_voss")
        self.assertEqual(records[0]["actor_key"], "Tester")
        self.assertEqual(records[0]["actor_dbref"], "#1")

    def test_appends_alongside_regular_turns(self):
        log_turn(
            conversation_id="conv-1",
            turn_id=1,
            npc_id="mara_voss",
            location="Corner Cafe",
            actor_key="Tester",
            actor_dbref="#1",
            player_message="hello",
            prompt_messages=[],
            model="qwen3:14b",
            prompt_version="1",
            npc_response="hi",
            tool_calls=[],
            flagged=False,
            path=self.log_path,
        )
        log_reset(
            conversation_id="conv-1",
            npc_id="mara_voss",
            actor_key="Tester",
            actor_dbref="#1",
            path=self.log_path,
        )
        records = self._read_records()
        self.assertEqual(len(records), 2)
        self.assertNotIn("event", records[0])
        self.assertEqual(records[1]["event"], "forget")


class QuestResetLogTests(SimpleTestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.log_path = Path(self._tmpdir.name) / "conversations.jsonl"

    def _read_records(self):
        with self.log_path.open(encoding="utf-8") as f:
            return [json.loads(line) for line in f]

    def test_writes_a_quest_reset_event_record(self):
        log_quest_reset(
            quest_key="quest_module_exchange",
            previous_state="has_faulty_module",
            actor_key="Tester",
            actor_dbref="#1",
            path=self.log_path,
        )
        records = self._read_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["event"], "quest_reset")
        self.assertEqual(records[0]["quest_key"], "quest_module_exchange")
        self.assertEqual(records[0]["previous_state"], "has_faulty_module")
        self.assertEqual(records[0]["actor_key"], "Tester")
        self.assertEqual(records[0]["actor_dbref"], "#1")

    def test_appends_alongside_regular_turns(self):
        log_turn(
            conversation_id="conv-1",
            turn_id=1,
            npc_id="mara_voss",
            location="Corner Cafe",
            actor_key="Tester",
            actor_dbref="#1",
            player_message="hello",
            prompt_messages=[],
            model="qwen3:14b",
            prompt_version="1",
            npc_response="hi",
            tool_calls=[],
            flagged=False,
            path=self.log_path,
        )
        log_quest_reset(
            quest_key="quest_module_exchange",
            previous_state="accepted",
            actor_key="Tester",
            actor_dbref="#1",
            path=self.log_path,
        )
        records = self._read_records()
        self.assertEqual(len(records), 2)
        self.assertNotIn("event", records[0])
        self.assertEqual(records[1]["event"], "quest_reset")
