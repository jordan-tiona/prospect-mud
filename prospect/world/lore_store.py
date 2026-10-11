"""
Lore store (design-bible 16.6): the bible split into chunks by
section, each pre-tagged by status, with only Established chunks
eligible for an NPC prompt (CLAUDE.md hard rule 4).

Chunks live as plain files under content/lore/<section_id>.md,
containing text extracted verbatim from the bible for sections that
are Established as a whole, or for just the Established portion of a
mixed-status section. See each file's own metadata comment for which
case applies and why. This module does not infer status from the
bible automatically - status is read off the bible by a human when a
chunk is added, which is the auditable, low-risk choice given how
much non-canon lore leaking into a prompt would undermine hard rule 4.
"""

from world.content_files import read_content_file, strip_html_comments


class LoreNotFoundError(Exception):
    """A requested section has no corresponding lore-store chunk yet."""


def get_lore_chunk(section_id: str) -> str:
    """
    Return the Established-only text for one bible section id (e.g.
    "11.2.1"), with its metadata comment stripped.
    """
    try:
        raw = read_content_file(f"lore/{section_id}.md")
    except FileNotFoundError as err:
        raise LoreNotFoundError(
            f"No lore-store chunk for section {section_id}. "
            f"Add content/lore/{section_id}.md (Established text only)."
        ) from err
    return strip_html_comments(raw)


def get_scoped_lore(section_ids: list) -> str:
    """
    Return the concatenated Established lore for a list of section
    ids, in the order given, each preceded by its section number so
    the model (and a reviewer) can see where each chunk comes from.
    """
    chunks = []
    for section_id in section_ids:
        text = get_lore_chunk(section_id)
        chunks.append(f"[{section_id}]\n{text}")
    return "\n\n".join(chunks)
