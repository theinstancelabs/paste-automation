import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]/'paste'
spec = importlib.util.spec_from_file_location('route', SCRIPTS/'run-survey-route.py')
route = importlib.util.module_from_spec(spec); spec.loader.exec_module(route)
NOW = 1790000000000

class RouteTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        for p in ['automation/plans','automation/evidence','.local-machine-backups']:(self.root/p).mkdir(parents=True)
        self.raw={'X':10,'Y':20,'Z':26.5,'A':200,'B':720}
        self.poses={k:{'x':1,'y':2,'z':3,'rotation':4} for k in ('N1','N2','top','bottom')}
        self.source=self.root/'source.json';self.image=self.root/'corridor.png'
        self.image.write_bytes(b'\x89PNG\r\n\x1a\nsynthetic');os.utime(self.image,ns=((NOW-1000)*1000000,)*2)
        q={'id':'12345678-1234-1234-1234-123456789abc','scope':'read-only-native-position-barrier','jvmStartMs':NOW-10000,'liveConfigurationSha256':'a'*64}
        self.source.write_text(json.dumps({'schema':1,'id':q['id'],'request':q,'status':'completed-read-only-position-barrier','noMotionCommandSubmitted':True,'controllerPositionVerified':True,'uncertainCompletion':False,'liveConfigurationSha256':'a'*64,'reported':self.raw,'afterQuerySnapshot':{'raw':self.raw,'driver':self.raw,'nativePoses':self.poses}}))
        self.spec={'schema':1,'scope':'reviewed-constant-Z-XY-survey-route','id':'22345678-1234-1234-1234-123456789abc','sourceReport':str(self.source),'sourceSha256':route.digest(self.source.read_bytes()),'operator':'test','reviewedEntireCorridor':True,'corridorEvidence':{'path':str(self.image),'sha256':route.digest(self.image.read_bytes()),'capturedMs':NOW-1000},'waypoints':[{'axis':'X','targetMm':25},{'axis':'Y','targetMm':15}]}
        self.calls=[]
    def dispatch(self,root):
        q=json.loads((root/'automation/plans/paste-survey-request.json').read_text());self.calls.append(q)
        raw=dict(q['expectedRaw']);raw[q['axis']]+=q['deltaMm']
        r={'schema':1,'id':q['id'],'request':q,'status':route.prepare.SUCCESS,'motionSubmitted':True,'nativeMotionCompletionReported':True,'controllerPositionVerified':True,'independentFirmwareStepVerified':True,'uncertainCompletion':False,'after':{'reported':raw},'afterQuerySnapshot':{'raw':raw,'driver':raw,'nativePoses':q['expectedNativePoses']}}
        p=root/'automation/evidence'/('paste-survey-'+q['id']);p.mkdir();(p/'report.json').write_text(json.dumps(r));return 'synthetic only'
    def run_route(self,dispatch=None,wait=route.await_terminal):
        return route.execute(self.spec,self.root,dispatch or self.dispatch,wait,lambda:NOW)
    def test_preview_and_split_bounds_order(self):
        p=route.plan(self.spec,NOW);self.assertFalse(p['dispatchPerformed']);self.assertEqual(len(p['steps']),3);self.assertEqual(self.calls,[])
        for step in p['steps']:
            self.assertLessEqual(abs(step['after'][step['axis']]-step['before'][step['axis']]),10)
            for k in 'ZAB':self.assertEqual(step['before'][k],step['after'][k])
        self.assertEqual(p['steps'][-1]['after'],{**self.raw,'X':25,'Y':15})
    def test_success_chains_terminal_state_and_same_image_without_replay(self):
        r=self.run_route();self.assertEqual(r['status'],'completed-route-awaiting-image-review');self.assertEqual(len(self.calls),3)
        self.assertEqual(self.calls[1]['expectedRaw']['X'],17.5)
        self.assertTrue(all(q['corridorEvidence']==self.spec['corridorEvidence'] for q in self.calls))
        with self.assertRaises(FileExistsError):self.run_route()
        self.assertEqual(len(self.calls),3)
    def test_dispatch_failure_even_with_success_report_never_advances(self):
        def fail(root):self.dispatch(root);raise subprocess.CalledProcessError(1,['synthetic'])
        with self.assertRaises(subprocess.CalledProcessError):self.run_route(fail)
        self.assertEqual(len(self.calls),1)
    def test_terminal_timeout_unknown_uuid_or_changed_state_stops(self):
        def fail_wait(*args):raise TimeoutError('synthetic timeout')
        with self.assertRaises(TimeoutError):self.run_route(wait=fail_wait)
        self.assertEqual(len(self.calls),1)
    def test_wrong_terminal_identity_stops_after_one_dispatch(self):
        def wrong(path, deadline, now):
            value=json.loads(path.read_bytes());value['id']='00000000-0000-0000-0000-000000000000';return json.dumps(value).encode()
        with self.assertRaises(ValueError):self.run_route(wait=wrong)
        self.assertEqual(len(self.calls),1)
    def test_image_expiry_between_steps_prevents_next_dispatch(self):
        clock=[NOW]
        def finish_then_expire(path, deadline, now):
            value=path.read_bytes();clock[0]=NOW+300001;return value
        with self.assertRaises(TimeoutError):route.execute(self.spec,self.root,self.dispatch,finish_then_expire,lambda:clock[0])
        self.assertEqual(len(self.calls),1)
    def test_failed_claim_cannot_replay(self):
        def fail(root):raise RuntimeError('synthetic dispatch failure')
        with self.assertRaises(RuntimeError):self.run_route(fail)
        with self.assertRaises(FileExistsError):self.run_route()
        self.assertEqual(self.calls,[])
    def test_bad_terminal_status_and_axis_drift(self):
        p=route.plan(self.spec,NOW);source=json.loads(self.source.read_text())
        for key,value in [('Z',26.501),('B',0),('X',99)]:
            bad=json.loads(json.dumps(source));bad['afterQuerySnapshot']['raw'][key]=value
            with self.assertRaises(ValueError):route.verify_state(bad,p,self.raw)
        bad=json.loads(json.dumps(source));bad['request']['jvmStartMs']+=1
        with self.assertRaises(ValueError):route.verify_state(bad,p,self.raw)
        bad=json.loads(json.dumps(source));bad['liveConfigurationSha256']='c'*64
        with self.assertRaises(ValueError):route.verify_state(bad,p,self.raw)
    def test_bad_geometry_limits_hash_or_stale_image(self):
        for points in [[{'axis':'XY','targetMm':12}],[{'axis':'Z','targetMm':1}],[{'axis':'X','targetMm':10}],[{'axis':'X','targetMm':251}],[{'axis':'X','targetMm':11 if i%2==0 else 10} for i in range(33)]]:
            with self.assertRaises(ValueError):route.plan({**self.spec,'waypoints':points},NOW)
        with self.assertRaises(ValueError):route.plan({**self.spec,'sourceSha256':'b'*64},NOW)
        with self.assertRaises(ValueError):route.plan(self.spec,NOW+300001)
    def test_unknown_existing_request_is_preserved(self):
        p=self.root/'automation/plans/paste-survey-request.json';p.write_text('{"id":"unknown"}')
        with self.assertRaises(ValueError):self.run_route()
        self.assertEqual(p.read_text(),'{"id":"unknown"}');self.assertEqual(self.calls,[])

if __name__=='__main__':unittest.main()
