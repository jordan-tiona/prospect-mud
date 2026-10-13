"""
Tests for world.room_content's parser (content-pipeline spec section
5.1).

Run with:
    evennia test world
"""

from django.test import SimpleTestCase

from world.room_content import RoomContentParseError, parse_room_text

_VALID = """\
<!--
room_id: old_quarter_square
status: Provisional
approval: Approved
bible_refs: 11.2.1, 11.2.3
-->

## Glance

A short arrival blurb.

## Description

The full look description.
"""


class ParseRoomTests(SimpleTestCase):
    def test_parses_valid_file(self):
        content = parse_room_text("old_quarter_square", _VALID)
        self.assertEqual(content.room_id, "old_quarter_square")
        self.assertEqual(content.status, "Provisional")
        self.assertEqual(content.approval, "Approved")
        self.assertEqual(content.bible_refs, ["11.2.1", "11.2.3"])
        self.assertEqual(content.glance, "A short arrival blurb.")
        self.assertEqual(content.desc, "The full look description.")

    def test_missing_glance_falls_back_to_none(self):
        raw = _VALID.replace("## Glance\n\nA short arrival blurb.\n\n", "")
        content = parse_room_text("old_quarter_square", raw)
        self.assertIsNone(content.glance)
        self.assertEqual(content.desc, "The full look description.")

    def test_missing_metadata_comment_raises(self):
        with self.assertRaises(RoomContentParseError):
            parse_room_text("old_quarter_square", "## Description\n\nJust text.")

    def test_mismatched_room_id_raises(self):
        with self.assertRaises(RoomContentParseError):
            parse_room_text("some_other_room", _VALID)

    def test_missing_required_field_raises(self):
        raw = _VALID.replace("approval: Approved\n", "")
        with self.assertRaises(RoomContentParseError):
            parse_room_text("old_quarter_square", raw)

    def test_missing_description_raises(self):
        raw = _VALID.replace(
            "## Description\n\nThe full look description.\n", ""
        )
        with self.assertRaises(RoomContentParseError):
            parse_room_text("old_quarter_square", raw)

    def test_html_comments_stripped_from_sections(self):
        raw = _VALID.replace(
            "The full look description.",
            "The full look description. <!-- TODO(lore): revisit -->",
        )
        content = parse_room_text("old_quarter_square", raw)
        self.assertNotIn("TODO(lore)", content.desc)
