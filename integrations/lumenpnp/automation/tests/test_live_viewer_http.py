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
import zipfile
from io import BytesIO
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

    def test_r33_repeat_result_and_images_are_authenticated_aliases_without_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            result_dir=Path(tmp)
            observation={'scope':'R33-recipe-four-pad-repeat-observation','status':'visual-candidate-not-qualified',
              'executionSeconds':58.26,'pads':['R19.1','R19.2','R18.1','R18.2'],
              'boardProgress':{'resistorPadsTouched':45,'resistorPadsTotal':80,'priorMixedQualityDepositsRemain':True},
              'physicalAcceptanceEstablished':False}
            (result_dir/'repeat-observation.json').write_text(json.dumps(observation))
            for family,values in [('R19',[.9777,.9770]),('R18',[1.0,.9945])]:
                (result_dir/(family+'-cv-measurements.json')).write_text(json.dumps({'scope':'conventional-before-after-paste-coverage',
                  'pads':[{'brightPadCoverageFraction':v,'equivalentChangedDiameterMm':1.0615+i*.05} for i,v in enumerate(values)]}))
            (result_dir/'after-R19.1.png').write_bytes(b'\x89PNG\r\n\x1a\nR19')
            (result_dir/'after-R18.1.png').write_bytes(b'\x89PNG\r\n\x1a\nR18')
            with mock.patch.object(live_viewer,'R33_RESULT_DIR',result_dir):
                status, _ = self.request('GET', '/paste-results/latest')
                self.assertEqual(status, 403)
                status, payload = self.request('GET', '/paste-results/latest', headers=self.private_headers())
                self.assertEqual(status, 200)
                image_status, data, headers = self.request_with_headers('GET', payload['imageUrls']['R19.1'], headers=self.private_headers())
        self.assertEqual(status, 200)
        self.assertEqual(payload['padIds'], ['R19.1', 'R19.2', 'R18.1', 'R18.2'])
        self.assertEqual(payload['boardProgress'], {'touched': 45, 'total': 80, 'priorMixedQualityDepositsRemain': True})
        self.assertFalse(payload['physicalAcceptanceEstablished'])
        self.assertEqual(payload['coveragePercentRange'], [97.7, 100.0])
        self.assertEqual(payload['equivalentChangedDiameterMmRange'], [1.06, 1.11])
        encoded=json.dumps(payload)
        self.assertNotIn('/home/', encoded)
        self.assertEqual(image_status, 200)
        self.assertEqual(headers['content-type'], 'image/png')
        self.assertTrue(data.startswith(b'\x89PNG'))
        self.assertIn('loadR33Result', live_viewer.PAGE.decode())

    def test_existing_r33_job_status_is_authenticated_read_only_descriptor(self):
        descriptor={'jobId':'a'*64,'preparedId':'b'*64,'action':'observe','stage':'completed',
          'boardSha256':'c'*64,'executionAuthorized':False,'reportStatus':'completed-contiguous-batch-awaiting-observation',
          'controllerPositionVerified':True,'uncertainCompletion':False,'nativePreviewPassed':True,
          'photos':[{'view':'top','name':'top-after-raw.png'}],
          'detail':'Read-only descriptor; no machine action.'}
        with mock.patch.object(live_viewer,'known_r33_service_status',return_value=descriptor):
            status,_=self.request('GET','/paste-jobs/known-r33/status')
            self.assertEqual(status,403)
            status,payload=self.request('GET','/paste-jobs/known-r33/status',headers=self.private_headers())
        self.assertEqual(status,200);self.assertEqual(payload['action'],'observe')
        self.assertFalse(payload['executionAuthorized']);self.assertTrue(payload['controllerPositionVerified'])
        self.assertNotIn('/home/',json.dumps(payload))
        self.assertIn('loadKnownJobStatus',live_viewer.PAGE.decode())

    def test_private_kicad_planner_saves_job_and_svg_without_enabling_execution(self):
        boundary='----viewer-board-test'
        board=b'''(kicad_pcb (version 20240108) (net 0 "")
          (gr_rect (start 0 0) (end 10 5) (layer "Edge.Cuts"))
          (footprint "Test:FP" (layer "F.Cu") (at 2 2)
            (property "Reference" "U1") (property "Value" "test")
            (pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu" "F.Paste") (net 0 "")))
          (footprint "Fiducial:F" (layer "F.Cu") (at 8 3)
            (property "Reference" "FID1") (property "Value" "fid")))'''
        parts=[]
        def part(name,value,filename=None,content_type=None):
            header=f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'
            if filename:header+=f'; filename="{filename}"'
            header+='\r\n'
            if content_type:header+=f'Content-Type: {content_type}\r\n'
            parts.append(header.encode()+b'\r\n'+value+b'\r\n')
        part('board',board,'demo.kicad_pcb','application/octet-stream')
        part('side',b'F.Cu');part('pasteThicknessMm',b'0.1');part('apertureScaling',b'1')
        body=b''.join(parts)+f'--{boundary}--\r\n'.encode()
        headers=self.private_headers(True,'planner-upload-0001')
        headers['Content-Type']='multipart/form-data; boundary='+boundary
        status,result=self.request('POST','/paste-jobs/plan',body,headers)
        self.assertEqual(status,201)
        self.assertEqual((result['fileName'],result['padCount'],result['footprintCount'],result['fiducialCount']),('demo.kicad_pcb',1,2,1))
        self.assertFalse(result['executionAuthorized'])
        self.assertTrue(result['jobUrl'].endswith(result['jobId']))
        status,job=self.request('GET',result['jobUrl'],headers=self.private_headers())
        self.assertEqual(status,200);self.assertEqual(job['scope'],'offline-kicad-paste-job');self.assertFalse(job['executionAuthorized'])
        status,readiness=self.request('GET',result['readinessUrl'],headers=self.private_headers())
        self.assertEqual(status,200);self.assertFalse(readiness['executionAuthorized'])
        self.assertEqual([stage['id'] for stage in readiness['stages']],['cad-plan','geometry-review','flow-calibration','board-registration','machine-session','native-openpnp-job'])
        flow=next(stage for stage in readiness['stages'] if stage['id']=='flow-calibration')
        self.assertEqual(flow['status'],'required');self.assertIn('unverified absent a measured-evidence binding',flow['detail'])
        status,data,headers=self.request_with_headers('GET',result['previewUrl'],headers=self.private_headers())
        self.assertEqual(status,200);self.assertEqual(headers['content-type'],'image/svg+xml; charset=utf-8')
        self.assertIn(b'CAD preview (not registered)',data);self.assertIn(b'FID1',data)
        status,data,headers=self.request_with_headers('GET',result['reviewBundleUrl'],headers=self.private_headers())
        self.assertEqual(status,200);self.assertEqual(headers['content-type'],'application/zip')
        with zipfile.ZipFile(BytesIO(data)) as archive:
            self.assertEqual(set(archive.namelist()),{'job.json','preview.svg','readiness.json','README.txt'})
            self.assertIn(b'not an OpenPnP machine job',archive.read('README.txt'))
        self.assertIn('Start paste — blocked',live_viewer.PAGE.decode())

    def test_kicad_planner_upload_requires_auth_and_rejects_non_board_files(self):
        boundary='----viewer-board-invalid';body=(f'--{boundary}\r\nContent-Disposition: form-data; name="board"; filename="bad.txt"\r\n\r\nhello\r\n--{boundary}--\r\n').encode()
        headers=self.private_headers(True,'planner-invalid-0001');headers['Content-Type']='multipart/form-data; boundary='+boundary
        status,_=self.request('POST','/paste-jobs/plan',body,{'Content-Type':headers['Content-Type']})
        self.assertEqual(status,403)
        status,result=self.request('POST','/paste-jobs/plan',body,headers)
        self.assertEqual(status,400);self.assertIn('.kicad_pcb',result['error'])

    def test_cad_labels_are_escaped_in_svg_preview(self):
        job={'board':{'fileName':'<script>alert(1)</script>.kicad_pcb','side':'F.Cu','boundsMm':[0,0,2,2]},
             'footprints':[{'reference':'<img src=x onerror=alert(1)>','centerMm':[1,1]}],
             'pads':[{'id':'<script>bad</script>','centerMm':[1,1],'sizeMm':[.5,.5],'doseStatus':'needs-calibration'}],
             'fiducials':[{'reference':'<svg onload=alert(1)>','boardXYmm':[1,1]}]}
        preview=live_viewer.render_paste_job_svg(job).decode()
        self.assertNotIn('<script>',preview);self.assertNotIn('<img ',preview);self.assertNotIn('<svg onload',preview)
        self.assertIn('&lt;script&gt;',preview)

    def test_svg_renders_exact_arc_and_marks_unresolved_outline(self):
        job={'board':{'fileName':'arc.kicad_pcb','side':'F.Cu','boundsMm':[0,0,2,2],
                      'outline':[{'type':'gr_arc','geometryStatus':'exact-circular-arc','centerMm':[1,1],
                                  'radiusMm':1,'startAngleDeg':0,'sweepAngleDeg':90}]}}
        svg=live_viewer.render_paste_job_svg(job).decode()
        self.assertIn('<path d="M 860.00 450.00 A 410.00 410.00 0 0 0 450.00 40.00"',svg)
        job['board']['outline'][0]={'type':'gr_arc','geometryStatus':'review-required-degenerate-arc'}
        svg=live_viewer.render_paste_job_svg(job).decode()
        self.assertIn('Outline review required: review-required-degenerate-arc',svg)

    def test_svg_renders_line_candidate_as_dashed_review_overlay(self):
        job={'board':{'fileName':'rows.kicad_pcb','side':'F.Cu','boundsMm':[0,0,4,2]},
          'finePitchGroups':[{'id':'fp-abc','kind':'fine-pitch-row','proposedLine':{'polylineMm':[[1,1],[2,1],[3,1]]}}]}
        svg=live_viewer.render_paste_job_svg(job).decode()
        self.assertIn('stroke="#ff9b4a"',svg)
        self.assertIn('stroke-dasharray="8 6"',svg)
        self.assertIn('individual pad deposits remain the default',svg)
        self.assertIn('Orange dashed lines are geometry candidates only',live_viewer.PAGE.decode())

    def test_paste_status_derives_live_stage_progress_without_exposing_report_path(self):
        with tempfile.TemporaryDirectory() as td:
            repository = Path(td)
            batch_id = '12345678-1234-1234-1234-123456789abc'
            report_dir = repository / 'automation/evidence' / ('paste-contiguous-batch-' + batch_id)
            report_dir.mkdir(parents=True)
            report_path = report_dir / 'report.json'
            report_path.write_text(json.dumps({
                'id': batch_id, 'status': 'running', 'motionSubmitted': True,
                'request': {'previewStages': [{}, {}, {}, {}], 'ftpTargetRecord': {'pads': [
                    {'padId': 'R1.1', 'rawPose': {'X': 10, 'Y': 20}},
                    {'padId': 'R1.2', 'rawPose': {'X': 30, 'Y': 40}},
                ]}},
                'stages': [{'verified': True, 'targetRaw': {'X': 10, 'Y': 20}},
                           {'verified': True, 'targetRaw': {'X': 30, 'Y': 40}},
                           {'verified': False, 'targetRaw': {'X': 10, 'Y': 20}}],
            }))
            status_file = repository / 'run-status.json'
            status_file.write_text(json.dumps({
                'status': 'running', 'phase': 'dispensing', 'currentPad': None,
                'completedPads': 0, 'totalPads': 8, 'message': 'runner active',
                'updatedAt': '2026-10-01T20:00:00Z', 'activeReport': str(report_path),
            }))
            with (mock.patch.object(live_viewer, 'REPOSITORY', repository),
                  mock.patch.object(live_viewer, 'PASTE_EVIDENCE_ROOT', repository / 'automation/evidence'),
                  mock.patch.object(live_viewer, 'PASTE_STATUS_PATH', status_file)):
                status, payload = self.request('GET', '/paste-status', headers=self.private_headers())
                self.assertEqual(status, 200)
                self.assertEqual(payload['currentPad'], 'R1.1')
                self.assertEqual(payload['completedPads'], 0)
                self.assertEqual(payload['totalPads'], 8)
                self.assertEqual(payload['message'], 'Dispensing script: verified stages 2/4; current pad R1.1')
                self.assertNotIn('activeReport', payload)
                self.assertNotIn(str(report_path), json.dumps(payload))

                report = json.loads(report_path.read_text())
                report['stages'] = [{'verified': True} for _ in range(4)]
                for report_status in ('completed-contiguous-air-batch-awaiting-observation',
                                      'completed-contiguous-batch-awaiting-observation'):
                    report['status'] = report_status
                    report_path.write_text(json.dumps(report))
                    status, payload = self.request('GET', '/paste-status', headers=self.private_headers())
                    self.assertEqual(payload['status'], 'completed')
                    self.assertEqual(payload['completedPads'], 0)
                    self.assertIn('awaiting image inspection after completion', payload['message'])

                # An active report outside the one allowed evidence path falls back to static metadata.
                status_file.write_text(json.dumps({
                    'status': 'running', 'phase': 'dispensing', 'currentPad': None,
                    'completedPads': 0, 'totalPads': 8, 'message': 'static fallback',
                    'updatedAt': '2026-10-01T20:00:00Z', 'activeReport': str(repository / 'escape.json'),
                }))
                status, payload = self.request('GET', '/paste-status', headers=self.private_headers())
                self.assertEqual(payload['message'], 'static fallback')
                self.assertIsNone(payload['currentPad'])

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
