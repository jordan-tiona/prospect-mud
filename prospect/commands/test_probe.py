"""
Run with:
    evennia test commands.test_probe
"""

from django.test import TestCase
from evennia import create_object

from world.skitters import bank_kills, record_kill


def _record_text(text="", **kwargs):
    if isinstance(text, (tuple, list)):
        text = text[0]
    return text


class ProbeTests(TestCase):
    def setUp(self):
        self.room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.room.db.desc = "The test room's description."
        self.actor = create_object("typeclasses.characters.Character", key="Tester", location=self.room)
        self.board = create_object("typeclasses.objects.RoomObject", key="notice board", location=self.room)
        self.board.db.desc = "The look text."
        self.messages = []
        self.actor.msg = lambda text="", **kw: self.messages.append(_record_text(text, **kw))

    def _output(self):
        return "\n".join(m for m in self.messages if m)

    def test_probe_shows_probe_desc(self):
        self.board.db.probe_desc = "The longer probe text."
        self.actor.execute_cmd("probe notice board")
        self.assertIn("The longer probe text.", self._output())
        self.assertNotIn("The look text.", self._output())

    def test_probe_without_probe_desc_shows_look_text(self):
        self.actor.execute_cmd("probe notice board")
        self.assertIn("The look text.", self._output())

    def test_look_ignores_probe_desc(self):
        self.board.db.probe_desc = "The longer probe text."
        self.actor.execute_cmd("look notice board")
        self.assertIn("The look text.", self._output())
        self.assertNotIn("The longer probe text.", self._output())

    def test_probe_strips_article(self):
        self.board.db.probe_desc = "The longer probe text."
        self.actor.execute_cmd("probe the notice board")
        self.assertIn("The longer probe text.", self._output())

    def test_probe_with_nothing_after(self):
        self.actor.execute_cmd("probe")
        self.assertIn("Probe what?", self._output())

    def test_probe_npc_shows_probe_desc(self):
        npc = create_object("typeclasses.npcs.NPC", key="a stranger", location=self.room)
        npc.db.desc = "The NPC's look text."
        npc.db.probe_desc = "The NPC's probe text."
        self.actor.execute_cmd("probe stranger")
        self.assertIn("The NPC's probe text.", self._output())

    def test_probe_hidden_object_not_found(self):
        # Same search and view locks as look: something this player can't
        # see (e.g. a quest prop whose commitment they've already had
        # offered) can't be probed either.
        hidden = create_object("typeclasses.objects.CommitmentHintObject", key="parcel", location=self.room)
        hidden.db.desc = "Hidden look text."
        hidden.db.probe_desc = "Hidden probe text."
        hidden.locks.add("view:false();search:false()")
        self.actor.execute_cmd("probe parcel")
        self.assertNotIn("Hidden probe text.", self._output())
        self.assertNotIn("Hidden look text.", self._output())

    def test_probe_per_looker_object_shows_its_look_text(self):
        # The pest log builds its text per player; probe shows the same.
        ledger = create_object("typeclasses.objects.SkitterLedgerObject", key="pest log", location=self.room)
        ledger.db.desc = "The pest log."
        ledger.db.probe_desc = "Unused probe text."
        record_kill(self.actor)
        bank_kills(self.actor)
        self.actor.execute_cmd("probe pest log")
        self.assertIn("Under your name: 1 skitter logged.", self._output())
