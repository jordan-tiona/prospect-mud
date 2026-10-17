"""
Tests for the prompt builder and its supporting modules (npc_profile,
lore_store). CLAUDE.md calls these out explicitly: this is where a
silent bug would leak non-canon lore into a model prompt (hard rule
4) or corrupt an NPC's declared identity.

Run with:
    evennia test world
"""

from django.test import SimpleTestCase

from world.emotes import format_emote, parse_reply
from world.lore_store import LoreNotFoundError, get_lore_chunk, get_scoped_lore
from world.npc_profile import NPCProfile, PersonaParseError, parse_persona, parse_persona_text
from world.output_check import is_flagged
from world.prompt_builder import build_system_prompt

ALL_NPC_IDS = ["mara_voss", "tarin_os", "iri_vael", "veska_renn", "given_marr", "daven_varek"]

VALID_PERSONA_TEXT = """# Test NPC

<!--
npc_id: test_npc
room: Test Room
species: Kell
pronouns: they/them
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
        self.assertEqual(profile.pronouns, "they/them")

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

    def test_max_reply_tokens_defaults_to_none(self):
        profile = parse_persona_text("test_npc", VALID_PERSONA_TEXT)
        self.assertIsNone(profile.max_reply_tokens)

    def test_max_reply_tokens_parsed_when_present(self):
        with_cap = VALID_PERSONA_TEXT.replace(
            "actions: test_action, another_action\n",
            "actions: test_action, another_action\nmax_reply_tokens: 90\n",
        )
        profile = parse_persona_text("test_npc", with_cap)
        self.assertEqual(profile.max_reply_tokens, 90)

    def test_non_numeric_max_reply_tokens_raises(self):
        broken = VALID_PERSONA_TEXT.replace(
            "actions: test_action, another_action\n",
            "actions: test_action, another_action\nmax_reply_tokens: a lot\n",
        )
        with self.assertRaises(PersonaParseError):
            parse_persona_text("test_npc", broken)

    def test_missing_pronouns_raises(self):
        broken = VALID_PERSONA_TEXT.replace("pronouns: they/them\n", "")
        with self.assertRaises(PersonaParseError):
            parse_persona_text("test_npc", broken)

    def test_desc_defaults_to_none(self):
        profile = parse_persona_text("test_npc", VALID_PERSONA_TEXT)
        self.assertIsNone(profile.desc)

    def test_desc_parsed_when_present(self):
        with_desc = VALID_PERSONA_TEXT.replace(
            "actions: test_action, another_action\n",
            "actions: test_action, another_action\ndesc: A test NPC with a plain look.\n",
        )
        profile = parse_persona_text("test_npc", with_desc)
        self.assertEqual(profile.desc, "A test NPC with a plain look.")
        # The metadata comment is stripped entirely before the prompt
        # sees anything, so desc text never leaks into profile.body.
        self.assertNotIn("A test NPC with a plain look.", profile.body)

    def test_probe_desc_defaults_to_none(self):
        self.assertIsNone(parse_persona_text("test_npc", VALID_PERSONA_TEXT).probe_desc)

    def test_probe_desc_parsed_and_kept_out_of_body(self):
        with_probe = VALID_PERSONA_TEXT.replace(
            "actions: test_action, another_action\n",
            "actions: test_action, another_action\nprobe_desc: A longer probe text.\n",
        )
        profile = parse_persona_text("test_npc", with_probe)
        self.assertEqual(profile.probe_desc, "A longer probe text.")
        self.assertNotIn("A longer probe text.", profile.body)


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
            self.assertIsInstance(profile.max_reply_tokens, int)
            self.assertTrue(profile.pronouns)


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
        lore_pos = prompt.index("## What you specifically know")
        self.assertLess(common_knowledge_pos, shared_rules_pos)
        self.assertLess(shared_rules_pos, persona_pos)
        self.assertLess(persona_pos, lore_pos)

    def test_pronouns_appear_after_persona(self):
        prompt = build_system_prompt("mara_voss").text
        persona_pos = prompt.index("You are Mara Voss")
        pronoun_pos = prompt.index("Your pronouns are she/her")
        self.assertLess(persona_pos, pronoun_pos)

    def test_pronouns_match_each_npcs_own_profile(self):
        for npc_id, expected in [
            ("mara_voss", "she/her"),
            ("tarin_os", "he/him"),
            ("iri_vael", "she/her"),
            ("veska_renn", "she/her"),
        ]:
            prompt = build_system_prompt(npc_id).text
            self.assertIn(f"Your pronouns are {expected}", prompt)

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


class OutputCheckTests(SimpleTestCase):
    def test_empty_reply_not_flagged(self):
        # Normal when a tool call carries the whole response; the talk
        # command (not this filter) decides what to do about it.
        flagged, _reason = is_flagged("")
        self.assertFalse(flagged)

    def test_assistant_leak_flagged(self):
        for text in (
            "As an AI, I don't have personal opinions.",
            "I'm just an AI assistant here to help.",
            "I am a language model trained by a company.",
        ):
            flagged, reason = is_flagged(text)
            self.assertTrue(flagged, msg=f"expected flag for: {text!r}")
            self.assertTrue(reason)

    def test_ordinary_in_character_reply_not_flagged(self):
        flagged, _reason = is_flagged('"Voldren, please. I run a cafe, not a mine," she says dryly.')
        self.assertFalse(flagged)

    def test_persona_slur_handling_not_flagged(self):
        # Mara's approved in-character response to being called "Cave
        # Crawler" (design-bible 14.6) must not be caught by the filter -
        # it's meant to reach the player, unlike an assistant-voice leak.
        flagged, _reason = is_flagged("Cave Crawler? I run a cafe, not a mine.")
        self.assertFalse(flagged)


class EmoteSplitTests(SimpleTestCase):
    def test_splits_single_emote_from_dialogue(self):
        self.assertEqual(
            parse_reply('*smiles and nods* Welcome in.'),
            [("emote", "smiles and nods"), ("dialogue", "Welcome in.")],
        )

    def test_multiple_emotes_in_order(self):
        self.assertEqual(
            parse_reply("*wipes the counter* Afternoon. *smiles*"),
            [("emote", "wipes the counter"), ("dialogue", "Afternoon."), ("emote", "smiles")],
        )

    def test_no_emotes_passes_through(self):
        self.assertEqual(parse_reply("Just ordinary speech."), [("dialogue", "Just ordinary speech.")])

    def test_emote_only_leaves_no_dialogue_segment(self):
        self.assertEqual(parse_reply("*shrugs*"), [("emote", "shrugs")])

    def test_strips_backslash_escaped_quotes_from_dialogue(self):
        # Confirmed live (2026-10-14, gpt-4.1-mini): the raw reply
        # content sometimes contains literal backslash-escaped quotes,
        # as if written to be embedded in a JSON string rather than
        # plain chat text - e.g. '\"Mornin\'.\"' instead of '"Mornin\'."'.
        # Real dialogue never legitimately contains a raw backslash.
        text = '\\"Mornin\'. Thanks, it keeps the Old Quarter\'s spirits up.\\"'
        self.assertEqual(
            parse_reply(text),
            [("dialogue", "Mornin'. Thanks, it keeps the Old Quarter's spirits up.")],
        )

    def test_strips_backslash_escaped_quotes_around_an_action(self):
        text = '\\"Well, you\'ve come to the right place.\\" *leans against the counter* \\"Front-row seat.\\"'
        self.assertEqual(
            parse_reply(text),
            [
                ("dialogue", "Well, you've come to the right place."),
                ("emote", "leans against the counter"),
                ("dialogue", "Front-row seat."),
            ],
        )

    def test_action_splits_dialogue_into_two_segments(self):
        # the project owner's preferred pattern: dialogue - action -
        # dialogue, rendered as three separate lines rather than every
        # action collapsing to the front of the reply.
        text = '"Well, you\'ve come to the right place." *leans against the counter* "I\'ve got a front-row seat."'
        self.assertEqual(
            parse_reply(text),
            [
                ("dialogue", "Well, you've come to the right place."),
                ("emote", "leans against the counter"),
                ("dialogue", "I've got a front-row seat."),
            ],
        )

    def test_format_emote_adds_period_and_name(self):
        self.assertEqual(
            format_emote("Mara Voss", "smiles and nods"), "|xMara Voss smiles and nods.|n"
        )

    def test_format_emote_keeps_existing_punctuation(self):
        self.assertEqual(format_emote("Mara Voss", "grins!"), "|xMara Voss grins!|n")

    def test_format_emote_fixes_first_person_pronouns(self):
        self.assertEqual(
            format_emote("Mara Voss", "wipes my hands on a towel", pronouns="she/her"),
            "|xMara Voss wipes her hands on a towel.|n",
        )

    def test_format_emote_fixes_i_me_myself(self):
        self.assertEqual(
            format_emote("Tarin Os", "I catch myself and steady me", pronouns="he/him"),
            "|xTarin Os He catch himself and steady him.|n",
        )

    def test_format_emote_with_no_pronouns_given_is_unchanged(self):
        self.assertEqual(
            format_emote("Mara Voss", "wipes my hands"), "|xMara Voss wipes my hands.|n"
        )

    def test_format_emote_with_unrecognized_pronouns_is_unchanged(self):
        self.assertEqual(
            format_emote("Iri Vael", "adjusts my badge", pronouns="xe/xem"),
            "|xIri Vael adjusts my badge.|n",
        )
