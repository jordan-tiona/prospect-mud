"""
Tests for world.ambient_content's parsers (content-pipeline spec
sections 5.2/5.3).

Run with:
    evennia test world
"""

from django.test import SimpleTestCase

from world.ambient_content import (
    AmbientContentParseError,
    parse_ambient_npc_text,
    parse_ambient_object_text,
)

_VALID_NPC = """\
<!--
ambient_id: square_elderly_kethari
room: old_quarter_square
status: Provisional
approval: Approved
bible_refs: 5.1, 11.2.6
-->

# An elderly Kethari

## Poses

- reading quietly from a tablet
- watching people cross the square

## Description

The full examine text.
"""

_VALID_OBJECT = """\
<!--
object_id: square_noticeboard
room: old_quarter_square
status: Provisional
approval: Approved
-->

# A public noticeboard

## Short Description

A fixed room-listing sentence.

## Description

The full examine text.
"""


class ParseAmbientNPCTests(SimpleTestCase):
    def test_parses_valid_file(self):
        content = parse_ambient_npc_text("square_elderly_kethari", _VALID_NPC)
        self.assertEqual(content.ambient_id, "square_elderly_kethari")
        self.assertEqual(content.room, "old_quarter_square")
        self.assertEqual(content.approval, "Approved")
        self.assertEqual(content.key, "An elderly Kethari")
        self.assertEqual(
            content.poses, ["reading quietly from a tablet", "watching people cross the square"]
        )
        self.assertEqual(content.desc, "The full examine text.")
        self.assertEqual(content.bible_refs, ["5.1", "11.2.6"])

    def test_missing_key_heading_raises(self):
        raw = _VALID_NPC.replace("# An elderly Kethari\n\n", "")
        with self.assertRaises(AmbientContentParseError):
            parse_ambient_npc_text("square_elderly_kethari", raw)

    def test_missing_poses_raises(self):
        raw = _VALID_NPC.replace(
            "## Poses\n\n- reading quietly from a tablet\n"
            "- watching people cross the square\n\n",
            "",
        )
        with self.assertRaises(AmbientContentParseError):
            parse_ambient_npc_text("square_elderly_kethari", raw)

    def test_empty_poses_section_raises(self):
        raw = _VALID_NPC.replace(
            "- reading quietly from a tablet\n- watching people cross the square\n", ""
        )
        with self.assertRaises(AmbientContentParseError):
            parse_ambient_npc_text("square_elderly_kethari", raw)

    def test_mismatched_ambient_id_raises(self):
        with self.assertRaises(AmbientContentParseError):
            parse_ambient_npc_text("some_other_npc", _VALID_NPC)


class ParseAmbientObjectTests(SimpleTestCase):
    def test_parses_valid_file(self):
        content = parse_ambient_object_text("square_noticeboard", _VALID_OBJECT)
        self.assertEqual(content.object_id, "square_noticeboard")
        self.assertEqual(content.room, "old_quarter_square")
        self.assertEqual(content.key, "A public noticeboard")
        self.assertEqual(content.short_desc, "A fixed room-listing sentence.")
        self.assertEqual(content.desc, "The full examine text.")

    def test_missing_short_description_raises(self):
        raw = _VALID_OBJECT.replace(
            "## Short Description\n\nA fixed room-listing sentence.\n\n", ""
        )
        with self.assertRaises(AmbientContentParseError):
            parse_ambient_object_text("square_noticeboard", raw)

    def test_mismatched_object_id_raises(self):
        with self.assertRaises(AmbientContentParseError):
            parse_ambient_object_text("some_other_object", _VALID_OBJECT)
