"""
Tests for the `bug`/`feedback` command (commands/feedback.py,
game-plan.md 6's Week 0 item 4).

Run with:
    evennia test commands
"""

from unittest.mock import patch

from django.test import TestCase
from evennia import create_account, create_object

_PASSWORD = "zqv-prospect-test-9273"


class FeedbackCommandTests(TestCase):
    def setUp(self):
        self.room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=self.room
        )
        account = create_account("FeedbackTesterAccount", "feedbacktester@example.com", _PASSWORD)
        self.addCleanup(account.delete)
        account.ndb.session_id = "session-abc"
        self.actor.account = account
        self.messages = []
        self.actor.msg = lambda text="", **kw: self.messages.append(text)

    @patch("commands.feedback.log_feedback")
    def test_bug_logs_with_the_bug_category(self, mock_log):
        self.actor.execute_cmd("bug the drink kept serving cold")

        mock_log.assert_called_once_with(
            session_id="session-abc",
            actor_key="Tester",
            actor_dbref=self.actor.dbref,
            location="Test Room",
            category="bug",
            message="the drink kept serving cold",
        )
        self.assertTrue(any("logged" in m.lower() for m in self.messages))

    @patch("commands.feedback.log_feedback")
    def test_feedback_alias_logs_with_the_feedback_category(self, mock_log):
        self.actor.execute_cmd("feedback I really liked that interaction")

        kwargs = mock_log.call_args.kwargs
        self.assertEqual(kwargs["category"], "feedback")
        self.assertEqual(kwargs["message"], "I really liked that interaction")

    @patch("commands.feedback.log_feedback")
    def test_empty_message_is_rejected_without_logging(self, mock_log):
        self.actor.execute_cmd("bug")

        mock_log.assert_not_called()
        self.assertTrue(any("usage" in m.lower() for m in self.messages))
