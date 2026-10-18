"""Tests for the MUD editor's check and export.

Run from the repo root:  python -m unittest discover -s ops/editor
"""

import copy
import shutil
import tempfile
import unittest
from pathlib import Path

import check
import export
from world_model import (KINDS_FILE, ROOT, dismissed_path, load_sector, manifest_path, parse_content, read_json,
                         write_json)


def codes(issues, level=None):
    return sorted({i.code for i in issues if level is None or i.level == level})


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

PERSONA_FILE = """<!--
npc_id: someone
room: Room B
approval: Approved
prompt_version: 1
knowledge_scope (bible sections, Established content only):
  1.1
actions: give_directions
pronouns: they/them
probe_desc: A closer look at someone.
-->

# Someone

You are someone.
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

    def add_room_c(self):
        self.write('rooms/room_c.md', ROOM_FILE.format(id='room_c', text='Room C.'))
        self.sector['rooms']['room_c'] = {'title': 'Room C', 'content': 'rooms/room_c.md'}

    def test_duplicate_exit_word_in_one_room(self):
        self.add_room_c()
        self.sector['exits'].append({'from': 'room_a', 'to': 'room_c', 'key': 'up', 'aliases': ['N'],
                                     'return': {'key': 'down', 'aliases': []}})
        self.assertEqual(codes(self.run_check(), check.ERROR), ['duplicate_exit'])

    def test_return_exit_words_are_claimed_too(self):
        self.add_room_c()
        self.sector['exits'].append({'from': 'room_c', 'to': 'room_a', 'key': 'down', 'aliases': [],
                                     'return': {'key': 'north', 'aliases': []}})
        self.assertEqual(codes(self.run_check(), check.ERROR), ['duplicate_exit'])

    def test_one_connection_per_pair_of_rooms(self):
        second = {'from': 'room_a', 'to': 'room_b', 'key': 'door', 'aliases': [], 'return': None}
        self.sector['exits'].append(second)
        issues = [i for i in self.run_check() if i.level == check.ERROR]
        self.assertEqual(codes(issues), ['duplicate_room_pair'])
        self.assertIn('exit[0] room_a->room_b', issues[0].message)

    def test_two_one_way_records_facing_each_other_are_one_connection(self):
        self.sector['exits'] = [
            {'from': 'room_a', 'to': 'room_b', 'key': 'north', 'aliases': [], 'return': None},
            {'from': 'room_b', 'to': 'room_a', 'key': 'south', 'aliases': [], 'return': None},
        ]
        self.assertEqual(codes(self.run_check(), check.ERROR), ['duplicate_room_pair'])

    def test_different_pairs_are_fine(self):
        self.add_room_c()
        self.sector['exits'].append({'from': 'room_b', 'to': 'room_c', 'key': 'east', 'aliases': [],
                                     'return': {'key': 'west', 'aliases': []}})
        self.assertEqual(self.run_check(), [])

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
            'draft_field': OBJECT_FILE.format(id='thing', name='a thing').replace(
                'approval: Approved', 'approval: Approved\nprobe_description: Draft (LR-X-0001); pending'),
            'missing_section': OBJECT_FILE.format(id='thing', name='a thing').split('## Description')[0],
            'missing_heading': OBJECT_FILE.format(id='thing', name='a thing').replace('# a thing\n', ''),
            'no_metadata': '# a thing\n\n## Short Description\n\nx\n\n## Description\n\ny\n',
            'bad_glance': OBJECT_FILE.format(id='thing', name='a thing').replace(
                'approval: Approved', 'approval: Approved\nglance: maybe'),
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

    def test_candidates_and_dismissed_files_are_not_stray(self):
        self.write('ambient/objects/candidate.md', OBJECT_FILE.format(id='candidate', name='a candidate')
                   .replace('approval: Approved', 'approval: Draft\nrequest: LR-OWNER-0001'))
        self.write('ambient/objects/rejected.md', OBJECT_FILE.format(id='rejected', name='a reject'))
        self.write('ambient/objects/stray.md', OBJECT_FILE.format(id='stray', name='a stray'))
        write_json(dismissed_path(self.root), {'dismissed': ['ambient/objects/rejected.md']})
        unused = [i.where for i in self.run_check() if i.code == 'unused_content']
        self.assertEqual(unused, ['content/ambient/objects/stray.md'])

    def test_dismissal_of_a_deleted_file_is_noted(self):
        write_json(dismissed_path(self.root), {'dismissed': ['ambient/objects/gone.md']})
        self.assertEqual([(i.level, i.code) for i in self.run_check()], [(check.INFO, 'stale_dismissal')])

    def test_prose_still_using_a_former_room_title(self):
        self.sector['rooms']['room_b']['title'] = 'The Annex'
        self.sector['rooms']['room_b']['editor'] = {'former_titles': ['Room B']}
        self.write('rooms/room_a.md', ROOM_FILE.format(id='room_a', text='Room B is north. <!-- Room B in a comment -->'))
        found = [i for i in self.run_check() if i.code == 'old_title']
        self.assertEqual([(i.level, i.where) for i in found], [(check.WARNING, 'room room_b')])
        self.assertIn('content/rooms/room_a.md', found[0].message)
        # Only in a comment, or only inside a current title that contains it: no warning.
        self.write('rooms/room_a.md', ROOM_FILE.format(id='room_a', text='North. <!-- Room B -->'))
        self.assertNotIn('old_title', codes(self.run_check()))
        self.sector['rooms']['room_a']['title'] = 'Old Annex'
        self.sector['rooms']['room_b']['editor'] = {'former_titles': ['Annex']}
        self.write('rooms/room_a.md', ROOM_FILE.format(id='room_a', text='Old Annex is here.'))
        self.assertNotIn('old_title', codes(self.run_check()))
        # A title another room has now isn't stale.
        self.sector['rooms']['room_b']['editor'] = {'former_titles': ['Old Annex']}
        self.assertNotIn('old_title', codes(self.run_check()))

    def test_check_never_writes(self):
        write_json(self.root / 'sectors/test/sector.json', self.sector)
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        check.check(self.root)
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})


class ExportTests(CheckTests.__base__):
    setUp = CheckTests.setUp
    write = CheckTests.write
    run_check = CheckTests.run_check

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
            'attributes': {'room_line': 'A thing is here.', 'desc': 'It is a thing.', 'in_glance': False}})
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
        # check.py doesn't require status:, but the game's ambient parser does.
        self.write('ambient/objects/thing.md', OBJECT_FILE.format(id='thing', name='a thing')
                   .replace('status: Provisional\n', ''))
        issues, path = self.export()
        self.assertIsNone(path)
        self.assertEqual(codes(issues, check.ERROR), ['parse_error'])

    def test_glance_follows_kind_default_unless_overridden(self):
        # LR-LORE-0005: ambient_object defaults to hide.
        _issues, path = self.export()
        self.assertIs(read_json(path)['entities']['thing']['attributes']['in_glance'], False)
        self.write('ambient/objects/thing.md', OBJECT_FILE.format(id='thing', name='a thing').replace(
            'approval: Approved', 'approval: Approved\nglance: Show'))
        _issues, path = self.export()
        self.assertIs(read_json(path)['entities']['thing']['attributes']['in_glance'], True)

    def test_probe_text_is_carried_when_authored(self):
        # ambient object: `## Probe Description`
        self.write('ambient/objects/thing.md', OBJECT_FILE.format(id='thing', name='a thing')
                   + '\n## Probe Description\n\nUp close, it is still a thing.\n')
        # generic object (content/objects/): the same section
        self.write('objects/hint.md', OBJECT_FILE.format(id='hint', name='a hint')
                   + '\n## Probe Description\n\nA closer look at the hint.\n')
        self.sector['entities']['hint'] = {'kind': 'quest_prop', 'room': 'room_a', 'content': 'objects/hint.md',
                                           'params': {'visibility': 'module_exchange_hint_visible'}}
        # persona: a `probe_desc:` metadata line, never the body
        self.write('npcs/someone.md', PERSONA_FILE)
        self.sector['entities']['someone'] = {'kind': 'talk_npc', 'room': 'room_b', 'content': 'npcs/someone.md'}
        _issues, path = self.export()
        entities = read_json(path)['entities']
        self.assertEqual(entities['thing']['attributes']['probe_desc'], 'Up close, it is still a thing.')
        self.assertEqual(entities['hint']['attributes']['probe_desc'], 'A closer look at the hint.')
        self.assertEqual(entities['someone']['attributes']['probe_desc'], 'A closer look at someone.')

    def test_no_probe_text_means_no_probe_attribute(self):
        _issues, path = self.export()
        self.assertNotIn('probe_desc', read_json(path)['entities']['thing']['attributes'])

    def test_probe_text_on_a_kind_that_ignores_it_is_warned(self):
        self.write('objects/sign.md', OBJECT_FILE.format(id='sign', name='a sign')
                   + '\n## Spoke Lines\n\n- North: somewhere.\n\n## Probe Description\n\nNever shown.\n')
        self.sector['entities']['sign'] = {'kind': 'signpost', 'room': 'room_a', 'content': 'objects/sign.md'}
        self.assertEqual(codes(self.run_check(), check.WARNING), ['probe_unused'])

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
        sector = load_sector(ROOT, 'elsewhere')
        self.assertEqual(len(manifest['exits']), sum(2 if e['return'] else 1 for e in sector['exits']))

    def test_committed_manifest_is_a_valid_export(self):
        # Not a staleness check (Lore commits mustn't break tests): only that
        # what's committed parses and is the format build_sector expects.
        manifest = read_json(manifest_path(ROOT, 'elsewhere'))
        self.assertEqual((manifest['format_version'], manifest['sector_id']), (1, 'elsewhere'))

    def test_elsewhere_only_blocked_by_approval(self):
        # Structure must be sound; the remaining errors are content still awaiting approval.
        issues = check.check(ROOT, ['elsewhere'])
        self.assertEqual([c for c in codes(issues, check.ERROR) if c not in ('not_approved', 'draft_field')], [])


class ParseContentTests(unittest.TestCase):
    def test_comments_are_stripped_from_sections_and_heading(self):
        content = parse_content('x.md', '<!--\na: 1\n-->\n# Name <!-- n -->\n\n## One\n\nText <!-- hidden -->\n')
        self.assertEqual(content.fields, {'a': '1'})
        self.assertEqual(content.heading, 'Name')
        self.assertEqual(content.sections, {'One': 'Text'})


if __name__ == '__main__':
    unittest.main()
