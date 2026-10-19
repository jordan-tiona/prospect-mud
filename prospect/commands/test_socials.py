"""
Tests for commands/socials.py: display-only social shortcuts.

Run with:
    evennia test commands.test_socials
"""

from unittest.mock import patch

from django.test import TestCase
from evennia import create_account, create_object
from evennia.objects.objects import DefaultObject

from world.stealth import hide, is_hidden


def _text(text):
    if isinstance(text, (tuple, list)):
        text = text[0]
    return text or ""


class SocialTests(TestCase):
    def setUp(self):
        self.room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.ravis = self._character("Ravis", [])
        self.mara = self._character("Mara", [])
        self.watcher = self._character("Watcher", [])
        self.received = {}
        patcher = patch.object(DefaultObject, "msg", autospec=True, side_effect=self._record)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _character(self, key, permissions):
        account = create_account(key, f"{key.lower()}@example.com", "testpassword123", permissions=permissions)
        char = create_object("typeclasses.characters.Character", key=key, location=self.room)
        char.db_account = account
        char.save()
        return char

    def _record(self, obj, text=None, **kwargs):
        self.received.setdefault(obj, []).append(_text(text))

    def _seen_by(self, char):
        return "\n".join(self.received.get(char, []))

    def test_untargeted_social(self):
        self.ravis.execute_cmd("smile")
        self.assertIn("You smile.", self._seen_by(self.ravis))
        self.assertIn("Ravis smiles.", self._seen_by(self.watcher))

    def test_targeted_social_has_three_views(self):
        self.ravis.execute_cmd("wave mara")
        self.assertIn("You wave to Mara.", self._seen_by(self.ravis))
        self.assertIn("Ravis waves to you.", self._seen_by(self.mara))
        self.assertIn("Ravis waves to Mara.", self._seen_by(self.watcher))
        self.assertNotIn("Ravis waves to Mara.", self._seen_by(self.mara))

    def test_aiming_at_yourself_is_untargeted(self):
        self.ravis.execute_cmd("nod me")
        self.assertIn("Ravis nods.", self._seen_by(self.watcher))

    def test_third_person_form_works_too(self):
        self.ravis.execute_cmd("nods mara")
        self.assertIn("You nod to Mara.", self._seen_by(self.ravis))
        self.assertIn("Ravis nods to Mara.", self._seen_by(self.watcher))

    def test_unknown_target_sends_nothing_to_the_room(self):
        self.ravis.execute_cmd("bow nobody")
        self.assertNotIn("bows", self._seen_by(self.watcher))

    def test_socials_lists_them(self):
        self.ravis.execute_cmd("socials")
        listing = self._seen_by(self.ravis)
        for verb in ("smile", "wink", "cheer"):
            self.assertIn(verb, listing)

    def test_social_reveals_hidden_staff(self):
        admin = self._character("Admin", ["Builder"])
        hide(admin)
        admin.execute_cmd("grin")
        self.assertFalse(is_hidden(admin))
        self.assertIn("Admin grins.", self._seen_by(self.watcher))
