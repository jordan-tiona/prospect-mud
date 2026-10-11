"""
Assembles an NPC's system prompt in the order CLAUDE.md specifies:
common-knowledge sheet -> shared rules -> persona file -> scoped lore
-> conversation. The conversation turns themselves are appended by
the caller (step 7); this module only builds the fixed system
portion that's rebuilt fresh for every player message.
"""

from dataclasses import dataclass

from world.content_files import read_content_file, strip_html_comments
from world.lore_store import get_scoped_lore
from world.npc_profile import NPCProfile, parse_persona


@dataclass
class SystemPrompt:
    npc_id: str
    prompt_version: str
    text: str


def build_system_prompt(npc_id: str) -> SystemPrompt:
    """Build the fixed system-prompt text for one NPC, by npc_id."""
    profile: NPCProfile = parse_persona(npc_id)

    common_knowledge = strip_html_comments(read_content_file("common-knowledge.md"))
    shared_rules = strip_html_comments(read_content_file("npc-shared-rules.md"))
    scoped_lore = get_scoped_lore(profile.knowledge_scope)

    sections = [common_knowledge, shared_rules, profile.body]
    if scoped_lore:
        sections.append(
            "## What you specifically know (not for the player to see verbatim)\n\n"
            + scoped_lore
        )

    text = "\n\n---\n\n".join(sections)
    return SystemPrompt(npc_id=profile.npc_id, prompt_version=profile.prompt_version, text=text)
