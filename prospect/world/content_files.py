"""
Shared helpers for reading the authored content/ files (CLAUDE.md's
"Content files" section): stripping HTML comments before anything
reaches a model, and resolving the content/ directory regardless of
where the game is run from.
"""

import re
from pathlib import Path

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# prospect/world/content_files.py -> parents[2] is the repo root
# (parents[0]=world, parents[1]=prospect, parents[2]=repo root).
CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"


def strip_html_comments(text: str) -> str:
    """Remove all HTML comments, including TODO(lore) notes, from text."""
    stripped = _HTML_COMMENT_RE.sub("", text)
    # collapse the blank-line runs comment removal tends to leave behind
    return re.sub(r"\n{3,}", "\n\n", stripped).strip()


def read_content_file(relative_path: str) -> str:
    """Read a file under content/ by its path relative to that directory."""
    path = CONTENT_DIR / relative_path
    return path.read_text(encoding="utf-8")
