"""
Tests for typeclasses/accounts.py's session-boundary logging
(world/session_log.py's session_start/session_end) - the login/
logout half of 2026-10-15's per-session command logging feature.

Run with:
    evennia test typeclasses
"""

from unittest.mock import patch

from django.test import TestCase
from evennia import create_account


class AccountSessionLoggingTests(TestCase):
    def setUp(self):
        self.account = create_account("Tester", "tester@example.com", "zqv-prospect-test-9273")
        self.addCleanup(self.account.delete)

    @patch("typeclasses.accounts.log_session_start")
    def test_post_login_generates_and_logs_a_session_id(self, mock_log_start):
        self.account.at_post_login(session=None)

        session_id = self.account.ndb.session_id
        self.assertTrue(session_id)
        mock_log_start.assert_called_once_with(session_id=session_id, account_key="Tester")

    @patch("typeclasses.accounts.log_session_start")
    def test_each_login_gets_a_fresh_session_id(self, mock_log_start):
        self.account.at_post_login(session=None)
        first_id = self.account.ndb.session_id

        self.account.at_post_login(session=None)
        second_id = self.account.ndb.session_id

        self.assertNotEqual(first_id, second_id)

    @patch("typeclasses.accounts.log_session_end")
    @patch("typeclasses.accounts.log_session_start")
    def test_disconnect_logs_the_same_session_id_from_login(self, mock_log_start, mock_log_end):
        self.account.at_post_login(session=None)
        session_id = self.account.ndb.session_id

        self.account.at_disconnect(reason="quit")

        mock_log_end.assert_called_once_with(session_id=session_id, account_key="Tester", reason="quit")

    @patch("typeclasses.accounts.log_session_end")
    def test_disconnect_without_a_prior_login_does_not_log(self, mock_log_end):
        self.account.at_disconnect(reason="quit")

        mock_log_end.assert_not_called()
