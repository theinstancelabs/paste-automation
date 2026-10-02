import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).with_name('job_service.py')
SPEC = importlib.util.spec_from_file_location('paste_job_service', MODULE)
S = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(S)

BOARD = b'''(kicad_pcb (footprint "T:X" (layer "F.Cu") (at 5 8)
  (property "Reference" "U1") (pad "1" smd rect (at 0 0) (size 1 2) (layers "F.Cu" "F.Paste"))))'''


class JobServiceTests(unittest.TestCase):
    def test_upload_plan_is_offline_and_persists_hash_bound_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = []
            service = S.PasteJobService(tmp, invoke=lambda *a, **k: calls.append(a))
            result = service.plan_upload(BOARD, {'filename': 'board.kicad_pcb'})
            self.assertEqual(result['status']['stage'], 'planned')
            self.assertFalse(result['executionAuthorized'])
            self.assertEqual(service.status(result['jobId'])['boardSha256'], result['boardSha256'])
            self.assertFalse(calls)

    def test_prepared_binding_requires_exact_uploaded_board_and_server_evidence_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'repo'; evidence = root / 'automation/evidence'; evidence.mkdir(parents=True)
            svc = S.PasteJobService(Path(tmp) / 'jobs', root=root)
            result = svc.plan_upload(BOARD, {'filename': 'board.kicad_pcb'})
            source = root / 'uploaded-board.kicad_pcb'; source.write_bytes(BOARD)
            prepared = evidence / 'prepared'; prepared.mkdir()
            q = {'id':'a37f652b-955b-4af4-ad61-640c0df5b49d','enabled':False,
                 'sessionId':'session','jvmStartMs':1,'liveConfigurationSha256':'config',
                 'ftpTargetRecord':{'cadEvidence':{'sha256':'wrong','path':str(source)}}}
            (prepared/'preview-request.json').write_text(json.dumps(q))
            with self.assertRaisesRegex(ValueError, 'not bound'):
                svc.bind_prepared(result['jobId'], prepared)
            q['ftpTargetRecord']['cadEvidence']['sha256'] = result['boardSha256']
            (prepared/'preview-request.json').write_text(json.dumps(q))
            bound = svc.bind_prepared(result['jobId'], prepared)
            self.assertEqual(bound['requestId'], q['id'])
            self.assertEqual(svc.status(result['jobId'])['stage'], 'prepared')
            with self.assertRaisesRegex(ValueError, 'server-selected'):
                svc.bind_prepared(result['jobId'], Path(tmp))

    def test_commissioning_descriptor_reports_observe_for_consumed_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'repo'; evidence = root / 'automation/evidence'; evidence.mkdir(parents=True)
            svc = S.PasteJobService(Path(tmp) / 'jobs', root=root)
            result = svc.plan_upload(BOARD, {'filename': 'board.kicad_pcb'})
            source = root / 'uploaded-board.kicad_pcb'; source.write_bytes(BOARD)
            prepared = evidence / 'prepared'; prepared.mkdir()
            q = {'id':'a37f652b-955b-4af4-ad61-640c0df5b49d','enabled':False,
                 'sessionId':'session','jvmStartMs':1,'liveConfigurationSha256':'config',
                 'ftpTargetRecord':{'cadEvidence':{'sha256':result['boardSha256'],'path':str(source)}}}
            (prepared/'preview-request.json').write_text(json.dumps(q))
            reportdir = evidence / ('paste-contiguous-batch-' + q['id']); reportdir.mkdir()
            (reportdir/'top-after-raw.png').write_bytes(b'fixture image bytes')
            (reportdir/'report.json').write_text(json.dumps({'id':q['id'],'status':'completed-contiguous-batch-awaiting-observation',
                'controllerPositionVerified':True,'uncertainCompletion':False,
                'afterImages':{'top':{'path':'top-after-raw.png'},'bottom':{'path':'missing.png'}}}))
            descriptor = svc.commissioning_descriptor(result['jobId'], prepared)
            self.assertEqual(descriptor['action'], 'observe')
            self.assertEqual(descriptor['status']['stage'], 'completed')
            self.assertEqual([p['view'] for p in descriptor['status']['photos']], ['top'])


if __name__ == '__main__':
    unittest.main()
