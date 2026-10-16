"""Tests for the MUD editor's importer and check.

Run from the repo root:  python -m unittest discover -s ops/editor
"""

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import check
import export
import import_legacy
from world_model import KINDS_FILE, ROOT, literals, load_content, manifest_path, parse_content, read_json, write_json

WORLD = ROOT / 'prospect/world'


def codes(issues, level=None):
    return sorted({i.code for i in issues if level is None or i.level == level})


class ImporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sector = import_legacy.build_sector(ROOT)

    def test_every_room_imported_with_title_and_content(self):
        rooms = literals(WORLD / 'build_rooms.py', ('ROOMS',))['ROOMS']
        self.assertEqual({r[0]: r[1] for r in rooms},
                         {k: v['title'] for k, v in self.sector['rooms'].items()})
        for room_id, room in self.sector['rooms'].items():
            self.assertEqual(room['content'], f'rooms/{room_id}.md')
            self.assertIn('editor', room)

    def test_every_exit_pair_imported(self):
        data = literals(WORLD / 'build_rooms.py', ('HUB', 'SPOKES', 'CHAINS'))
        expected = {(data['HUB'], spoke, fwd[0], back[0]) for spoke, fwd, back in data['SPOKES']}
        expected |= {(src, dst, fwd[0], back[0]) for src, dst, fwd, back in data['CHAINS']}
        actual = {(e['from'], e['to'], e['key'], e['return']['key']) for e in self.sector['exits']}
        self.assertEqual(expected, actual)
        self.assertEqual(len(self.sector['exits']), len(expected))

    def test_every_built_entity_imported_in_its_room(self):
        entities = self.sector['entities']
        expected = {}
        for npc_id, _name, room in literals(WORLD / 'build_npcs.py', ('NPCS',))['NPCS']:
            expected[npc_id] = ('talk_npc', room)
        ambient = literals(WORLD / 'build_ambient.py', ('AMBIENT_NPC_IDS', 'AMBIENT_OBJECT_IDS'))
        for kind, folder, key in (('ambient_npc', 'ambient/npcs', 'AMBIENT_NPC_IDS'),
                                  ('ambient_object', 'ambient/objects', 'AMBIENT_OBJECT_IDS')):
            for ambient_id in ambient[key]:
                expected[ambient_id] = (kind, load_content(ROOT, f'{folder}/{ambient_id}.md').fields['room'])
        for prop in literals(WORLD / 'build_quest_props.py', ('QUEST_PROPS',))['QUEST_PROPS']:
            expected[prop[0]] = ('quest_prop', prop[1])
        expected['civic_information_display'] = ('revision_display', 'corner_cafe')
        expected['old_quarter_square_signpost'] = ('signpost', 'old_quarter_square')
        expected['civic_office_skitter_ledger'] = ('skitter_ledger', 'civic_office')
        expected['gardening_kit'] = ('gardening_kit', 'residential_courtyard')
        expected['planting_bed'] = ('planting_bed', 'old_quarter_square')
        self.assertEqual(expected, {k: (v['kind'], v['room']) for k, v in entities.items()})

    def test_quest_prop_lock_calls_become_params(self):
        for prop_id, _room, _key, _line, _desc, lock_call in literals(
                WORLD / 'build_quest_props.py', ('QUEST_PROPS',))['QUEST_PROPS']:
            params = self.sector['entities'][prop_id]['params']
            arg = f"({params['commitment_type']})" if 'commitment_type' in params else '()'
            self.assertEqual(lock_call, params['visibility'] + arg)

    def test_garden_aliases_kept(self):
        for prop in import_legacy.garden_props(ROOT):
            self.assertEqual(prop['aliases'], self.sector['entities'][prop['id']].get('aliases', []))

    def test_import_is_deterministic(self):
        self.assertEqual(self.sector, import_legacy.build_sector(ROOT))

    def test_committed_sector_file_matches_a_fresh_import(self):
        # Holds only until the editor starts owning the sector file; drop it then.
        committed = json.loads((ROOT / 'sectors/elsewhere/sector.json').read_text(encoding='utf-8'))
        self.assertEqual(self.sector, committed)

    def test_refuses_to_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'sectors/elsewhere/sector.json'
            target.parent.mkdir(parents=True)
            target.write_text('{"keep": true}', encoding='utf-8')
            self.assertEqual(import_legacy.main(['--root', temp]), 1)
            self.assertEqual(target.read_text(encoding='utf-8'), '{"keep": true}')


class MovedProseTests(unittest.TestCase):
    """Approved text in content/objects/ must match the in-code copy the game still reads, until build_sector replaces the old scripts."""

    def content(self, object_id):
        return load_content(ROOT, f'objects/{object_id}.md')

    def assert_object(self, object_id, key, room_line, desc=None):
        content = self.content(object_id)
        self.assertEqual(content.fields['object_id'], object_id)
        if content.fields.get('approval') != 'Approved':
            # A Lore revision awaiting approval may differ from the in-code copy:
            # the game keeps the last approved text until Dev/Tools copy the new
            # one across after approval (see LR-0001's resolution).
            return
        self.assertEqual(content.heading, key)
        self.assertEqual(content.sections['Short Description'], room_line)
        if desc is not None:
            self.assertEqual(content.sections['Description'], desc)

    def test_quest_props(self):
        for prop_id, _room, key, room_line, desc, _lock in literals(
                WORLD / 'build_quest_props.py', ('QUEST_PROPS',))['QUEST_PROPS']:
            self.assert_object(prop_id, key, room_line, desc)

    def test_garden_props(self):
        for prop in import_legacy.garden_props(ROOT):
            self.assert_object(prop['id'], prop['key'], prop['room_line'], prop['desc'])

    def test_noticeboard(self):
        data = literals(WORLD / 'build_noticeboard.py', ('DISPLAY_PROP_ID', 'ROOM_LINE'))
        self.assert_object(data['DISPLAY_PROP_ID'], import_legacy.single_prop_key(ROOT, 'build_noticeboard.py'),
                           data['ROOM_LINE'])

    def test_skitter_ledger(self):
        data = literals(WORLD / 'build_skitter_ledger.py', ('LEDGER_PROP_ID', 'KEY', 'ROOM_LINE', 'DESC'))
        self.assert_object(data['LEDGER_PROP_ID'], data['KEY'], data['ROOM_LINE'], data['DESC'])

    def test_signpost(self):
        data = literals(WORLD / 'build_signpost.py', ('SIGNPOST_PROP_ID', 'ROOM_LINE', 'SPOKE_LINES'))
        self.assert_object(data['SIGNPOST_PROP_ID'], import_legacy.single_prop_key(ROOT, 'build_signpost.py'),
                           data['ROOM_LINE'])
        lines = self.content(data['SIGNPOST_PROP_ID']).sections['Spoke Lines'].splitlines()
        self.assertEqual([line.removeprefix('- ') for line in lines], data['SPOKE_LINES'])


ROOM_FILE = """<!--
room_id: {id}
status: Provisional
approval: Approved
-->

## Description

{text}
"""

OBJECT_FILE = """<!--
object_id: {id}
room: room_a
status: Provisional
approval: Approved
-->

# {name}

## Short Description

A thing is here.

## Description

It is a thing.
"""

BASE_SECTOR = {
    'format_version': 1,
    'sector_id': 'test',
    'rooms': {
        'room_a': {'title': 'Room A', 'content': 'rooms/room_a.md'},
        'room_b': {'title': 'Room B', 'content': 'rooms/room_b.md'},
    },
    'exits': [
        {'from': 'room_a', 'to': 'room_b', 'key': 'north', 'aliases': ['n'],
         'return': {'key': 'south', 'aliases': ['s']}},
    ],
    'entities': {
        'thing': {'kind': 'ambient_object', 'room': 'room_a', 'content': 'ambient/objects/thing.md'},
    },
}


class CheckTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / KINDS_FILE).parent.mkdir(parents=True)
        shutil.copy2(ROOT / KINDS_FILE, self.root / KINDS_FILE)
        for room_id in ('room_a', 'room_b'):
            self.write(f'rooms/{room_id}.md', ROOM_FILE.format(id=room_id, text='A plain room.'))
        self.write('ambient/objects/thing.md', OBJECT_FILE.format(id='thing', name='a thing'))
        self.sector = copy.deepcopy(BASE_SECTOR)

    def write(self, relative, text):
        path = self.root / 'content' / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')

    def run_check(self, only=None):
        """Issues, minus the 'not exported yet' note every unexported fixture gets."""
        write_json(self.root / 'sectors/test/sector.json', self.sector)
        return [i for i in check.check(self.root, only) if i.code != 'not_exported']

    def test_valid_sector_is_clean(self):
        self.assertEqual(self.run_check(), [])

    def test_missing_return_is_an_error_and_null_is_one_way(self):
        del self.sector['exits'][0]['return']
        self.assertIn('exit_no_return', codes(self.run_check(), check.ERROR))
        self.sector['exits'][0]['return'] = None
        issues = self.run_check()
        self.assertEqual(codes(issues, check.ERROR), [])
        self.assertIn('one_way_exit', codes(issues, check.INFO))
        self.assertEqual(codes(issues, check.WARNING), ['dead_end', 'unreachable'])

    def test_duplicate_exit_word_in_one_room(self):
        self.sector['exits'].append({'from': 'room_a', 'to': 'room_b', 'key': 'up', 'aliases': ['N'],
                                     'return': {'key': 'down', 'aliases': []}})
        self.assertEqual(codes(self.run_check(), check.ERROR), ['duplicate_exit'])

    def test_return_exit_words_are_claimed_too(self):
        self.sector['exits'].append({'from': 'room_b', 'to': 'room_a', 'key': 'south', 'aliases': [],
                                     'return': {'key': 'up', 'aliases': []}})
        self.assertEqual(codes(self.run_check(), check.ERROR), ['duplicate_exit'])

    def test_unknown_rooms(self):
        self.sector['exits'][0]['to'] = 'nowhere'
        self.sector['entities']['thing']['room'] = 'nowhere'
        self.assertEqual(codes(self.run_check(), check.ERROR), ['unknown_room'])

    def test_unknown_kind(self):
        self.sector['entities']['thing']['kind'] = 'dragon'
        self.assertEqual(codes(self.run_check(), check.ERROR), ['unknown_kind'])

    def test_params_are_checked_against_the_allowlist(self):
        self.write('objects/hint.md', OBJECT_FILE.format(id='hint', name='a hint'))
        self.sector['entities']['hint'] = {'kind': 'quest_prop', 'room': 'room_a', 'content': 'objects/hint.md'}
        self.assertEqual(codes(self.run_check(), check.ERROR), ['missing_param'])
        self.sector['entities']['hint']['params'] = {'visibility': 'always_visible', 'colour': 'red'}
        self.assertEqual(codes(self.run_check(), check.ERROR), ['bad_param_value', 'unknown_param'])
        self.sector['entities']['hint']['params'] = {'visibility': 'commitment_hint_visible',
                                                     'commitment_type': 'deliver_parcel'}
        self.assertEqual(codes(self.run_check(), check.ERROR), [])

    def test_content_reference_problems(self):
        cases = {
            'no_content': None,
            'missing_content': 'ambient/objects/absent.md',
            'bad_content_path': '../outside.md',
        }
        for code, ref in cases.items():
            with self.subTest(code):
                self.sector['entities']['thing']['content'] = ref
                self.assertEqual(codes(self.run_check(only=['test']), check.ERROR), [code])

    def test_content_file_problems(self):
        cases = {
            'content_id_mismatch': OBJECT_FILE.format(id='other', name='a thing'),
            'not_approved': OBJECT_FILE.format(id='thing', name='a thing').replace('Approved', 'Draft'),
            'missing_section': OBJECT_FILE.format(id='thing', name='a thing').split('## Description')[0],
            'missing_heading': OBJECT_FILE.format(id='thing', name='a thing').replace('# a thing\n', ''),
            'no_metadata': '# a thing\n\n## Short Description\n\nx\n\n## Description\n\ny\n',
        }
        for code, text in cases.items():
            with self.subTest(code):
                self.write('ambient/objects/thing.md', text)
                self.assertEqual(codes(self.run_check(), check.ERROR), [code])

    def test_unapproved_room_blocks(self):
        self.write('rooms/room_b.md', ROOM_FILE.format(id='room_b', text='x').replace('Approved', 'Draft'))
        self.assertEqual(codes(self.run_check(), check.ERROR), ['not_approved'])

    def test_todo_lore_warned_only_when_visible(self):
        self.write('rooms/room_a.md', ROOM_FILE.format(id='room_a', text='A room. <!-- TODO(lore): name it -->'))
        self.assertEqual(self.run_check(), [])
        self.write('rooms/room_a.md', ROOM_FILE.format(id='room_a', text='TODO(lore): describe this room.'))
        self.assertEqual(codes(self.run_check(), check.WARNING), ['visible_todo'])

    def test_duplicate_ids(self):
        self.sector['entities']['room_a'] = self.sector['entities'].pop('thing')
        self.assertIn('duplicate_id', codes(self.run_check(), check.ERROR))
        path = self.root / 'sectors/test/sector.json'
        path.write_text('{"rooms": {"room_a": {}, "room_a": {}}}', encoding='utf-8')
        self.assertEqual(codes(check.check(self.root), check.ERROR), ['duplicate_id'])

    def test_bad_ids_and_header(self):
        self.sector['rooms']['Room C'] = {'title': 'C', 'content': 'rooms/room_a.md'}
        self.sector['format_version'] = 2
        self.sector['sector_id'] = 'other'
        self.assertEqual(codes(self.run_check(), check.ERROR),
                         ['bad_id', 'content_id_mismatch', 'format_version', 'sector_id'])

    def test_disconnected_and_exitless_rooms(self):
        self.write('rooms/room_c.md', ROOM_FILE.format(id='room_c', text='Alone.'))
        self.sector['rooms']['room_c'] = {'title': 'Room C', 'content': 'rooms/room_c.md'}
        self.assertEqual(codes(self.run_check(), check.WARNING), ['disconnected', 'no_exits'])

    def test_required_rooms(self):
        kinds = self.root / KINDS_FILE
        kinds.write_text(kinds.read_text(encoding='utf-8').replace(
            'REQUIRED_ROOM_IDS = {', 'REQUIRED_ROOM_IDS = {\n    "test": ["room_a"],', 1), encoding='utf-8')
        self.assertEqual(self.run_check(), [])
        del self.sector['rooms']['room_a']
        self.sector['exits'] = []
        self.sector['entities'] = {}
        self.assertIn('missing_required_room', codes(self.run_check(), check.ERROR))

    def test_unused_content_only_on_a_full_check(self):
        self.write('ambient/objects/spare.md', OBJECT_FILE.format(id='spare', name='a spare'))
        self.assertEqual(codes(self.run_check(), check.WARNING), ['unused_content'])
        self.assertEqual(self.run_check(only=['test']), [])

    def test_check_never_writes(self):
        write_json(self.root / 'sectors/test/sector.json', self.sector)
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        check.check(self.root)
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})


class ExportTests(CheckTests.__base__):
    setUp = CheckTests.setUp
    write = CheckTests.write

    def export(self):
        write_json(self.root / 'sectors/test/sector.json', self.sector)
        return export.export(self.root, 'test')

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_exports_resolved_manifest(self):
        issues, path = self.export()
        self.assertEqual(path, manifest_path(self.root, 'test'))
        manifest = read_json(path)
        self.assertEqual(manifest['rooms']['room_a'], {
            'title': 'Room A', 'typeclass': 'typeclasses.rooms.Room', 'tag_category': 'phase1_neighborhood',
            'desc': 'A plain room.', 'glance': None})
        self.assertEqual(manifest['exits'], [
            {'id': 'room_a__north', 'from': 'room_a', 'to': 'room_b', 'key': 'north', 'aliases': ['n']},
            {'id': 'room_b__south', 'from': 'room_b', 'to': 'room_a', 'key': 'south', 'aliases': ['s']}])
        self.assertEqual(manifest['entities']['thing'], {
            'kind': 'ambient_object', 'typeclass': 'typeclasses.objects.RoomObject',
            'tag_category': 'phase1_ambient', 'room': 'room_a', 'key': 'a thing', 'aliases': [],
            'attributes': {'room_line': 'A thing is here.', 'desc': 'It is a thing.'}})
        self.assertEqual(sorted(manifest['sources']), [
            'content/ambient/objects/thing.md', 'content/rooms/room_a.md', 'content/rooms/room_b.md',
            'sectors/test/sector.json'])
        self.assertNotIn('editor', path.read_text(encoding='utf-8'))

    def test_one_way_exit_exports_one_direction(self):
        self.sector['exits'][0]['return'] = None
        _issues, path = self.export()
        self.assertEqual([e['id'] for e in read_json(path)['exits']], ['room_a__north'])

    def test_refuses_on_error_and_keeps_old_manifest(self):
        self.export()
        before = self.snapshot()
        self.write('rooms/room_b.md', ROOM_FILE.format(id='room_b', text='x').replace('Approved', 'Draft'))
        self.sector['rooms']['room_b']['title'] = 'Renamed'
        issues, path = self.export()
        self.assertIsNone(path)
        self.assertIn('not_approved', codes(issues, check.ERROR))
        after = self.snapshot()
        self.assertEqual(before['prospect/world/data/sectors/test.json'],
                         after['prospect/world/data/sectors/test.json'])

    def test_game_parser_failure_is_reported_not_raised(self):
        self.write('ambient/objects/thing.md', OBJECT_FILE.format(id='thing', name='a thing')
                   .replace('room: room_a\n', ''))
        issues, path = self.export()
        self.assertIsNone(path)
        self.assertEqual(codes(issues, check.ERROR), ['parse_error'])

    def test_quest_prop_locks_from_params(self):
        self.write('objects/hint.md', OBJECT_FILE.format(id='hint', name='a hint'))
        self.sector['entities']['hint'] = {'kind': 'quest_prop', 'room': 'room_a', 'content': 'objects/hint.md',
                                           'params': {'visibility': 'module_exchange_hint_visible'}}
        _issues, path = self.export()
        self.assertEqual(read_json(path)['entities']['hint']['locks'],
                         'view:module_exchange_hint_visible();search:module_exchange_hint_visible();get:false()')

    def test_export_is_deterministic_and_writes_only_the_manifest(self):
        write_json(self.root / 'sectors/test/sector.json', self.sector)
        before = self.snapshot()
        export.export(self.root, 'test')
        first = self.snapshot()
        export.export(self.root, 'test')
        self.assertEqual(first, self.snapshot())
        self.assertEqual(set(first) - set(before), {'prospect/world/data/sectors/test.json'})
        self.assertEqual({k: v for k, v in first.items() if k in before}, before)

    def test_staleness(self):
        self.export()
        self.assertEqual(check.check(self.root, ['test']), [])
        self.sector['rooms']['room_a']['editor'] = {'x': 999, 'y': 1}  # layout only: not a game change
        write_json(self.root / 'sectors/test/sector.json', self.sector)
        self.assertEqual(check.check(self.root, ['test']), [])
        self.write('rooms/room_a.md', ROOM_FILE.format(id='room_a', text='A changed room.'))
        issues = check.check(self.root, ['test'])
        self.assertEqual(codes(issues), ['stale_manifest'])
        self.assertIn('content/rooms/room_a.md', issues[0].message)

    def test_crlf_checkout_hashes_the_same(self):
        self.export()
        path = self.root / 'content/rooms/room_a.md'
        data = path.read_bytes()
        flipped = data.replace(b'\r\n', b'\n') if b'\r\n' in data else data.replace(b'\n', b'\r\n')
        self.assertNotEqual(data, flipped)
        path.write_bytes(flipped)
        self.assertEqual(check.check(self.root, ['test']), [])


class RealSectorTests(unittest.TestCase):
    def test_elsewhere_resolves_with_the_game_parsers(self):
        manifest = export.build_manifest(ROOT, 'elsewhere')
        self.assertEqual(len(manifest['exits']), 2 * len(import_legacy.build_sector(ROOT)['exits']))

    def test_elsewhere_only_blocked_by_approval(self):
        # Structure must be sound; the remaining errors are content still awaiting approval.
        issues = check.check(ROOT, ['elsewhere'])
        self.assertEqual([c for c in codes(issues, check.ERROR) if c != 'not_approved'], [])


class ParseContentTests(unittest.TestCase):
    def test_comments_are_stripped_from_sections_and_heading(self):
        content = parse_content('x.md', '<!--\na: 1\n-->\n# Name <!-- n -->\n\n## One\n\nText <!-- hidden -->\n')
        self.assertEqual(content.fields, {'a': '1'})
        self.assertEqual(content.heading, 'Name')
        self.assertEqual(content.sections, {'One': 'Text'})


if __name__ == '__main__':
    unittest.main()
