"""
Tests for world/prompt_builder.py against the real content files: the
shared action rules reach exactly the NPCs that have each action, and
every action an NPC lists is explained somewhere in its prompt.
"""

from django.test import SimpleTestCase

from world.actions import _ACTION_VALIDATORS
from world.content_files import CONTENT_DIR, read_content_file
from world.npc_profile import parse_persona
from world.prompt_builder import ACTIONS_DIR, build_system_prompt, shared_action_rules

NPC_IDS = sorted(path.stem for path in (CONTENT_DIR / "npcs").glob("*.md"))
ACTION_FILES = sorted(path.stem for path in (CONTENT_DIR / ACTIONS_DIR).glob("*.md"))


class SharedActionRulesTests(SimpleTestCase):
    def test_every_action_file_is_a_real_action(self):
        for name in ACTION_FILES:
            with self.subTest(action=name):
                self.assertIn(name, _ACTION_VALIDATORS)

    def test_a_block_appears_only_for_npcs_with_that_action(self):
        for npc_id in NPC_IDS:
            profile = parse_persona(npc_id)
            text = build_system_prompt(npc_id).text
            for name in ACTION_FILES:
                with self.subTest(npc=npc_id, action=name):
                    self.assertEqual(f"### {name}\n" in text, name in profile.actions)

    def test_no_actions_with_files_gives_nothing(self):
        self.assertEqual(shared_action_rules(["serve_drink"]), "")

    def test_comments_are_stripped(self):
        self.assertNotIn("<!--", shared_action_rules(ACTION_FILES))
        self.assertIn("### give_directions", shared_action_rules(["give_directions"]))

    def test_action_rules_sit_after_the_persona_and_before_scoped_lore(self):
        profile = parse_persona("iri_vael")
        text = build_system_prompt("iri_vael").text
        rules = text.index("## How your actions work")
        self.assertGreater(rules, text.index(profile.body[-200:]))
        if "## What you specifically know" in text:
            self.assertLess(rules, text.index("## What you specifically know"))


class PersonaActionCoverageTests(SimpleTestCase):
    def test_every_listed_action_is_real(self):
        for npc_id in NPC_IDS:
            for name in parse_persona(npc_id).actions:
                with self.subTest(npc=npc_id, action=name):
                    self.assertIn(name, _ACTION_VALIDATORS)

    def test_every_listed_action_is_explained_in_the_prompt(self):
        # A persona bullet, a content/actions file, or the shared rules.
        shared_rules = read_content_file("npc-shared-rules.md")
        for npc_id in NPC_IDS:
            profile = parse_persona(npc_id)
            for name in profile.actions:
                with self.subTest(npc=npc_id, action=name):
                    self.assertTrue(
                        f"**{name}**" in profile.body or name in ACTION_FILES or f"`{name}`" in shared_rules
                    )
