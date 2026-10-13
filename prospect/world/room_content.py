"""
Parses a room content file's leading HTML-comment metadata block plus
its `## Glance` / `## Description` body sections (content-pipeline
spec section 5.1: https://claude.ai/artifact/94ujHRXZNTcD82m14XrjDw),
and strips all HTML comments (including TODO(lore) notes) from the
body first.
"""

import re
from dataclasses import dataclass, field

from world.content_files import read_content_file, strip_html_comments

_METADATA_COMMENT_RE = re.compile(r"<!--(.*?)-->", re.DOTALL)
_FIELD_RE = re.compile(r"^\s*(\w+)\s*:\s*(.*)$", re.MULTILINE)
_H2_SPLIT_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


class RoomContentParseError(Exception):
    """A room content file is missing required metadata or structure."""


@dataclass
class RoomContent:
    room_id: str
    status: str
    approval: str
    desc: str  # full `look` description
    glance: str | None = None  # short blurb shown on room entry; falls back to desc if unset
    bible_refs: list = field(default_factory=list)


def _parse_metadata(comment_text: str) -> dict:
    return {m.group(1): m.group(2).strip() for m in _FIELD_RE.finditer(comment_text)}


def _split_h2_sections(body: str) -> dict:
    """{heading_text: section_body} for every '## Heading' in `body`."""
    parts = _H2_SPLIT_RE.split(body)
    sections = {}
    for i in range(1, len(parts), 2):
        sections[parts[i].strip()] = parts[i + 1].strip() if i + 1 < len(parts) else ""
    return sections


def parse_room(room_id: str) -> RoomContent:
    """Load and parse content/rooms/<room_id>.md."""
    raw = read_content_file(f"rooms/{room_id}.md")
    return parse_room_text(room_id, raw)


def parse_room_text(room_id: str, raw: str) -> RoomContent:
    """Core parsing logic, separated from file I/O so it's testable
    against inline fixture strings."""
    comment_match = _METADATA_COMMENT_RE.search(raw)
    if not comment_match:
        raise RoomContentParseError(f"{room_id}.md has no leading HTML-comment metadata block.")

    fields = _parse_metadata(comment_match.group(1))

    required = ("room_id", "status", "approval")
    missing = [key for key in required if not fields.get(key)]
    if missing:
        raise RoomContentParseError(f"{room_id}.md metadata is missing: {', '.join(missing)}")

    if fields["room_id"] != room_id:
        raise RoomContentParseError(
            f"{room_id}.md declares room_id '{fields['room_id']}', which doesn't match its filename."
        )

    sections = _split_h2_sections(strip_html_comments(raw))
    desc = sections.get("Description")
    if not desc:
        raise RoomContentParseError(f"{room_id}.md has no '## Description' section.")

    bible_refs = [s.strip() for s in fields.get("bible_refs", "").split(",") if s.strip()]

    return RoomContent(
        room_id=fields["room_id"],
        status=fields["status"],
        approval=fields["approval"],
        desc=desc,
        glance=sections.get("Glance") or None,
        bible_refs=bible_refs,
    )
