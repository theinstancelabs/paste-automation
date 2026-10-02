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

if __name__=='__main__': unittest.main()
