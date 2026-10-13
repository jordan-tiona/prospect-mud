"""
Tests for typeclasses.objects.indent_paragraphs and its wiring into
get_display_desc - the project owner's choice (four-space indent on
every paragraph, including the first) for visually separating
paragraphs, since Evennia's own output formatting collapses a blank
line between them down to a single line break.

Run with:
    evennia test typeclasses
"""

from django.test import TestCase
from evennia import create_object

from typeclasses.objects import indent_paragraphs


class IndentParagraphsTests(TestCase):
    def test_single_paragraph_is_indented(self):
        self.assertEqual(indent_paragraphs("Just one paragraph."), "    Just one paragraph.")

    def test_empty_text_is_unchanged(self):
        self.assertEqual(indent_paragraphs(""), "")
        self.assertIsNone(indent_paragraphs(None))

    def test_every_paragraph_gets_indented(self):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        self.assertEqual(
            indent_paragraphs(text),
            "    First paragraph.\n    Second paragraph.\n    Third paragraph.",
        )

    def test_extra_blank_lines_between_paragraphs_are_tolerated(self):
        text = "First paragraph.\n\n\nSecond paragraph."
        self.assertEqual(
            indent_paragraphs(text), "    First paragraph.\n    Second paragraph."
        )


class GetDisplayDescIndentationTests(TestCase):
    def setUp(self):
        self.room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.looker = create_object(
            "typeclasses.characters.Character", key="Tester", location=self.room
        )

    def test_room_full_desc_is_indented(self):
        self.room.db.desc = "First paragraph.\n\nSecond paragraph."
        self.assertEqual(
            self.room.get_display_desc(self.looker),
            "    First paragraph.\n    Second paragraph.",
        )

    def test_room_glance_is_indented_too(self):
        self.room.db.glance = "First.\n\nSecond."
        self.assertEqual(
            self.room.get_display_desc(self.looker, glance=True), "    First.\n    Second."
        )

    def test_room_object_desc_is_indented(self):
        obj = create_object(
            "typeclasses.objects.RoomObject",
            key="a sign",
            location=self.room,
            attributes=[("desc", "First paragraph.\n\nSecond paragraph.")],
        )
        self.assertEqual(
            obj.get_display_desc(self.looker),
            "    First paragraph.\n    Second paragraph.",
        )

    def test_npc_desc_is_indented(self):
        npc = create_object(
            "typeclasses.npcs.NPC",
            key="A dockhand",
            location=self.room,
            attributes=[("desc", "First paragraph.\n\nSecond paragraph.")],
        )
        self.assertEqual(
            npc.get_display_desc(self.looker),
            "    First paragraph.\n    Second paragraph.",
        )
