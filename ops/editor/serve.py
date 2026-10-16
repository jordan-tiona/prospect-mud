"""MUD editor: local web viewer for sector files (milestone 5a, read-only).

Run from any directory:  python ops/editor/serve.py [--port 8765] [--no-browser]

Serves only to 127.0.0.1 and never writes anything: every request other than
GET is refused. Sector structure comes from sectors/<id>/sector.json, prose
from content/ (read through world_model, the same loaders check.py and
export.py use), and problems from check.py itself, so the viewer can't
disagree with them. No game server, database or model is needed.
"""

import argparse
import json
import sys
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from check import check_sector
from world_model import ID_RE, ROOT, load_content, load_kinds, load_sector, sector_ids

STATIC_DIR = Path(__file__).resolve().parent / 'static'
STATIC_FILES = {  # the only files served; nothing is looked up by path
    '/': ('index.html', 'text/html; charset=utf-8'),
    '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
    '/app.css': ('app.css', 'text/css; charset=utf-8'),
}
DEFAULT_PORT = 8765


def _file_view(root, relative):
    """A content file as the viewer shows it: metadata, heading and
    comment-stripped sections (what could reach players)."""
    if not relative:
        return None
    try:
        content = load_content(root, relative)
    except ValueError:
        return {'path': relative, 'exists': False, 'error': 'outside content/'}
    if content is None:
        return {'path': relative, 'exists': False}
    return {'path': relative, 'exists': True, 'fields': content.fields, 'heading': content.heading,
            'sections': content.sections, 'approval': content.fields.get('approval'),
            'status': content.fields.get('status')}


def _referenced(root):
    refs = set()
    for sector_id in sector_ids(root):
        try:
            sector = load_sector(root, sector_id)
        except ValueError:
            continue
        refs |= {item.get('content') for item in [*sector.get('rooms', {}).values(),
                                                  *sector.get('entities', {}).values()]}
    return refs


def unplaced(root):
    """Content files in a kind's folder that no sector uses, with their request: line."""
    room_kind, kinds = load_kinds(root)
    folders = {room_kind['content_dir']: 'room'}
    for name, kind in kinds.items():
        folders.setdefault(kind['content_dir'], name)
    refs = _referenced(root)
    base = Path(root) / 'content'
    result = []
    for folder, kind in sorted(folders.items()):
        for path in sorted((base / folder).glob('*.md')):
            relative = path.relative_to(base).as_posix()
            if relative in refs:
                continue
            view = _file_view(root, relative)
            view['kind_folder'] = folder
            view['request'] = (view.get('fields') or {}).get('request') or None
            result.append(view)
    return result


def sector_view(root, sector_id):
    sector = load_sector(root, sector_id)
    issues, _refs = check_sector(root, sector_id)
    manifest = {'state': 'fresh', 'changed': []}
    for issue in issues:
        if issue.code == 'not_exported':
            manifest['state'] = 'not_exported'
        elif issue.code == 'stale_manifest':
            manifest = {'state': 'stale', 'changed': issue.message.split(': ', 1)[1].split(', ')}
    rooms = {room_id: {**room, 'file': _file_view(root, room.get('content'))}
             for room_id, room in sector.get('rooms', {}).items()}
    entities = {entity_id: {**entity, 'file': _file_view(root, entity.get('content'))}
                for entity_id, entity in sector.get('entities', {}).items()}
    return {
        'sector_id': sector_id,
        'notes': sector.get('notes', ''),
        'rooms': rooms,
        'exits': sector.get('exits', []),
        'entities': entities,
        'issues': [vars(i) for i in issues if i.code not in ('not_exported', 'stale_manifest')],
        'manifest': manifest,
    }


class Handler(BaseHTTPRequestHandler):
    root = ROOT
    port = DEFAULT_PORT
    server_version = 'MUDEditor/0.1'

    def log_message(self, format, *args):  # quieter console: errors only
        if not args or not str(args[1]).startswith(('2', '3')):
            super().log_message(format, *args)

    def _send(self, status, body, content_type='application/json; charset=utf-8'):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def _host_ok(self):
        # Refuse other Host names, so a web page can't read this via DNS rebinding.
        return self.headers.get('Host', '') in {f'127.0.0.1:{self.port}', f'localhost:{self.port}'}

    def do_GET(self):
        if not self._host_ok():
            return self._send(HTTPStatus.FORBIDDEN, {'error': 'unexpected Host header'})
        path = unquote(urlsplit(self.path).path)
        if path in STATIC_FILES:
            filename, content_type = STATIC_FILES[path]
            return self._send(HTTPStatus.OK, (STATIC_DIR / filename).read_bytes(), content_type)
        if path == '/api/sectors':
            return self._send(HTTPStatus.OK, {'sectors': sector_ids(self.root)})
        if path == '/api/unplaced':
            return self._send(HTTPStatus.OK, {'unplaced': unplaced(self.root)})
        if path.startswith('/api/sector/'):
            sector_id = path.removeprefix('/api/sector/')
            if ID_RE.fullmatch(sector_id) and sector_id in sector_ids(self.root):
                try:
                    return self._send(HTTPStatus.OK, sector_view(self.root, sector_id))
                except ValueError as exc:  # bad JSON, duplicate keys: show it, don't crash
                    return self._send(HTTPStatus.UNPROCESSABLE_ENTITY, {'error': str(exc)})
        return self._send(HTTPStatus.NOT_FOUND, {'error': 'not found'})

    def _read_only(self):
        self._send(HTTPStatus.METHOD_NOT_ALLOWED, {'error': 'the viewer is read-only'})

    do_POST = do_PUT = do_PATCH = do_DELETE = _read_only


def make_server(root=ROOT, port=DEFAULT_PORT):
    """A server bound to 127.0.0.1 (port 0 picks a free one; tests use that)."""
    handler = type('BoundHandler', (Handler,), {'root': Path(root)})
    server = ThreadingHTTPServer(('127.0.0.1', port), handler)
    handler.port = server.server_address[1]
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    parser.add_argument('--no-browser', action='store_true', help="don't open a browser tab")
    parser.add_argument('--root', type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    server = make_server(args.root, args.port)
    url = f'http://127.0.0.1:{server.server_address[1]}/'
    print(f'MUD editor (read-only) at {url}  - Ctrl+C to stop.')
    if not args.no_browser:
        threading.Timer(0.5, webbrowser.open, (url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
