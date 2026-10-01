import importlib.util
import json
import tempfile
import stat
from unittest.mock import patch
import unittest
from pathlib import Path
from types import SimpleNamespace

p = Path(__file__).with_name('run-prepared-contiguous-batch.py')
spec = importlib.util.spec_from_file_location('prepared_runner', p)
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.prepared = self.root / 'prepared'; self.prepared.mkdir()
        (self.root / 'automation/plans').mkdir(parents=True)
        self.q = dict(id='12345678-1234-1234-1234-123456789abc', scope='contiguous-native-ftp-conditioned-eight-pad-preview', enabled=False)
        self.save(); self.calls = []

    def tearDown(self): self.tmp.cleanup()
    def save(self): (self.prepared / 'preview-request.json').write_text(json.dumps(self.q))
    def invoke(self, cmd, **kwargs):
        self.calls.append(cmd)
        if 'finalize' in cmd:
            p = self.root/'automation/evidence'/('paste-contiguous-batch-preview-'+self.q['id'])/'runtime-request.json'
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text(json.dumps({**self.q, 'scope':self.q['scope'].removesuffix('-preview')}))
            return SimpleNamespace(stdout=str(p))
        return SimpleNamespace()

    def terminal(self, path, ident, preview, seconds):
        self.assertEqual(seconds, 300)
        return dict(status='completed-model-only-contiguous-batch-preview' if preview else 'completed-contiguous-batch-awaiting-observation')

    def test_preview_single_dispatch_then_observe_same_id_without_replay(self):
        a = M.run(self.prepared, True, self.root, self.invoke, self.terminal)
        b = M.run(self.prepared, True, self.root, self.invoke, self.terminal)
        self.assertEqual(len(self.calls), 1); self.assertTrue(a['dispatchedThisInvocation']); self.assertFalse(b['dispatchedThisInvocation'])
        self.assertIn(self.q['id'], json.loads((self.prepared/'runner-preview-attempt.json').read_text())['report'])

    def test_receipt_file_and_directory_are_synced_before_dispatch(self):
        synced=[];real=M.os.fsync
        def fsync(fd):
            synced.append(stat.S_ISDIR(M.os.fstat(fd).st_mode));real(fd)
        def invoke(cmd,**kwargs):
            self.assertEqual(synced,[False,True]);return self.invoke(cmd,**kwargs)
        with patch.object(M.os,'fsync',side_effect=fsync):
            M.run(self.prepared,True,self.root,invoke,self.terminal)
        self.assertEqual(len(self.calls),1)

    def test_legacy_same_id_report_without_receipt_never_dispatches(self):
        for preview in (True,False):
            action='paste-contiguous-batch-preview' if preview else 'paste-contiguous-batch'
            report=self.root/'automation/evidence'/(action+'-'+self.q['id'])/'report.json'
            report.parent.mkdir(parents=True,exist_ok=True)
            report.write_text(json.dumps(dict(id=self.q['id'],status='completed-model-only-contiguous-batch-preview' if preview else 'completed-contiguous-batch-awaiting-observation',noControllerAccess=True,noMotion=True,controllerPositionVerified=True,uncertainCompletion=False)))
            result=M.run(self.prepared,preview,self.root,self.invoke)
            self.assertTrue(result['existingIdObserved']);self.assertFalse(result['dispatchedThisInvocation'])
            self.assertFalse((self.prepared/('runner-'+('preview' if preview else 'execute')+'-attempt.json')).exists())
        self.assertEqual(self.calls,[])

    def test_timeout_or_bridge_failure_cannot_redispatch(self):
        def timeout(*args): raise TimeoutError('uncertain')
        with self.assertRaises(TimeoutError): M.run(self.prepared, True, self.root, self.invoke, timeout)
        M.run(self.prepared, True, self.root, self.invoke, self.terminal)
        self.assertEqual(len(self.calls), 1)
        self.q['id']='22345678-1234-1234-1234-123456789abc';self.save()
        with self.assertRaises(ValueError):M.run(self.prepared, True, self.root, self.invoke, self.terminal)
        self.assertEqual(len(self.calls), 1)

    def test_execute_finalizes_before_one_dispatch_and_preserves_request(self):
        original=(self.prepared/'preview-request.json').read_bytes()
        M.run(self.prepared, False, self.root, self.invoke, self.terminal)
        self.assertEqual(len(self.calls),2);self.assertIn('finalize',self.calls[0]);self.assertIn('paste-contiguous-batch',self.calls[1])
        self.assertEqual(original,(self.prepared/'preview-request.json').read_bytes())
        M.run(self.prepared, False, self.root, self.invoke, self.terminal);self.assertEqual(len(self.calls),2)

    def test_uncertain_bridge_exception_retains_receipt_and_never_resubmits(self):
        def fail(cmd, **kwargs):
            self.calls.append(cmd)
            raise M.subprocess.CalledProcessError(1,cmd)
        with self.assertRaises(M.subprocess.CalledProcessError):M.run(self.prepared,True,self.root,fail,self.terminal)
        M.run(self.prepared,True,self.root,self.invoke,self.terminal)
        self.assertEqual(len(self.calls),1)

    def test_finalize_failure_does_not_dispatch_or_install_plan(self):
        def fail(cmd, **kwargs):
            self.calls.append(cmd)
            raise M.subprocess.CalledProcessError(1,cmd,stderr='exact preview mismatch')
        with self.assertRaisesRegex(ValueError,'exact preview mismatch'):M.run(self.prepared,False,self.root,fail,self.terminal)
        self.assertEqual(len(self.calls),1)
        self.assertFalse((self.root/'automation/plans/paste-contiguous-batch-request.json').exists())

    def test_real_poll_ignores_partial_json_and_rejects_uncertain_or_other_id(self):
        report=self.root/'report.json';clock=[0];report.write_text('{')
        def now():return clock[0]
        def sleep(_):
            clock[0]+=1
            report.write_text(json.dumps(dict(id=self.q['id'],status='completed-contiguous-batch-awaiting-observation',controllerPositionVerified=True,uncertainCompletion=False)))
        M.wait_report(report,self.q['id'],False,60,now,sleep)
        for update in ({'id':'other'}, {'uncertainCompletion':True}, {'status':'stopped-contiguous-batch-no-retry'}):
            r=json.loads(report.read_text());r.update(update);report.write_text(json.dumps(r))
            with self.assertRaises(RuntimeError):M.wait_report(report,self.q['id'],False,60,now,sleep)
            sleep(0)
        report.unlink()
        with self.assertRaises(TimeoutError):M.wait_report(report,self.q['id'],False,0,now,sleep)

    def test_non_group_timeout_is_sixty_and_missing_selection_is_not_implicit(self):
        self.q['scope']='contiguous-native-ftp-conditioned-two-pad-preview';self.save()
        def wait(report,ident,preview,seconds):self.assertEqual(seconds,60);return {'status':'complete'}
        M.run(self.prepared,True,self.root,self.invoke,wait)

    def test_selected_pad_scope_is_allowed_and_observed_for_three_hundred_seconds(self):
        self.q['scope']='contiguous-native-ftp-selected-pads-preview';self.save()
        M.run(self.prepared,True,self.root,self.invoke,self.terminal)
        self.assertEqual(len(self.calls),1)


if __name__ == '__main__':unittest.main()
