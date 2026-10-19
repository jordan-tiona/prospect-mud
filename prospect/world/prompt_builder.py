"""
Assembles an NPC's system prompt in the order CLAUDE.md specifies:
common-knowledge sheet -> shared rules -> persona file -> shared
action rules (content/actions/, only the NPC's own actions) -> scoped
lore -> conversation. The conversation turns themselves are appended by
the caller (step 7); this module only builds the fixed system
portion that's rebuilt fresh for every player message.
"""

from dataclasses import dataclass

from world.content_files import CONTENT_DIR, read_content_file, strip_html_comments
from world.lore_store import get_scoped_lore
from world.npc_profile import NPCProfile, parse_persona


ACTIONS_DIR = "actions"


def shared_action_rules(actions: list) -> str:
    """How each of these actions works, from content/actions/<name>.md,
    for the actions that have a file there: mechanics written once for
    every NPC with the action, while the persona's own `## Actions`
    bullet keeps only what's particular to that NPC. Empty when none
    of `actions` has one."""
    blocks = []
    for name in actions:
        if (CONTENT_DIR / ACTIONS_DIR / f"{name}.md").exists():
            body = strip_html_comments(read_content_file(f"{ACTIONS_DIR}/{name}.md")).strip()
            blocks.append(f"### {name}\n\n{body}")
    if not blocks:
        return ""
    return (
        "## How your actions work\n\n"
        "These hold for every person who has the action. Your own Actions list above says what each "
        "one is for in your case.\n\n" + "\n\n".join(blocks)
    )


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
    action_rules = shared_action_rules(profile.actions)
    if action_rules:
        sections.append(action_rules)
    sections.append(
        f"Your pronouns are {profile.pronouns}. Use them for yourself - never first person - in any action you write."
    )
    if scoped_lore:
        sections.append(
            "## What you specifically know (not for the player to see verbatim)\n\n"
            + scoped_lore
        )

    text = "\n\n---\n\n".join(sections)
    return SystemPrompt(npc_id=profile.npc_id, prompt_version=profile.prompt_version, text=text)
