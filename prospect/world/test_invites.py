"""
Unit tests for the invite-code registry (world/invites.py,
game-plan.md 6.2's last safeguards-audit item).

Run with:
    evennia test world
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase
from evennia import GLOBAL_SCRIPTS

from world.invites import (
    _CODE_LENGTH,
    all_codes,
    announce_registration,
    consume_code,
    describe,
    generate_codes,
    record_registration,
)


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

    def test_a_code_keeps_its_note(self):
        code = generate_codes(1, note="screen reader player")[0]

        self.assertEqual(GLOBAL_SCRIPTS.invite_registry.db.codes[code]["note"], "screen reader player")


class InviteRegistrationTests(TestCase):
    def setUp(self):
        GLOBAL_SCRIPTS.invite_registry.db.codes = {}
        self.code = generate_codes(1, note="screen reader player")[0]

    def test_describe_an_unused_code(self):
        self.assertEqual(
            describe(self.code, GLOBAL_SCRIPTS.invite_registry.db.codes[self.code]),
            f'{self.code}: unused - "screen reader player"',
        )

    def test_describe_a_code_used_before_a_character_exists(self):
        consume_code(self.code, used_by="10.0.0.1")

        line = describe(self.code, GLOBAL_SCRIPTS.invite_registry.db.codes[self.code])

        self.assertIn("no character yet", line)

    def test_registration_records_the_character(self):
        consume_code(self.code, used_by="10.0.0.1")
        record_registration(f" {self.code.lower()} ", "kaelin", "Kaelin")

        entry = GLOBAL_SCRIPTS.invite_registry.db.codes[self.code]
        self.assertEqual((entry["account"], entry["character"]), ("kaelin", "Kaelin"))
        self.assertIn("by Kaelin", describe(self.code, entry))

    def test_registration_of_an_unknown_code_changes_nothing(self):
        self.assertIsNone(record_registration("NOTREAL1", "kaelin", "Kaelin"))

    def test_lists_codes_oldest_first(self):
        second = generate_codes(1)[0]

        self.assertEqual([code for code, _ in all_codes()], [self.code, second])

    def test_announce_reaches_staff_only(self):
        consume_code(self.code, used_by="10.0.0.1")
        record_registration(self.code, "kaelin", "Kaelin")
        staff, player = MagicMock(is_superuser=False), MagicMock(is_superuser=False)
        staff.check_permstring.return_value = True
        player.check_permstring.return_value = False

        with patch("world.invites.SESSION_HANDLER") as handler:
            handler.all_connected_accounts.return_value = [staff, player]
            announce_registration(self.code)

        staff.msg.assert_called_once_with(
            f'[Invite] Code {self.code} "screen reader player" is now playing as Kaelin.'
        )
        player.msg.assert_not_called()
