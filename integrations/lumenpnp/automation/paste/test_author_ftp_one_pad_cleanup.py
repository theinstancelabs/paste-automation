import copy,importlib.util,json,tempfile,time,unittest
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
s=Path(__file__).with_name('author-ftp-one-pad-cleanup.py');spec=importlib.util.spec_from_file_location('cleanup_author',s);M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
class CleanupAuthorTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  def write(n,v):
   p=self.root/n;p.write_bytes(v if isinstance(v,bytes) else json.dumps(v).encode());return M.C.evidence(p)
  self.write=write;session=dict(sessionId='test',jvmStartMs=1,liveConfigurationSha256='a'*64);raw=dict(X=10,Y=20,Z=53.45,A=720,B=-3000)
  src={k:write(k+'.json',{}) for k in M.SOURCES};im=write('top.png',b'\x89PNG\r\n\x1a\ntest');now=int(time.time()*1000)
  src.update(template=write('template.json',session),barrier=write('barrier.json',{'afterQuerySnapshot':{'raw':raw}}),stationaryImage=im,tipImage=im,defectImage=im,registration=write('registration.json',{'resistorPadMachineXYTargets':[{'padId':'R16.2','machineXYMm':[100,200]}]}),surface=write('surface.json',{'surface':{'rawZ':58.4,'estimatedGapMm':.45,'gapUncertaintyMm':.3}}),tipOffset=write('offset.json',{'cameraMinusTipXYMm':[45.4,-64.49]}),profileBase=write('profile.json',session))
  src['defectReport']=write('report.json',{'status':'completed-camera-survey-awaiting-image-review','finishedAt':datetime.fromtimestamp(now/1000,timezone.utc).isoformat(),'controllerPositionVerified':True,'uncertainCompletion':False,'request':session,'afterImages':{'top':{'path':'top.png'}}})
  src['targetBase']=write('target.json',{'boardId':'FTP','cadEvidence':src['registration'],'padChecks':[{'reference':r,'reviewedAligned':True,'reportEvidence':src['defectReport'],'imageEvidence':im} for r in ('R1','R16','R40')],'inlineConditioning':{},'compensatedSequence':{}})
  self.q=dict(schema=1,scope='reviewed-one-pad-cleanup-authoring-inputs',reviewedBy='synthetic reviewer',reviewedMs=now,reviewBasis='Synthetic explicit full clearance and defect review',profileBasis='Synthetic above-board surface profile review',startRaw=raw,xyClearanceRawZ=53.45,padId='R16.2',retractDegrees=20,dwellMilliseconds=2000,defectCapturedMs=now,attestations={k:True for k in M.ATTESTATIONS},sources=src)
 def tearDown(self):self.tmp.cleanup()
 def load(self,e,j=True):return json.loads(Path(e['path']).read_bytes()) if j else Path(e['path']).read_bytes()
 def test_explicit_identity_positive_amount_and_review_preserved(self):
  before=copy.deepcopy(self.q);r,p,t=M.derive(self.q,self.load,self.q['reviewedMs'])
  self.assertEqual(before,self.q);self.assertEqual(t['reviewedMs'],self.q['reviewedMs']);self.assertEqual(t['pads'][0]['rawPose'],dict(X=54.6,Y=264.49,Z=58.4,A=720));self.assertEqual(t['cleanupSequence']['retractDegrees'],20)
  self.assertNotIn('inlineConditioning',t);self.assertNotIn('compensatedSequence',t);self.assertEqual(r['rawZRange'],[53.45,58.4]);self.assertAlmostEqual(p['estimatedGapMm'],5.4)
 def test_explicit100_selects_distinct_five_stage_protocol(self):
  self.q['retractDegrees']=100
  _,_,t=M.derive(self.q,self.load,self.q['reviewedMs'])
  self.assertEqual(t['cleanupSequence']['protocol'],'positive-B-aspiration-series-lift-one-pad');self.assertEqual(t['cleanupSequence']['retractDegrees'],100)
  for bad in (True,100.0,80,120,-100):
   self.q['retractDegrees']=bad
   with self.assertRaises(ValueError):M.derive(self.q,self.load,self.q['reviewedMs'])
 def test_missing_review_wrong_start_stale_defect_negative_amount_fail(self):
  for edit in [lambda q:q['attestations'].update(defectReviewed=False),lambda q:q.update(reviewedMs=q['reviewedMs']-300001),lambda q:q['startRaw'].update(B=-999),lambda q:q.update(defectCapturedMs=q['defectCapturedMs']-1),lambda q:q.update(retractDegrees=-20),lambda q:q.update(padId='R16.1')]:
   q=copy.deepcopy(self.q);edit(q)
   with self.assertRaises(ValueError):M.derive(q,self.load,self.q['reviewedMs'])
 def test_disabled_preparer_exclusive_output_and_input_hashes(self):
  ip=self.root/'inputs.json';ip.write_text(json.dumps(self.q));out=self.root/'out';calls=[]
  def run(cmd,**kwargs):calls.append(cmd);return SimpleNamespace(stdout='{"enabled":false}')
  with patch.object(M.subprocess,'run',side_effect=run):M.build(ip,out)
  self.assertEqual(Path(calls[0][1]).name,'prepare-ftp-one-pad-cleanup.py');self.assertNotIn('--execute',calls[0]);self.assertEqual(json.loads((out/'targets.json').read_text())['pads'][0]['defectCapturedMs'],self.q['defectCapturedMs'])
  with self.assertRaises(FileExistsError):M.build(ip,out)
  Path(self.q['sources']['surface']['path']).write_text('{}')
  with self.assertRaises(ValueError):M.build(ip,self.root/'changed')
if __name__=='__main__':unittest.main()
