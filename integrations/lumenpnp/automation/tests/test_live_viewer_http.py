import http.client
import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
if 'PIL' not in sys.modules:
    pil = types.ModuleType('PIL')
    pil.Image = object()
    sys.modules['PIL'] = pil
if 'Xlib' not in sys.modules:
    xlib = types.ModuleType('Xlib')
    xlib.X = types.SimpleNamespace(IsViewable=1, ZPixmap=2)
    xlib.display = types.SimpleNamespace(Display=None)
    sys.modules['Xlib'] = xlib
import live_viewer

PUBLIC_ORIGIN = 'https://paste-viewer.example.trycloudflare.com'


class _Display:
    def screen(self):
        return type('Screen', (), {'root': type('Root', (), {'query_tree': lambda self: type('Tree', (), {'children': []})()})()})()


class LiveViewerHttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.state = Path(cls.directory.name) / 'state'
        cls.state.mkdir()
        (cls.state / 'chat-source.json').write_text(json.dumps({
            'path': str(cls.state / 'rollout.jsonl'),
            'thread': '01a0cfa4-7e41-77c0-a7be-1c22a2da8908',
        }))
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        cls.port = sock.getsockname()[1]
        sock.close()
        cls.server = None
        original_server = live_viewer.ThreadingHTTPServer

        class CapturingServer(original_server):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                cls.server = self

        cls.server_patch = mock.patch.object(live_viewer, 'ThreadingHTTPServer', CapturingServer)
        cls.display_patch = mock.patch.object(live_viewer.display, 'Display', _Display)
        cls.server_patch.start()
        cls.display_patch.start()
        cls.original_argv = sys.argv
        sys.argv = ['live_viewer.py', '--bind', '127.0.0.1', '--port', str(cls.port),
                    '--state', str(cls.state), '--public-origin', PUBLIC_ORIGIN]
        cls.main_thread = threading.Thread(target=live_viewer.main, daemon=True)
        cls.main_thread.start()
        deadline = time.time() + 3
        while cls.server is None and time.time() < deadline:
            time.sleep(.01)
        if cls.server is None:
            raise RuntimeError('Viewer did not start')
        cls.token = (cls.state / 'token').read_text().strip()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.main_thread.join(1)
        sys.argv = cls.original_argv
        cls.display_patch.stop()
        cls.server_patch.stop()
        cls.directory.cleanup()

    def request(self, method, path, body=None, headers=None):
        status, data, _ = self.request_with_headers(method, path, body, headers)
        return status, json.loads(data) if data else None

    def request_with_headers(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        data = response.read()
        response_headers = {key.lower(): value for key, value in response.getheaders()}
        connection.close()
        return response.status, data, response_headers

    def private_headers(self, csrf=False, key=None):
        headers = {'Authorization': 'Bearer ' + self.token}
        if csrf:
            _, response = self.request('GET', '/csrf', headers=headers)
            headers.update({'Origin': PUBLIC_ORIGIN, 'X-Viewer-CSRF': response['token'],
                            'Content-Type': 'application/json', 'Idempotency-Key': key})
        return headers

    def test_rejects_unauthenticated_and_malformed_posts(self):
        status, _ = self.request('POST', '/messages', b'{}', {'Content-Type': 'application/json'})
        self.assertEqual(status, 403)
        status, body = self.request('POST', '/messages', b'[]', self.private_headers(True, 'malformed-0001'))
        self.assertEqual(status, 400)
        self.assertEqual(body['error'], 'Expected a JSON object.')

    def test_paste_status_is_authenticated_read_only_and_reports_fixed_schema(self):
        path = self.state / 'run-status.json'
        path.write_text(json.dumps({'status': 'running', 'phase': 'capture',
            'currentPad': 'FID2', 'completedPads': 1, 'totalPads': 3,
            'message': '<unsafe>', 'updatedAt': '2026-10-01T20:00:00Z',
            'extra': 'ignored'}))
        with mock.patch.object(live_viewer, 'PASTE_STATUS_PATH', path):
            status, body = self.request('GET', '/paste-status')
            self.assertEqual(status, 403)
            status, data, headers = self.request_with_headers(
                'GET', '/paste-status', headers=self.private_headers())
        self.assertEqual(status, 200)
        self.assertEqual(headers['cache-control'], 'no-store')
        self.assertEqual(json.loads(data), {
            'status': 'running', 'phase': 'capture', 'currentPad': 'FID2',
            'completedPads': 1, 'totalPads': 3, 'message': '<unsafe>',
            'updatedAt': '2026-10-01T20:00:00Z'})
        self.assertNotIn('extra', body or {})
        self.assertIn("el('message').textContent=s.message||''", live_viewer.PAGE.decode())

    def test_dispatches_once_and_reports_success(self):
        with mock.patch.object(live_viewer.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            headers = self.private_headers(True, 'duplicate-0001')
            status, body = self.request('POST', '/messages', json.dumps({'message': 'Check feeder.'}), headers)
            self.assertEqual((status, body['status']), (201, 'delivered'))
            status, duplicate = self.request('POST', '/messages', json.dumps({'message': 'Check feeder.'}), headers)
            self.assertEqual((status, duplicate['status']), (200, 'delivered'))
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][:4], ['codex', 'queue', '--thread', '01a0cfa4-7e41-77c0-a7be-1c22a2da8908'])

    def test_https_public_origin_is_exact_and_mismatch_never_dispatches(self):
        with mock.patch.object(live_viewer.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            headers = self.private_headers(True, 'origin-mismatch-0001')
            headers['Origin'] = 'https://attacker.example'
            status, body = self.request('POST', '/messages', json.dumps({'message': 'Must not dispatch.'}), headers)
            self.assertEqual(status, 403)
            self.assertEqual(body['error'], 'Access denied.')
            run.assert_not_called()

            headers = self.private_headers(True, 'origin-exact-0001')
            status, body = self.request('POST', '/messages', json.dumps({'message': 'HTTPS origin accepted.'}), headers)
            self.assertEqual((status, body['status']), (201, 'delivered'))
            run.assert_called_once()

    def test_https_inspection_cookie_is_secure(self):
        status, body, headers = self.request_with_headers(
            'POST', '/inspection/session', b'',
            {'Authorization': 'Bearer ' + self.token, 'Origin': PUBLIC_ORIGIN, 'Content-Length': '0'})
        self.assertEqual((status, body), (204, b''))
        cookie = headers['set-cookie']
        self.assertIn('HttpOnly', cookie)
        self.assertIn('SameSite=Strict', cookie)
        self.assertIn('Secure', cookie)

    def test_public_origin_validation_and_lan_default(self):
        self.assertEqual(live_viewer.validate_public_origin(PUBLIC_ORIGIN), PUBLIC_ORIGIN)
        self.assertIsNone(live_viewer.validate_public_origin(None))
        self.assertEqual(live_viewer.expected_request_origin(None, '192.0.2.4:8765'), 'http://192.0.2.4:8765')
        for invalid in ('ftp://viewer.example', 'https://viewer.example/path',
                        'https://user@viewer.example', 'https://viewer.example?x=1',
                        'https://viewer.example#section', 'https://viewer.example:bad'):
            with self.subTest(invalid=invalid), self.assertRaises(argparse.ArgumentTypeError):
                live_viewer.validate_public_origin(invalid)

    def test_reports_failed_and_uncertain_dispatches(self):
        with mock.patch.object(live_viewer.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)):
            status, body = self.request('POST', '/messages', json.dumps({'message': 'Fail once.'}), self.private_headers(True, 'failed-0001'))
            self.assertEqual((status, body['status']), (201, 'failed'))
        with mock.patch.object(live_viewer.subprocess, 'run', side_effect=subprocess.TimeoutExpired('codex', 20)):
            status, body = self.request('POST', '/messages', json.dumps({'message': 'Was it queued?'}), self.private_headers(True, 'unknown-0001'))
            self.assertEqual((status, body['status']), (201, 'unknown'))

    def test_accepts_four_thousand_unicode_characters(self):
        message = '🟢' * 4_000
        payload = json.dumps({'message': message}, ensure_ascii=False).encode()
        with mock.patch.object(live_viewer.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)):
            status, body = self.request('POST', '/messages', payload, self.private_headers(True, 'unicode-0001'))
        self.assertEqual((status, body['status']), (201, 'delivered'))


if __name__ == '__main__':
    unittest.main()
