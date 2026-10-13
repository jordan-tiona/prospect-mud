"""
Run with:
    evennia test commands
"""

from django.test import TestCase
from evennia import create_object


def _record_text(text="", **kwargs):
    if isinstance(text, (tuple, list)):
        text = text[0]
    return text


class LookAliasTests(TestCase):
    def setUp(self):
        self.room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=self.room
        )
        self.board = create_object(
            "typeclasses.objects.Object", key="notice board", location=self.room
        )
        self.messages = []
        self.actor.msg = lambda text="", **kw: self.messages.append(_record_text(text, **kw))

    def test_look_at_object(self):
        self.actor.execute_cmd("look at notice board")
        self.assertTrue(any("notice board" in m for m in self.messages))

    def test_l_at_object(self):
        self.actor.execute_cmd("l at notice board")
        self.assertTrue(any("notice board" in m for m in self.messages))

    def test_plain_look_still_works(self):
        self.actor.execute_cmd("look notice board")
        self.assertTrue(any("notice board" in m for m in self.messages))

    def test_look_at_with_nothing_after_shows_room(self):
        self.actor.execute_cmd("look at")
        self.assertTrue(any("Test Room" in m for m in self.messages))

    def test_look_at_the_object_strips_article(self):
        self.actor.execute_cmd("look at the notice board")
        self.assertTrue(any("notice board" in m for m in self.messages))

    def test_look_a_object_strips_article(self):
        self.board.key = "board"
        self.board.save()
        self.actor.execute_cmd("look at a board")
        self.assertTrue(any("board" in m for m in self.messages))

    def test_look_an_object_strips_article(self):
        self.board.key = "announcement"
        self.board.save()
        self.actor.execute_cmd("look at an announcement")
        self.assertTrue(any("announcement" in m for m in self.messages))

    def test_look_the_object_without_at_also_strips_article(self):
        self.actor.execute_cmd("look the notice board")
        self.assertTrue(any("notice board" in m for m in self.messages))
