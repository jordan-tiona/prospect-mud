"""
Parses ambient (non-LLM) NPC and object content files: leading
HTML-comment metadata plus body sections (content-pipeline spec
sections 5.2/5.3: https://claude.ai/artifact/94ujHRXZNTcD82m14XrjDw),
and strips all HTML comments first.

Ambient NPCs are a sentence-opening display key (e.g. "An elderly
Kell") plus `## Poses` (one or more rotating pose fragments for
typeclasses.npcs.NPC.set_ambient_poses) and `## Description` (the
`look` text). Objects are a display key plus a fixed `## Short
Description` (the room-listing line, typeclasses.objects.RoomObject's
`room_line`) and `## Description`.

An ambient NPC may also have `## Emotes`: complete sentences that
world/idle_emotes.py sends to the room now and then (LR-LORE-0006).

Either may also have an optional `## Probe Description`: the longer
text `probe <thing>` shows (commands/probe.py). Without one, `probe`
shows the `look` text.
"""

import re
from dataclasses import dataclass, field

from world.content_files import read_content_file, strip_html_comments

_METADATA_COMMENT_RE = re.compile(r"<!--(.*?)-->", re.DOTALL)
_FIELD_RE = re.compile(r"^\s*(\w+)\s*:\s*(.*)$", re.MULTILINE)
_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_H2_SPLIT_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_BULLET_RE = re.compile(r"^\s*-\s*(.+?)\s*$")


class AmbientContentParseError(Exception):
    """An ambient content file is missing required metadata or structure."""


@dataclass
class AmbientNPCContent:
    ambient_id: str
    room: str  # legacy, optional ("" if absent); placement comes from the sector file
    status: str
    approval: str
    key: str  # sentence-opening display key, e.g. "An elderly Kell"
    poses: list  # pose fragments for "<key> is here, <pose>."
    desc: str  # full `look` text
    bible_refs: list = field(default_factory=list)
    probe_desc: str | None = None  # optional `## Probe Description`: `probe <npc>` text
    emotes: list = field(default_factory=list)  # optional `## Emotes`: world/idle_emotes.py lines


@dataclass
class AmbientObjectContent:
    object_id: str
    room: str  # legacy, optional ("" if absent); placement comes from the sector file
    status: str
    approval: str
    key: str  # display key, shown on direct examine
    short_desc: str  # fixed room-listing sentence (RoomObject.room_line)
    desc: str  # full `look <object>` text
    bible_refs: list = field(default_factory=list)
    probe_desc: str | None = None  # optional `## Probe Description`: `probe <object>` text


def _parse_metadata(comment_text: str) -> dict:
    return {m.group(1): m.group(2).strip() for m in _FIELD_RE.finditer(comment_text)}


def _split_h2_sections(body: str) -> dict:
    """{heading_text: section_body} for every '## Heading' in `body`."""
    parts = _H2_SPLIT_RE.split(body)
    sections = {}
    for i in range(1, len(parts), 2):
        sections[parts[i].strip()] = parts[i + 1].strip() if i + 1 < len(parts) else ""
    return sections


def _parse_key(body: str, file_id: str) -> str:
    h1 = _H1_RE.search(body)
    if not h1:
        raise AmbientContentParseError(f"{file_id}.md has no '# <key>' heading.")
    return h1.group(1).strip()


def _parse_bullets(section_text: str) -> list:
    bullets = []
    for line in section_text.splitlines():
        match = _BULLET_RE.match(line)
        if match:
            bullets.append(match.group(1))
    return bullets


def parse_ambient_npc(ambient_id: str) -> AmbientNPCContent:
    """Load and parse content/ambient/npcs/<ambient_id>.md."""
    raw = read_content_file(f"ambient/npcs/{ambient_id}.md")
    return parse_ambient_npc_text(ambient_id, raw)


def parse_ambient_npc_text(ambient_id: str, raw: str) -> AmbientNPCContent:
    comment_match = _METADATA_COMMENT_RE.search(raw)
    if not comment_match:
        raise AmbientContentParseError(
            f"{ambient_id}.md has no leading HTML-comment metadata block."
        )

    fields = _parse_metadata(comment_match.group(1))

    # No "room": placement comes from the sector file now (MUD Editor Step C);
    # a legacy room: field is still read, but optional.
    required = ("ambient_id", "status", "approval")
    missing = [key for key in required if not fields.get(key)]
    if missing:
        raise AmbientContentParseError(f"{ambient_id}.md metadata is missing: {', '.join(missing)}")

    if fields["ambient_id"] != ambient_id:
        raise AmbientContentParseError(
            f"{ambient_id}.md declares ambient_id '{fields['ambient_id']}', "
            "which doesn't match its filename."
        )

    body = strip_html_comments(raw)
    key = _parse_key(body, ambient_id)
    sections = _split_h2_sections(body)

    poses = _parse_bullets(sections.get("Poses", ""))
    if not poses:
        raise AmbientContentParseError(f"{ambient_id}.md has no entries in its '## Poses' section.")

    desc = sections.get("Description")
    if not desc:
        raise AmbientContentParseError(f"{ambient_id}.md has no '## Description' section.")

    bible_refs = [s.strip() for s in fields.get("bible_refs", "").split(",") if s.strip()]

    return AmbientNPCContent(
        ambient_id=fields["ambient_id"],
        room=fields.get("room", ""),
        status=fields["status"],
        approval=fields["approval"],
        key=key,
        poses=poses,
        desc=desc,
        bible_refs=bible_refs,
        probe_desc=sections.get("Probe Description") or None,
        emotes=_parse_bullets(sections.get("Emotes", "")),
    )


def parse_ambient_object(object_id: str) -> AmbientObjectContent:
    """Load and parse content/ambient/objects/<object_id>.md."""
    raw = read_content_file(f"ambient/objects/{object_id}.md")
    return parse_ambient_object_text(object_id, raw)


def parse_ambient_object_text(object_id: str, raw: str) -> AmbientObjectContent:
    comment_match = _METADATA_COMMENT_RE.search(raw)
    if not comment_match:
        raise AmbientContentParseError(
            f"{object_id}.md has no leading HTML-comment metadata block."
        )

    fields = _parse_metadata(comment_match.group(1))

    required = ("object_id", "status", "approval")  # room: optional, as above
    missing = [key for key in required if not fields.get(key)]
    if missing:
        raise AmbientContentParseError(f"{object_id}.md metadata is missing: {', '.join(missing)}")

    if fields["object_id"] != object_id:
        raise AmbientContentParseError(
            f"{object_id}.md declares object_id '{fields['object_id']}', "
            "which doesn't match its filename."
        )

    body = strip_html_comments(raw)
    key = _parse_key(body, object_id)
    sections = _split_h2_sections(body)

    short_desc = sections.get("Short Description")
    if not short_desc:
        raise AmbientContentParseError(f"{object_id}.md has no '## Short Description' section.")

    desc = sections.get("Description")
    if not desc:
        raise AmbientContentParseError(f"{object_id}.md has no '## Description' section.")

    bible_refs = [s.strip() for s in fields.get("bible_refs", "").split(",") if s.strip()]

    return AmbientObjectContent(
        object_id=fields["object_id"],
        room=fields.get("room", ""),
        status=fields["status"],
        approval=fields["approval"],
        key=key,
        short_desc=short_desc,
        desc=desc,
        bible_refs=bible_refs,
        probe_desc=sections.get("Probe Description") or None,
    )
