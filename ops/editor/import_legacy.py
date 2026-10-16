"""One-off importer: today's world/build_*.py data -> sectors/elsewhere/sector.json.

Run from any directory:  python ops/editor/import_legacy.py [--force]

Reads the builders' literal data (and, for the builders that wire
objects inside build(), their _get_room/_get_or_create call arguments) with
ast, never executing game code. Map positions come from the Obsidian canvas
where it has them; other rooms are placed next to a neighbour by exit
direction. Writes only the sector file, and refuses to overwrite one that
exists unless --force is given (after the first import, the editor owns it).
"""

import argparse
import ast
import sys
from pathlib import Path

from world_model import FORMAT_VERSION, ROOT, literals, load_content, read_json, sector_path, write_json

SECTOR_ID = 'elsewhere'
WORLD = 'prospect/world'
CANVAS = 'maps/Elsewhere Map.canvas'

# Editor map offsets per exit direction, matching the canvas's spacing.
STEP_X, STEP_Y = 560, 430
OFFSETS = {
    'north': (0, -1), 'south': (0, 1), 'east': (1, 0), 'west': (-1, 0),
    'northeast': (1, -1), 'northwest': (-1, -1), 'southeast': (1, 1), 'southwest': (-1, 1),
    'up': (0, -1), 'down': (0, 1),
}


def _module(root, name):
    return ast.parse((Path(root) / WORLD / name).read_text(encoding='utf-8-sig'))


def _function(module, name):
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise ValueError(f'function {name}() not found')


def _const(node):
    return ast.literal_eval(node)


def _room_calls(func):
    """{variable: room_tag} for `var = _get_room("tag")`, plus the list of all tags in call order."""
    names, tags = {}, []
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == '_get_room':
            tags.append(_const(node.args[0]))
    for node in ast.walk(func):
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                and getattr(node.value.func, 'id', None) == '_get_room'):
            names[node.targets[0].id] = _const(node.value.args[0])
    return names, tags


def _create_object_key(func):
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'create_object':
            for kw in node.keywords:
                if kw.arg == 'key':
                    return _const(kw.value)
    raise ValueError('create_object(key=...) not found')


def single_room(root, builder):
    """The one room a single-prop builder (noticeboard, signpost) places into."""
    _, tags = _room_calls(_function(_module(root, builder), 'build'))
    if len(tags) != 1:
        raise ValueError(f'{builder}: expected exactly one _get_room() call, found {tags}')
    return tags[0]


def single_prop_key(root, builder):
    return _create_object_key(_function(_module(root, builder), 'build'))


def garden_props(root):
    """[{id, typeclass, key, room, desc, room_line, aliases}] from build_garden_props.build()."""
    func = _function(_module(root, 'build_garden_props.py'), 'build')
    rooms, _ = _room_calls(func)
    props = []
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == '_get_or_create':
            prop_id, typeclass, key, room_var, desc = node.args
            kwargs = {kw.arg: _const(kw.value) for kw in node.keywords}
            props.append(dict(id=_const(prop_id), typeclass=_const(typeclass), key=_const(key),
                              room=rooms[room_var.id], desc=_const(desc),
                              room_line=kwargs.get('room_line'), aliases=kwargs.get('aliases') or []))
    return props


def _canvas_positions(root):
    path = Path(root) / CANVAS
    if not path.is_file():
        return {}
    return {n['id']: (n['x'], n['y']) for n in read_json(path).get('nodes', []) if 'x' in n}


def _layout(room_ids, exits, known):
    """Canvas positions where known; otherwise beside an already-placed neighbour."""
    placed = {r: known[r] for r in room_ids if r in known}
    if not placed and room_ids:
        placed[room_ids[0]] = (0, 0)
    links = []
    for e in exits:
        links.append((e['from'], e['to'], e['key']))
        if e['return']:
            links.append((e['to'], e['from'], e['return']['key']))
    progress = True
    while progress and len(placed) < len(room_ids):
        progress = False
        for src, dst, key in links:
            if src in placed and dst not in placed:
                dx, dy = OFFSETS.get(key, (1, 0))
                x, y = placed[src][0] + dx * STEP_X, placed[src][1] + dy * STEP_Y
                while any(abs(x - px) < 280 and abs(y - py) < 215 for px, py in placed.values()):
                    x -= STEP_X // 2
                placed[dst] = (x, y)
                progress = True
    for r in room_ids:  # unconnected rooms: park in a row below the map
        placed.setdefault(r, (len(placed) * 300, 2000))
    return {r: {'x': placed[r][0], 'y': placed[r][1]} for r in room_ids}


def build_sector(root=ROOT):
    root = Path(root)
    rooms_data = literals(root / WORLD / 'build_rooms.py', ('ROOMS', 'HUB', 'SPOKES', 'CHAINS'))
    npcs = literals(root / WORLD / 'build_npcs.py', ('NPCS',))['NPCS']
    ambient = literals(root / WORLD / 'build_ambient.py', ('AMBIENT_NPC_IDS', 'AMBIENT_OBJECT_IDS'))
    quest_props = literals(root / WORLD / 'build_quest_props.py', ('QUEST_PROPS',))['QUEST_PROPS']
    noticeboard_id = literals(root / WORLD / 'build_noticeboard.py', ('DISPLAY_PROP_ID',))['DISPLAY_PROP_ID']
    signpost_id = literals(root / WORLD / 'build_signpost.py', ('SIGNPOST_PROP_ID',))['SIGNPOST_PROP_ID']
    ledger = literals(root / WORLD / 'build_skitter_ledger.py', ('LEDGER_PROP_ID', 'ALIASES'))
    ledger_id = ledger['LEDGER_PROP_ID']

    room_ids = [room_id for room_id, _title, _desc in rooms_data['ROOMS']]
    rooms = {room_id: {'title': title, 'content': f'rooms/{room_id}.md'}
             for room_id, title, _desc in rooms_data['ROOMS']}

    exits = []
    hub = rooms_data['HUB']
    for spoke, (fwd, fwd_aliases), (back, back_aliases) in rooms_data['SPOKES']:
        exits.append({'from': hub, 'to': spoke, 'key': fwd, 'aliases': list(fwd_aliases),
                      'return': {'key': back, 'aliases': list(back_aliases)}})
    for src, dst, (fwd, fwd_aliases), (back, back_aliases) in rooms_data['CHAINS']:
        exits.append({'from': src, 'to': dst, 'key': fwd, 'aliases': list(fwd_aliases),
                      'return': {'key': back, 'aliases': list(back_aliases)}})

    entities = {}
    for npc_id, _name, room in npcs:
        entities[npc_id] = {'kind': 'talk_npc', 'room': room, 'content': f'npcs/{npc_id}.md'}
    for kind, folder, ids in (('ambient_npc', 'ambient/npcs', ambient['AMBIENT_NPC_IDS']),
                              ('ambient_object', 'ambient/objects', ambient['AMBIENT_OBJECT_IDS'])):
        for ambient_id in ids:
            relative = f'{folder}/{ambient_id}.md'
            content = load_content(root, relative)
            if content is None or not content.fields.get('room'):
                raise ValueError(f'{relative}: needed for its room, but missing or has no room field')
            entities[ambient_id] = {'kind': kind, 'room': content.fields['room'], 'content': relative}
    for prop_id, room, _key, _line, _desc, lock_call in quest_props:
        func, _, arg = lock_call.partition('(')
        arg = arg.rstrip(')').strip()
        params = {'visibility': func.strip()}
        if arg:
            params['commitment_type'] = arg
        entities[prop_id] = {'kind': 'quest_prop', 'room': room, 'content': f'objects/{prop_id}.md',
                             'params': params}
    entities[noticeboard_id] = {'kind': 'revision_display', 'room': single_room(root, 'build_noticeboard.py'),
                                'content': f'objects/{noticeboard_id}.md'}
    entities[signpost_id] = {'kind': 'signpost', 'room': single_room(root, 'build_signpost.py'),
                             'content': f'objects/{signpost_id}.md'}
    entities[ledger_id] = {'kind': 'skitter_ledger', 'room': single_room(root, 'build_skitter_ledger.py'),
                           'content': f'objects/{ledger_id}.md', 'aliases': list(ledger['ALIASES'])}
    garden_kinds = {'typeclasses.objects.GardeningKit': 'gardening_kit',
                    'typeclasses.objects.PlantingBed': 'planting_bed'}
    for prop in garden_props(root):
        entity = {'kind': garden_kinds[prop['typeclass']], 'room': prop['room'],
                  'content': f"objects/{prop['id']}.md"}
        if prop['aliases']:
            entity['aliases'] = list(prop['aliases'])
        entities[prop['id']] = entity

    duplicates = set(rooms) & set(entities)
    if duplicates:
        raise ValueError(f'IDs used by both a room and an entity: {sorted(duplicates)}')

    for room_id, position in _layout(room_ids, exits, _canvas_positions(root)).items():
        rooms[room_id]['editor'] = position

    return {'format_version': FORMAT_VERSION, 'sector_id': SECTOR_ID, 'notes': '',
            'rooms': rooms, 'exits': exits, 'entities': entities}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--force', action='store_true', help='overwrite an existing sector file')
    parser.add_argument('--root', type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    target = sector_path(args.root, SECTOR_ID)
    if target.exists() and not args.force:
        print(f'{target} already exists; the editor owns it now. Use --force to re-import.', file=sys.stderr)
        return 1
    sector = build_sector(args.root)
    write_json(target, sector)
    print(f"Wrote {target}: {len(sector['rooms'])} rooms, {len(sector['exits'])} exit pairs, "
          f"{len(sector['entities'])} entities.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
