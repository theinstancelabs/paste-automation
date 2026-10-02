import importlib.util,json,os,tempfile,time,unittest
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
SPEC=importlib.util.spec_from_file_location('native_selected_author',Path(__file__).with_name('author-native-selected-ftp-group.py'))
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)
class SelectedNativeGroupTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.now=int(time.time()*1000)
  self.session={'sessionId':'unit-session','jvmStartMs':17,'liveConfigurationSha256':'a'*64,'syringeId':'unit-syringe'}
  self.raw={'X':300.0,'Y':210.0,'Z':58.45,'A':200,'B':-3000}
  self.template=self.json('template.json',self.session)
  self.barrier=self.json('barrier.json',{'status':'completed-read-only-position-barrier','controllerPositionVerified':True,'noMotionCommandSubmitted':True,'uncertainCompletion':False,'request':{'jvmStartMs':17},'liveConfigurationSha256':'a'*64,'afterQuerySnapshot':{'raw':self.raw}})
  self.stationary=self.file('stationary.png',b'\x89PNG\r\n\x1a\ntest');self.tip=self.file('tip.png',b'\x89PNG\r\n\x1a\ntest')
  for p in (self.stationary,self.tip):os.utime(p,ns=((self.now-100)*1_000_000,)*2)
  self.registration=self.json('registration.json',{'resistorPadMachineXYTargets':[{'padId':f'R{r}.{s}','machineXYMm':[350+r+s,150+r-s]} for r in (28,27,26) for s in (1,2)]})
  self.target=self.json('target.json',{'schema':1,'scope':'ftp-selected-pads-targets','boardId':'board-unit',**self.session,'quantizationMm':.01,'cadEvidence':{'path':'/cad','sha256':'b'*64}})
  self.profile=self.json('profile.json',{**self.session,'provenance':'commissioning-provisional','precisionCalibrated':False,'flowCalibrated':False,'estimatedGapMm':.65,'gapUncertaintyMm':.2})
  self.offset=self.json('tip-offset.json',{'cameraMinusTipXYMm':[45.4,-64.49]})
  self.previous=self.json('previous.json',{'status':'completed-contiguous-batch-awaiting-observation'})
  self.ledger=self.json('ledger.json',{'status':'verified','sessionId':'unit-session','lastVerifiedB':-3000})
  basis=self.file('basis.png',b'basis')
  self.surface=self.json('surface.json',{'boardId':'board-unit','provenance':'commissioning-provisional','precisionCalibrated':False,'flowCalibrated':False,'jvmStartMs':17,'liveConfigurationSha256':'a'*64,'reviewedBy':'unit reviewer','basisEvidence':M.evidence(basis),'surface':{'rawZ':58.15,'estimatedGapMm':.65,'gapUncertaintyMm':.2}})
  self.experiment=self.json('experiment.json',{'schema':1,'scope':'reviewed-scrap-retraction-coupon','mode':'transfer-preparation','maximumTransferElapsedMilliseconds':15000,'primeDegrees':60,'preWipeReliefDegrees':20,'idleReliefDegrees':40,'conditioningDoseDegrees':20,'conditioningDwellMilliseconds':2000,'doseDegrees':6,'dwellMilliseconds':2000,'retractDegrees':2,'retractDwellMilliseconds':500,'conditioningFinalWipeMm':0,'startRaw':self.raw,'workRawZ':58.45,'clearanceRawZ':53.45,'targetsXY':[{'X':301.5,'Y':210.0},{'X':302.5,'Y':211.0}]})
  self.report_map={}
  for padid in M.selected_pad_ids(['R28','R27','R26'])+list(M.CONTROLS):
   directory=self.root/padid.replace('.','_');directory.mkdir();image=directory/'top.png';image.write_bytes(b'\x89PNG\r\n\x1a\ntop');os.utime(image,ns=((self.now-100)*1_000_000,)*2)
   report=directory/'report.json';report.write_text(json.dumps({'status':'completed-camera-survey-awaiting-image-review','controllerPositionVerified':True,'uncertainCompletion':False,'finishedAt':datetime.fromtimestamp(self.now/1000,timezone.utc).isoformat().replace('+00:00','Z'),'request':{'jvmStartMs':17,'liveConfigurationSha256':'a'*64},'afterImages':{'top':{'path':'top.png'}}}))
   self.report_map[padid]=str(report)
  self.reports=self.json('reports.json',self.report_map)
 def tearDown(self):self.tmp.cleanup()
 def file(self,name,data):p=self.root/name;p.write_bytes(data);return p
 def json(self,name,data):p=self.root/name;p.write_text(json.dumps(data));return p
 def args(self,**edits):
  data=dict(output=str(self.root/'out'),template=str(self.template),barrier=str(self.barrier),stationary_image=str(self.stationary),tip_image=str(self.tip),registration=str(self.registration),target_base=str(self.target),profile_base=str(self.profile),tip_offset=str(self.offset),previous_report=str(self.previous),ledger=str(self.ledger),scrap_experiment=str(self.experiment),surface=str(self.surface),reports=str(self.reports),registration_revalidation=None,refs='R28,R27,R26',prime_x=300.0,prime_y=210.0,dummy_x=302.5,dummy_y=211.0,reviewer='reviewer',review='Reviewed all selected and control pad images, the clean board, shared provisional surface, and reviewed route clearance evidence.',reviewed_pad=M.selected_pad_ids(['R28','R27','R26']),surface_reviewed_pad=M.selected_pad_ids(['R28','R27','R26']),reviewed_control=list(M.CONTROLS))
  data.update({flag:True for flag in M.ATTESTATION_FLAGS.values()});data.update(edits);return SimpleNamespace(**data)
 def test_six_pads_uses_checked_conditioning_prefix_and_stays_at_238_gross(self):
  result=M.build_inputs(self.args(),self.now)
  self.assertEqual(result['budget'],{'conditioningGrossDegrees':102,'selectedPadsGrossDegrees':96,'idleReliefGrossDegrees':40,'grossDegrees':238})
  self.assertLessEqual(result['prefixStages'],96)
  doc=json.loads(result['input'].read_text());self.assertEqual(len(doc['selectedPads']),6)
  self.assertEqual(doc['xyClearanceRawZ'],53.45);self.assertEqual(doc['conditioningRawZRange'],[53.45,58.45])
  self.assertEqual(set(doc['sources']),{'template','barrier','stationaryImage','tipImage','registration','targetBase','profileBase','tipOffset','previousReport','ledger','scrapExperiment'})
 def test_explicit_short_dose_and_r6_are_bound_through_prefix_and_budget(self):
  selected=M.selected_pad_ids(['R28','R27'])
  args=self.args(dose_degrees=4,retract_degrees=6,dwell_milliseconds=200,refs='R28,R27',reviewed_pad=selected,surface_reviewed_pad=selected)
  result=M.build_inputs(args,self.now);doc=json.loads(result['input'].read_text())
  self.assertEqual((doc['doseDegrees'],doc['retractDegrees'],doc['dwellMilliseconds']),(4,6,200))
  self.assertEqual(result['budget']['conditioningGrossDegrees'],106)
  self.assertEqual(result['budget']['selectedPadsGrossDegrees'],64)
  self.assertEqual(result['budget']['grossDegrees'],210)
  self.assertEqual(doc['startRaw'],self.raw)
  experiment=dict(json.loads(self.experiment.read_text()),retractDegrees=doc['retractDegrees'])
  _,prefix,_,_=M.conditioning_prefix(experiment,self.raw,self.profile and json.loads(self.profile.read_text()),M.evidence(self.stationary),300.0,210.0,302.5,211.0)
  at=self.raw['B'];b_deltas=[]
  for stage in prefix:
   if stage['axis']=='B':b_deltas.append(stage['target']-at);at=stage['target']
  self.assertIn(6,b_deltas)
  self.assertEqual(experiment['retractDegrees'],6)
  with self.assertRaisesRegex(ValueError,'240-degree'):
   M.build_inputs(self.args(output=str(self.root/'over-cap'),dose_degrees=4,retract_degrees=6,dwell_milliseconds=200),self.now)
 def test_one_second_per_pad_dwell_is_accepted_and_hash_bound(self):
  selected=M.selected_pad_ids(['R28'])
  result=M.build_inputs(self.args(refs='R28',reviewed_pad=selected,surface_reviewed_pad=selected,
    dose_degrees=4,retract_degrees=6,dwell_milliseconds=1000),self.now)
  doc=json.loads(result['input'].read_text())
  self.assertEqual(doc['dwellMilliseconds'],1000)
 def test_application_restart_proof_is_hash_bound_in_reviewed_sources(self):
  proof=self.json('application-restart-continuity.json',{'sessionId':'unit-session','liveConfigurationSha256':'a'*64,'transitions':[{'oldJvmStartMs':16,'newJvmStartMs':17}]})
  doc=M.build_inputs(self.args(application_restart_evidence=str(proof)),self.now)['inputs']
  self.assertEqual(doc['sources']['applicationRestartEvidence'],M.evidence(proof))
 def test_route_budget_matches_existing_selected_pad_math_and_allows_safe_three_pair_recipe(self):
  self.assertEqual(M.route_gross(3,106,dose=2,retract=6),{'conditioningGrossDegrees':106,'selectedPadsGrossDegrees':84,'idleReliefGrossDegrees':40,'grossDegrees':230})
  self.assertEqual(M.route_gross(3,106,dose=4,retract=6)['grossDegrees'],242)
  parser=M.make_parser()
  self.assertEqual(parser.parse_args(['--dose-degrees','6','--retract-degrees','6','--dwell-milliseconds','1000',
   '--output','x','--template','t','--barrier','b','--stationary-image','s','--tip-image','i','--registration','r','--target-base','tb',
   '--profile-base','p','--tip-offset','o','--previous-report','pr','--ledger','l','--scrap-experiment','e','--surface','sf','--reports','rp',
   '--refs','R1','--prime-x','1','--prime-y','2','--dummy-x','3','--dummy-y','4','--reviewer','xx','--review','a'*60]).dwell_milliseconds,1000)
 def test_R3_conditioning6_recipe_budget_and_legacy_defaults(self):
  exp=dict(json.loads(self.experiment.read_text()),retractDegrees=3)
  _,prefix,_,accounting=M.conditioning_prefix(exp,self.raw,json.loads(self.profile.read_text()),M.evidence(self.stationary),300,210,302.5,211,6)
  budget=M.route_gross(1,accounting['grossCommandedDegrees'],dose=6,retract=3)
  self.assertEqual(budget,{'conditioningGrossDegrees':89,'selectedPadsGrossDegrees':24,'idleReliefGrossDegrees':40,'grossDegrees':153})
  self.assertEqual(M.route_gross(1,102,dose=12,retract=2)['grossDegrees'],174)
  parser=M.make_parser()
  self.assertEqual(parser.parse_args(['--conditioning-dose-degrees','6','--retract-degrees','3',
   '--output','x','--template','t','--barrier','b','--stationary-image','s','--tip-image','i','--registration','r','--target-base','tb',
   '--profile-base','p','--tip-offset','o','--previous-report','pr','--ledger','l','--scrap-experiment','e','--surface','sf','--reports','rp',
   '--refs','R1','--prime-x','1','--prime-y','2','--dummy-x','3','--dummy-y','4','--reviewer','xx','--review','a'*60]).conditioning_dose_degrees,6)
  self.assertEqual(M.make_parser().parse_args(['--output','x','--template','t','--barrier','b','--stationary-image','s','--tip-image','i','--registration','r','--target-base','tb',
   '--profile-base','p','--tip-offset','o','--previous-report','pr','--ledger','l','--scrap-experiment','e','--surface','sf','--reports','rp',
   '--refs','R1','--prime-x','1','--prime-y','2','--dummy-x','3','--dummy-y','4','--reviewer','xx','--review','a'*60]).conditioning_dose_degrees,20)
 def test_no_historical_control_fallback_and_report_provenance(self):
  bad=dict(self.report_map);bad.pop('R16.1');self.reports=self.json('reports-missing-control.json',bad)
  with self.assertRaisesRegex(ValueError,'all current controls|all controls'):M.build_inputs(self.args(),self.now)
  self.reports=self.json('reports-restored.json',self.report_map);report=Path(self.report_map['R28.1']);doc=json.loads(report.read_text());doc['request']['jvmStartMs']=18;report.write_text(json.dumps(doc))
  with self.assertRaisesRegex(ValueError,'JVM/configuration'):M.build_inputs(self.args(),self.now)
 def test_explicit_review_flags_and_route_limits_reject_missing_or_extra_authorization(self):
  args=self.args();args.board_cleaned_reviewed=False
  with self.assertRaisesRegex(ValueError,'boardCleaned'):M.explicit_attestations(args)
  self.assertEqual(M.route_gross(3,102)['grossDegrees'],238)
  with self.assertRaisesRegex(ValueError,'one to three'):M.route_gross(4,102)
  args=self.args(reviewed_pad=['R28.1'])
  with self.assertRaisesRegex(ValueError,'each selected pad'):M.build_inputs(args,self.now)
if __name__=='__main__':unittest.main()
