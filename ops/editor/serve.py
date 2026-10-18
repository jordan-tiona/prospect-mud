"""MUD editor: local web editor for sector files.

Run from any directory:  python ops/editor/serve.py [--port 8765] [--no-browser]

Serves only to 127.0.0.1. Sector structure comes from sectors/<id>/sector.json,
prose from content/ (read through world_model, the same loaders check.py and
export.py use), and problems from check.py itself, so the editor can't
disagree with them. No game server, database or model is needed.

Writes (milestones 5b-5c) go through store.py and touch only the editor's own
files: a sector's sector.json, plus its gitignored .history/ and .autosave/
folders; sectors/_dismissed.json (the tray's dismiss list); or, for Export, the
manifest via export.py. Prose in content/ is never written. Every
write request must carry the random token embedded in the page (header
X-Editor-Token) and a JSON body, so other web pages can't trigger one.
"""

import argparse
import json
import secrets
import sys
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

import export
import store
from check import ERROR, check_sector, check_sector_data, map_grid
from world_model import ID_RE, ROOT, load_content, load_dismissed, load_kinds, load_sector, sector_ids

STATIC_DIR = Path(__file__).resolve().parent / 'static'
STATIC_FILES = {  # the only files served; nothing is looked up by path
    '/': ('index.html', 'text/html; charset=utf-8'),
    '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
    '/core.js': ('core.js', 'text/javascript; charset=utf-8'),
    '/app.css': ('app.css', 'text/css; charset=utf-8'),
}
TOKEN_PLACEHOLDER = b'__EDITOR_TOKEN__'
DEFAULT_PORT = 8765


def _file_view(root, relative):
    """A content file as the editor shows it: metadata, heading and
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
    """Content files in a kind's folder that no saved sector uses: the candidate
    tray. Each carries its request: line and whether it was dismissed."""
    refs = _referenced(root)
    dismissed = load_dismissed(root)
    base = Path(root) / 'content'
    result = []
    for folder in sorted(store.content_folders(root)):
        for path in sorted((base / folder).glob('*.md')):
            relative = path.relative_to(base).as_posix()
            if relative in refs:
                continue
            view = _file_view(root, relative)
            view['kind_folder'] = folder
            view['request'] = (view.get('fields') or {}).get('request') or None
            view['dismissed'] = relative in dismissed
            result.append(view)
    return result


def tray_view(root):
    """The tray: unplaced files, the whole dismiss list, and which dismissed
    paths no longer exist (so their entries can be cleared)."""
    dismissed = sorted(load_dismissed(root))
    gone = [p for p in dismissed if not (Path(root) / 'content' / p).is_file()]
    return {'unplaced': unplaced(root), 'dismissed': dismissed, 'dismissed_missing': gone}


def kinds_view(root):
    """The Dev-owned allowlist, as the editor's dropdowns need it."""
    room_kind, kinds = load_kinds(root)
    return {
        'room': {'content_dir': room_kind['content_dir'], 'id_field': room_kind['id_field']},
        'kinds': {name: {'content_dir': k['content_dir'], 'id_field': k['id_field'], 'params': k['params']}
                  for name, k in kinds.items()},
    }


def _manifest_state(issues):
    manifest = {'state': 'fresh', 'changed': []}
    for issue in issues:
        if issue.code == 'not_exported':
            manifest['state'] = 'not_exported'
        elif issue.code == 'stale_manifest':
            manifest = {'state': 'stale', 'changed': issue.message.split(': ', 1)[1].split(', ')}
    return manifest


def _visible(issues):
    return [vars(i) for i in issues if i.code not in ('not_exported', 'stale_manifest')]


def _grid(sector):
    """{room_id: [x, y, z]} worked out from the anchor, exits and pins, for the
    map and room panel. Malformed data gives what can be worked out, or nothing."""
    try:
        return {room: list(cell) for room, cell in map_grid(sector)[0].items()}
    except (AttributeError, TypeError):
        return {}


def sector_view(root, sector_id):
    sector = load_sector(root, sector_id)
    issues, _refs = check_sector(root, sector_id)
    files = {}
    for item in [*sector.get('rooms', {}).values(), *sector.get('entities', {}).values()]:
        if item.get('content'):
            files[item['content']] = _file_view(root, item['content'])
    return {
        'sector_id': sector_id,
        'sector': sector,  # the editable document, exactly as saved
        'version': store.version_of(root, sector_id),
        'files': files,
        'issues': _visible(issues),
        'manifest': _manifest_state(issues),
        'grid': _grid(sector),
        'autosave': store.autosave_info(root, sector_id),
        **kinds_view(root),
    }


class Handler(BaseHTTPRequestHandler):
    root = ROOT
    port = DEFAULT_PORT
    token = ''
    server_version = 'MUDEditor/0.3'

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

    def _sector_from_path(self, path, suffix=''):
        """The sector id in /api/sector/<id><suffix>, if it names a real sector."""
        rest = path.removeprefix('/api/sector/')
        if not path.startswith('/api/sector/') or not rest.endswith(suffix):
            return None
        sector_id = rest[: len(rest) - len(suffix)] if suffix else rest
        return sector_id if ID_RE.fullmatch(sector_id) and sector_id in sector_ids(self.root) else None

    # ---------------------------------------------------------------- GET

    def do_GET(self):
        if not self._host_ok():
            return self._send(HTTPStatus.FORBIDDEN, {'error': 'unexpected Host header'})
        path = unquote(urlsplit(self.path).path)
        if path in STATIC_FILES:
            filename, content_type = STATIC_FILES[path]
            body = (STATIC_DIR / filename).read_bytes()
            if filename == 'index.html':
                body = body.replace(TOKEN_PLACEHOLDER, self.token.encode('ascii'))
            return self._send(HTTPStatus.OK, body, content_type)
        if path == '/api/sectors':
            return self._send(HTTPStatus.OK, {'sectors': sector_ids(self.root)})
        if path == '/api/unplaced':
            try:
                return self._send(HTTPStatus.OK, tray_view(self.root))
            except ValueError as exc:  # a broken _dismissed.json
                return self._send(HTTPStatus.UNPROCESSABLE_ENTITY, {'error': str(exc)})
        sector_id = self._sector_from_path(path, '/autosave')
        if sector_id:
            return self._send(HTTPStatus.OK, {'sector': store.load_autosave(self.root, sector_id)})
        sector_id = self._sector_from_path(path)
        if sector_id:
            try:
                return self._send(HTTPStatus.OK, sector_view(self.root, sector_id))
            except ValueError as exc:  # bad JSON, duplicate keys: show it, don't crash
                return self._send(HTTPStatus.UNPROCESSABLE_ENTITY, {'error': str(exc)})
        return self._send(HTTPStatus.NOT_FOUND, {'error': 'not found'})

    # --------------------------------------------------------------- POST

    def _write_allowed(self):
        if not self._host_ok():
            return False
        if not secrets.compare_digest(self.headers.get('X-Editor-Token', ''), self.token):
            return False
        return self.headers.get('Content-Type', '').split(';')[0].strip() == 'application/json'

    def do_POST(self):
        if not self._write_allowed():
            return self._send(HTTPStatus.FORBIDDEN, {'error': 'missing or wrong editor token'})
        path = unquote(urlsplit(self.path).path)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            body = store.parse_body(self.rfile.read(length)) if length else {}
        except (ValueError, store.InvalidSector) as exc:
            return self._send(HTTPStatus.BAD_REQUEST, {'error': str(exc)})
        if path == '/api/dismiss':
            return self._dismiss(body)
        for suffix, action in (('/check', self._check), ('/save', self._save), ('/autosave', self._autosave),
                               ('/autosave/discard', self._discard), ('/export', self._export)):
            sector_id = self._sector_from_path(path, suffix)
            if sector_id:
                return action(sector_id, body)
        return self._send(HTTPStatus.NOT_FOUND, {'error': 'not found'})

    def _check(self, sector_id, body):
        """Live check of the editor's unsaved document. Writes nothing."""
        sector = body.get('sector')
        problems = store.validate_shape(self.root, sector_id, sector)
        if problems:
            return self._send(HTTPStatus.OK, {'issues': [], 'problems': problems, 'grid': {}})
        issues, _refs = check_sector_data(self.root, sector_id, sector, manifest=False)
        return self._send(HTTPStatus.OK, {'issues': _visible(issues), 'problems': [], 'grid': _grid(sector)})

    def _save(self, sector_id, body):
        try:
            version = store.save(self.root, sector_id, body.get('sector'), body.get('base_version'))
        except store.InvalidSector as exc:
            return self._send(HTTPStatus.UNPROCESSABLE_ENTITY, {'error': 'not saved', 'problems': exc.problems})
        except store.SaveConflict as exc:
            return self._send(HTTPStatus.CONFLICT, {'error': str(exc), 'current_version': exc.current_version})
        return self._send(HTTPStatus.OK, {'version': version, 'view': sector_view(self.root, sector_id)})

    def _autosave(self, sector_id, body):
        sector = body.get('sector')
        if not isinstance(sector, dict):
            return self._send(HTTPStatus.BAD_REQUEST, {'error': 'sector must be an object'})
        rotated = store.autosave(self.root, sector_id, sector, body.get('base_version'))
        return self._send(HTTPStatus.OK, {'rotated': rotated})

    def _discard(self, sector_id, _body):
        store.discard_autosave(self.root, sector_id)
        return self._send(HTTPStatus.OK, {'discarded': True})

    def _export(self, sector_id, _body):
        issues, path = export.export(self.root, sector_id)
        errors = [vars(i) for i in issues if i.level == ERROR]
        if path is None:
            return self._send(HTTPStatus.UNPROCESSABLE_ENTITY, {'exported': False, 'errors': errors})
        return self._send(HTTPStatus.OK, {'exported': True, 'path': Path(path).relative_to(self.root).as_posix(),
                                          'view': sector_view(self.root, sector_id)})

    def _dismiss(self, body):
        """{paths: [...], dismissed: true|false}: add to or take off the tray's dismiss list."""
        try:
            store.set_dismissed(self.root, body.get('paths'), body.get('dismissed') is not False)
        except store.InvalidSector as exc:
            return self._send(HTTPStatus.UNPROCESSABLE_ENTITY, {'error': str(exc), 'problems': exc.problems})
        except ValueError as exc:  # a broken _dismissed.json
            return self._send(HTTPStatus.UNPROCESSABLE_ENTITY, {'error': str(exc)})
        return self._send(HTTPStatus.OK, tray_view(self.root))

    def _not_allowed(self):
        self._send(HTTPStatus.METHOD_NOT_ALLOWED, {'error': 'use GET or POST'})

    do_PUT = do_PATCH = do_DELETE = _not_allowed


def make_server(root=ROOT, port=DEFAULT_PORT, token=None):
    """A server bound to 127.0.0.1 (port 0 picks a free one; tests use that)."""
    handler = type('BoundHandler', (Handler,), {'root': Path(root), 'token': token or secrets.token_urlsafe(32)})
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
    print(f'MUD editor at {url}  - Ctrl+C to stop.')
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
