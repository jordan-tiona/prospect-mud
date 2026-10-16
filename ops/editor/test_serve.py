"""Tests for the MUD editor's server (milestones 5a-5c) and store.py.

Run from the repo root:  python -m unittest discover -s ops/editor
"""

import copy
import http.client
import json
import threading
import unittest
import unittest.mock

import serve
import store
from test_editor import OBJECT_FILE, ROOM_FILE, CheckTests
from world_model import ROOT, dismissed_path, read_json, sector_path, write_json

TOKEN = 'test-token'


class _Fixture(unittest.TestCase):
    setUp_fixture = CheckTests.setUp
    write = CheckTests.write

    def setUp(self):
        self.setUp_fixture()
        write_json(self.root / 'sectors/test/sector.json', self.sector)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}


class ServeTests(_Fixture):
    def setUp(self):
        super().setUp()
        quiet = unittest.mock.patch.object(serve.Handler, 'log_message', lambda *args: None)
        quiet.start()
        self.addCleanup(quiet.stop)
        self.server = serve.make_server(self.root, 0, token=TOKEN)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, method, path, body=None, host=None, token=TOKEN, content_type='application/json'):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        headers = {'Host': host or f'127.0.0.1:{self.port}'}
        if body is not None:
            headers['Content-Type'] = content_type
            if token is not None:
                headers['X-Editor-Token'] = token
            body = body if isinstance(body, bytes) else json.dumps(body).encode('utf-8')
        conn.request(method, path, body=body, headers=headers)
        res = conn.getresponse()
        data = res.read()
        conn.close()
        return res.status, res.getheader('Content-Type'), data

    def get_json(self, path):
        status, _type, data = self.request('GET', path)
        self.assertEqual(status, 200, data)
        return json.loads(data)

    def post(self, path, body, **kwargs):
        status, _type, data = self.request('POST', path, body, **kwargs)
        return status, json.loads(data or b'{}')

    def view(self):
        return self.get_json('/api/sector/test')

    # ------------------------------------------------------------ reading

    def test_lists_sectors(self):
        self.assertEqual(self.get_json('/api/sectors'), {'sectors': ['test']})

    def test_sector_view_carries_the_document_prose_and_version(self):
        view = self.view()
        self.assertEqual(view['sector'], self.sector)
        self.assertEqual(view['version'], store.version_of(self.root, 'test'))
        self.assertEqual(view['files']['rooms/room_a.md']['sections']['Description'], 'A plain room.')
        self.assertEqual(view['files']['ambient/objects/thing.md']['heading'], 'a thing')
        self.assertEqual(view['issues'], [])
        self.assertEqual(view['manifest'], {'state': 'not_exported', 'changed': []})
        self.assertIn('quest_prop', view['kinds'])
        self.assertEqual(view['room']['content_dir'], 'rooms')
        self.assertIsNone(view['autosave'])

    def test_comments_never_reach_the_page(self):
        self.write('rooms/room_a.md', ROOM_FILE.format(id='room_a', text='Visible. <!-- TODO(lore): hidden -->'))
        self.assertEqual(self.view()['files']['rooms/room_a.md']['sections']['Description'], 'Visible.')

    def test_unplaced_content_with_its_request(self):
        self.write('rooms/candidate.md', ROOM_FILE.format(id='candidate', text='A candidate.')
                   .replace('approval: Approved', 'approval: Draft\nrequest: LR-OWNER-0001'))
        self.write('ambient/objects/spare.md', OBJECT_FILE.format(id='spare', name='a spare'))
        unplaced = {u['path']: u for u in self.get_json('/api/unplaced')['unplaced']}
        self.assertEqual(set(unplaced), {'rooms/candidate.md', 'ambient/objects/spare.md'})
        self.assertEqual(unplaced['rooms/candidate.md']['request'], 'LR-OWNER-0001')
        self.assertIsNone(unplaced['ambient/objects/spare.md']['request'])

    def test_dismiss_and_restore_candidates(self):
        self.write('rooms/candidate.md', ROOM_FILE.format(id='candidate', text='A candidate.')
                   .replace('approval: Approved', 'approval: Draft\nrequest: LR-OWNER-0001'))
        self.write('rooms/other.md', ROOM_FILE.format(id='other', text='Another.'))
        before = self.snapshot()
        status, tray = self.post('/api/dismiss', {'paths': ['rooms/candidate.md', 'rooms/other.md']})
        self.assertEqual(status, 200, tray)
        self.assertEqual({u['path']: u['dismissed'] for u in tray['unplaced']},
                         {'rooms/candidate.md': True, 'rooms/other.md': True})
        self.assertEqual(read_json(dismissed_path(self.root)),
                         {'dismissed': ['rooms/candidate.md', 'rooms/other.md'], 'format_version': 1})
        status, tray = self.post('/api/dismiss', {'paths': ['rooms/other.md'], 'dismissed': False})
        self.assertEqual({u['path']: u['dismissed'] for u in tray['unplaced']},
                         {'rooms/candidate.md': True, 'rooms/other.md': False})
        after = self.snapshot()
        touched = {p for p in set(before) | set(after) if before.get(p) != after.get(p)}
        self.assertEqual(touched, {'sectors/_dismissed.json'})
        self.assertEqual(self.get_json('/api/sectors'), {'sectors': ['test']})

    def test_dismiss_refuses_what_it_cannot_place(self):
        self.write('notes/elsewhere.md', 'x')
        for paths in (['../sectors/test/sector.json'], ['rooms/nope.md'], ['notes/elsewhere.md'], [], 'rooms/room_a.md'):
            status, data = self.post('/api/dismiss', {'paths': paths})
            self.assertEqual(status, 422, paths)
        self.assertFalse(dismissed_path(self.root).exists())
        self.assertEqual(self.post('/api/dismiss', {'paths': ['rooms/room_a.md']}, token='wrong')[0], 403)

    def test_dismissed_file_that_was_deleted_can_be_cleared(self):
        write_json(dismissed_path(self.root), {'dismissed': ['rooms/gone.md']})
        self.assertEqual(self.get_json('/api/unplaced')['dismissed_missing'], ['rooms/gone.md'])
        status, tray = self.post('/api/dismiss', {'paths': ['rooms/gone.md'], 'dismissed': False})
        self.assertEqual((status, tray['dismissed_missing']), (200, []))

    def test_broken_sector_file_is_reported_not_crashed(self):
        (self.root / 'sectors/test/sector.json').write_text('{"rooms": {"a": {}, "a": {}}}', encoding='utf-8')
        status, _type, data = self.request('GET', '/api/sector/test')
        self.assertEqual(status, 422)
        self.assertIn('duplicate', json.loads(data)['error'])

    def test_serves_the_page_with_this_sessions_token(self):
        for path, kind in (('/', 'text/html'), ('/app.js', 'text/javascript'), ('/core.js', 'text/javascript'),
                           ('/app.css', 'text/css')):
            status, content_type, data = self.request('GET', path)
            self.assertEqual(status, 200, path)
            self.assertTrue(content_type.startswith(kind), path)
        _status, _type, page = self.request('GET', '/')
        self.assertIn(f'content="{TOKEN}"'.encode(), page)
        self.assertNotIn(serve.TOKEN_PLACEHOLDER, page)

    def test_only_known_paths_are_served(self):
        for path in ('/serve.py', '/../serve.py', '/static/../serve.py', '/%2e%2e/serve.py',
                     '/api/sector/..%2f..%2fsectors', '/api/sector/nope', '/api/sector/Test'):
            status, _type, _data = self.request('GET', path)
            self.assertEqual(status, 404, path)

    def test_refuses_foreign_host_headers(self):
        self.assertEqual(self.request('GET', '/api/sectors', host='evil.example')[0], 403)
        self.assertEqual(self.request('GET', '/api/sectors', host=f'localhost:{self.port}')[0], 200)

    # ----------------------------------------------------------- writing

    def test_writes_need_the_token_and_json(self):
        before = self.snapshot()
        body = {'sector': self.sector, 'base_version': self.view()['version']}
        for kwargs in ({'token': None}, {'token': 'wrong'}, {'content_type': 'text/plain'},
                       {'host': 'evil.example'}):
            status, _data = self.post('/api/sector/test/save', body, **kwargs)
            self.assertEqual(status, 403, kwargs)
        for method in ('PUT', 'PATCH', 'DELETE'):
            self.assertEqual(self.request(method, '/api/sector/test', body=b'{}')[0], 405, method)
        self.assertEqual(before, self.snapshot())

    def test_save_writes_sector_json_and_keeps_the_previous_version(self):
        view = self.view()
        changed = copy.deepcopy(view['sector'])
        changed['rooms']['room_a']['title'] = 'Room A, renamed'
        status, data = self.post('/api/sector/test/save', {'sector': changed, 'base_version': view['version']})
        self.assertEqual(status, 200, data)
        self.assertEqual(read_json(sector_path(self.root, 'test'))['rooms']['room_a']['title'], 'Room A, renamed')
        self.assertEqual(data['version'], store.version_of(self.root, 'test'))
        history = list((self.root / 'sectors/test/.history').glob('sector-*.json'))
        self.assertEqual(len(history), 1)
        self.assertEqual(read_json(history[0])['rooms']['room_a']['title'], 'Room A')

    def test_save_refuses_when_the_file_changed_on_disk(self):
        view = self.view()
        on_disk = copy.deepcopy(self.sector)
        on_disk['notes'] = 'edited elsewhere'
        write_json(sector_path(self.root, 'test'), on_disk)
        before = self.snapshot()
        status, data = self.post('/api/sector/test/save', {'sector': view['sector'], 'base_version': view['version']})
        self.assertEqual(status, 409)
        self.assertEqual(data['current_version'], store.version_of(self.root, 'test'))
        self.assertEqual(before, self.snapshot())

    def test_save_refuses_malformed_sectors(self):
        view = self.view()
        bad = copy.deepcopy(view['sector'])
        bad['exits'][0]['to'] = 'nowhere'
        bad['entities']['thing']['kind'] = 'dragon'
        before = self.snapshot()
        status, data = self.post('/api/sector/test/save', {'sector': bad, 'base_version': view['version']})
        self.assertEqual(status, 422)
        self.assertTrue(any('nowhere' in p or 'to must be' in p for p in data['problems']))
        self.assertTrue(any('dragon' in p for p in data['problems']))
        self.assertEqual(before, self.snapshot())

    def test_a_placeholder_room_with_check_errors_can_still_be_saved(self):
        view = self.view()
        changed = copy.deepcopy(view['sector'])
        changed['rooms']['planned'] = {'title': 'Planned', 'editor': {'x': 0, 'y': 600}}
        status, data = self.post('/api/sector/test/save', {'sector': changed, 'base_version': view['version']})
        self.assertEqual(status, 200, data)
        self.assertIn('no_content', [i['code'] for i in data['view']['issues']])

    def test_live_check_of_unsaved_edits_writes_nothing(self):
        changed = copy.deepcopy(self.sector)
        changed['exits'].append({'from': 'room_b', 'to': 'room_a', 'key': 'door', 'aliases': [], 'return': None})
        before = self.snapshot()
        status, data = self.post('/api/sector/test/check', {'sector': changed})
        self.assertEqual(status, 200)
        self.assertEqual([i['code'] for i in data['issues'] if i['level'] == 'error'], ['duplicate_room_pair'])
        self.assertEqual(before, self.snapshot())

    def test_autosave_restore_and_discard(self):
        view = self.view()
        changed = copy.deepcopy(view['sector'])
        changed['rooms']['room_b']['title'] = 'Unsaved'
        status, data = self.post('/api/sector/test/autosave', {'sector': changed, 'base_version': view['version']})
        self.assertEqual((status, data), (200, {'rotated': True}))
        self.assertEqual(read_json(sector_path(self.root, 'test')), self.sector)  # sector.json untouched
        offer = self.view()['autosave']
        self.assertTrue(offer['base_matches'])
        self.assertEqual(self.get_json('/api/sector/test/autosave')['sector'], changed)
        self.post('/api/sector/test/autosave/discard', {})
        self.assertIsNone(self.view()['autosave'])

    def test_export_button_refuses_on_errors_and_writes_on_success(self):
        self.write('rooms/room_b.md', ROOM_FILE.format(id='room_b', text='x').replace('Approved', 'Draft'))
        status, data = self.post('/api/sector/test/export', {})
        self.assertEqual(status, 422)
        self.assertEqual([e['code'] for e in data['errors']], ['not_approved'])
        self.assertFalse((self.root / 'prospect/world/data/sectors/test.json').exists())
        self.write('rooms/room_b.md', ROOM_FILE.format(id='room_b', text='x'))
        status, data = self.post('/api/sector/test/export', {})
        self.assertEqual(status, 200, data)
        self.assertEqual(data['path'], 'prospect/world/data/sectors/test.json')
        self.assertEqual(data['view']['manifest']['state'], 'fresh')

    def test_writes_stay_inside_the_sector_and_manifest(self):
        view = self.view()
        changed = copy.deepcopy(view['sector'])
        changed['notes'] = 'hello'
        before = self.snapshot()
        self.post('/api/sector/test/autosave', {'sector': changed, 'base_version': view['version']})
        self.post('/api/sector/test/save', {'sector': changed, 'base_version': view['version']})
        self.post('/api/sector/test/export', {})
        after = self.snapshot()
        touched = {p for p in set(before) | set(after) if before.get(p) != after.get(p)}
        self.assertTrue(all(p.startswith('sectors/test/') or p == 'prospect/world/data/sectors/test.json'
                            for p in touched), touched)
        self.assertEqual({p for p in before if p.startswith('content/')}, {p for p in after if p.startswith('content/')})
        self.assertTrue(all(before[p] == after[p] for p in before if p.startswith('content/')))


class StoreTests(_Fixture):
    def test_history_keeps_only_the_newest(self):
        version = store.version_of(self.root, 'test')
        with unittest.mock.patch.object(store, 'HISTORY_KEEP', 3):
            for i in range(5):
                with unittest.mock.patch.object(store, 'now', return_value=1_000_000 + i):
                    changed = copy.deepcopy(self.sector)
                    changed['notes'] = f'save {i}'
                    version = store.save(self.root, 'test', changed, version)
        kept = sorted((self.root / 'sectors/test/.history').glob('sector-*.json'))
        self.assertEqual(len(kept), 3)
        self.assertEqual(read_json(kept[-1]).get('notes'), 'save 3')  # the version before the last save

    def test_autosave_rotates_every_five_minutes_keeping_five(self):
        folder = self.root / 'sectors/test/.autosave'
        t = 2_000_000
        for minute in range(0, 40):  # an edit every minute for 40 minutes
            with unittest.mock.patch.object(store, 'now', return_value=t + minute * 60):
                changed = copy.deepcopy(self.sector)
                changed['notes'] = f'minute {minute}'
                store.autosave(self.root, 'test', changed, 'v')
        rotating = sorted(folder.glob('auto-*.json'))
        self.assertEqual(len(rotating), store.ROTATE_KEEP)
        stamps = [read_json(p)['saved_at'] for p in rotating]
        self.assertTrue(all(b - a >= store.ROTATE_EVERY for a, b in zip(stamps, stamps[1:])))
        self.assertEqual(read_json(folder / 'latest.json')['sector']['notes'], 'minute 39')

    def test_saving_clears_latest_but_keeps_rotating_copies(self):
        version = store.version_of(self.root, 'test')
        changed = copy.deepcopy(self.sector)
        changed['notes'] = 'x'
        store.autosave(self.root, 'test', changed, version)
        store.save(self.root, 'test', changed, version)
        folder = self.root / 'sectors/test/.autosave'
        self.assertFalse((folder / 'latest.json').exists())
        self.assertEqual(len(list(folder.glob('auto-*.json'))), 1)
        self.assertIsNone(store.autosave_info(self.root, 'test'))

    def test_autosave_offer_warns_when_the_file_moved_on(self):
        old_version = store.version_of(self.root, 'test')
        changed = copy.deepcopy(self.sector)
        changed['notes'] = 'autosaved'
        store.autosave(self.root, 'test', changed, old_version)
        elsewhere = copy.deepcopy(self.sector)
        elsewhere['notes'] = 'git pull'
        write_json(sector_path(self.root, 'test'), elsewhere)
        self.assertEqual(store.autosave_info(self.root, 'test')['base_matches'], False)

    def test_validate_shape_accepts_the_real_sector(self):
        sector = read_json(sector_path(ROOT, 'elsewhere'))
        self.assertEqual(store.validate_shape(ROOT, 'elsewhere', sector), [])

    def test_validate_shape_problems(self):
        bad = copy.deepcopy(self.sector)
        bad['extra'] = 1
        bad['rooms']['Bad Id'] = {'title': 3}
        bad['exits'].append({'from': 'room_a', 'to': 'room_b', 'key': '', 'return': {'key': 'x', 'bogus': 1}})
        bad['entities']['room_a'] = {'kind': 'ambient_object', 'room': 'room_a', 'params': {'x': 1}}
        bad['rooms']['room_b']['editor'] = {'x': 0, 'y': 0, 'former_titles': 'Room B'}
        problems = ' | '.join(store.validate_shape(self.root, 'test', bad))
        for expected in ("unknown top-level field 'extra'", 'room Bad Id: IDs must match', 'title must be text',
                         'key must be text', 'return must be null', 'ID already used by a room',
                         'params must map names to text', 'former titles must be a list of text'):
            self.assertIn(expected, problems)

    def test_write_json_is_atomic(self):
        path = self.root / 'sectors/test/sector.json'
        write_json(path, {'a': 1})
        self.assertEqual(read_json(path), {'a': 1})
        self.assertEqual(list(path.parent.glob('.*.tmp')), [])


class RealSectorViewTests(unittest.TestCase):
    def test_elsewhere_view_builds(self):
        view = serve.sector_view(ROOT, 'elsewhere')
        self.assertIn('old_quarter_square', view['sector']['rooms'])
        self.assertTrue(all(f['exists'] for f in view['files'].values()))


if __name__ == '__main__':
    unittest.main()
