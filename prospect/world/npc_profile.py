"""
Parses an NPC persona file's leading HTML-comment metadata block
(CLAUDE.md: "Persona files begin with an HTML comment holding
machine-readable metadata (`npc_id`, `room`, `prompt_version`,
`knowledge_scope`, `actions`)"), and strips all HTML comments
(including TODO(lore) notes) from the body before it can reach a
prompt.
"""

import re
from dataclasses import dataclass

from world.content_files import read_content_file, strip_html_comments

_METADATA_COMMENT_RE = re.compile(r"<!--(.*?)-->", re.DOTALL)
_FIELD_RE = re.compile(r"^\s*(\w+)\s*:\s*(.*)$", re.MULTILINE)
_KNOWLEDGE_SCOPE_LABEL_RE = re.compile(r"^\s*knowledge_scope\b.*:\s*$", re.MULTILINE)


class PersonaParseError(Exception):
    """The persona file is missing required metadata fields."""


@dataclass
class NPCProfile:
    npc_id: str
    room: str
    prompt_version: str
    knowledge_scope: list
    actions: list
    pronouns: str  # e.g. "she/her" - injected into the prompt by build_system_prompt
    body: str  # persona text with all HTML comments stripped
    # Per-NPC reply-length cap (world/llm_client.py's `max_tokens`).
    # Optional - falls back to settings.LLM_MAX_TOKENS when unset, so
    # existing persona files without this field keep working.
    max_reply_tokens: int | None = None


def _parse_metadata(comment_text: str) -> dict:
    fields = {}
    lines = comment_text.splitlines()
    for i, line in enumerate(lines):
        # knowledge_scope's label line carries a parenthetical note before
        # its colon ("knowledge_scope (bible sections, ...):"), so it can't
        # match the plain "key: value" pattern below; its value is the
        # next non-blank line instead.
        if _KNOWLEDGE_SCOPE_LABEL_RE.match(line):
            value = lines[i + 1].strip() if i + 1 < len(lines) else ""
            fields["knowledge_scope"] = value
            continue
        match = _FIELD_RE.match(line)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip()
        fields[key] = value
    return fields


def parse_persona(npc_id: str) -> NPCProfile:
    """Load and parse content/npcs/<npc_id>.md."""
    raw = read_content_file(f"npcs/{npc_id}.md")
    return parse_persona_text(npc_id, raw)


def parse_persona_text(npc_id: str, raw: str) -> NPCProfile:
    """
    Core parsing logic, separated from file I/O so it's testable
    against inline fixture strings.
    """
    comment_match = _METADATA_COMMENT_RE.search(raw)
    if not comment_match:
        raise PersonaParseError(f"{npc_id}.md has no leading HTML-comment metadata block.")

    fields = _parse_metadata(comment_match.group(1))

    required = ("npc_id", "room", "prompt_version", "knowledge_scope", "actions", "pronouns")
    missing = [key for key in required if key not in fields or not fields[key]]
    if missing:
        raise PersonaParseError(f"{npc_id}.md metadata is missing: {', '.join(missing)}")

    if fields["npc_id"] != npc_id:
        raise PersonaParseError(
            f"{npc_id}.md declares npc_id '{fields['npc_id']}', which doesn't match its filename."
        )

    knowledge_scope = [s.strip() for s in fields["knowledge_scope"].split(",") if s.strip()]
    actions = [s.strip() for s in fields["actions"].split(",") if s.strip()]

    max_reply_tokens = None
    raw_max_reply_tokens = fields.get("max_reply_tokens")
    if raw_max_reply_tokens:
        try:
            max_reply_tokens = int(raw_max_reply_tokens)
        except ValueError:
            raise PersonaParseError(
                f"{npc_id}.md has a non-numeric max_reply_tokens: '{raw_max_reply_tokens}'"
            )

    return NPCProfile(
        npc_id=fields["npc_id"],
        room=fields["room"],
        prompt_version=fields["prompt_version"],
        knowledge_scope=knowledge_scope,
        actions=actions,
        pronouns=fields["pronouns"],
        body=strip_html_comments(raw),
        max_reply_tokens=max_reply_tokens,
    )
