"""
Unit tests for the invite-code registry (world/invites.py,
game-plan.md 6.2's last safeguards-audit item).

Run with:
    evennia test world
"""

from django.test import TestCase
from evennia import GLOBAL_SCRIPTS

from world.invites import _CODE_LENGTH, consume_code, generate_codes


class InviteCodeTests(TestCase):
    def setUp(self):
        GLOBAL_SCRIPTS.invite_registry.db.codes = {}

    def test_generates_the_requested_count_of_distinct_codes(self):
        codes = generate_codes(5)

        self.assertEqual(len(codes), 5)
        self.assertEqual(len(set(codes)), 5)
        self.assertTrue(all(len(code) == _CODE_LENGTH for code in codes))

    def test_a_freshly_generated_code_is_unused(self):
        code = generate_codes(1)[0]

        self.assertTrue(consume_code(code, used_by="10.0.0.1"))

    def test_a_code_is_single_use(self):
        code = generate_codes(1)[0]
        consume_code(code, used_by="10.0.0.1")

        self.assertFalse(consume_code(code, used_by="10.0.0.2"))

    def test_an_unknown_code_is_rejected(self):
        self.assertFalse(consume_code("NOTREAL1", used_by="10.0.0.1"))

    def test_check_is_case_and_whitespace_insensitive(self):
        code = generate_codes(1)[0]

        self.assertTrue(consume_code(f"  {code.lower()}  ", used_by="10.0.0.1"))

    def test_a_used_code_records_who_used_it(self):
        code = generate_codes(1)[0]
        consume_code(code, used_by="10.0.0.1")

        self.assertEqual(GLOBAL_SCRIPTS.invite_registry.db.codes[code]["used_by"], "10.0.0.1")
