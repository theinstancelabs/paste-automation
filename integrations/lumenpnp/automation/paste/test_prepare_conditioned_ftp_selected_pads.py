import importlib.util
import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT=Path(__file__).with_name('prepare-conditioned-ftp-selected-pads.py')
SPEC=importlib.util.spec_from_file_location('prepare_conditioned_ftp_selected_pads',SCRIPT)
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)

class SelectedPadsBuilderTests(unittest.TestCase):
    def test_fractional_comparison_targets_bind_actual_absolute_count_phase(self):
        start=-3773.5
        for percent,steps in ((15,4),(20,5),(25,7),(30,8)):
            requested=6*percent/100
            actual,count=M.fractional_target(start,requested,steps,'positive')
            target=round((start+actual)*100)/100
            self.assertEqual(count,M.controller_steps(target)-M.controller_steps(start))
            self.assertLessEqual(abs(count-requested*4.44),.5)
            self.assertAlmostEqual(count/4.44,steps/4.44)
        # At this B phase 1.5 degrees does not reliably make seven steps if sent raw.
        raw=round((start+1.5)*100)/100
        self.assertNotEqual(M.controller_steps(raw)-M.controller_steps(start),7)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.now=int(time.time()*1000)
        self.session={'sessionId':'test-session','jvmStartMs':1,'liveConfigurationSha256':'a'*64,'syringeId':'test-syringe'}
        self.raw={'X':0.0,'Y':0.0,'Z':58.40,'A':720.0,'B':-1000.0}
        self.image=self.write('review.jpg',b'\xff\xd8\xffreview');os.utime(self.image,ns=(self.now*1_000_000-1_000_000,self.now*1_000_000-1_000_000))
        self.evfile=self.json('basis.json',{'reviewed':True});self.ev=M.ev(self.evfile)
        self.profile=self.json('profile.json',{**self.session,'provenance':'commissioning-provisional','precisionCalibrated':False,'flowCalibrated':False,'rawPose':{k:self.raw[k] for k in 'XYZA'},'estimatedGapMm':.4,'gapUncertaintyMm':.3})
        self.experiment={'schema':1,'scope':'reviewed-scrap-retraction-coupon','mode':'transfer-preparation','maximumTransferElapsedMilliseconds':15000,'conditioningDoseDegrees':12,'conditioningRestoreDegrees':3,'conditioningDwellMilliseconds':2000,'dwellMilliseconds':2000,'retractDegrees':3,'retractDwellMilliseconds':500,'conditioningFinalWipeMm':0,'idleReliefDegrees':20,'preWipeReliefDegrees':20,'primeDegrees':40,'doseDegrees':4,'startRaw':self.raw,'workRawZ':58.4,'clearanceRawZ':53.4,'targetsXY':[{'X':2.0,'Y':0.0},{'X':3.0,'Y':0.0}]}
        self.experiment_file=self.json('experiment.json',self.experiment)
        self.review=self.json('review.json',{'reviewedBy':'reviewer','reviewedMs':self.now,'experimentEvidence':M.ev(self.experiment_file),'imageEvidence':M.ev(self.image),'image':str(self.image)})
        self.profile_data=json.loads(self.profile.read_text());self.profile_data['measurementEvidence']=M.ev(self.review);self.profile=self.json('profile.json',self.profile_data)
        self.registration=self.json('registration.json',{'resistorPadMachineXYTargets':[{'padId':'R3.1','machineXYMm':[10.0,10.0]},{'padId':'R2.2','machineXYMm':[12.0,11.0]}]})
        self.cad=self.json('cad.json',{'ok':True});self.offset=self.json('offset.json',{'ok':True});self.surface1=self.surface('surface-r3.json',58.37);self.surface2=self.surface('surface-r2.json',58.36)
        self.reports=[];self.pads=[]
        for ix,(padid,x,y,z,surf) in enumerate([('R3.1',10.0,10.0,58.37,self.surface1),('R2.2',12.0,11.0,58.36,self.surface2)]):
            folder=self.root/f'pad{ix}';folder.mkdir();img=folder/'top.png';img.write_bytes(b'\x89PNG\r\n\x1a\ntest')
            report=folder/'report.json';report.write_text(json.dumps({'status':'completed-camera-survey-awaiting-image-review','controllerPositionVerified':True,'uncertainCompletion':False,'finishedAt':datetime.fromtimestamp(self.now/1000,timezone.utc).isoformat().replace('+00:00','Z'),'request':{'jvmStartMs':1,'liveConfigurationSha256':'a'*64},'afterImages':{'top':{'path':'top.png'}}}))
            surface={'rawZ':z,'estimatedGapMm':.4,'gapUncertaintyMm':.3}
            self.pads.append({'padId':padid,'rawPose':{'X':x,'Y':y,'Z':z,'A':720.0},'padIdentityReviewed':True,'padAvailableReviewed':True,'availabilityCapturedMs':self.now,'availabilityReportEvidence':M.ev(report),'availabilityImageEvidence':M.ev(img),'surface':surface,'surfaceEvidence':M.ev(surf)})
        self.target={'schema':1,'scope':'ftp-selected-pads-targets','boardId':'ftp-board',**self.session,'reviewedBy':'reviewer','reviewedMs':self.now,'quantizationMm':.01,'boardUnmovedSinceRegistration':True,'boardCleaned':True,'padsAvailable':True,'provenance':'commissioning-provisional','precisionCalibrated':False,'flowCalibrated':False,'surface':self.pads[0]['surface'],'surfaceEvidence':self.pads[0]['surfaceEvidence'],'cadEvidence':M.ev(self.cad),'registrationEvidence':M.ev(self.registration),'tipOffsetEvidence':M.ev(self.offset),'padAvailabilityImage':self.pads[0]['availabilityImageEvidence'],'cameraMinusTipXYMm':[0.0,0.0],'pads':self.pads,'compensatedSequence':{'schema':1,'protocol':'restore-dose-retract-lift-selected-pads','doseDegrees':4,'retractDegrees':3,'dwellMilliseconds':200,'retractDwellMilliseconds':500,'idleReliefDegrees':40}}
        self.target_file=self.json('target.json',self.target)
        self.template=self.json('template.json',self.session)
        self.barrier=self.json('barrier.json',{'status':'completed-read-only-position-barrier','controllerPositionVerified':True,'noMotionCommandSubmitted':True,'uncertainCompletion':False,'finishedAt':datetime.now(timezone.utc).isoformat(),'request':{'jvmStartMs':1},'liveConfigurationSha256':'a'*64,'afterQuerySnapshot':{'raw':self.raw,'nativePoses':{'N1':{'x':0,'y':0,'z':58.4},'N2':{'x':0,'y':0,'z':58.4},'top':{'x':0,'y':0,'z':0},'bottom':{'x':0,'y':0,'z':0}}}})
        self.prev=self.json('previous.json',{'ok':True});self.ledger=self.json('ledger.json',{'ok':True})

    def tearDown(self): self.tmp.cleanup()
    def write(self,name,data): p=self.root/name;p.write_bytes(data);return p
    def json(self,name,data): p=self.root/name;p.write_text(json.dumps(data,indent=2)+'\n');return p
    def surface(self,name,z): return self.json(name,{'boardId':'ftp-board','provenance':'commissioning-provisional','precisionCalibrated':False,'flowCalibrated':False,'reviewedBy':'reviewer','jvmStartMs':1,'liveConfigurationSha256':'a'*64,'surface':{'rawZ':z,'estimatedGapMm':.4,'gapUncertaintyMm':.3},'basisEvidence':self.ev})

    def test_selected_surfaces_route_exact_prefix_gap_and_accounting_offline(self):
        args=SimpleNamespace(template=str(self.template),barrier=str(self.barrier),target_record=str(self.target_file),experiment=str(self.experiment_file),profile=str(self.profile),clearance_review=str(self.review),image=str(self.image),previous_report=str(self.prev),ledger=str(self.ledger),output=str(self.root/'out'),xy_clearance_raw_z=53.4)
        def generic(cmd,**kwargs):
            out=Path(cmd[cmd.index('--output')+1]);out.mkdir(parents=True);(out/'preview-request.json').write_text('{"enabled":false}\n');return SimpleNamespace(stdout='/tmp/preview-request.json')
        with patch.object(M.subprocess,'run',side_effect=generic): M.build(args)
        recipe=json.loads((self.root/'out'/'recipe.json').read_text());target=json.loads((self.root/'out'/'targets.json').read_text())
        prefix,_,condition=M.PREP.stages_for(self.experiment,M.ev(self.review),.4,.3)
        self.assertEqual(recipe['stages'][:len(prefix)],prefix)
        self.assertEqual(target['inlineConditioning']['prefixStageCount'],len(prefix))
        self.assertEqual([p['padId'] for p in target['pads']],['R3.1','R2.2'])
        self.assertEqual(target['pads'][0]['doseStageIndices'],[target['pads'][0]['restoreStageIndex']+1])
        idle=target['compensatedSequence']['finalIdleStageIndices']
        last=recipe['stages'][idle[0]]
        self.assertAlmostEqual(last['estimatedGapMm'],.4+58.36-53.4)
        self.assertEqual(recipe['targetSurface'],'ftp-selected-pads')
        self.assertEqual(recipe['bAccounting']['grossChargedDegrees'],condition['grossCommandedDegrees']+8+12+40)
        self.assertFalse(json.loads((self.root/'out'/'native'/'preview-request.json').read_text()).get('enabled',True))
        self.assertEqual(len(recipe['stages']),len(prefix)+17)  # One long Y leg is split at the existing 9.9 mm cap.

    def test_explicit_35_pad_dose6_preparer_builds_within_new_stage_cap_offline(self):
        targets=self.registration.read_text();reg=json.loads(targets);byid={p['padId']:p for p in reg['resistorPadMachineXYTargets']}
        pads=list(self.pads)
        identities=[f'R{ref}.{n}' for ref in range(1,18) for n in (1,2) if f'R{ref}.{n}' not in ('R3.1','R2.2')]+['R30.2']
        for ix,padid in enumerate(identities):
            folder=self.root/f'wide{ix}';folder.mkdir();img=folder/'top.png';img.write_bytes(b'\x89PNG\r\n\x1a\ntest')
            report=folder/'report.json';report.write_text(json.dumps({'status':'completed-camera-survey-awaiting-image-review','controllerPositionVerified':True,'uncertainCompletion':False,'finishedAt':datetime.fromtimestamp(self.now/1000,timezone.utc).isoformat().replace('+00:00','Z'),'request':{'jvmStartMs':1,'liveConfigurationSha256':'a'*64},'afterImages':{'top':{'path':'top.png'}}}))
            surf=self.json(f'wide-surface{ix}.json',{'boardId':'ftp-board','provenance':'commissioning-provisional','precisionCalibrated':False,'flowCalibrated':False,'reviewedBy':'reviewer','jvmStartMs':1,'liveConfigurationSha256':'a'*64,'surface':{'rawZ':58.37,'estimatedGapMm':.404,'gapUncertaintyMm':.3},'basisEvidence':self.ev})
            surface={'rawZ':58.37,'estimatedGapMm':.404,'gapUncertaintyMm':.3}
            x,y=12+ix*.01,11+ix*.01;byid[padid]={'padId':padid,'machineXYMm':[x,y]}
            pads.append({'padId':padid,'rawPose':{'X':x,'Y':y,'Z':58.37,'A':720.0},'padIdentityReviewed':True,'padAvailableReviewed':True,'availabilityCapturedMs':self.now,'availabilityReportEvidence':M.ev(report),'availabilityImageEvidence':M.ev(img),'surface':surface,'surfaceEvidence':M.ev(surf)})
        reg['resistorPadMachineXYTargets']=list(byid.values());self.registration.write_text(json.dumps(reg))
        target=dict(self.target,pads=pads);target['compensatedSequence']=dict(target['compensatedSequence'],doseDegrees=6);self.json('wide-target.json',target)
        args=SimpleNamespace(template=str(self.template),barrier=str(self.barrier),target_record=str(self.root/'wide-target.json'),experiment=str(self.experiment_file),profile=str(self.profile),clearance_review=str(self.review),image=str(self.image),previous_report=str(self.prev),ledger=str(self.ledger),output=str(self.root/'wide-out'),xy_clearance_raw_z=53.4,up_to_40=True)
        called=[]
        def generic(cmd,**kwargs):
            called.append(cmd);out=Path(cmd[cmd.index('--output')+1]);out.mkdir(parents=True);(out/'preview-request.json').write_text('{"enabled":false}\n');return SimpleNamespace(stdout='/tmp/preview-request.json')
        with patch.object(M.subprocess,'run',side_effect=generic): M.build(args)
        recipe=json.loads((self.root/'wide-out'/'recipe.json').read_text())
        request=json.loads((self.root/'wide-out'/'native'/'preview-request.json').read_text())
        self.assertEqual(recipe['targetSurface'],'ftp-selected-pads-up-to-40')
        self.assertEqual(recipe['bAccounting']['selectedPadCount'],35)
        self.assertGreater(len(recipe['stages']),96);self.assertLessEqual(len(recipe['stages']),400)
        self.assertEqual(recipe['bAccounting']['grossChargedDegrees'],recipe['bAccounting']['conditioningGrossDegrees']+35*12+40)
        self.assertNotIn('--up-to-40',called[0])  # Scope is selected by the recipe target, not a generic CLI bypass.


    def test_four_group_fractional_comparison_builds_bounded_routes_offline(self):
        lane_y=[0.0,2.14,4.29,6.44]
        groups=[];lane_experiments=[];pads=[]
        templates=self.pads
        for gi,pct in enumerate((15,20,25,30)):
            px,py=0.0,lane_y[gi]
            wipes=[{'X':px+1.50,'Y':py},{'X':px+5.34,'Y':py}]
            ids=[f'R{r}.{side}' for r in range(gi*4+1,gi*4+5) for side in (1,2)]
            groups.append({'group':gi+1,'retractPercent':pct,'padIds':ids,'primeRawXY':[px,py],'scrapTargetsXY':wipes})
            lane_experiments.append({'group':gi+1,'primeRawXY':[px,py],'targetsXY':wipes})
            for j,padid in enumerate(ids):
                base=templates[(gi*8+j)%2]
                pads.append({**base,'padId':padid,'group':gi+1,'retractPercent':pct,'rawPose':{'X':20+gi*3+j*.1,'Y':20+j*.1,'Z':base['surface']['rawZ'],'A':720.0}})
        self.experiment.update(primeDegrees=60,conditioningDoseDegrees=6,conditioningRestoreDegrees=0,targetsXY=groups[0]['scrapTargetsXY'],comparisonGroupTargetsXY=lane_experiments)
        self.experiment_file=self.json('comparison-experiment.json',self.experiment)
        review={'reviewedBy':'reviewer','reviewedMs':self.now,'experimentEvidence':M.ev(self.experiment_file),'imageEvidence':M.ev(self.image),'image':str(self.image)}
        self.review=self.json('comparison-review.json',review)
        profile=json.loads(self.profile.read_text());profile['measurementEvidence']=M.ev(self.review);self.profile=self.json('comparison-profile.json',profile)
        target={**self.target,'pads':pads,'surface':pads[0]['surface'],'surfaceEvidence':pads[0]['surfaceEvidence'],'reviewedMs':self.now,
                'compensatedSequence':{'schema':1,'protocol':'restore-dose-retract-lift-retraction-comparison','doseDegrees':6,'retractDegrees':3,'conditioningRetractDegrees':3,'dwellMilliseconds':2000,'retractDwellMilliseconds':500,'idleReliefDegrees':40},
                'retractionComparison':{'schema':1,'protocol':'four-group-fractional-retraction-comparison','doseDegrees':6,'stepsPerDegree':4.44,'groups':groups}}
        target_file=self.json('comparison-target.json',target)
        args=SimpleNamespace(template=str(self.template),barrier=str(self.barrier),target_record=str(target_file),experiment=str(self.experiment_file),profile=str(self.profile),clearance_review=str(self.review),image=str(self.image),previous_report=str(self.prev),ledger=str(self.ledger),output=str(self.root/'comparison-out'),xy_clearance_raw_z=53.4,retraction_comparison=True,up_to_40=False)
        def generic(cmd,**kwargs):
            out=Path(cmd[cmd.index('--output')+1]);out.mkdir(parents=True);(out/'preview-request.json').write_text('{"enabled":false}\n');return SimpleNamespace(stdout='/tmp/preview-request.json')
        with patch.object(M.subprocess,'run',side_effect=generic): M.build(args)
        recipe=json.loads((self.root/'comparison-out'/'recipe.json').read_text());built=json.loads((self.root/'comparison-out'/'targets.json').read_text())
        self.assertEqual(recipe['targetSurface'],'ftp-selected-pads-retraction-comparison')
        self.assertEqual(len(recipe['stages']),len(built['stages']) if 'stages' in built else len(recipe['stages']))
        self.assertLessEqual(len(recipe['stages']),400);self.assertLessEqual(recipe['bAccounting']['grossChargedDegrees'],813)
        self.assertEqual([g['retractPercent'] for g in built['retractionComparison']['groups']],[15,20,25,30])
        for gi,g in enumerate(built['retractionComparison']['groups']):
            self.assertEqual(g['groupIdleReliefStageIndices'][1],g['groupEndStageIndex'])
            self.assertEqual(recipe['stages'][g['groupIdleReliefStageIndices'][1]]['dwellMilliseconds'],2000)
            self.assertEqual(len(g['padIds']),8)
            block=built['pads'][gi*8:(gi+1)*8]
            self.assertEqual(block[0]['restoreRawDelta'],-3.0)
            for prev,pad in zip(block,block[1:]): self.assertAlmostEqual(pad['restoreRawDelta'],-prev['actualRetractRawDelta'],places=8)
        self.assertFalse(json.loads((self.root/'comparison-out'/'native'/'preview-request.json').read_text()).get('enabled',True))

    def test_minimum_travel_pair_carry_route_retracts_only_after_each_second_pad(self):
        pads=[];reg=[]
        for ref_i,ref in enumerate(range(17,21)):
            for side,x in ((1,10.0+ref_i*3.0),(2,10.7+ref_i*3.0)):
                padid=f'R{ref}.{side}';base=self.pads[(ref_i+side)%2];pose={'X':x,'Y':10.0,'Z':base['surface']['rawZ'],'A':720.0}
                pads.append({**base,'padId':padid,'rawPose':pose,'componentReference':padid.rsplit('.',1)[0],'pairOrder':side,'retractPercent':30,'requestedRetractionDegrees':1.8})
                reg.append({'padId':padid,'machineXYMm':[x,10.0]})
        self.registration.write_text(json.dumps({'resistorPadMachineXYTargets':reg}))
        experiment={**self.experiment,'conditioningDoseDegrees':6,'conditioningRestoreDegrees':0,'primeDegrees':60,'dwellMilliseconds':2000,'retractDegrees':3,'retractDwellMilliseconds':500,'idleReliefDegrees':40,'startRaw':self.raw}
        ef=self.json('minimum-travel-experiment.json',experiment)
        review=self.json('minimum-travel-review.json',{'reviewedBy':'reviewer','reviewedMs':self.now,'experimentEvidence':M.ev(ef),'imageEvidence':M.ev(self.image)})
        prof=json.loads(self.profile.read_text());prof['measurementEvidence']=M.ev(review);pf=self.json('minimum-travel-profile.json',prof)
        plan=M.MIN.plan_minimum_travel_transitions([{'reference':p['padId'].rsplit('.',1)[0],'pad':p['padId'].rsplit('.',1)[1],'xy_mm':[p['rawPose']['X'],p['rawPose']['Y']]} for p in pads])
        target={**self.target,'pads':pads,'surface':pads[0]['surface'],'surfaceEvidence':pads[0]['surfaceEvidence'],'reviewedMs':self.now,
          'pairReferences':['R17','R18','R19','R20'],
          'minimumTravelPolicy':{'schema':1,'protocol':'same-component-pair-no-interim-retract','plan':plan,'orderedPadIds':[p['padId'] for p in pads]},
          'compensatedSequence':{'schema':1,'protocol':'restore-dose-pair-carry-retract-lift-minimum-travel-eight-pad','doseDegrees':6,'retractDegrees':3,'retractPercent':30,'requestedRetractionDegrees':1.8,'conditioningRetractDegrees':3,'dwellMilliseconds':2000,'retractDwellMilliseconds':500,'idleReliefDegrees':40}}
        tf=self.json('minimum-travel-target.json',target)
        args=SimpleNamespace(template=str(self.template),barrier=str(self.barrier),target_record=str(tf),experiment=str(ef),profile=str(pf),clearance_review=str(review),image=str(self.image),previous_report=str(self.prev),ledger=str(self.ledger),output=str(self.root/'minimum-travel-out'),xy_clearance_raw_z=53.4,minimum_travel_eight_pad=True)
        def generic(cmd,**kwargs):
            out=Path(cmd[cmd.index('--output')+1]);out.mkdir(parents=True);(out/'preview-request.json').write_text('{"enabled":false}\n');return SimpleNamespace(stdout='/tmp/preview-request.json')
        with patch.object(M.subprocess,'run',side_effect=generic): M.build(args)
        recipe=json.loads((self.root/'minimum-travel-out'/'recipe.json').read_text());built=json.loads((self.root/'minimum-travel-out'/'targets.json').read_text())
        self.assertEqual(recipe['targetSurface'],'ftp-selected-pads-minimum-travel-eight-pad')
        self.assertLessEqual(len(recipe['stages']),150);self.assertLessEqual(recipe['bAccounting']['grossChargedDegrees'],220)
        for pair_start in (0,2,4,6):
            first,second=built['pads'][pair_start:pair_start+2]
            self.assertIsNotNone(first['restoreStageIndex']);self.assertIsNone(first['retractStageIndex'])
            self.assertIsNone(second['restoreStageIndex']);self.assertIsNotNone(second['retractStageIndex'])
            self.assertEqual(first['doseStageIndices'][0],first['restoreStageIndex']+1)
            self.assertEqual(second['doseStageIndices'][0]+1,second['retractStageIndex'])
            self.assertLessEqual(built['minimumTravelPolicy']['plan']['transitions'][pair_start]['xyTravelMm'],2)
        final=built['compensatedSequence']['finalIdleStageIndices']
        self.assertEqual(final[-1],len(recipe['stages'])-1)
        self.assertEqual([recipe['stages'][i]['axis'] for i in final],['B','B'])
        self.assertAlmostEqual(recipe['stages'][final[1]]['target']-recipe['stages'][final[0]]['target'],20)
        self.assertFalse(json.loads((self.root/'minimum-travel-out'/'native'/'preview-request.json').read_text()).get('enabled',True))

if __name__=='__main__': unittest.main()
