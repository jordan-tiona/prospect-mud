"""
Tests for ambient NPCs reacting to `say to <name>` (LR-LORE-0007):
world/npc_addressing.py's addressed_ambient_npc, world/ambient_reactions.py,
the addressed-responses loader in world/ambient_content.py, and the
`say` wiring.

Run with:
    evennia test world.test_ambient_reactions
"""

from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from evennia import create_object

from world.ambient_content import parse_addressed_responses_text
from world.npc_addressing import addressed_ambient_npc

_RESPONSES = """\
<!--
content_id: ambient_addressed_responses
approval: {approval}
-->

# Ambient NPC responses

## Responses

- {{name}} nods.
- {{name}} shrugs.
"""

_LINES = ["{name} nods."]


def _text(text):
    return text[0] if isinstance(text, (tuple, list)) else text or ""


class ParseAddressedResponsesTests(SimpleTestCase):
    def test_approved_file_gives_its_lines(self):
        self.assertEqual(parse_addressed_responses_text(_RESPONSES.format(approval="Approved")),
                         ["{name} nods.", "{name} shrugs."])

    def test_draft_file_gives_nothing(self):
        self.assertEqual(parse_addressed_responses_text(_RESPONSES.format(approval="Draft")), [])


class AmbientReactionTests(TestCase):
    def setUp(self):
        self.square = create_object("typeclasses.rooms.Room", key="Square")
        self.street = create_object("typeclasses.rooms.Room", key="Street")
        self.kell = create_object("typeclasses.npcs.NPC", key="An elderly Kell", location=self.square)
        self.courier = create_object("typeclasses.npcs.NPC", key="An Astrel courier", location=self.square)
        self.actor = create_object("typeclasses.characters.Character", key="Tester", location=self.square)
        self.actor.ndb.ambient_reacted = None
        self.messages = []
        self.actor.msg = lambda text="", **kw: self.messages.append(_text(text))
        self.other = create_object("typeclasses.characters.Character", key="Other", location=self.square)
        self.other_messages = []
        self.other.msg = lambda text="", **kw: self.other_messages.append(_text(text))
        patcher = patch("world.ambient_reactions.addressed_responses", return_value=_LINES)
        self.responses = patcher.start()
        self.addCleanup(patcher.stop)

    def _say(self, message):
        self.actor.execute_cmd(f"say {message}")

    def _reactions(self, messages=None):
        return [m for m in (self.messages if messages is None else messages) if m.endswith(" nods.")]

    # -- matching ----------------------------------------------------------

    def test_names_that_match(self):
        for speech in ("to An elderly Kell, hi", "to elderly kell, hi", "to the Kell, hi", "to Kell hi",
                       "TO THE ELDERLY KELL"):
            with self.subTest(speech):
                self.assertEqual(addressed_ambient_npc(speech, self.square), self.kell)
        self.assertEqual(addressed_ambient_npc("to the courier, wait", self.square), self.courier)

    def test_names_that_do_not_match(self):
        for speech in ("hello Kell", "I'm a Kell too", "to Kellan, hi", "to someone, hi", "tomorrow, Kell"):
            with self.subTest(speech):
                self.assertIsNone(addressed_ambient_npc(speech, self.square))

    def test_talk_npcs_are_not_ambient(self):
        create_object("typeclasses.npcs.TalkativeNPC", key="Mara Voss", location=self.square)
        self.assertIsNone(addressed_ambient_npc("to Mara, hi", self.square))

    # -- say ---------------------------------------------------------------

    def test_first_address_gets_a_reaction_after_the_speech(self):
        self._say("to the Kell, nice day")
        self.assertEqual(self._reactions(), ["The elderly Kell nods."])
        self.assertLess(next(i for i, m in enumerate(self.messages) if "nice day" in m),
                        self.messages.index("The elderly Kell nods."))

    def test_only_the_speaker_sees_the_reaction(self):
        self._say("to the Kell, nice day")
        self.assertTrue(any("nice day" in m for m in self.other_messages))
        self.assertEqual(self._reactions(self.other_messages), [])

    def test_once_per_visit_per_npc(self):
        self._say("to the Kell, nice day")
        self._say("to the Kell, I said nice day")
        self._say("to the courier, hello")
        self.assertEqual(self._reactions(), ["The elderly Kell nods.", "The Astrel courier nods."])

    def test_leaving_and_coming_back_resets_it(self):
        self._say("to the Kell, hello")
        self.actor.move_to(self.street, quiet=True)
        self.actor.move_to(self.square, quiet=True)
        self._say("to the Kell, hello again")
        self.assertEqual(len(self._reactions()), 2)

    def test_no_reaction_while_the_lines_are_draft(self):
        self.responses.return_value = []
        self._say("to the Kell, hello")
        self.assertEqual(self._reactions(), [])
        # Not used up: once lines exist, the first address still reacts.
        self.responses.return_value = _LINES
        self._say("to the Kell, hello")
        self.assertEqual(len(self._reactions()), 1)

    def test_plain_speech_gets_no_reaction(self):
        self._say("what a day, Kell")
        self.assertEqual(self._reactions(), [])
