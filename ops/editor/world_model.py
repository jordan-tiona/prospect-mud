"""Shared, read-only loaders for the MUD editor (docs/mud-editor-sector-format.md).

Reads sector files, the entity-kind allowlist and content/ Markdown without
importing the game. Nothing here writes to content/ - prose is read-only to
the editor. The only writer is write_json(), used for sector/manifest files.
"""

import ast
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SECTORS_DIR = 'sectors'
KINDS_FILE = 'prospect/world/entity_kinds.py'
FORMAT_VERSION = 1
ID_RE = re.compile(r'[a-z0-9_]+')

_COMMENT_RE = re.compile(r'<!--(.*?)-->', re.S)
_FIELD_RE = re.compile(r'^\s*(\w+)\s*:\s*(.*?)\s*$', re.M)
_H1_RE = re.compile(r'^#\s+(.+?)\s*$', re.M)
_H2_SPLIT_RE = re.compile(r'^##\s+(.+?)\s*$', re.M)


class DuplicateKeyError(ValueError):
    pass


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f'duplicate key {key!r}')
        result[key] = value
    return result


def read_json(path):
    """Parse JSON, rejecting duplicate keys (a silent overwrite would hide an ID clash)."""
    return json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=_no_duplicates)


def write_json(path, data):
    """Deterministic JSON: 2-space indent, sorted keys, UTF-8, trailing newline."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + '\n'
    path.write_text(text, encoding='utf-8', newline='\n')


def literals(path, names):
    """Read explicit literal assignments from a Python file without executing it."""
    result = {}
    for node in ast.parse(Path(path).read_text(encoding='utf-8-sig')).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in names:
                    result[target.id] = ast.literal_eval(node.value)
    missing = set(names) - result.keys()
    if missing:
        raise ValueError(f'{Path(path).name}: missing literal assignments: {sorted(missing)}')
    return result


def load_kinds(root=ROOT):
    """(ROOM_KIND, KINDS) from the Dev-owned allowlist."""
    data = literals(Path(root) / KINDS_FILE, ('ROOM_KIND', 'KINDS'))
    return data['ROOM_KIND'], data['KINDS']


def strip_comments(text):
    return re.sub(r'\n{3,}', '\n\n', _COMMENT_RE.sub('', text)).strip()


@dataclass
class ContentFile:
    """A content/ Markdown file as the editor sees it. `sections` and `heading`
    come from comment-stripped text, i.e. what could reach players."""
    path: str  # relative to content/
    fields: dict
    has_metadata: bool
    heading: str | None
    sections: dict
    visible_text: str


def parse_content(relative, text):
    comment = _COMMENT_RE.search(text)
    fields = {}
    if comment:
        fields = {m[1]: m[2] for m in _FIELD_RE.finditer(comment[1])}
    visible = strip_comments(text)
    heading = _H1_RE.search(visible)
    parts = _H2_SPLIT_RE.split(visible)
    sections = {parts[i].strip(): parts[i + 1].strip() if i + 1 < len(parts) else ''
                for i in range(1, len(parts), 2)}
    return ContentFile(relative, fields, bool(comment), heading[1] if heading else None, sections, visible)


def content_path(root, relative):
    """Resolve a content reference, refusing anything outside content/."""
    base = (Path(root) / 'content').resolve()
    path = (base / relative).resolve()
    if not path.is_relative_to(base):
        raise ValueError(f'content path outside content/: {relative}')
    return path


def load_content(root, relative):
    """ContentFile, or None if the file doesn't exist. Raises ValueError on a path outside content/."""
    path = content_path(root, relative)
    if not path.is_file():
        return None
    return parse_content(relative, path.read_text(encoding='utf-8-sig'))


def sector_path(root, sector_id):
    return Path(root) / SECTORS_DIR / sector_id / 'sector.json'


def sector_ids(root=ROOT):
    base = Path(root) / SECTORS_DIR
    return sorted(p.parent.name for p in base.glob('*/sector.json')) if base.is_dir() else []


def load_sector(root, sector_id):
    return read_json(sector_path(root, sector_id))


MANIFEST_DIR = 'prospect/world/data/sectors'
EDITOR_ONLY_FIELDS = ('editor', 'notes')


def manifest_path(root, sector_id):
    return Path(root) / MANIFEST_DIR / f'{sector_id}.json'


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _without_editor_fields(value):
    if isinstance(value, dict):
        return {k: _without_editor_fields(v) for k, v in value.items() if k not in EDITOR_ONLY_FIELDS}
    if isinstance(value, list):
        return [_without_editor_fields(v) for v in value]
    return value


def source_hashes(root, sector_id, sector, content_refs):
    """{source path: sha256} for a manifest's `sources`. The sector file is hashed
    without editor-only fields (moving a map box isn't a game change), and text is
    hashed with LF line endings so Windows checkouts (autocrlf) hash the same."""
    canonical = json.dumps(_without_editor_fields(sector), sort_keys=True, ensure_ascii=False)
    hashes = {f'{SECTORS_DIR}/{sector_id}/sector.json': _sha256(canonical.encode('utf-8'))}
    for relative in sorted(content_refs):
        data = content_path(root, relative).read_bytes().replace(b'\r\n', b'\n')
        hashes[f'content/{relative}'] = _sha256(data)
    return hashes
