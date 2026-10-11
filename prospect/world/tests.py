"""
Tests for the prompt builder and its supporting modules (npc_profile,
lore_store). CLAUDE.md calls these out explicitly: this is where a
silent bug would leak non-canon lore into a model prompt (hard rule
4) or corrupt an NPC's declared identity.

Run with:
    evennia test world
"""

from django.test import SimpleTestCase

from world.lore_store import LoreNotFoundError, get_lore_chunk, get_scoped_lore
from world.npc_profile import NPCProfile, PersonaParseError, parse_persona, parse_persona_text
from world.prompt_builder import build_system_prompt

ALL_NPC_IDS = ["mara_voss", "tarin_os", "iri_vael"]

VALID_PERSONA_TEXT = """# Test NPC

<!--
npc_id: test_npc
room: Test Room
species: Kethari
prompt_version: 3
knowledge_scope (bible sections, Established content only):
  11.2.1, 5.8
actions: test_action, another_action
-->

You are a test NPC. <!-- TODO(lore): this note must never reach a prompt. -->
"""


class ParsePersonaTextTests(SimpleTestCase):
    def test_parses_all_required_fields(self):
        profile = parse_persona_text("test_npc", VALID_PERSONA_TEXT)
        self.assertEqual(profile.npc_id, "test_npc")
        self.assertEqual(profile.room, "Test Room")
        self.assertEqual(profile.prompt_version, "3")
        self.assertEqual(profile.knowledge_scope, ["11.2.1", "5.8"])
        self.assertEqual(profile.actions, ["test_action", "another_action"])

    def test_strips_html_comments_from_body(self):
        profile = parse_persona_text("test_npc", VALID_PERSONA_TEXT)
        self.assertNotIn("<!--", profile.body)
        self.assertNotIn("TODO(lore)", profile.body)
        self.assertIn("You are a test NPC.", profile.body)

    def test_missing_metadata_comment_raises(self):
        with self.assertRaises(PersonaParseError):
            parse_persona_text("test_npc", "# Test NPC\n\nNo metadata here.\n")

    def test_missing_required_field_raises(self):
        broken = VALID_PERSONA_TEXT.replace("prompt_version: 3\n", "")
        with self.assertRaises(PersonaParseError):
            parse_persona_text("test_npc", broken)

    def test_npc_id_mismatch_raises(self):
        with self.assertRaises(PersonaParseError):
            parse_persona_text("different_id", VALID_PERSONA_TEXT)


class RealPersonaFileTests(SimpleTestCase):
    """Parses the actual authored persona files in content/npcs/."""

    def test_all_prototype_npcs_parse(self):
        for npc_id in ALL_NPC_IDS:
            profile = parse_persona(npc_id)
            self.assertIsInstance(profile, NPCProfile)
            self.assertEqual(profile.npc_id, npc_id)
            self.assertTrue(profile.room)
            self.assertTrue(profile.knowledge_scope)
            self.assertTrue(profile.actions)
            self.assertNotIn("<!--", profile.body)


class LoreStoreTests(SimpleTestCase):
    def test_known_chunk_has_no_html_comments(self):
        text = get_lore_chunk("11.2.1")
        self.assertNotIn("<!--", text)
        self.assertIn("Elsewhere", text)

    def test_unknown_section_raises(self):
        with self.assertRaises(LoreNotFoundError):
            get_lore_chunk("99.99")

    def test_scoped_lore_concatenates_in_order(self):
        combined = get_scoped_lore(["5.8", "11.2.1"])
        self.assertLess(combined.index("[5.8]"), combined.index("[11.2.1]"))

    def test_every_prototype_npc_knowledge_scope_resolves(self):
        """
        Every section id named in a persona's knowledge_scope must have
        a corresponding lore-store chunk, or that NPC's prompt would
        silently drop knowledge it's supposed to have.
        """
        for npc_id in ALL_NPC_IDS:
            profile = parse_persona(npc_id)
            for section_id in profile.knowledge_scope:
                get_lore_chunk(section_id)  # raises LoreNotFoundError if missing


class PromptBuilderTests(SimpleTestCase):
    def test_section_ordering(self):
        """
        CLAUDE.md: common-knowledge -> shared rules -> persona ->
        scoped lore -> conversation.
        """
        prompt = build_system_prompt("mara_voss").text
        common_knowledge_pos = prompt.index("Elsewhere has been around for about four centuries")
        shared_rules_pos = prompt.index("You are a resident of Elsewhere")
        persona_pos = prompt.index("You are Mara Voss")
        lore_pos = prompt.index("[11.2.1]")
        self.assertLess(common_knowledge_pos, shared_rules_pos)
        self.assertLess(shared_rules_pos, persona_pos)
        self.assertLess(persona_pos, lore_pos)

    def test_no_html_comments_reach_the_prompt(self):
        for npc_id in ALL_NPC_IDS:
            prompt = build_system_prompt(npc_id).text
            self.assertNotIn("<!--", prompt)
            self.assertNotIn("TODO(lore)", prompt)

    def test_provisional_lore_never_appears(self):
        """
        Hard rule 4's own named examples of content that must never
        reach a prompt. Freehold and Meridian are Provisional; the
        Sealing is explicitly called out as a proposed/provisional
        term.
        """
        for npc_id in ALL_NPC_IDS:
            prompt = build_system_prompt(npc_id).text
            for forbidden in ("Freehold", "Meridian", "the Sealing"):
                self.assertNotIn(forbidden, prompt)

    def test_builds_for_all_prototype_npcs(self):
        for npc_id in ALL_NPC_IDS:
            result = build_system_prompt(npc_id)
            self.assertEqual(result.npc_id, npc_id)
            self.assertTrue(result.text)
