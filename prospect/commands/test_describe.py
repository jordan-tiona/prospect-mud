"""
Tests for commands/describe.py: setting, showing and clearing a pose
and the two descriptions, including the plain-English phrasings, and
where each one shows up (room line, look, probe).

Run with:
    evennia test commands.test_describe
"""

from django.test import TestCase
from evennia import create_object


def _record_text(text="", **kwargs):
    if isinstance(text, (tuple, list)):
        text = text[0]
    return text


class DescribeTests(TestCase):
    def setUp(self):
        self.room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.room.db.desc = "The test room's description."
        self.actor = create_object("typeclasses.characters.Character", key="Tester", location=self.room)
        self.other = create_object("typeclasses.characters.Character", key="Other", location=self.room)
        self.messages = []
        self.actor.msg = lambda text="", **kw: self.messages.append(_record_text(text, **kw))
        self.other_messages = []
        self.other.msg = lambda text="", **kw: self.other_messages.append(_record_text(text, **kw))

    def _output(self):
        return "\n".join(m for m in self.messages if m)

    def test_terse_forms_set_each_field(self):
        self.actor.execute_cmd("describe pose leaning on the counter")
        self.actor.execute_cmd("describe short tall and rangy, with a scarred jaw")
        self.actor.execute_cmd("describe long Years of dock work show in the hands.")
        self.assertEqual(self.actor.db.ambient_pose, "leaning on the counter")
        self.assertEqual(self.actor.db.desc, "tall and rangy, with a scarred jaw")
        self.assertEqual(self.actor.db.probe_desc, "Years of dock work show in the hands.")

    def test_plain_english_forms(self):
        self.actor.execute_cmd("change my short description to tall and rangy")
        self.actor.execute_cmd("set my pose to leaning on the counter.")
        self.actor.execute_cmd("update my bio: Years of dock work.")
        self.assertEqual(self.actor.db.desc, "tall and rangy")
        self.assertEqual(self.actor.db.ambient_pose, "leaning on the counter")
        self.assertEqual(self.actor.db.probe_desc, "Years of dock work.")

    def test_clearing(self):
        self.actor.db.ambient_pose = "leaning on the counter"
        self.actor.db.desc = "tall"
        self.actor.execute_cmd("clear my pose")
        self.actor.execute_cmd("describe clear short")
        self.assertFalse(self.actor.db.ambient_pose)
        self.assertFalse(self.actor.db.desc)

    def test_over_the_limit_is_refused_and_nothing_changes(self):
        self.actor.db.ambient_pose = "leaning on the counter"
        self.actor.execute_cmd("describe pose " + "x" * 41)
        self.assertEqual(self.actor.db.ambient_pose, "leaning on the counter")
        self.assertIn("at most 40", self._output())

    def test_bare_describe_lists_every_field_and_how_to_change_it(self):
        self.actor.execute_cmd("describe")
        output = self._output()
        for word in ("POSE", "SHORT", "LONG", "LOOK", "PROBE"):
            self.assertIn(word, output)

    def test_bare_describe_shows_what_others_see(self):
        self.actor.db.species = "Kell"
        self.actor.db.sex = "female"
        self.actor.db.ambient_pose = "leaning on the counter"
        self.actor.execute_cmd("describe")
        output = self._output()
        self.assertIn("In the room: Tester is here, leaning on the counter.", output)
        self.assertIn("When they LOOK at you: A Kell woman.", output)
        self.assertIn("When they PROBE you: (the same as LOOK)", output)
        self.assertIn("can see you're a Kell woman", output)

    def test_what_others_see_without_species_or_sex(self):
        self.actor.db.probe_desc = "Years of dock work."
        self.actor.execute_cmd("describe")
        output = self._output()
        self.assertIn("In the room: Tester is here.", output)
        self.assertIn("When they PROBE you: Years of dock work.", output)
        self.assertIn("no species or sex set", output)

    def test_field_with_no_text_shows_it(self):
        self.actor.db.desc = "tall and rangy"
        self.actor.execute_cmd("describe short")
        self.assertIn("tall and rangy", self._output())
        self.assertEqual(self.actor.db.desc, "tall and rangy")

    def test_unknown_field_explains_the_choices(self):
        self.actor.execute_cmd("change my mind")
        self.assertIn("pose, your short description or your long description", self._output())

    def test_stock_setdesc_is_gone(self):
        self.actor.execute_cmd("setdesc anything at all")
        self.assertFalse(self.actor.db.desc)

    def test_others_see_pose_on_look_and_long_on_probe(self):
        self.actor.execute_cmd("describe pose leaning on the counter")
        self.actor.execute_cmd("describe short tall and rangy")
        self.actor.execute_cmd("describe long Years of dock work.")
        self.other.execute_cmd("look")
        self.other.execute_cmd("look Tester")
        self.other.execute_cmd("probe Tester")
        seen = "\n".join(m for m in self.other_messages if m)
        self.assertIn("Tester is here, leaning on the counter.", seen)
        self.assertIn("tall and rangy", seen)
        self.assertIn("Years of dock work.", seen)

    def test_look_without_a_short_description_shows_species_and_sex(self):
        self.actor.db.species = "Kell"
        self.actor.db.sex = "female"
        self.other.execute_cmd("look Tester")
        seen = "\n".join(m for m in self.other_messages if m)
        self.assertIn("A Kell woman.", seen)
