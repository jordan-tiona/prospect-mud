"""Read-only consistency check for sector files (docs/mud-editor-sector-format.md Section 6).

Run from any directory:  python ops/editor/check.py [sector_id ...]
With no sector IDs, checks every sector under sectors/. Exits 1 if any
check reports an error. Never writes anything.
"""

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from world_model import (DISMISSED_FILE, FORMAT_VERSION, ID_RE, MAP_AXES, MAP_STEPS, ROOT, DuplicateKeyError,
                         load_content, load_dismissed, load_kinds, load_required_rooms, load_sector, manifest_path,
                         read_json, sector_ids, sector_path, source_hashes, valid_map_pin)

ERROR, WARNING, INFO = 'error', 'warning', 'info'


@dataclass(frozen=True)
class Issue:
    level: str
    code: str
    where: str
    message: str

    def __str__(self):
        return f'{self.level.upper():7} {self.code:18} {self.where}: {self.message}'


def _content_issues(root, where, relative, kind, object_id):
    """Checks a room's or entity's content reference. Returns (issues, ContentFile or None)."""
    if not relative:
        return [Issue(ERROR, 'no_content', where, 'no content file referenced (request prose from Lore)')], None
    try:
        content = load_content(root, relative)
    except ValueError as exc:
        return [Issue(ERROR, 'bad_content_path', where, str(exc))], None
    if content is None:
        return [Issue(ERROR, 'missing_content', where, f'content/{relative} does not exist')], None
    issues = []
    if not relative.startswith(kind['content_dir'] + '/'):
        issues.append(Issue(WARNING, 'content_location', where,
                            f"content/{relative} is outside this kind's folder content/{kind['content_dir']}/"))
    if not content.has_metadata:
        issues.append(Issue(ERROR, 'no_metadata', where, f'content/{relative} has no HTML-comment metadata'))
        return issues, content
    declared = content.fields.get(kind['id_field'])
    if declared != object_id:
        issues.append(Issue(ERROR, 'content_id_mismatch', where,
                            f"content/{relative} declares {kind['id_field']}: {declared!r}, expected {object_id!r}"))
    approval = content.fields.get('approval')
    if approval != 'Approved':
        issues.append(Issue(ERROR, 'not_approved', where,
                            f'content/{relative} approval is {approval!r}, not Approved'))
    # Per-field approval, e.g. `probe_description: Draft (LR-DEV-0001, ...)`:
    # an approved file can still carry a draft section or metadata line.
    for field, value in content.fields.items():
        if field != 'approval' and str(value).startswith('Draft'):
            issues.append(Issue(ERROR, 'draft_field', where,
                                f'content/{relative} marks {field} as {value!r}; needs owner approval first'))
    glance = content.fields.get('glance')
    if glance is not None and glance.strip().lower() not in ('show', 'hide'):
        issues.append(Issue(ERROR, 'bad_glance', where,
                            f"content/{relative} has glance: {glance!r}; use 'show' or 'hide'"))
    for section in kind['required_sections']:
        if not content.sections.get(section):
            issues.append(Issue(ERROR, 'missing_section', where, f'content/{relative} has no "## {section}"'))
    if kind['needs_heading'] and not content.heading:
        issues.append(Issue(ERROR, 'missing_heading', where, f'content/{relative} has no "# Name" heading'))
    if content.sections.get('Probe Description') and kind.get('probe', True) is False:
        issues.append(Issue(WARNING, 'probe_unused', where,
                            f'content/{relative} has a "## Probe Description", but this kind shows its '
                            'per-player look text for probe too, so players never see it'))
    if 'TODO(lore)' in content.visible_text:
        issues.append(Issue(WARNING, 'visible_todo', where,
                            f'content/{relative} has TODO(lore) text outside an HTML comment'))
    return issues, content


def _exit_issues(sector, rooms):
    issues = []
    used = defaultdict(dict)  # room -> {command word: exit description}
    pairs = {}  # frozenset of the two rooms -> the first exit record between them
    out_links, in_links = defaultdict(set), defaultdict(set)

    def claim(room, key, aliases, where):
        for word in [key, *aliases]:
            word_l = str(word).lower()
            if word_l in used[room]:
                issues.append(Issue(ERROR, 'duplicate_exit', where,
                                    f'"{word}" already used in {room} by {used[room][word_l]}'))
            else:
                used[room][word_l] = where

    for i, ex in enumerate(sector.get('exits', [])):
        where = f"exit[{i}] {ex.get('from')}->{ex.get('to')}"
        src, dst = ex.get('from'), ex.get('to')
        bad = [f'{field} {value!r}' for field, value in (('from', src), ('to', dst)) if value not in rooms]
        if bad:
            issues.append(Issue(ERROR, 'unknown_room', where, f"unknown room: {', '.join(bad)}"))
            continue
        if not ex.get('key'):
            issues.append(Issue(ERROR, 'exit_no_key', where, 'exit has no key'))
            continue
        if src == dst:
            issues.append(Issue(WARNING, 'self_exit', where, 'exit leads back into the same room'))
        # One connection per pair of rooms (owner decision, 2026-10-16): a record
        # already covers both directions, and synonyms are aliases.
        pair = frozenset((src, dst))
        if pair in pairs:
            issues.append(Issue(ERROR, 'duplicate_room_pair', where,
                                f'{pairs[pair]} already connects these rooms - merge them into one '
                                'record (extra words go in aliases; the way back in "return")'))
        else:
            pairs[pair] = where
        claim(src, ex['key'], ex.get('aliases', []), where)
        out_links[src].add(dst)
        in_links[dst].add(src)
        if 'return' not in ex:
            issues.append(Issue(ERROR, 'exit_no_return', where,
                                'no "return" key: give the return exit, or "return": null for a one-way exit'))
        elif ex['return'] is None:
            issues.append(Issue(INFO, 'one_way_exit', where, 'one-way exit (return: null)'))
        elif not ex['return'].get('key'):
            issues.append(Issue(ERROR, 'exit_no_key', where, 'return exit has no key'))
        else:
            claim(dst, ex['return']['key'], ex['return'].get('aliases', []), where + ' (return)')
            out_links[dst].add(src)
            in_links[src].add(dst)

    for room in rooms:
        if not out_links[room] and not in_links[room]:
            issues.append(Issue(WARNING, 'no_exits', f'room {room}', 'room has no exits'))
        elif not out_links[room]:
            issues.append(Issue(WARNING, 'dead_end', f'room {room}', 'no exit leads out of this room'))
        elif not in_links[room]:
            issues.append(Issue(WARNING, 'unreachable', f'room {room}', 'no exit leads into this room'))

    # A sector is one walkable map: warn if it splits into separate pieces.
    neighbours = defaultdict(set)
    for room in rooms:
        neighbours[room] |= out_links[room] | in_links[room]
    seen, parts = set(), 0
    for room in rooms:
        if room in seen:
            continue
        parts += 1
        stack = [room]
        while stack:
            r = stack.pop()
            if r not in seen:
                seen.add(r)
                stack.extend(neighbours[r] - seen)
    if parts > 1:
        issues.append(Issue(WARNING, 'disconnected', 'sector',
                            f'rooms form {parts} separate groups with no exits between them'))
    return issues


def map_grid(sector):
    """({room_id: (x, y, z)}, issues): grid coordinates worked out from the
    sector's map_anchor (0,0,0), one step per compass exit, with each room's
    map_pin overriding (owner's grid policy, 2026-10-18). A room that no
    anchor or pin reaches through compass exits gets no coordinates."""
    rooms = sector.get('rooms', {})
    issues, coords, pinned = [], {}, set()
    anchor = sector.get('map_anchor')
    if anchor is None:
        if rooms:
            issues.append(Issue(WARNING, 'no_map_anchor', 'sector',
                                'no map anchor: choose the room at (0,0,0) so rooms get map coordinates'))
    elif anchor not in rooms:
        issues.append(Issue(ERROR, 'bad_map_anchor', 'sector', f'map anchor {anchor!r} is not a room in this sector'))
        anchor = None
    else:
        coords[anchor] = (0, 0, 0)
    for room_id, room in rooms.items():
        if 'map_pin' not in room:
            continue
        if valid_map_pin(room['map_pin']):
            coords[room_id] = tuple(room['map_pin'][a] for a in MAP_AXES)
            pinned.add(room_id)
        else:
            issues.append(Issue(ERROR, 'bad_map_pin', f'room {room_id}', 'map pin must be whole numbers x, y and z'))

    moves = defaultdict(list)  # room -> [(other room, step, exit key or None, where)]
    for i, ex in enumerate(sector.get('exits', [])):
        src, dst = ex.get('from'), ex.get('to')
        if src not in rooms or dst not in rooms or src == dst:
            continue  # reported by _exit_issues
        where = f'exit[{i}] {src}->{dst}'
        sides = [(src, dst, ex.get('key'), where)]
        if ex.get('return'):
            sides.append((dst, src, ex['return'].get('key'), where + ' (return)'))
        for a, b, key, side in sides:
            step = MAP_STEPS.get(str(key or '').strip().lower())
            if step:
                moves[a].append((b, step, key, side))
            # A one-way exit can also place its own start room from its end. That
            # reverse move has no key, so the mismatch check below skips it.
            if step and not ex.get('return'):
                moves[b].append((a, tuple(-d for d in step), None, side))

    queue = [r for r in rooms if r in coords]
    queue.sort(key=lambda r: (r != anchor, r))
    while queue:
        room = queue.pop(0)
        for other, step, _key, _side in moves[room]:
            if other not in coords:
                coords[other] = tuple(c + d for c, d in zip(coords[room], step))
                queue.append(other)

    for room in rooms:
        for other, step, key, side in moves[room]:
            if key is None or room not in coords or other not in coords or {room, other} & pinned:
                continue  # a pin confirms an exception to the one-step rule
            actual = tuple(b - a for a, b in zip(coords[room], coords[other]))
            if actual != step:
                issues.append(Issue(WARNING, 'exit_off_grid', side,
                                    f'"{key}" should be one step {key}, but {other} is at '
                                    f'{_fmt(coords[other])} and {room} at {_fmt(coords[room])}: '
                                    'fix the exits, or pin a room to confirm the exception'))
    if anchor is not None or pinned:
        for room in rooms:
            if room not in coords:
                issues.append(Issue(WARNING, 'off_map', f'room {room}',
                                    "can't be reached from the map anchor by compass exits, so it has no map "
                                    'coordinates: connect it, or pin it'))
    cells = defaultdict(list)
    for room, cell in coords.items():
        cells[cell].append(room)
    for cell, here in sorted(cells.items()):
        for room in sorted(here) if len(here) > 1 else []:
            others = ', '.join(r for r in sorted(here) if r != room)
            issues.append(Issue(ERROR, 'map_overlap', f'room {room}',
                                f"works out to map cell {_fmt(cell)}, the same as {others}: change an exit's "
                                'direction, or pin one of the rooms elsewhere'))
    return coords, issues


def _fmt(cell):
    return '(' + ','.join(str(c) for c in cell) + ')'


def _mentions(text, title, current_titles):
    """Does `text` mention `title` as a whole phrase, outside any current room
    title that contains it ("Square" inside "Old Quarter Square")?"""
    for current in current_titles:
        if title.lower() in current.lower() and title.lower() != current.lower():
            text = re.sub(re.escape(current), ' ', text, flags=re.I)
    return re.search(rf'(?<!\w){re.escape(title)}(?!\w)', text, re.I) is not None


def _former_title_issues(root, rooms):
    """A renamed room keeps its old titles in editor.former_titles (the editor
    records them). Warn about content files whose player-visible text still
    says an old title, until the prose is updated or the owner forgets the
    title. Titles another room currently has are skipped: a mention may be it."""
    current_titles = {r.get('title', '') for r in rooms.values() if r.get('title')}
    former = [(room_id, room['title'], old) for room_id, room in rooms.items()
              for old in (room.get('editor') or {}).get('former_titles', [])
              if old and old.lower() not in {t.lower() for t in current_titles}]
    if not former:
        return []
    base = Path(root) / 'content'
    texts = {path.relative_to(base).as_posix(): load_content(root, path.relative_to(base).as_posix()).visible_text
             for path in sorted(base.rglob('*.md'))}
    issues = []
    for room_id, title, old in former:
        for relative, text in texts.items():
            if _mentions(text, old, current_titles):
                issues.append(Issue(WARNING, 'old_title', f'room {room_id}',
                                    f'content/{relative} still mentions "{old}" (now "{title}"): ask Lore to '
                                    'update it, or forget the old title in the editor'))
    return issues


def check_sector(root, sector_id):
    """All issues for one sector, plus the content paths it references."""
    where = f'sectors/{sector_id}/sector.json'
    if not sector_path(root, sector_id).is_file():
        return [Issue(ERROR, 'no_sector', where, 'file not found')], set()
    try:
        sector = load_sector(root, sector_id)
    except DuplicateKeyError as exc:
        return [Issue(ERROR, 'duplicate_id', where, str(exc))], set()
    except ValueError as exc:
        return [Issue(ERROR, 'bad_json', where, str(exc))], set()
    return check_sector_data(root, sector_id, sector)


def check_sector_data(root, sector_id, sector, manifest=True):
    """check_sector() for a sector dict that may not be saved yet (the editor's
    live check). manifest=False skips the staleness comparison, which only
    means something for the saved file."""
    where = f'sectors/{sector_id}/sector.json'
    room_kind, kinds = load_kinds(root)
    issues, referenced = [], set()
    if sector.get('format_version') != FORMAT_VERSION:
        issues.append(Issue(ERROR, 'format_version', where,
                            f"format_version {sector.get('format_version')!r}, expected {FORMAT_VERSION}"))
    if sector.get('sector_id') != sector_id:
        issues.append(Issue(ERROR, 'sector_id', where,
                            f"declares sector_id {sector.get('sector_id')!r}, but lives in sectors/{sector_id}/"))

    rooms = sector.get('rooms', {})
    entities = sector.get('entities', {})
    for object_id in sorted(set(rooms) & set(entities)):
        issues.append(Issue(ERROR, 'duplicate_id', object_id, 'used by both a room and an entity'))
    for object_id in [*rooms, *entities]:
        if not ID_RE.fullmatch(object_id):
            issues.append(Issue(ERROR, 'bad_id', object_id, 'IDs must match [a-z0-9_]+'))

    for room_id in load_required_rooms(root).get(sector_id, []):
        if room_id not in rooms:
            issues.append(Issue(ERROR, 'missing_required_room', f'room {room_id}',
                                'game code finds this room by tag (REQUIRED_ROOM_IDS in '
                                'prospect/world/entity_kinds.py); the sector must keep it'))

    for room_id, room in rooms.items():
        here = f'room {room_id}'
        if not room.get('title'):
            issues.append(Issue(ERROR, 'no_title', here, 'room has no title'))
        found, _ = _content_issues(root, here, room.get('content'), room_kind, room_id)
        issues += found
        if room.get('content'):
            referenced.add(room['content'])

    for entity_id, entity in entities.items():
        here = f'entity {entity_id}'
        kind = kinds.get(entity.get('kind'))
        if kind is None:
            issues.append(Issue(ERROR, 'unknown_kind', here,
                                f"kind {entity.get('kind')!r} is not in prospect/world/entity_kinds.py"))
            continue
        if entity.get('room') not in rooms:
            issues.append(Issue(ERROR, 'unknown_room', here, f"unknown room {entity.get('room')!r}"))
        params = entity.get('params', {})
        for name, value in params.items():
            spec = kind['params'].get(name)
            if spec is None:
                issues.append(Issue(ERROR, 'unknown_param', here, f"kind {entity['kind']} has no param {name!r}"))
            elif value not in spec['values']:
                issues.append(Issue(ERROR, 'bad_param_value', here,
                                    f"{name}={value!r} is not one of {spec['values']}"))
        for name, spec in kind['params'].items():
            if spec['required'] and name not in params:
                issues.append(Issue(ERROR, 'missing_param', here, f'kind {entity["kind"]} requires param {name!r}'))
        found, _ = _content_issues(root, here, entity.get('content'), kind, entity_id)
        issues += found
        if entity.get('content'):
            referenced.add(entity['content'])

    issues += _exit_issues(sector, rooms)
    issues += map_grid(sector)[1]
    issues += _former_title_issues(root, rooms)
    if manifest:
        issues += _manifest_issues(root, sector_id, sector, referenced)
    return issues, referenced


def _manifest_issues(root, sector_id, sector, referenced):
    """Is the exported manifest up to date with the sector and its prose?"""
    path = manifest_path(root, sector_id)
    where = path.relative_to(root).as_posix()
    if not path.is_file():
        return [Issue(INFO, 'not_exported', where, 'sector has not been exported yet')]
    try:
        current = source_hashes(root, sector_id, sector, referenced)
        exported = read_json(path).get('sources', {})
    except (OSError, ValueError):
        return []  # missing content etc. is already reported above
    changed = sorted(p for p in current.keys() | exported.keys() if current.get(p) != exported.get(p))
    if changed:
        return [Issue(WARNING, 'stale_manifest', where, 'changed since last export: ' + ', '.join(changed))]
    return []


def _unused_content(root, referenced):
    """Stray content: files no sector uses that aren't candidates either. A file
    with a `request:` line waits in the editor's tray, and a dismissed one has
    been looked at, so neither is warned about (Section 8.1)."""
    room_kind, kinds = load_kinds(root)
    folders = sorted({room_kind['content_dir'], *(k['content_dir'] for k in kinds.values())})
    base = Path(root) / 'content'
    try:
        dismissed = load_dismissed(root)
    except ValueError as exc:
        return [Issue(ERROR, 'bad_json', DISMISSED_FILE, str(exc))]
    issues = []
    for folder in folders:
        for path in sorted((base / folder).glob('*.md')):
            relative = path.relative_to(base).as_posix()
            if relative in referenced or relative in dismissed:
                continue
            if load_content(root, relative).fields.get('request'):
                continue
            issues.append(Issue(WARNING, 'unused_content', f'content/{relative}', 'not used by any sector'))
    for relative in sorted(dismissed - referenced):
        if not (base / relative).is_file():
            issues.append(Issue(INFO, 'stale_dismissal', DISMISSED_FILE,
                                f'content/{relative} no longer exists; Restore it in the tray to drop the entry'))
    return issues


def check(root=ROOT, only=None):
    """Issues for the given sectors (default: all). Unused-content warnings need
    every sector loaded, so they're only reported for a full check."""
    root = Path(root)
    all_ids = sector_ids(root)
    if not all_ids and not only:
        return [Issue(ERROR, 'no_sector', 'sectors/', 'no sector files found')]
    issues, referenced = [], set()
    for sector_id in only or all_ids:
        found, refs = check_sector(root, sector_id)
        issues += found
        referenced |= refs
    if not only:
        issues += _unused_content(root, referenced)
    return issues


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('sectors', nargs='*', help='sector IDs (default: all)')
    parser.add_argument('--root', type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    issues = check(args.root, args.sectors or None)
    order = {ERROR: 0, WARNING: 1, INFO: 2}
    for issue in sorted(issues, key=lambda i: (order[i.level], i.where, i.code)):
        print(issue)
    counts = {level: sum(i.level == level for i in issues) for level in order}
    print(f"\n{counts[ERROR]} error(s), {counts[WARNING]} warning(s), {counts[INFO]} info.")
    return 1 if counts[ERROR] else 0


if __name__ == '__main__':
    sys.exit(main())
