"""Saving sector files from the MUD editor (milestones 5b-5c).

The only files this module writes are the editor's own:
    sectors/<id>/sector.json           - on an explicit Save (tracked by git)
    sectors/<id>/.history/*.json       - the previous version, kept on each Save (last HISTORY_KEEP)
    sectors/<id>/.autosave/latest.json - unsaved work, a few seconds after each change
    sectors/<id>/.autosave/auto-*.json - a copy of latest every ROTATE_EVERY seconds (last ROTATE_KEEP)
    sectors/_dismissed.json            - candidates dismissed from the tray (tracked by git)
The .history and .autosave folders are gitignored, and check.py, export.py and
the game never read them. Prose in content/ is never written.
"""

import hashlib
import json
import threading
import time

from world_model import (FORMAT_VERSION, ID_RE, content_path, dismissed_path, dump_json, load_dismissed, load_kinds,
                         read_json, sector_path, write_json)

HISTORY_DIR = '.history'
AUTOSAVE_DIR = '.autosave'
HISTORY_KEEP = 20
ROTATE_KEEP = 5
ROTATE_EVERY = 300  # seconds

now = time.time  # tests patch this


class SaveConflict(Exception):
    """sector.json changed on disk since the editor loaded it."""

    def __init__(self, current_version):
        super().__init__('sector.json changed on disk since it was loaded')
        self.current_version = current_version


class InvalidSector(ValueError):
    """The submitted sector isn't a well-formed sector file."""

    def __init__(self, problems):
        super().__init__('; '.join(problems))
        self.problems = problems


def _stamp():
    return time.strftime('%Y-%m-%dT%H-%M-%S', time.localtime(now()))


def _unique(folder, prefix):
    path = folder / f'{prefix}{_stamp()}.json'
    n = 2
    while path.exists():
        path = folder / f'{prefix}{_stamp()}-{n}.json'
        n += 1
    return path


def _prune(folder, pattern, keep):
    files = sorted(folder.glob(pattern))  # timestamped names sort oldest first
    for old in files[:-keep] if keep else files:
        old.unlink()


def version_of(root, sector_id):
    """A version token for sector.json: the hash of its bytes (None if absent)."""
    path = sector_path(root, sector_id)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


# ----------------------------------------------------------- validation

TOP_KEYS = {'format_version', 'sector_id', 'notes', 'rooms', 'exits', 'entities'}
ROOM_KEYS = {'title', 'content', 'editor', 'notes'}
EXIT_KEYS = {'from', 'to', 'key', 'aliases', 'return'}
RETURN_KEYS = {'key', 'aliases'}
ENTITY_KEYS = {'kind', 'room', 'content', 'aliases', 'params', 'notes'}


def _str_list(value):
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def validate_shape(root, sector_id, sector):
    """Structural problems that would make the file malformed. Not a substitute
    for check.py: a well-formed sector may still have check errors (Draft
    content, missing prose for a placeholder room), and saving it is fine."""
    problems = []
    if not isinstance(sector, dict):
        return ['the sector must be a JSON object']
    _room_kind, kinds = load_kinds(root)
    problems += [f'unknown top-level field {k!r}' for k in sorted(set(sector) - TOP_KEYS)]
    if sector.get('format_version') != FORMAT_VERSION:
        problems.append(f'format_version must be {FORMAT_VERSION}')
    if sector.get('sector_id') != sector_id:
        problems.append(f'sector_id must be {sector_id!r}')
    if not isinstance(sector.get('notes', ''), str):
        problems.append('notes must be text')

    rooms = sector.get('rooms')
    if not isinstance(rooms, dict):
        return problems + ['rooms must be an object']
    for room_id, room in rooms.items():
        where = f'room {room_id}'
        if not ID_RE.fullmatch(room_id):
            problems.append(f'{where}: IDs must match [a-z0-9_]+')
        if not isinstance(room, dict):
            problems.append(f'{where}: must be an object')
            continue
        problems += [f'{where}: unknown field {k!r}' for k in sorted(set(room) - ROOM_KEYS)]
        if not isinstance(room.get('title'), str):
            problems.append(f'{where}: title must be text')
        if 'content' in room and not isinstance(room['content'], str):
            problems.append(f'{where}: content must be a path')
        editor = room.get('editor', {})
        if not (isinstance(editor, dict) and all(isinstance(editor.get(c, 0), (int, float)) for c in ('x', 'y'))):
            problems.append(f'{where}: editor position must be numbers')
        if not isinstance(room.get('notes', ''), str):
            problems.append(f'{where}: notes must be text')

    exits = sector.get('exits')
    if not isinstance(exits, list):
        return problems + ['exits must be a list']
    for i, ex in enumerate(exits):
        where = f'exit {i}'
        if not isinstance(ex, dict):
            problems.append(f'{where}: must be an object')
            continue
        problems += [f'{where}: unknown field {k!r}' for k in sorted(set(ex) - EXIT_KEYS)]
        for end in ('from', 'to'):
            if ex.get(end) not in rooms:
                problems.append(f'{where}: {end} must be a room in this sector')
        if not (isinstance(ex.get('key'), str) and ex['key'].strip()):
            problems.append(f'{where}: key must be text')
        if not _str_list(ex.get('aliases', [])):
            problems.append(f'{where}: aliases must be a list of text')
        back = ex.get('return')
        if back is not None:
            if not isinstance(back, dict) or set(back) - RETURN_KEYS:
                problems.append(f'{where}: return must be null or {{key, aliases}}')
            elif not (isinstance(back.get('key'), str) and back['key'].strip()) or not _str_list(back.get('aliases', [])):
                problems.append(f'{where}: return needs a key and a list of aliases')

    entities = sector.get('entities')
    if not isinstance(entities, dict):
        return problems + ['entities must be an object']
    for entity_id, entity in entities.items():
        where = f'entity {entity_id}'
        if not ID_RE.fullmatch(entity_id):
            problems.append(f'{where}: IDs must match [a-z0-9_]+')
        if entity_id in rooms:
            problems.append(f'{where}: ID already used by a room')
        if not isinstance(entity, dict):
            problems.append(f'{where}: must be an object')
            continue
        problems += [f'{where}: unknown field {k!r}' for k in sorted(set(entity) - ENTITY_KEYS)]
        if entity.get('kind') not in kinds:
            problems.append(f'{where}: unknown kind {entity.get("kind")!r}')
        if entity.get('room') not in rooms:
            problems.append(f'{where}: room must be a room in this sector')
        if 'content' in entity and not isinstance(entity['content'], str):
            problems.append(f'{where}: content must be a path')
        if not _str_list(entity.get('aliases', [])):
            problems.append(f'{where}: aliases must be a list of text')
        params = entity.get('params', {})
        if not (isinstance(params, dict) and all(isinstance(v, str) for v in params.values())):
            problems.append(f'{where}: params must map names to text')
    return problems


# ----------------------------------------------------------------- save


def save(root, sector_id, sector, base_version):
    """Write sector.json if it's still the version the editor loaded. Keeps the
    previous version in .history/ and clears the now-saved autosave. Returns the
    new version. Raises InvalidSector or SaveConflict without writing anything."""
    problems = validate_shape(root, sector_id, sector)
    if problems:
        raise InvalidSector(problems)
    current = version_of(root, sector_id)
    if current != base_version:
        raise SaveConflict(current)
    path = sector_path(root, sector_id)
    if path.is_file():
        history = path.parent / HISTORY_DIR
        history.mkdir(exist_ok=True)
        _unique(history, 'sector-').write_bytes(path.read_bytes())
        _prune(history, 'sector-*.json', HISTORY_KEEP)
    write_json(path, sector)
    latest = path.parent / AUTOSAVE_DIR / 'latest.json'
    if latest.is_file():
        latest.unlink()
    return version_of(root, sector_id)


# ------------------------------------------------------------- autosave


def _autosave_dir(root, sector_id):
    return sector_path(root, sector_id).parent / AUTOSAVE_DIR


def autosave(root, sector_id, sector, base_version):
    """Record unsaved work. Writes latest.json every time; every ROTATE_EVERY
    seconds also keeps a copy in the rotating set of ROTATE_KEEP. Returns
    whether a rotating copy was made."""
    folder = _autosave_dir(root, sector_id)
    record = {'base_version': base_version, 'saved_at': now(), 'sector': sector}
    write_json(folder / 'latest.json', record)
    rotating = sorted(folder.glob('auto-*.json'))
    newest_at = read_json(rotating[-1]).get('saved_at', 0) if rotating else None
    if newest_at is None or now() - newest_at >= ROTATE_EVERY:
        _unique(folder, 'auto-').write_text(dump_json(record), encoding='utf-8', newline='\n')
        _prune(folder, 'auto-*.json', ROTATE_KEEP)
        return True
    return False


def autosave_info(root, sector_id):
    """What the editor offers to restore: the latest autosave, if it differs from
    what's saved. `base_matches` says whether sector.json is still the version
    that autosave started from (if not, restoring would undo those changes)."""
    latest = _autosave_dir(root, sector_id) / 'latest.json'
    if not latest.is_file():
        return None
    try:
        record = read_json(latest)
        current = read_json(sector_path(root, sector_id))
    except (OSError, ValueError):
        return None
    if record.get('sector') == current:
        return None
    return {'saved_at': record.get('saved_at'), 'base_matches': record.get('base_version') == version_of(root, sector_id)}


def load_autosave(root, sector_id):
    latest = _autosave_dir(root, sector_id) / 'latest.json'
    return read_json(latest).get('sector') if latest.is_file() else None


def discard_autosave(root, sector_id):
    """Drop latest.json; the rotating copies are kept until they rotate out."""
    latest = _autosave_dir(root, sector_id) / 'latest.json'
    if latest.is_file():
        latest.unlink()


def snapshots(root, sector_id):
    """[(kind, path)] of kept copies, newest first - for a later 'restore a version' view."""
    base = sector_path(root, sector_id).parent
    found = [('autosave', p) for p in (base / AUTOSAVE_DIR).glob('auto-*.json')]
    found += [('saved', p) for p in (base / HISTORY_DIR).glob('sector-*.json')]
    return sorted(found, key=lambda item: item[1].name.split('-', 1)[1], reverse=True)


# ------------------------------------------------------------ dismissed

_dismiss_lock = threading.Lock()


def content_folders(root):
    """The content/ folders the allowlist's kinds (and rooms) read from."""
    room_kind, kinds = load_kinds(root)
    return {room_kind['content_dir'], *(k['content_dir'] for k in kinds.values())}


def set_dismissed(root, paths, dismissed):
    """Add `paths` to sectors/_dismissed.json (dismissed=True) or take them off
    it. Dismissing needs an existing .md file in a kind's folder; restoring
    accepts any listed path, so an entry for a deleted file can be cleared.
    Returns the new sorted list. Raises InvalidSector without writing."""
    if not (isinstance(paths, list) and paths and all(isinstance(p, str) for p in paths)):
        raise InvalidSector(['paths must be a non-empty list of content paths'])
    with _dismiss_lock:
        current = load_dismissed(root)
        if dismissed:
            folders = content_folders(root)
            problems = []
            for relative in paths:
                try:
                    ok = content_path(root, relative).is_file()
                except ValueError:
                    ok = False
                if not ok or not relative.endswith('.md') or relative.rsplit('/', 1)[0] not in folders:
                    problems.append(f'not a content file the editor can place: {relative}')
            if problems:
                raise InvalidSector(problems)
            updated = current | set(paths)
        else:
            updated = current - set(paths)
        if updated != current:
            write_json(dismissed_path(root), {'dismissed': sorted(updated), 'format_version': FORMAT_VERSION})
        return sorted(updated)


def parse_body(raw, limit=2_000_000):
    """Decode a request body as JSON, refusing anything over `limit` bytes."""
    if len(raw) > limit:
        raise InvalidSector([f'request is larger than {limit} bytes'])
    try:
        return json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError) as exc:
        raise InvalidSector([f'request is not JSON: {exc}']) from exc

