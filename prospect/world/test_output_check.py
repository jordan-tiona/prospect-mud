"""Tests for world/output_check.py."""

from django.test import SimpleTestCase

from world.output_check import is_flagged


class IsFlaggedTests(SimpleTestCase):
    def test_ordinary_reply_passes(self):
        self.assertEqual(is_flagged('"Morning. Kettle\'s on." *wipes down the counter*'), (False, ""))

    def test_empty_reply_passes(self):
        self.assertEqual(is_flagged(""), (False, ""))

    def test_assistant_voice_is_flagged(self):
        self.assertTrue(is_flagged('"As an AI, I can\'t do that."')[0])

    def test_leaked_tool_call_is_flagged(self):
        text = '"Would you take it to him?" *calls functions.propose_commitment with commitment_type "deliver_parcel"*'
        self.assertEqual(is_flagged(text), (True, "leaked an internal action or errand name"))

    def test_bare_errand_id_is_flagged(self):
        self.assertTrue(is_flagged('"That\'s the hunt_skitters job."')[0])

    def test_hyphens_and_apostrophes_pass(self):
        self.assertFalse(is_flagged('"It\'s a well-kept, old-quarter sort of place - mind the step."')[0])
