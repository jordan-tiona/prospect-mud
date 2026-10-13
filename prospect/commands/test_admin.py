"""
Tests for the builder-only `forget`/`restock` testing commands
(commands/admin.py).

Run with:
    evennia test commands
"""

from unittest.mock import patch

from django.test import TestCase
from evennia import create_object

from world.actions import DEFAULT_STOCK, get_quest_state, validate_and_apply
from world.build_npcs import build as build_npcs
from world.build_rooms import build as build_rooms
from world.commitments import accept_commitment, get_state_summary, propose_commitment, record_acknowledgment


class ForgetCommandTests(TestCase):
    def setUp(self):
        rooms = build_rooms()
        npcs = build_npcs()
        self.cafe = rooms["corner_cafe"]
        self.mara = npcs["mara_voss"]
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=self.cafe
        )
        self.actor.permissions.add("Builder")
        self.messages = []
        self.actor.msg = lambda text="", **kw: self.messages.append(text)

        # Real logging is covered by world/test_conversation_log.py;
        # here we just confirm commands/admin.py calls it correctly,
        # the same convention test_say.py uses for log_turn.
        log_patcher = patch("commands.admin.log_reset")
        self.mock_log_reset = log_patcher.start()
        self.addCleanup(log_patcher.stop)

    def test_clears_existing_history(self):
        self.mara.ndb.conversations = {self.actor.dbref: [{"role": "user", "content": "hi"}]}
        self.mara.ndb.conversation_ids = {self.actor.dbref: "abc123"}
        self.mara.ndb.turn_counters = {self.actor.dbref: 3}

        self.actor.execute_cmd("forget Mara Voss")

        self.assertNotIn(self.actor.dbref, self.mara.ndb.conversations)
        self.assertNotIn(self.actor.dbref, self.mara.ndb.conversation_ids)
        self.assertNotIn(self.actor.dbref, self.mara.ndb.turn_counters)
        self.assertTrue(any("clear your conversation history" in m for m in self.messages))

        self.mock_log_reset.assert_called_once_with(
            conversation_id="abc123",
            npc_id="mara_voss",
            actor_key="Tester",
            actor_dbref=self.actor.dbref,
        )

    def test_no_history_does_not_log_a_reset(self):
        self.actor.execute_cmd("forget Mara Voss")

        self.mock_log_reset.assert_not_called()

    def test_no_history_gives_clear_feedback(self):
        self.actor.execute_cmd("forget Mara Voss")

        self.assertTrue(any("no conversation history" in m for m in self.messages))

    def test_non_talkative_target_is_rejected(self):
        self.actor.execute_cmd("forget south")  # the exit back to Old Quarter Square

        self.assertTrue(any("doesn't seem to remember" in m for m in self.messages))

    def test_requires_builder_permission(self):
        self.actor.permissions.remove("Builder")
        self.mara.ndb.conversations = {self.actor.dbref: [{"role": "user", "content": "hi"}]}

        self.actor.execute_cmd("forget Mara Voss")

        self.assertIn(self.actor.dbref, self.mara.ndb.conversations)


class RestockCommandTests(TestCase):
    def setUp(self):
        rooms = build_rooms()
        npcs = build_npcs()
        self.workshop = rooms["maintenance_workshop"]
        self.tarin = npcs["tarin_os"]
        self.mara = npcs["mara_voss"]
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=self.workshop
        )
        self.actor.permissions.add("Builder")
        self.messages = []
        self.actor.msg = lambda text="", **kw: self.messages.append(text)

    def test_resets_depleted_stock_to_default(self):
        self.tarin.db.stock = {"spare part": 0, "hand tool": 1}

        self.actor.execute_cmd("restock Tarin Os")

        self.assertEqual(self.tarin.db.stock, DEFAULT_STOCK)
        self.assertTrue(any("restock" in m for m in self.messages))

    def test_npc_without_hand_over_item_is_rejected(self):
        self.mara.location = self.workshop  # bring her within search range

        self.actor.execute_cmd("restock Mara Voss")

        self.assertTrue(any("doesn't keep any stock" in m for m in self.messages))

    def test_non_npc_target_is_rejected(self):
        self.actor.execute_cmd("restock west")  # the exit back to Old Quarter Square

        self.assertTrue(any("doesn't keep any stock" in m for m in self.messages))

    def test_requires_builder_permission(self):
        self.actor.permissions.remove("Builder")
        self.tarin.db.stock = {"spare part": 0, "hand tool": 0}

        self.actor.execute_cmd("restock Tarin Os")

        self.assertEqual(self.tarin.db.stock, {"spare part": 0, "hand tool": 0})


class ResetQuestCommandTests(TestCase):
    def setUp(self):
        rooms = build_rooms()
        npcs = build_npcs()
        self.cafe = rooms["corner_cafe"]
        self.mara = npcs["mara_voss"]
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=self.cafe
        )
        self.actor.permissions.add("Builder")
        self.messages = []
        self.actor.msg = lambda text="", **kw: self.messages.append(text)

        log_patcher = patch("commands.admin.log_quest_reset")
        self.mock_log_quest_reset = log_patcher.start()
        self.addCleanup(log_patcher.stop)

    def test_resets_own_quest_state_with_no_argument(self):
        validate_and_apply(self.mara, self.actor, "accept_help", {})

        self.actor.execute_cmd("resetquest")

        self.assertEqual(get_quest_state(self.actor), "not_started")
        self.assertTrue(any("reset" in m for m in self.messages))

    def test_resets_named_player(self):
        other = create_object(
            "typeclasses.characters.Character", key="Other", location=self.cafe
        )
        validate_and_apply(self.mara, other, "accept_help", {})

        self.actor.execute_cmd("resetquest Other")

        self.assertEqual(get_quest_state(other), "not_started")

    def test_already_at_start_gives_clear_feedback_and_does_not_log(self):
        self.actor.execute_cmd("resetquest")

        self.assertTrue(any("already at the start" in m for m in self.messages))
        self.mock_log_quest_reset.assert_not_called()

    def test_logs_the_previous_state(self):
        validate_and_apply(self.mara, self.actor, "accept_help", {})
        validate_and_apply(self.mara, self.actor, "give_faulty_module", {})

        self.actor.execute_cmd("resetquest")

        self.mock_log_quest_reset.assert_called_once_with(
            quest_key="quest_module_exchange",
            previous_state="has_faulty_module",
            actor_key="Tester",
            actor_dbref=self.actor.dbref,
        )

    def test_requires_builder_permission(self):
        self.actor.permissions.remove("Builder")
        validate_and_apply(self.mara, self.actor, "accept_help", {})

        self.actor.execute_cmd("resetquest")

        self.assertEqual(get_quest_state(self.actor), "accepted")


class ResetCommitmentCommandTests(TestCase):
    COMMITMENT_TYPE = "discrepancy_report"

    def setUp(self):
        rooms = build_rooms()
        build_npcs()
        self.workshop = rooms["maintenance_workshop"]
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=self.workshop
        )
        self.actor.permissions.add("Builder")
        self.messages = []
        self.actor.msg = lambda text="", **kw: self.messages.append(text)

        log_patcher = patch("commands.admin.log_commitment_reset")
        self.mock_log_commitment_reset = log_patcher.start()
        self.addCleanup(log_patcher.stop)

    def test_resets_own_commitment_with_no_argument(self):
        propose_commitment(self.actor, self.COMMITMENT_TYPE)
        accept_commitment(self.actor, self.COMMITMENT_TYPE)

        self.actor.execute_cmd("resetcommitment")

        self.assertEqual(get_state_summary(self.actor, self.COMMITMENT_TYPE), "not offered")
        self.assertTrue(any("reset" in m for m in self.messages))

    def test_resets_named_player(self):
        other = create_object(
            "typeclasses.characters.Character", key="Other", location=self.workshop
        )
        propose_commitment(other, self.COMMITMENT_TYPE)
        accept_commitment(other, self.COMMITMENT_TYPE)

        self.actor.execute_cmd("resetcommitment Other")

        self.assertEqual(get_state_summary(other, self.COMMITMENT_TYPE), "not offered")

    def test_nothing_to_reset_gives_clear_feedback_and_does_not_log(self):
        self.actor.execute_cmd("resetcommitment")

        self.assertTrue(any("no commitment progress" in m for m in self.messages))
        self.mock_log_commitment_reset.assert_not_called()

    def test_logs_the_previous_state(self):
        propose_commitment(self.actor, self.COMMITMENT_TYPE)
        accept_commitment(self.actor, self.COMMITMENT_TYPE)
        record_acknowledgment(self.actor, self.COMMITMENT_TYPE, "veska_renn")

        self.actor.execute_cmd("resetcommitment")

        self.mock_log_commitment_reset.assert_called_once_with(
            commitment_type=self.COMMITMENT_TYPE,
            had_offer=False,
            previous_statuses=["open"],
            actor_key="Tester",
            actor_dbref=self.actor.dbref,
        )

    def test_requires_builder_permission(self):
        self.actor.permissions.remove("Builder")
        propose_commitment(self.actor, self.COMMITMENT_TYPE)
        accept_commitment(self.actor, self.COMMITMENT_TYPE)

        self.actor.execute_cmd("resetcommitment")

        self.assertEqual(get_state_summary(self.actor, self.COMMITMENT_TYPE), "open, not yet acknowledged")
