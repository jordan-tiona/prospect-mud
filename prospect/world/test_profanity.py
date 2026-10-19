"""
Tests for world/profanity.py and the speech paths that use it: say
and whisper (Character.at_pre_say), pose, channels, and appearance
text. Tell, chargen and NPC-addressed say have their own tests in
commands/test_tell.py, commands/test_chargen.py and
commands/test_say.py.
"""

import re
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from evennia import create_object
from evennia.objects.objects import DefaultObject
from evennia.utils import create

from world import appearance
from world.content_files import CONTENT_DIR
from world.profanity import description_is_profane, mask_speech, name_is_profane


class MaskSpeechTests(SimpleTestCase):
    def test_masks_profanity(self):
        self.assertEqual(mask_speech("What the fuck is this shit?"), "What the **** is this ****?")

    def test_masks_letter_swaps(self):
        self.assertEqual(mask_speech("sh1t happens"), "**** happens")

    def test_mild_words_pass(self):
        line = "Well damn, that's a hell of a thing, you bastard."
        self.assertEqual(mask_speech(line), line)

    def test_ordinary_and_setting_words_pass(self):
        for line in ["Mara, can I get a coffee?", "Being called a Cave Crawler stings.", "A Voldren and a Drask."]:
            with self.subTest(line=line):
                self.assertEqual(mask_speech(line), line)

    def test_empty(self):
        self.assertEqual(mask_speech(""), "")


class NameTests(SimpleTestCase):
    def test_rejects_profane_names(self):
        for name in ["Shit", "Fuckyourself", "Mr Fuckyourself", "Fuuuck", "Shitface", "Damn"]:
            with self.subTest(name=name):
                self.assertTrue(name_is_profane(name))

    def test_real_names_containing_short_roots_pass(self):
        for name in ["Hancock", "Cassandra", "Dickens", "Peacock", "Fukuda", "Bass", "Nigel", "Sam", "Mara Voss"]:
            with self.subTest(name=name):
                self.assertFalse(name_is_profane(name))

    def test_no_name_in_the_content_files_is_rejected(self):
        # Covers the generated-name lists and every NPC and place name.
        words = set()
        for path in CONTENT_DIR.rglob("*.md"):
            words |= set(re.findall(r"\b[A-Z][a-z]{2,}\b", path.read_text(encoding="utf-8")))
        self.assertEqual(sorted(w for w in words if name_is_profane(w)), [])


class DescriptionTests(SimpleTestCase):
    def test_profanity_is_rejected_and_mild_words_pass(self):
        self.assertTrue(description_is_profane("a shitty grin"))
        self.assertTrue(description_is_profane("wears a FUCKOFF badge"))
        self.assertFalse(description_is_profane("looks like hell after the night shift"))

    def test_appearance_validate_refuses_it(self):
        cleaned, error = appearance.validate("short", "a shitty grin")
        self.assertEqual(cleaned, "")
        self.assertIn("free of profanity", error)


def _text(text):
    if isinstance(text, (tuple, list)):
        text = text[0]
    return text or ""


class SpeechPathTests(TestCase):
    def setUp(self):
        self.room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.ana = create_object("typeclasses.characters.Character", key="Ana Pell", location=self.room)
        self.ravis = create_object("typeclasses.characters.Character", key="Ravis Vardur", location=self.room)
        self.received = {}
        patcher = patch.object(DefaultObject, "msg", autospec=True, side_effect=self._record)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _record(self, obj, text=None, **kwargs):
        self.received.setdefault(obj, []).append(_text(text))

    def _seen_by(self, char):
        return "\n".join(self.received.get(char, []))

    def test_say_is_masked_for_everyone(self):
        self.ana.execute_cmd("say this is shit")
        self.assertIn("This is ****.", self._seen_by(self.ravis))
        self.assertIn("This is ****.", self._seen_by(self.ana))
        self.assertNotIn("shit", self._seen_by(self.ravis))

    def test_whisper_is_masked(self):
        self.ana.execute_cmd("whisper Ravis Vardur = this is shit")
        self.assertIn("****", self._seen_by(self.ravis))
        self.assertNotIn("shit", self._seen_by(self.ravis))

    def test_pose_is_masked(self):
        self.ana.execute_cmd("pose mutters something about shit")
        self.assertIn("mutters something about ****.", self._seen_by(self.ravis))

    def test_channel_lines_are_masked(self):
        channel = create.create_channel("ProfanityTest", typeclass="typeclasses.channels.Channel")
        self.assertEqual(channel.at_pre_msg("what the fuck"), "what the ****")
