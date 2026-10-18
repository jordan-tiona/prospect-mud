"""Export a sector to the engine manifest (docs/mud-editor-sector-format.md Section 6).

Run from any directory:  python ops/editor/export.py [sector_id ...]
With no sector IDs, exports every sector under sectors/. Each sector is
checked first (check.py); any error refuses that sector's export and leaves
its existing manifest untouched. Writes only prospect/world/data/sectors/.

Prose is parsed with the game's own content parsers (world/room_content.py,
world/ambient_content.py, world/npc_profile.py - plain Python, no Evennia),
so the manifest carries exactly the text the game would show.
"""

import argparse
import sys
from pathlib import Path

from check import ERROR, Issue, check_sector, map_grid
from world_model import (FORMAT_VERSION, MAP_AXES, ROOT, load_kinds, load_sector, manifest_path, parse_content,
                         content_path, source_hashes, write_json)

_GAME_DIR = Path(__file__).resolve().parents[2] / 'prospect'
if str(_GAME_DIR) not in sys.path:
    sys.path.insert(0, str(_GAME_DIR))

from world.ambient_content import (AmbientContentParseError, parse_ambient_npc_text,  # noqa: E402
                                   parse_ambient_object_text)
from world.npc_profile import PersonaParseError, parse_persona_text  # noqa: E402
from world.room_content import RoomContentParseError, parse_room_text  # noqa: E402

PARSE_ERRORS = (AmbientContentParseError, PersonaParseError, RoomContentParseError, KeyError, ValueError)


class _BlankDefault(dict):
    def __missing__(self, key):
        return ''


def _read(root, relative):
    return content_path(root, relative).read_text(encoding='utf-8-sig')


def _talk_npc(entity_id, raw):
    profile = parse_persona_text(entity_id, raw)
    key = parse_content('', raw).heading
    attributes = {'npc_id': entity_id}
    if profile.desc:
        attributes['desc'] = profile.desc
    if profile.probe_desc:  # `probe_desc:` metadata line, never the persona body
        attributes['probe_desc'] = profile.probe_desc
    if profile.emotes:  # `## Emotes`, cut from the persona body (world/idle_emotes.py)
        attributes['emotes'] = profile.emotes
    return {'key': key, 'aliases': [key.split()[0]], 'attributes': attributes}


def _with_probe(attributes, probe_desc):
    """`probe <thing>` text (commands/probe.py), only when authored."""
    if probe_desc:
        attributes['probe_desc'] = probe_desc
    return attributes


def _ambient_npc(entity_id, raw):
    content = parse_ambient_npc_text(entity_id, raw)
    attributes = _with_probe({'desc': content.desc}, content.probe_desc)
    if content.emotes:  # world/idle_emotes.py
        attributes['emotes'] = content.emotes
    return {'key': content.key, 'aliases': [], 'attributes': attributes, 'poses': content.poses}


def _ambient_object(entity_id, raw):
    content = parse_ambient_object_text(entity_id, raw)
    return {'key': content.key, 'aliases': [],
            'attributes': _with_probe({'room_line': content.short_desc, 'desc': content.desc}, content.probe_desc)}


def _object(entity_id, raw):
    """content/objects/ files: '# key', '## Short Description' (room line),
    optional '## Description', '## Probe Description' and '## Spoke Lines' (a '- ' list)."""
    content = parse_content('', raw)
    attributes = _with_probe({'room_line': content.sections['Short Description']},
                             content.sections.get('Probe Description'))
    if content.sections.get('Description'):
        attributes['desc'] = content.sections['Description']
    if 'Spoke Lines' in content.sections:
        attributes['spoke_lines'] = [line.strip().removeprefix('- ').strip()
                                     for line in content.sections['Spoke Lines'].splitlines() if line.strip()]
    return {'key': content.heading, 'aliases': [], 'attributes': attributes}


_RESOLVERS = {'talk_npc': _talk_npc, 'ambient_npc': _ambient_npc, 'ambient_object': _ambient_object}
_NPC_KINDS = ('talk_npc', 'ambient_npc')
GLANCE_VALUES = {'show': True, 'hide': False}


def _in_glance(kind, raw):
    """Whether an object's room line shows in the arrival glance: the content
    file's `glance: show | hide` metadata line, else the kind's default
    (world/entity_kinds.py; LR-LORE-0005). check.py rejects any other value."""
    value = parse_content('', raw).fields.get('glance', '').strip().lower()
    return GLANCE_VALUES.get(value, kind.get('glance', True))


def build_manifest(root, sector_id):
    """Resolve a sector into its manifest dict. Doesn't validate - export() checks
    first; tests call this directly to compare against today's builders."""
    root = Path(root)
    sector = load_sector(root, sector_id)
    room_kind, kinds = load_kinds(root)
    refs = set()

    grid, _issues = map_grid(sector)
    rooms = {}
    for room_id, room in sector['rooms'].items():
        refs.add(room['content'])
        parsed = parse_room_text(room_id, _read(root, room['content']))
        rooms[room_id] = {'title': room['title'], 'typeclass': room_kind['typeclass'],
                          'tag_category': room_kind['tag_category'], 'desc': parsed.desc, 'glance': parsed.glance}
        if room_id in grid:  # check.py warns about a room the grid can't reach (off_map)
            rooms[room_id]['map'] = dict(zip(MAP_AXES, grid[room_id]))

    exits = []
    for ex in sector['exits']:
        pairs = [(ex['from'], ex['to'], ex['key'], ex.get('aliases', []))]
        if ex.get('return'):
            pairs.append((ex['to'], ex['from'], ex['return']['key'], ex['return'].get('aliases', [])))
        for src, dst, key, aliases in pairs:
            exits.append({'id': f'{src}__{key}', 'from': src, 'to': dst, 'key': key, 'aliases': list(aliases)})

    entities = {}
    for entity_id, entity in sector['entities'].items():
        kind = kinds[entity['kind']]
        refs.add(entity['content'])
        raw = _read(root, entity['content'])
        resolved = _RESOLVERS.get(entity['kind'], _object)(entity_id, raw)
        if entity['kind'] not in _NPC_KINDS:
            resolved['attributes']['in_glance'] = _in_glance(kind, raw)
        resolved['aliases'] = resolved['aliases'] + [a for a in entity.get('aliases', [])
                                                     if a not in resolved['aliases']]
        resolved.update(kind=entity['kind'], typeclass=kind['typeclass'], tag_category=kind['tag_category'],
                        room=entity['room'])
        if kind.get('locks'):
            resolved['locks'] = kind['locks'].format_map(_BlankDefault(entity.get('params', {})))
        entities[entity_id] = resolved

    return {'format_version': FORMAT_VERSION, 'sector_id': sector_id,
            'sources': source_hashes(root, sector_id, sector, refs),
            'rooms': rooms, 'exits': exits, 'entities': entities}


def export(root, sector_id):
    """(issues, written path or None). Refuses to write if check reports any error."""
    issues, _refs = check_sector(root, sector_id)
    if any(i.level == ERROR for i in issues):
        return issues, None
    try:
        manifest = build_manifest(root, sector_id)
    except PARSE_ERRORS as exc:
        # The game's parsers can be stricter than check.py (e.g. ambient
        # files still need a room: field); report, don't crash.
        return issues + [Issue(ERROR, 'parse_error', f'sectors/{sector_id}', f'{type(exc).__name__}: {exc}')], None
    path = manifest_path(root, sector_id)
    write_json(path, manifest)
    return issues, path


def main(argv=None):
    from world_model import sector_ids

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('sectors', nargs='*', help='sector IDs (default: all)')
    parser.add_argument('--root', type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    refused = 0
    for sector_id in args.sectors or sector_ids(args.root):
        issues, path = export(args.root, sector_id)
        for issue in issues:
            if issue.code != 'stale_manifest':
                print(issue)
        if path is None:
            refused += 1
            errors = sum(i.level == ERROR for i in issues)
            print(f'REFUSED {sector_id}: {errors} error(s); existing manifest left unchanged.\n')
        else:
            print(f'Exported {sector_id} -> {path}\n')
    return 1 if refused else 0


if __name__ == '__main__':
    sys.exit(main())
