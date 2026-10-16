"""
Tests for the ambient NPC's rotating-pose mechanism
(typeclasses.npcs.NPC.set_ambient_poses / at_pose_tick).

Run with:
    evennia test typeclasses
"""

from unittest.mock import patch

from django.test import TestCase
from evennia import create_object


class AmbientPoseRotationTests(TestCase):
    def setUp(self):
        # A real room: with no location, Evennia sets home to DEFAULT_HOME
        # (#2), which doesn't exist in the test DB and fails teardown's
        # foreign-key check.
        room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.npc = create_object("typeclasses.npcs.NPC", key="A dockhand", location=room, home=room)

    def test_set_ambient_poses_seeds_an_initial_pose(self):
        self.npc.set_ambient_poses(["sweeping", "coiling a line"])
        self.assertIn(self.npc.db.ambient_pose, ["sweeping", "coiling a line"])

    def test_set_ambient_poses_stores_the_full_list(self):
        poses = ["sweeping", "coiling a line", "checking a manifest"]
        self.npc.set_ambient_poses(poses)
        self.assertEqual(self.npc.db.ambient_poses, poses)

    def test_pose_tick_picks_from_the_list(self):
        self.npc.set_ambient_poses(["sweeping", "coiling a line"])
        self.npc.at_pose_tick()
        self.assertIn(self.npc.db.ambient_pose, ["sweeping", "coiling a line"])

    def test_pose_tick_prefers_a_different_pose_when_possible(self):
        self.npc.set_ambient_poses(["sweeping", "coiling a line"])
        self.npc.db.ambient_pose = "sweeping"
        with patch("typeclasses.npcs.random.choice", side_effect=lambda seq: seq[0]):
            self.npc.at_pose_tick()
        self.assertEqual(self.npc.db.ambient_pose, "coiling a line")

    def test_pose_tick_is_silent(self):
        self.npc.set_ambient_poses(["sweeping", "coiling a line"])
        with patch.object(self.npc, "msg") as mock_msg:
            self.npc.at_pose_tick()
        mock_msg.assert_not_called()

    def test_pose_tick_without_poses_set_does_nothing(self):
        # an NPC using a single fixed db.ambient_pose, never subscribed
        self.npc.db.ambient_pose = "idly drying a glass"
        self.npc.at_pose_tick()
        self.assertEqual(self.npc.db.ambient_pose, "idly drying a glass")

    def test_set_ambient_poses_subscribes_to_ticker_handler(self):
        with patch("typeclasses.npcs.TICKER_HANDLER") as mock_handler:
            self.npc.set_ambient_poses(["sweeping", "coiling a line"])
        mock_handler.add.assert_called_once()
        _, kwargs = mock_handler.add.call_args
        self.assertEqual(kwargs["callback"], self.npc.at_pose_tick)
        self.assertEqual(kwargs["idstring"], "ambient_pose")
