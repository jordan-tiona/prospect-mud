"""Tests for the MUD editor viewer's server (milestone 5a).

Run from the repo root:  python -m unittest discover -s ops/editor
"""

import http.client
import json
import threading
import unittest
import unittest.mock

import export
import serve
from test_editor import OBJECT_FILE, ROOM_FILE, CheckTests
from world_model import ROOT, write_json


class ServeTests(unittest.TestCase):
    setUp_fixture = CheckTests.setUp
    write = CheckTests.write

    def setUp(self):
        self.setUp_fixture()
        quiet = unittest.mock.patch.object(serve.Handler, 'log_message', lambda *args: None)
        quiet.start()
        self.addCleanup(quiet.stop)
        write_json(self.root / 'sectors/test/sector.json', self.sector)
        self.server = serve.make_server(self.root, 0)
        self.port = self.server.server_address[1]
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, method, path, host=None, body=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        headers = {'Host': host or f'127.0.0.1:{self.port}'}
        conn.request(method, path, body=body, headers=headers)
        res = conn.getresponse()
        data = res.read()
        conn.close()
        return res.status, res.getheader('Content-Type'), data

    def get_json(self, path):
        status, _type, data = self.request('GET', path)
        self.assertEqual(status, 200, data)
        return json.loads(data)

    def snapshot(self):
        return {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_lists_sectors(self):
        self.assertEqual(self.get_json('/api/sectors'), {'sectors': ['test']})

    def test_sector_view_carries_structure_prose_and_approval(self):
        view = self.get_json('/api/sector/test')
        room = view['rooms']['room_a']
        self.assertEqual(room['title'], 'Room A')
        self.assertEqual(room['file']['sections']['Description'], 'A plain room.')
        self.assertEqual(room['file']['approval'], 'Approved')
        self.assertEqual(view['exits'][0]['key'], 'north')
        thing = view['entities']['thing']
        self.assertEqual((thing['room'], thing['file']['heading']), ('room_a', 'a thing'))
        self.assertEqual(view['issues'], [])
        self.assertEqual(view['manifest'], {'state': 'not_exported', 'changed': []})

    def test_comments_never_reach_the_viewer(self):
        self.write('rooms/room_a.md', ROOM_FILE.format(id='room_a', text='Visible. <!-- TODO(lore): hidden -->'))
        room = self.get_json('/api/sector/test')['rooms']['room_a']
        self.assertEqual(room['file']['sections']['Description'], 'Visible.')

    def test_check_issues_and_manifest_state(self):
        self.write('rooms/room_b.md', ROOM_FILE.format(id='room_b', text='x').replace('Approved', 'Draft'))
        view = self.get_json('/api/sector/test')
        self.assertEqual([i['code'] for i in view['issues']], ['not_approved'])
        self.write('rooms/room_b.md', ROOM_FILE.format(id='room_b', text='x'))
        export.export(self.root, 'test')
        self.assertEqual(self.get_json('/api/sector/test')['manifest']['state'], 'fresh')
        self.write('rooms/room_b.md', ROOM_FILE.format(id='room_b', text='changed'))
        manifest = self.get_json('/api/sector/test')['manifest']
        self.assertEqual(manifest, {'state': 'stale', 'changed': ['content/rooms/room_b.md']})

    def test_unplaced_content_with_its_request(self):
        self.write('rooms/candidate.md', ROOM_FILE.format(id='candidate', text='A candidate.')
                   .replace('approval: Approved', 'approval: Draft\nrequest: LR-OWNER-0001'))
        self.write('ambient/objects/spare.md', OBJECT_FILE.format(id='spare', name='a spare'))
        unplaced = {u['path']: u for u in self.get_json('/api/unplaced')['unplaced']}
        self.assertEqual(set(unplaced), {'rooms/candidate.md', 'ambient/objects/spare.md'})
        self.assertEqual(unplaced['rooms/candidate.md']['request'], 'LR-OWNER-0001')
        self.assertEqual(unplaced['rooms/candidate.md']['sections']['Description'], 'A candidate.')
        self.assertIsNone(unplaced['ambient/objects/spare.md']['request'])

    def test_broken_sector_file_is_reported_not_crashed(self):
        (self.root / 'sectors/test/sector.json').write_text('{"rooms": {"a": {}, "a": {}}}', encoding='utf-8')
        status, _type, data = self.request('GET', '/api/sector/test')
        self.assertEqual(status, 422)
        self.assertIn('duplicate', json.loads(data)['error'])

    def test_serves_the_page(self):
        for path, kind in (('/', 'text/html'), ('/app.js', 'text/javascript'), ('/app.css', 'text/css')):
            status, content_type, _data = self.request('GET', path)
            self.assertEqual(status, 200, path)
            self.assertTrue(content_type.startswith(kind), path)

    def test_read_only(self):
        before = self.snapshot()
        for method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            status, _type, _data = self.request(method, '/api/sector/test', body=b'{}')
            self.assertEqual(status, 405, method)
        self.assertEqual(before, self.snapshot())

    def test_only_known_paths_are_served(self):
        for path in ('/serve.py', '/../serve.py', '/static/../serve.py', '/%2e%2e/serve.py',
                     '/api/sector/..%2f..%2fsectors', '/api/sector/nope', '/api/sector/Test'):
            status, _type, _data = self.request('GET', path)
            self.assertEqual(status, 404, path)

    def test_refuses_foreign_host_headers(self):
        status, _type, _data = self.request('GET', '/api/sectors', host='evil.example')
        self.assertEqual(status, 403)
        status, _type, _data = self.request('GET', '/api/sectors', host=f'localhost:{self.port}')
        self.assertEqual(status, 200)


class RealSectorViewTests(unittest.TestCase):
    def test_elsewhere_view_builds(self):
        view = serve.sector_view(ROOT, 'elsewhere')
        self.assertIn('old_quarter_square', view['rooms'])
        self.assertTrue(all(r['file']['exists'] for r in view['rooms'].values()))


if __name__ == '__main__':
    unittest.main()
