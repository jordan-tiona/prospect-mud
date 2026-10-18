"""
Tests for staff stealth (world/stealth.py, commands/stealth.py): what a
player sees of a hidden admin, what a hidden admin's broadcasts reach,
speaking revealing them, and hidden staff not counting toward implicit
NPC addressing.

Run with:
    evennia test commands.test_stealth
"""

from unittest.mock import patch

from django.test import TestCase
from evennia import create_account, create_object
from evennia.objects.objects import DefaultObject

from world.build_npcs import build as build_npcs
from world.build_rooms import build as build_rooms
from world.npc_addressing import resolve_addressee
from world.stealth import hide, is_hidden, is_staff


def _text(text):
    if isinstance(text, (tuple, list)):
        text = text[0]
    return text or ""


class StealthTests(TestCase):
    def setUp(self):
        self.room = create_object("typeclasses.rooms.Room", key="Test Room")
        self.elsewhere = create_object("typeclasses.rooms.Room", key="Other Room")
        self.admin = self._character("Admin", ["Builder"])
        self.player = self._character("Player", [])
        self.received = {}
        patcher = patch.object(DefaultObject, "msg", autospec=True, side_effect=self._record)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _character(self, key, permissions):
        account = create_account(key, f"{key.lower()}@example.com", "testpassword123", permissions=permissions)
        char = create_object("typeclasses.characters.Character", key=key, location=self.room)
        char.db_account = account
        char.save()
        return char

    def _record(self, obj, text=None, **kwargs):
        self.received.setdefault(obj, []).append(_text(text))

    def _seen_by(self, char):
        return "\n".join(self.received.get(char, []))

    def test_staff_detection(self):
        self.assertTrue(is_staff(self.admin))
        self.assertFalse(is_staff(self.player))
        npc = create_object("typeclasses.characters.Character", key="Nobody", location=self.room)
        self.assertFalse(is_staff(npc))

    def test_stealth_is_staff_only(self):
        self.player.execute_cmd("stealth")
        self.assertFalse(is_hidden(self.player))

    def test_toggle(self):
        self.admin.execute_cmd("stealth")
        self.assertTrue(is_hidden(self.admin))
        self.admin.execute_cmd("stealth")
        self.assertFalse(is_hidden(self.admin))
        self.admin.execute_cmd("stealth on")
        self.assertTrue(is_hidden(self.admin))
        self.admin.execute_cmd("stealth off")
        self.assertFalse(is_hidden(self.admin))

    def test_hidden_admin_missing_from_player_room_view_and_search(self):
        hide(self.admin)
        view = self.room.return_appearance(self.player)
        self.assertNotIn("Admin", view)
        self.assertIsNone(self.player.search("Admin", quiet=True) or None)

    def test_hidden_admin_sees_reminder_and_visible_admin_does_not(self):
        self.assertNotIn("hidden", self.admin.at_look(self.room))
        hide(self.admin)
        self.assertIn("You are hidden from players", self.admin.at_look(self.room))

    def test_movement_not_announced_to_players(self):
        hide(self.admin)
        self.received.clear()  # hiding itself is announced
        self.admin.move_to(self.elsewhere)
        self.admin.move_to(self.room)
        self.assertNotIn("Admin", self._seen_by(self.player))

    def test_movement_still_announced_to_other_staff(self):
        other_staff = self._character("Mod", ["Builder"])
        hide(self.admin)
        self.admin.move_to(self.elsewhere)
        self.assertIn("Admin", self._seen_by(other_staff))

    def test_visible_admin_movement_is_announced(self):
        self.admin.move_to(self.elsewhere)
        self.assertIn("Admin", self._seen_by(self.player))

    def test_pose_reveals_with_reminder_and_goes_through(self):
        hide(self.admin)
        self.admin.execute_cmd("pose waves.")
        self.assertFalse(is_hidden(self.admin))
        self.assertIn("Speaking has revealed you", self._seen_by(self.admin))
        self.assertIn("waves", self._seen_by(self.player))
        self.assertIn("Admin", self.room.return_appearance(self.player))

    def test_revealing_is_announced_to_the_room(self):
        hide(self.admin)
        self.admin.execute_cmd("stealth off")
        self.assertIn("Admin arrives from... nowhere?", self._seen_by(self.player))
        self.assertNotIn("arrives from... nowhere?", self._seen_by(self.admin))

    def test_speaking_while_hidden_announces_before_the_speech(self):
        hide(self.admin)
        self.admin.execute_cmd("say hello all")
        seen = self._seen_by(self.player)
        self.assertLess(seen.index("arrives from... nowhere?"), seen.index("Hello all"))

    def test_hiding_is_announced_to_the_room(self):
        self.admin.execute_cmd("stealth on")
        self.assertIn("Admin leaves to the... nowhere?", self._seen_by(self.player))
        self.assertNotIn("nowhere?", self._seen_by(self.admin))

    def test_turning_stealth_on_while_hidden_announces_nothing(self):
        hide(self.admin)
        self.received.clear()
        self.admin.execute_cmd("stealth on")
        self.assertNotIn("nowhere?", self._seen_by(self.player))

    def test_turning_stealth_off_while_visible_announces_nothing(self):
        self.admin.execute_cmd("stealth off")
        self.assertNotIn("arrives from... nowhere?", self._seen_by(self.player))

    def test_emote_adds_a_missing_period(self):
        self.admin.execute_cmd("emote smiles")
        self.assertIn("Admin smiles.", self._seen_by(self.player))

    def test_emote_keeps_existing_punctuation(self):
        from commands.stealth import punctuate_pose

        for text in ("waves!", 'says, "hi"', "shrugs...", "grins (barely)", "nods?"):
            self.assertEqual(punctuate_pose(text), text)
        self.assertEqual(punctuate_pose("smiles  "), "smiles.")

    def test_ambient_say_reveals_and_goes_through(self):
        hide(self.admin)
        self.admin.execute_cmd("say hello all")
        self.assertFalse(is_hidden(self.admin))
        self.assertIn("Hello all", self._seen_by(self.player))


class StaffAddressingTests(TestCase):
    def setUp(self):
        rooms = build_rooms()
        npcs = build_npcs()
        self.cafe = rooms["corner_cafe"]
        self.mara = npcs["mara_voss"]
        self.player = create_object("typeclasses.characters.Character", key="Player", location=self.cafe)
        account = create_account("Admin", "admin@example.com", "testpassword123", permissions=["Builder"])
        self.admin = create_object("typeclasses.characters.Character", key="Admin", location=self.cafe)
        self.admin.db_account = account
        self.admin.save()

    def test_hidden_staff_dont_block_a_players_implicit_say(self):
        hide(self.admin)
        npc, _ = resolve_addressee("hello there", self.cafe, speaker=self.player)
        self.assertEqual(npc, self.mara)

    def test_visible_staff_count_like_any_player(self):
        # The tester can see them and may be talking to them (owner, 2026-10-17).
        npc, _ = resolve_addressee("hello there", self.cafe, speaker=self.player)
        self.assertIsNone(npc)
        npc, _ = resolve_addressee("to Mara, hello there", self.cafe, speaker=self.player)
        self.assertEqual(npc, self.mara)

    def test_staff_speaker_with_a_player_present_must_name_the_npc(self):
        npc, _ = resolve_addressee("hello there", self.cafe, speaker=self.admin)
        self.assertIsNone(npc)
        npc, _ = resolve_addressee("to Mara, hello there", self.cafe, speaker=self.admin)
        self.assertEqual(npc, self.mara)

    def test_staff_speaker_alone_with_the_npc_is_addressed_implicitly(self):
        self.player.location = None
        npc, _ = resolve_addressee("hello there", self.cafe, speaker=self.admin)
        self.assertEqual(npc, self.mara)
