import importlib.util
import json
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT = Path(__file__).with_name('prepare-conditioned-ftp-pair.py')
SPEC = importlib.util.spec_from_file_location('prepare_conditioned_ftp_pair', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ConditionedPairBuilderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.now = int(time.time()*1000)
        self.session = {'sessionId':'test-session','jvmStartMs':1,'liveConfigurationSha256':'a'*64,
                        'syringeId':'test-syringe','provenance':'commissioning-provisional',
                        'precisionCalibrated':False,'flowCalibrated':False}
        self.raw = {'X':0.0,'Y':0.0,'Z':58.45,'A':720.0,'B':-1000.0}
        self.image = self.write('view.jpg',b'\xff\xd8\xfftest')
        self.exp = {'schema':1,'scope':'reviewed-scrap-retraction-coupon','mode':'transfer-preparation',
                    'maximumTransferElapsedMilliseconds':15000,'conditioningDoseDegrees':20,
                    'retractDwellMilliseconds':500,'idleReliefDegrees':20,'preWipeReliefDegrees':20,
                    'primeDegrees':60,'dwellMilliseconds':500,'conditioningDwellMilliseconds':2000,
                    'doseDegrees':4,'retractDegrees':2,'startRaw':self.raw,
                    'workRawZ':58.45,'clearanceRawZ':53.45,
                    'targetsXY':[{'X':0.0,'Y':1.0},{'X':10.0,'Y':1.0}]}
        self.experiment = self.json('experiment.json',self.exp)
        self.review = self.json('review.json',{'reviewedBy':'reviewer','reviewedMs':max(self.now,self.image.stat().st_mtime_ns//1_000_000),
                'experimentEvidence':MODULE.path_evidence(self.experiment),
                'imageEvidence':MODULE.path_evidence(self.image)})
        self.profile = self.json('profile.json',{**self.session,'rawPose':{k:self.raw[k] for k in 'XYZA'},
                'estimatedGapMm':0.4,'gapUncertaintyMm':0.3,
                'measurementEvidence':MODULE.path_evidence(self.review)})
        self.registration = self.json('registration.json',{'resistorPadMachineXYTargets':[
                {'padId':'R40.1','machineXYMm':[20.0,20.0]},
                {'padId':'R40.2','machineXYMm':[21.0,20.0]}]})
        self.evidence_file = self.json('evidence.json',{'ok':True})
        ev=MODULE.path_evidence(self.evidence_file)
        self.target={'schema':1,'scope':'ftp-two-pad-commissioning-targets',**self.session,
            'quantizationMm':0.01,'boardUnmovedSinceRegistration':True,
            'surface':{'rawZ':58.3,'estimatedGapMm':0.4,'gapUncertaintyMm':0.3},
            'cameraMinusTipXYMm':[0,0],
            'cadEvidence':ev,'registrationEvidence':MODULE.path_evidence(self.registration),
            'tipOffsetEvidence':ev,'surfaceEvidence':ev,'padAvailabilityImage':ev,
            'compensatedSequence':{'schema':1,'protocol':'restore-dose-retract-lift-two-pad',
                'doseDegrees':4,'retractDegrees':2,'dwellMilliseconds':300,
                'retractDwellMilliseconds':500,'idleReliefDegrees':40,
                'conditioningReportEvidence':ev,'conditioningLedgerEvidence':ev,
                'preparationExperimentEvidence':ev,'tipObservationEvidence':ev,
                'conditioningFinishedMs':1,'maximumElapsedMilliseconds':120000},
            'pads':[{'padId':'R40.1','rawPose':{'X':20.0,'Y':20.0,'Z':58.3,'A':720.0}},
                    {'padId':'R40.2','rawPose':{'X':21.0,'Y':20.0,'Z':58.3,'A':720.0}}]}
        self.target_file=self.json('target.json',self.target)
        self.report=self.json('previous-report.json',{'ok':True})
        self.ledger=self.json('ledger.json',{'ok':True})
        self.template=self.json('template.json',{**self.session})
        self.barrier=self.json('barrier.json',{'status':'completed-read-only-position-barrier',
            'controllerPositionVerified':True,'noMotionCommandSubmitted':True,'uncertainCompletion':False,
            'finishedAt':datetime.now(timezone.utc).isoformat(),
            'request':{'jvmStartMs':1},'liveConfigurationSha256':'a'*64,
            'afterQuerySnapshot':{'raw':self.raw,'nativePoses':{
                'N1':{'x':0.0,'y':0.0,'z':58.45},'N2':{'x':0.0,'y':0.0,'z':58.45},
                'top':{'x':0.0,'y':0.0,'z':0.0},'bottom':{'x':0.0,'y':0.0,'z':0.0}}}})

    def tearDown(self): self.tmp.cleanup()

    def write(self,name,data):
        p=self.root/name;p.write_bytes(data);return p

    def json(self,name,data):
        p=self.root/name;p.write_text(json.dumps(data,indent=2)+'\n');return p

    def test_combines_exact_prefix_clearance_and_pair_suffix(self):
        expected_prefix,_,_=MODULE.PREP.stages_for(self.exp,MODULE.path_evidence(self.review),0.4,0.3)
        args=SimpleNamespace(template=str(self.template),barrier=str(self.barrier),target_record=str(self.target_file),
            experiment=str(self.experiment),profile=str(self.profile),clearance_review=str(self.review),image=str(self.image),
            previous_report=str(self.report),ledger=str(self.ledger),output=str(self.root/'out'),
            xy_clearance_raw_z=53.4,maximum_transfer_ms=15000)
        commands=[]
        def offline_run(cmd, **kwargs):
            commands.append(cmd)
            Path(cmd[-1]).mkdir(parents=True,exist_ok=True)
            (Path(cmd[-1])/'preview-request.json').write_text('{\"enabled\":false}\n')
            return SimpleNamespace(stdout='offline validator ok')
        with patch.object(MODULE.subprocess,'run',side_effect=offline_run):
            MODULE.build(args)
        recipe=json.loads((self.root/'out'/'recipe.json').read_text())
        targets=json.loads((self.root/'out'/'targets.json').read_text())
        inline=targets['inlineConditioning']
        self.assertEqual(inline['prefixStageCount'],len(expected_prefix))
        self.assertEqual(inline['retractionStageIndex'],len(expected_prefix)-2)
        self.assertEqual(inline['liftStageIndex'],len(expected_prefix)-1)
        self.assertEqual(recipe['stages'][:len(expected_prefix)],expected_prefix)
        self.assertEqual(recipe['stages'][len(expected_prefix)],{'axis':'Z','target':53.4})
        self.assertEqual([p['padId'] for p in targets['pads']],['R40.1','R40.2'])
        self.assertEqual(targets['compensatedSequence']['finalIdleStageIndices'][-1],len(recipe['stages'])-1)
        for forbidden in ('conditioningReportEvidence','conditioningLedgerEvidence','preparationExperimentEvidence',
                          'tipObservationEvidence','conditioningFinishedMs','maximumElapsedMilliseconds'):
            self.assertNotIn(forbidden,targets['compensatedSequence'])
        self.assertEqual(recipe['targetSurface'],'scrap-conditioned-ftp-demo')
        self.assertEqual(recipe['clearanceReviewEvidence'],MODULE.path_evidence(self.review))
        self.assertEqual(recipe['inlineConditioningEvidence'],MODULE.path_evidence(self.experiment))
        self.assertEqual(recipe['bAccounting']['grossChargedDegrees'],
                         recipe['conditioningAccounting']['grossCommandedDegrees']+
                         recipe['bAccounting']['ftpPairGrossDegrees'])
        self.assertEqual(commands[0][2:4],['prepare','--template'])
        self.assertFalse(json.loads((self.root/'out'/'native'/'preview-request.json').read_text()).get('enabled',True))

if __name__=='__main__': unittest.main()
