"""
Tests for the builder-only `forget` testing command (commands/admin.py).

Run with:
    evennia test commands
"""

from unittest.mock import patch

from django.test import TestCase
from evennia import create_object

from world.actions import (
    PARCEL_TAG_CATEGORY,
    _actor_has_correct_parcel,
    _create_parcel_for,
    _validate_accept_help,
    _validate_give_faulty_module,
    get_quest_state,
)
from world.build_npcs import build as build_npcs
from world.build_rooms import build as build_rooms
from world.commitments import (
    accept_commitment,
    fulfill_commitment_with_precondition,
    get_open_commitment_id,
    get_state_summary,
    propose_commitment,
    record_acknowledgment,
)


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
        _validate_accept_help(self.mara, self.actor, {})

        self.actor.execute_cmd("resetquest")

        self.assertEqual(get_quest_state(self.actor), "not_started")
        self.assertTrue(any("reset" in m for m in self.messages))

    def test_resets_named_player(self):
        other = create_object(
            "typeclasses.characters.Character", key="Other", location=self.cafe
        )
        _validate_accept_help(self.mara, other, {})

        self.actor.execute_cmd("resetquest Other")

        self.assertEqual(get_quest_state(other), "not_started")

    def test_already_at_start_gives_clear_feedback_and_does_not_log(self):
        self.actor.execute_cmd("resetquest")

        self.assertTrue(any("already at the start" in m for m in self.messages))
        self.mock_log_quest_reset.assert_not_called()

    def test_logs_the_previous_state(self):
        _validate_accept_help(self.mara, self.actor, {})
        _validate_give_faulty_module(self.mara, self.actor, {})

        self.actor.execute_cmd("resetquest")

        self.mock_log_quest_reset.assert_called_once_with(
            quest_key="quest_module_exchange",
            previous_state="has_faulty_module",
            actor_key="Tester",
            actor_dbref=self.actor.dbref,
        )

    def test_requires_builder_permission(self):
        self.actor.permissions.remove("Builder")
        _validate_accept_help(self.mara, self.actor, {})

        self.actor.execute_cmd("resetquest")

        self.assertEqual(get_quest_state(self.actor), "accepted")


class ResetCommitmentCommandTests(TestCase):
    # verify_display_revision (holder=mara_voss, clerk=iri_vael) used
    # purely as an example commitment_type to exercise resetcommitment's
    # generic clearing logic. (Originally discrepancy_report; removed
    # 2026-10-16, see CLAUDE.md's "One quest offer per NPC".)
    COMMITMENT_TYPE = "verify_display_revision"

    def setUp(self):
        rooms = build_rooms()
        self.npcs = build_npcs()
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

        rumor_log_patcher = patch("commands.admin.log_rumor_reset")
        self.mock_log_rumor_reset = rumor_log_patcher.start()
        self.addCleanup(rumor_log_patcher.stop)

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
        record_acknowledgment(self.actor, self.COMMITMENT_TYPE, "iri_vael")

        self.actor.execute_cmd("resetcommitment")

        self.mock_log_commitment_reset.assert_any_call(
            commitment_type=self.COMMITMENT_TYPE,
            had_offer=False,
            previous_statuses=["open"],
            had_declined=False,
            actor_key="Tester",
            actor_dbref=self.actor.dbref,
        )

    def test_resets_a_commitment_type_no_longer_in_scenarios(self):
        # Simulates data from before a commitment_type rename (e.g. the
        # 2026-10-13 parcel redesign's old "deliver_parcel_to_tarin",
        # no longer a key in SCENARIOS) - resetcommitment must still
        # find and clear it, not just the currently-authored types.
        from world.commitments import COMMITMENTS_KEY

        stale_id = "stale-commitment-id"
        self.actor.attributes.add(
            COMMITMENTS_KEY,
            {
                stale_id: {
                    "commitment_id": stale_id,
                    "commitment_type": "deliver_parcel_to_tarin",
                    "maker_dbref": self.actor.dbref,
                    "holder_npc_id": "tarin_os",
                    "fulfilled_by_npc_id": None,
                    "status": "open",
                    "created_at": "2026-01-01T00:00:00+00:00",
                }
            },
        )

        self.actor.execute_cmd("resetcommitment")

        self.assertEqual(self.actor.attributes.get(COMMITMENTS_KEY), {})
        self.assertTrue(any("reset" in m for m in self.messages))

    def test_reset_removes_a_stray_carried_parcel(self):
        propose_commitment(self.actor, "deliver_parcel")
        accept_commitment(self.actor, "deliver_parcel")
        commitment_id = get_open_commitment_id(self.actor, "deliver_parcel")
        _create_parcel_for(self.actor, commitment_id)

        self.actor.execute_cmd("resetcommitment")

        self.assertFalse(_actor_has_correct_parcel(self.actor, commitment_id))
        self.assertTrue(any("stray carried parcel" in m for m in self.messages))

    def test_reset_clears_the_generated_revision(self):
        from world.noticeboard import get_or_create_expected_revision

        get_or_create_expected_revision(self.actor)

        self.actor.execute_cmd("resetcommitment")

        self.assertTrue(any("noticeboard revision" in m for m in self.messages))

    def test_reset_with_no_revision_generated_does_not_mention_it(self):
        self.actor.execute_cmd("resetcommitment")

        self.assertFalse(any("noticeboard revision" in m for m in self.messages))

    def test_reset_clears_the_tended_bed_flag(self):
        from world.garden import is_bed_tended, mark_bed_tended

        mark_bed_tended(self.actor)

        self.actor.execute_cmd("resetcommitment")

        self.assertFalse(is_bed_tended(self.actor))
        self.assertTrue(any("tended-planting-bed flag" in m for m in self.messages))

    def test_reset_with_no_tended_bed_does_not_mention_it(self):
        self.actor.execute_cmd("resetcommitment")

        self.assertFalse(any("tended-planting-bed flag" in m for m in self.messages))

    def test_reset_clears_the_skitter_kill_count(self):
        from world.skitters import kills_for, record_kill

        record_kill(self.actor)
        record_kill(self.actor)

        self.actor.execute_cmd("resetcommitment")

        self.assertEqual(kills_for(self.actor), 0)
        self.assertTrue(any("skitter kill count (was 2)" in m for m in self.messages))

    def test_reset_with_no_skitter_kills_does_not_mention_it(self):
        self.actor.execute_cmd("resetcommitment")

        self.assertFalse(any("skitter kill count" in m for m in self.messages))

    def test_requires_builder_permission(self):
        self.actor.permissions.remove("Builder")
        propose_commitment(self.actor, self.COMMITMENT_TYPE)
        accept_commitment(self.actor, self.COMMITMENT_TYPE)

        self.actor.execute_cmd("resetcommitment")

        self.assertEqual(get_state_summary(self.actor, self.COMMITMENT_TYPE), "open, not yet acknowledged")

    def test_reset_clears_rumor_knowledge_and_reputation_credit(self):
        # docs/phase2e-word-gets-around-design.md: resetcommitment must
        # also clear the parcel-rumor's "informed" flag and Mara's
        # reputation credit, since both are downstream of deliver_parcel
        # and a stale one would otherwise survive the underlying
        # commitment being cleared out from under it.
        from world.actions import (
            _validate_accept_commitment,
            _validate_accept_handoff,
            _validate_propose_commitment,
            _validate_report_parcel_delivery,
        )
        from world.reputation import get_reputation
        from world.rumors import has_reputation_credit

        tarin = self.npcs["tarin_os"]
        mara = self.npcs["mara_voss"]
        # Uses the validators (not the bare commitments.py lifecycle
        # functions) specifically because deliver_parcel's accept also
        # creates the real carried Parcel object accept_handoff's
        # possession check needs - see ParcelActionWiringTests in
        # world/test_actions.py for the same requirement.
        _validate_propose_commitment(mara, self.actor, {"commitment_type": "deliver_parcel"})
        _validate_accept_commitment(mara, self.actor, {"commitment_type": "deliver_parcel"})
        _validate_accept_handoff(tarin, self.actor, {"commitment_type": "deliver_parcel"})
        _validate_report_parcel_delivery(mara, self.actor, {"reported_recipient": "tarin"})
        self.assertEqual(get_reputation(self.actor, "mara_voss"), 1)

        self.actor.execute_cmd("resetcommitment")

        self.assertEqual(get_reputation(self.actor, "mara_voss"), 0)
        self.assertFalse(has_reputation_credit(self.actor))
        self.assertTrue(any("rumor knowledge" in m for m in self.messages))
        self.mock_log_rumor_reset.assert_called_once()

    def test_reset_with_no_rumor_progress_does_not_mention_it_or_log(self):
        self.actor.execute_cmd("resetcommitment")

        self.assertFalse(any("rumor knowledge" in m for m in self.messages))
        self.mock_log_rumor_reset.assert_not_called()

class ResetMemoryCommandTests(TestCase):
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

        log_patcher = patch("commands.admin.log_memory_reset")
        self.mock_log_memory_reset = log_patcher.start()
        self.addCleanup(log_patcher.stop)

    def test_resets_own_memory_with_no_argument(self):
        from world.npc_memory import memory_context_for, remember_fact

        remember_fact(self.actor, "tarin_os", "grew up near the Docks")

        self.actor.execute_cmd("resetmemory")

        self.assertIsNone(memory_context_for("tarin_os", self.actor))
        self.assertTrue(any("cleared" in m for m in self.messages))

    def test_resets_named_player(self):
        from world.npc_memory import memory_context_for, remember_fact

        other = create_object(
            "typeclasses.characters.Character", key="Other", location=self.workshop
        )
        remember_fact(other, "tarin_os", "grew up near the Docks")

        self.actor.execute_cmd("resetmemory Other")

        self.assertIsNone(memory_context_for("tarin_os", other))

    def test_nothing_to_reset_gives_clear_feedback_and_does_not_log(self):
        self.actor.execute_cmd("resetmemory")

        self.assertTrue(any("no stored NPC memory" in m for m in self.messages))
        self.mock_log_memory_reset.assert_not_called()

    def test_logs_the_previous_facts(self):
        from world.npc_memory import remember_fact

        remember_fact(self.actor, "tarin_os", "grew up near the Docks")

        self.actor.execute_cmd("resetmemory")

        self.mock_log_memory_reset.assert_called_once()
        kwargs = self.mock_log_memory_reset.call_args.kwargs
        self.assertEqual(kwargs["npc_id"], "tarin_os")
        self.assertEqual(len(kwargs["previous_facts"]), 1)

    def test_requires_builder_permission(self):
        from world.npc_memory import memory_context_for, remember_fact

        self.actor.permissions.remove("Builder")
        remember_fact(self.actor, "tarin_os", "grew up near the Docks")

        self.actor.execute_cmd("resetmemory")

        self.assertIsNotNone(memory_context_for("tarin_os", self.actor))


class MemoryDebugCommandTests(TestCase):
    def setUp(self):
        rooms = build_rooms()
        build_npcs()
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=rooms["maintenance_workshop"]
        )
        self.actor.permissions.add("Builder")
        self.messages = []
        self.actor.msg = lambda text="", **kw: self.messages.append(text)

    def test_toggles_on_then_off(self):
        self.actor.execute_cmd("memorydebug")
        self.assertTrue(self.actor.attributes.get("memory_debug_enabled"))
        self.assertTrue(any("now on" in m for m in self.messages))

        self.actor.execute_cmd("memorydebug")
        self.assertFalse(self.actor.attributes.get("memory_debug_enabled"))
        self.assertTrue(any("now off" in m for m in self.messages))

    def test_defaults_to_self_with_no_argument(self):
        self.actor.execute_cmd("memorydebug")
        self.assertTrue(self.actor.attributes.get("memory_debug_enabled"))

    def test_can_target_another_player(self):
        other = create_object(
            "typeclasses.characters.Character", key="Other", location=self.actor.location
        )
        self.actor.execute_cmd("memorydebug Other")
        self.assertTrue(other.attributes.get("memory_debug_enabled"))
        self.assertFalse(self.actor.attributes.get("memory_debug_enabled"))

    def test_requires_builder_permission(self):
        self.actor.permissions.remove("Builder")
        self.actor.execute_cmd("memorydebug")
        self.assertFalse(self.actor.attributes.get("memory_debug_enabled"))


class GenerateInviteCommandTests(TestCase):
    def setUp(self):
        room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.actor = create_object(
            "typeclasses.characters.Character", key="Tester", location=room
        )
        self.actor.permissions.add("Builder")
        self.messages = []
        self.actor.msg = lambda text="", **kw: self.messages.append(text)

    def test_generates_the_requested_number_of_codes(self):
        self.actor.execute_cmd("geninvite 3")

        shown = "\n".join(self.messages)
        lines = [line for line in shown.splitlines() if line.strip() and ":" not in line]
        # One header line plus 3 code lines.
        self.assertTrue(any("New invite code" in m for m in self.messages))
        self.assertEqual(len(lines), 3)

    def test_rejects_a_non_numeric_count(self):
        self.actor.execute_cmd("geninvite none")

        self.assertTrue(any("Usage:" in m for m in self.messages))

    def test_rejects_a_missing_count(self):
        self.actor.execute_cmd("geninvite")

        self.assertTrue(any("Usage:" in m for m in self.messages))

    def test_requires_builder_permission(self):
        self.actor.permissions.remove("Builder")
        self.actor.execute_cmd("geninvite 1")

        self.assertFalse(any("New invite code" in m for m in self.messages))
