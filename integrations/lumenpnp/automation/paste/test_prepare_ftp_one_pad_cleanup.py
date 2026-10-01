import importlib.util,json,tempfile,time,unittest
from datetime import datetime,timezone
from pathlib import Path
S=Path(__file__).with_name('prepare-ftp-one-pad-cleanup.py');spec=importlib.util.spec_from_file_location('one_pad_cleanup',S);M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
class OnePadCleanupTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.now=int(time.time()*1000)
  self.reg=self.root/'registration.json';self.reg.write_text(json.dumps({'resistorPadMachineXYTargets':[{'padId':'R1.1','machineXYMm':[25.0,-2.0]},{'padId':'R40.1','machineXYMm':[30.0,10.0]}]}))
  self.reg_ev=M.evidence(self.reg);self.ev={'path':str(self.reg),'sha256':self.reg_ev['sha256']}
  self.target={'scope':'ftp-one-pad-cleanup-targets','registrationEvidence':self.ev,'surfaceEvidence':self.ev,'surface':{'rawZ':58.3,'estimatedGapMm':.4,'gapUncertaintyMm':.3},'cameraMinusTipXYMm':[5.0,2.0],
   'cleanupSequence':{'schema':1,'protocol':'positive-B-aspiration-lift-one-pad','retractDegrees':6,'dwellMilliseconds':500},
   'pads':[{'padId':'R1.1','rawPose':{'X':20.0,'Y':-4.0,'Z':58.3,'A':720}}]}
  self.raw={'X':0.0,'Y':0.0,'Z':53.4,'A':720,'B':-1000};self.poses={n:{'x':0.0,'y':0.0,'z':53.4,'rotation':720 if n=='N1' else -1800} for n in ('N1','N2')}
 def tearDown(self):self.tmp.cleanup()
 def test_route_bounds_all_linear_moves_and_immediate_positive_lift(self):
  for amount in (6,20):
   self.target['cleanupSequence']['retractDegrees']=amount
   out,stages,bounds,heads,acct=M.build_route(self.raw,self.poses,self.target,53.4);p=out['pads'][0];i=p['aspirationStageIndex'];l=p['liftStageIndex']
   self.assertEqual(stages[i]['axis'],'B');self.assertEqual(stages[i]['target']-self.raw['B'],amount)
   self.assertEqual(stages[i]['dwellMilliseconds'],500);self.assertEqual(stages[l]['axis'],'Z');self.assertEqual(l,i+1);self.assertEqual(l,len(stages)-1)
   self.assertTrue(all(x['axis']!='B' for n,x in enumerate(stages) if n!=i));self.assertEqual(acct['grossChargedDegrees'],amount);self.assertEqual(acct['finalB'],self.raw['B']+amount)
   z=53.4;xy={'X':0.0,'Y':0.0}
   for stage in stages:
    if stage['axis']=='X' or stage['axis']=='Y':self.assertEqual(z,53.4);self.assertLessEqual(abs(stage['target']-xy[stage['axis']]),9.9+1e-9);xy[stage['axis']]=stage['target']
    if stage['axis']=='Z':self.assertLessEqual(abs(stage['target']-z),5.0);z=stage['target']
 def test_target_gate_rejects_compensated_pair_and_noneligible_or_unreviewed_pad(self):
  template={'sessionId':'s','jvmStartMs':1,'liveConfigurationSha256':'a'*64};now=self.now
  t={**self.target,'schema':1,'boardId':'board','sessionId':'s','jvmStartMs':1,'liveConfigurationSha256':'a'*64,'reviewedBy':'reviewer','reviewedMs':now,'boardUnmovedSinceRegistration':True,'provenance':'commissioning-provisional','precisionCalibrated':False,'flowCalibrated':False,'quantizationMm':.01,'cleanupSequence':self.target['cleanupSequence'],'cadEvidence':self.ev,'registrationRevalidationEvidence':self.ev,'tipOffsetEvidence':self.ev,'padChecks':[{'reference':r,'reviewedAligned':True,'reportEvidence':self.ev,'imageEvidence':self.ev} for r in ('R1','R16','R40')],'defectReviewed':True}
  pad={**self.target['pads'][0],'padIdentityReviewed':True,'defectReviewed':True,'defectCapturedMs':now,'defectReportEvidence':self.ev,'defectImageEvidence':self.ev};t['pads']=[pad]
  self.assertEqual(M.validate_target(t,now,template)[0]['padId'],'R1.1')
  for edit in (lambda x:x.update(compensatedSequence={}),lambda x:x['pads'][0].update(padId='R40.2'),lambda x:x['pads'][0].update(defectReviewed=False),lambda x:x['cleanupSequence'].update(dwellMilliseconds=2001),lambda x:x['cleanupSequence'].update(retractDegrees=4)):
   q=json.loads(json.dumps(t));edit(q)
   with self.assertRaises(ValueError):M.validate_target(q,now,template)
 def test_one_stage_approach_and_lift_allow_exact_five_mm(self):
  self.target['surface']['rawZ']=58.4;self.target['pads'][0]['rawPose']['Z']=58.4
  out,stages,*_=M.build_route(self.raw,self.poses,self.target,53.4)
  zs=[(i,s) for i,s in enumerate(stages) if s['axis']=='Z']
  self.assertEqual([s['target'] for _,s in zs],[58.4,53.4])
  self.assertEqual(zs[1][0],out['pads'][0]['liftStageIndex'])
 def test_defect_report_binds_fresh_same_session_top_image(self):
  im=self.root/'top.png';im.write_bytes(b'\x89PNG\r\ntest');finish=datetime.fromtimestamp(self.now/1000,timezone.utc).isoformat().replace('+00:00','Z')
  report=self.root/'report.json';report.write_text(json.dumps({'status':'completed-camera-survey-awaiting-image-review','finishedAt':finish,'controllerPositionVerified':True,'uncertainCompletion':False,'request':{'jvmStartMs':1,'liveConfigurationSha256':'a'*64},'afterImages':{'top':{'path':im.name}}}))
  p={'defectReportEvidence':M.evidence(report),'defectImageEvidence':M.evidence(im),'defectCapturedMs':self.now}
  self.assertEqual(M.validate_defect_observation(p,{'jvmStartMs':1,'liveConfigurationSha256':'a'*64},self.now)['status'],'completed-camera-survey-awaiting-image-review')
  p['defectCapturedMs']-=1
  with self.assertRaises(ValueError):M.validate_defect_observation(p,{'jvmStartMs':1,'liveConfigurationSha256':'a'*64},self.now)
if __name__=='__main__':unittest.main()
