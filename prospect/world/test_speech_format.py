"""
Run with:
    evennia test world
"""

from django.test import SimpleTestCase

from world.speech_format import normalize_speech


class NormalizeSpeechTests(SimpleTestCase):
    def test_capitalizes_first_letter(self):
        text, _ = normalize_speech("hello there")
        self.assertEqual(text, "Hello there.")

    def test_adds_missing_period(self):
        text, _ = normalize_speech("hello there")
        self.assertTrue(text.endswith("."))

    def test_does_not_double_up_existing_period(self):
        text, _ = normalize_speech("hello there.")
        self.assertEqual(text, "Hello there.")

    def test_keeps_existing_exclamation_point(self):
        text, _ = normalize_speech("watch out!")
        self.assertEqual(text, "Watch out!")

    def test_keeps_existing_question_mark(self):
        text, _ = normalize_speech("how are you?")
        self.assertEqual(text, "How are you?")

    def test_reports_is_question_for_question_mark(self):
        _, is_question = normalize_speech("how are you?")
        self.assertTrue(is_question)

    def test_reports_not_a_question_for_statement(self):
        _, is_question = normalize_speech("hello there")
        self.assertFalse(is_question)

    def test_already_capitalized_is_left_alone(self):
        text, _ = normalize_speech("Hello there.")
        self.assertEqual(text, "Hello there.")

    def test_empty_string_is_unchanged(self):
        text, is_question = normalize_speech("")
        self.assertEqual(text, "")
        self.assertFalse(is_question)

    def test_leading_non_letter_is_left_alone(self):
        # e.g. an ellipsis or a leading emoticon - no letter to
        # capitalize, don't crash or mangle it.
        text, _ = normalize_speech("...well")
        self.assertEqual(text, "...well.")

    def test_strips_surrounding_whitespace(self):
        text, _ = normalize_speech("  hello there  ")
        self.assertEqual(text, "Hello there.")

    def test_capitalizes_standalone_i(self):
        text, _ = normalize_speech("can i get a hot drink")
        self.assertEqual(text, "Can I get a hot drink.")

    def test_capitalizes_i_in_contraction(self):
        text, _ = normalize_speech("i'm not sure what i'll do")
        self.assertEqual(text, "I'm not sure what I'll do.")

    def test_does_not_touch_i_inside_a_longer_word(self):
        text, _ = normalize_speech("hi there, this is fine")
        self.assertEqual(text, "Hi there, this is fine.")

    def test_capitalizes_after_every_sentence(self):
        text, _ = normalize_speech("that's great. how are you. i'm fine")
        self.assertEqual(text, "That's great. How are you. I'm fine.")

    def test_capitalizes_after_exclamation_and_question_marks(self):
        text, _ = normalize_speech("watch out! are you okay? i think so")
        self.assertEqual(text, "Watch out! Are you okay? I think so.")

    def test_is_question_still_reflects_the_final_sentence(self):
        _, is_question = normalize_speech("that's great. are you okay?")
        self.assertTrue(is_question)
