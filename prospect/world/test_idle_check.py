"""
Unit tests for world/idle_check.py's check_idle_sessions - the
periodic idle-time gameplay event (game-plan.md 6.2, driven by
typeclasses/scripts.py's IdleMonitor ticker). Uses lightweight fake
session/account/puppet objects rather than a real connected session,
same approach as commands/test_chargen.py's `_FakeSession`.

Run with:
    evennia test world
"""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from world.idle_check import IDLE_THRESHOLD_SECONDS, check_idle_sessions


def _fake_session(*, idle_time, has_account=True, has_puppet=True):
    session = MagicMock()
    session.ndb.idle_logged = False
    if has_account:
        session.account.idle_time = idle_time
        session.account.ndb.session_id = "abc123"
    else:
        session.account = None
    if has_puppet:
        session.puppet.key = "Tester"
        session.puppet.dbref = "#5"
        session.puppet.location.key = "Old Quarter Square"
        session.puppet.account = session.account
    else:
        session.puppet = None
    return session


class CheckIdleSessionsTests(SimpleTestCase):
    @patch("world.idle_check.log_idle")
    @patch("world.idle_check.SESSION_HANDLER")
    def test_logs_once_a_session_crosses_the_threshold(self, mock_handler, mock_log_idle):
        session = _fake_session(idle_time=IDLE_THRESHOLD_SECONDS + 1)
        mock_handler.get_sessions.return_value = [session]

        check_idle_sessions()

        mock_log_idle.assert_called_once()
        self.assertTrue(session.ndb.idle_logged)

    @patch("world.idle_check.log_idle")
    @patch("world.idle_check.SESSION_HANDLER")
    def test_does_not_log_below_the_threshold(self, mock_handler, mock_log_idle):
        session = _fake_session(idle_time=IDLE_THRESHOLD_SECONDS - 1)
        mock_handler.get_sessions.return_value = [session]

        check_idle_sessions()

        mock_log_idle.assert_not_called()

    @patch("world.idle_check.log_idle")
    @patch("world.idle_check.SESSION_HANDLER")
    def test_does_not_log_again_while_still_idle(self, mock_handler, mock_log_idle):
        session = _fake_session(idle_time=IDLE_THRESHOLD_SECONDS + 1)
        session.ndb.idle_logged = True
        mock_handler.get_sessions.return_value = [session]

        check_idle_sessions()

        mock_log_idle.assert_not_called()

    @patch("world.idle_check.log_idle")
    @patch("world.idle_check.SESSION_HANDLER")
    def test_rearms_once_activity_resumes(self, mock_handler, mock_log_idle):
        session = _fake_session(idle_time=5)
        session.ndb.idle_logged = True
        mock_handler.get_sessions.return_value = [session]

        check_idle_sessions()

        self.assertFalse(session.ndb.idle_logged)

    @patch("world.idle_check.log_idle")
    @patch("world.idle_check.SESSION_HANDLER")
    def test_skips_a_session_with_no_account_or_puppet(self, mock_handler, mock_log_idle):
        no_account = _fake_session(idle_time=IDLE_THRESHOLD_SECONDS + 1, has_account=False)
        no_puppet = _fake_session(idle_time=IDLE_THRESHOLD_SECONDS + 1, has_puppet=False)
        mock_handler.get_sessions.return_value = [no_account, no_puppet]

        check_idle_sessions()

        mock_log_idle.assert_not_called()
