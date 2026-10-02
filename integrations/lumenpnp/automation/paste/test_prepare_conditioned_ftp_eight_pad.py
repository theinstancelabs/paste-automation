import importlib.util
import json
import os
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from datetime import datetime, timezone
from pathlib import Path

SCRIPT=Path(__file__).with_name('prepare-conditioned-ftp-eight-pad.py')
SPEC=importlib.util.spec_from_file_location('prepare_conditioned_ftp_eight_pad',SCRIPT)
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)
PAIR_TEST=Path(__file__).with_name('test_prepare_conditioned_ftp_pair.py')
PAIR_SPEC=importlib.util.spec_from_file_location('conditioned_pair_fixture',PAIR_TEST)
PAIR_FIXTURE=importlib.util.module_from_spec(PAIR_SPEC);PAIR_SPEC.loader.exec_module(PAIR_FIXTURE)

class EightPadBuilderTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.now=int(time.time()*1000)
        self.cfg='a'*64;self.image=self.root/'view.png';self.image.write_bytes(b'\x89PNG\r\ntest')
        finished=datetime.fromtimestamp(self.now/1000,timezone.utc).isoformat().replace('+00:00','Z')
        self.report=self.root/'camera-report.json'
        self.report.write_text(json.dumps({'status':'completed-camera-survey-awaiting-image-review','finishedAt':finished,
            'controllerPositionVerified':True,'uncertainCompletion':False,'liveConfigurationSha256':self.cfg,
            'request':{'jvmStartMs':9,'liveConfigurationSha256':self.cfg},'afterImages':{'top':{'path':self.image.name}}}))
        self.report_evidence=M.ev(self.report);self.image_evidence=M.ev(self.image)
        refs=['R1','R2','R3','R4'];pads=[]
        for r in refs:
            for n in (1,2):pads.append({'padId':f'{r}.{n}','padAvailableReviewed':True,
                'padIdentityReviewed':True,'availabilityImageEvidence':self.image_evidence,
                'availabilityReportEvidence':self.report_evidence,'availabilityCapturedMs':self.now})
        self.target={'schema':1,'scope':'ftp-eight-pad-commissioning-targets','pairReferences':refs,'pads':pads,
            'compensatedSequence':{'schema':1,'protocol':'restore-dose-retract-lift-eight-pad','doseDegrees':4,
                'retractDegrees':2,'dwellMilliseconds':200,'retractDwellMilliseconds':500,'idleReliefDegrees':40}}

    def tearDown(self):self.tmp.cleanup()

    def test_accepts_dose_4_and_6_with_fresh_pad_reports(self):
        for dose in (4,6):
            self.target['compensatedSequence']['doseDegrees']=dose
            refs,pads=M.validate_eight(self.target);sources=M.validate_availability_reports(pads,{'jvmStartMs':9,'liveConfigurationSha256':self.cfg},self.now)
            self.assertEqual(refs,['R1','R2','R3','R4']);self.assertEqual(len(sources),2)

    def test_rejects_stale_or_mismatched_pad_report(self):
        self.target['pads'][0]['availabilityCapturedMs']-=300001
        with self.assertRaises(ValueError):M.validate_availability_reports(self.target['pads'],{'jvmStartMs':9,'liveConfigurationSha256':self.cfg},self.now)
        self.target['pads'][0]['availabilityCapturedMs']=self.now
        with self.assertRaises(ValueError):M.validate_availability_reports(self.target['pads'],{'jvmStartMs':10,'liveConfigurationSha256':self.cfg},self.now)

    def test_rejects_incomplete_pair_or_unsupported_dose(self):
        self.target['pads'][1]['padId']='R1.1'
        with self.assertRaises(ValueError):M.validate_eight(self.target)

    def test_full_build_preserves_reversed_pairs_and_single_final_idle(self):
        fixture=PAIR_FIXTURE.ConditionedPairBuilderTests();fixture.setUp()
        try:
            barrier_data=json.loads(fixture.barrier.read_text())
            for key,rotation in (('N1',720),('N2',-1816),('top',0),('bottom',0)):
                barrier_data['afterQuerySnapshot']['nativePoses'][key]['rotation']=rotation
            fixture.barrier.write_text(json.dumps(barrier_data))
            now=fixture.now
            # Give the captured image the exact deterministic authored clock
            # value; filesystem nanoseconds must not race review timestamps.
            os.utime(fixture.image,ns=(now*1_000_000,now*1_000_000))
            finished=datetime.fromtimestamp(now/1000,timezone.utc).isoformat().replace('+00:00','Z')
            report=fixture.json('availability-report.json',{'status':'completed-camera-survey-awaiting-image-review','finishedAt':finished,
                'controllerPositionVerified':True,'uncertainCompletion':False,'request':{'jvmStartMs':1,'liveConfigurationSha256':'a'*64},
                'afterImages':{'top':{'path':fixture.image.name}}})
            reg={'resistorPadMachineXYTargets':[]};pads=[];refs=['R1','R2','R3','R4']
            for i,ref in enumerate(refs):
                for suffix in (2,1):
                    x=20.0+i*2+(0 if suffix==1 else 1);y=20.0
                    padid=f'{ref}.{suffix}';reg['resistorPadMachineXYTargets'].append({'padId':padid,'machineXYMm':[x,y]})
                    pads.append({'padId':padid,'rawPose':{'X':x,'Y':y,'Z':58.3,'A':720},'padAvailableReviewed':True,
                        'padIdentityReviewed':True,'availabilityImageEvidence':M.ev(fixture.image),
                        'availabilityReportEvidence':M.ev(report),'availabilityCapturedMs':now})
            registration=fixture.json('eight-registration.json',reg)
            target=dict(fixture.target);target.update({'scope':'ftp-eight-pad-commissioning-targets','pairReferences':refs,
                'registrationEvidence':M.ev(registration),'pads':pads,'compensatedSequence':{
                    'schema':1,'protocol':'restore-dose-retract-lift-eight-pad','doseDegrees':4,'retractDegrees':2,
                    'dwellMilliseconds':200,'retractDwellMilliseconds':500,'idleReliefDegrees':40}})
            target_file=fixture.json('eight-target.json',target)
            fixture.exp['scope']='reviewed-scrap-retraction-coupon';fixture.exp['doseDegrees']=4
            experiment=fixture.json('eight-experiment.json',fixture.exp)
            review=fixture.json('eight-review.json',{'reviewedBy':'reviewer','reviewedMs':now,
                'experimentEvidence':M.PREP.WIPE.evidence(experiment),'imageEvidence':M.PREP.WIPE.evidence(fixture.image)})
            profile=fixture.profile.read_text();profiledata=json.loads(profile);profiledata['measurementEvidence']=M.PREP.WIPE.evidence(review)
            fixture.profile.write_text(json.dumps(profiledata))
            args=SimpleNamespace(template=str(fixture.template),barrier=str(fixture.barrier),target_record=str(target_file),
                experiment=str(experiment),profile=str(fixture.profile),clearance_review=str(review),image=str(fixture.image),
                previous_report=str(fixture.report),ledger=str(fixture.ledger),output=str(fixture.root/'eight-out'),xy_clearance_raw_z=53.4)
            def offline_run(cmd,**kwargs):
                Path(cmd[-1]).mkdir(parents=True,exist_ok=True);(Path(cmd[-1])/'preview-request.json').write_text('{"enabled":false}\n')
                return SimpleNamespace(stdout='offline validator ok')
            with patch.object(M.subprocess,'run',side_effect=offline_run):M.build(args)
            recipe=json.loads((fixture.root/'eight-out'/'recipe.json').read_text());out=json.loads((fixture.root/'eight-out'/'targets.json').read_text())
            self.assertEqual(len(recipe['stages']),65);self.assertEqual(len(out['pads']),8)
            for i in range(4):self.assertEqual([p['padId'] for p in out['pads'][i*2:i*2+2]],[f'{refs[i]}.2',f'{refs[i]}.1'])
            self.assertEqual([p['padId'] for p in out['pads'] if p.get('finalIdleStageIndices')],[])
            self.assertEqual(len(out['compensatedSequence']['finalIdleStageIndices']),2)
            dose4=recipe['bAccounting']['grossChargedDegrees']
            self.assertEqual(dose4,206)
            self.assertEqual(recipe['bAccounting']['netDegrees'],-50)
            states=[];at=dict(fixture.raw)
            for stage in recipe['stages']:
                states.append(dict(at));at[stage['axis']]=stage['target']
            accounted=set(i for i in range(out['inlineConditioning']['prefixStageCount']) if recipe['stages'][i]['axis']=='B')
            for pad in out['pads']:
                r,d,b,l=pad['restoreStageIndex'],pad['doseStageIndices'][0],pad['retractStageIndex'],pad['liftStageIndex']
                self.assertEqual([d,b,l],[r+1,r+2,r+3])
                self.assertEqual({k:states[r][k] for k in 'XYZA'},pad['rawPose'])
                self.assertEqual([recipe['stages'][i]['target']-states[i]['B'] for i in (r,d,b)],[-2,-4,2])
                self.assertEqual(recipe['stages'][b]['dwellMilliseconds'],500)
                self.assertEqual(recipe['stages'][l],{'axis':'Z','target':53.4})
                accounted.update((r,d,b))
            idle=out['compensatedSequence']['finalIdleStageIndices']
            self.assertEqual(idle,[len(recipe['stages'])-2,len(recipe['stages'])-1])
            self.assertEqual([recipe['stages'][i]['target']-states[i]['B'] for i in idle],[20,20])
            self.assertEqual([recipe['stages'][i]['dwellMilliseconds'] for i in idle],[0,2000])
            accounted.update(idle)
            self.assertEqual(accounted,{i for i,v in enumerate(recipe['stages']) if v['axis']=='B'})
            target['compensatedSequence']['doseDegrees']=6;target['compensatedSequence']['dwellMilliseconds']=1000;fixture.json('eight-target.json',target)
            fixture.exp['doseDegrees']=6;experiment.write_text(json.dumps(fixture.exp))
            review.write_text(json.dumps({'reviewedBy':'reviewer','reviewedMs':now,'experimentEvidence':M.PREP.WIPE.evidence(experiment),'imageEvidence':M.PREP.WIPE.evidence(fixture.image)}))
            profiledata['measurementEvidence']=M.PREP.WIPE.evidence(review);fixture.profile.write_text(json.dumps(profiledata))
            args.output=str(fixture.root/'eight-out-dose6')
            with patch.object(M.subprocess,'run',side_effect=offline_run):M.build(args)
            recipe6=json.loads((fixture.root/'eight-out-dose6'/'recipe.json').read_text())
            self.assertEqual(recipe6['bAccounting']['grossChargedDegrees'],222)
            self.assertEqual(recipe6['bAccounting']['netDegrees'],-66)
            out6=json.loads((fixture.root/'eight-out-dose6'/'targets.json').read_text())
            for pad in out6['pads']:
                self.assertEqual(recipe6['stages'][pad['doseStageIndices'][0]]['dwellMilliseconds'],1000)
                self.assertEqual(recipe6['stages'][pad['retractStageIndex']]['dwellMilliseconds'],500)
                self.assertEqual(recipe6['stages'][pad['restoreStageIndex']]['dwellMilliseconds'],0)
            target['compensatedSequence'].update(doseDegrees=20,dwellMilliseconds=2000)
            fixture.json('eight-target.json',target);fixture.exp['doseDegrees']=20;experiment.write_text(json.dumps(fixture.exp))
            review.write_text(json.dumps({'reviewedBy':'reviewer','reviewedMs':now,'experimentEvidence':M.PREP.WIPE.evidence(experiment),'imageEvidence':M.PREP.WIPE.evidence(fixture.image)}))
            profiledata['measurementEvidence']=M.PREP.WIPE.evidence(review);fixture.profile.write_text(json.dumps(profiledata));args.output=str(fixture.root/'eight-out-dose20')
            with patch.object(M.subprocess,'run',side_effect=offline_run):M.build(args)
            recipe20=json.loads((fixture.root/'eight-out-dose20'/'recipe.json').read_text());out20=json.loads((fixture.root/'eight-out-dose20'/'targets.json').read_text())
            self.assertEqual(len(recipe20['stages']),len(recipe6['stages']))
            self.assertEqual(recipe20['bAccounting']['grossChargedDegrees'],334)
            self.assertEqual(recipe20['bAccounting']['netDegrees'],-178)
            for pad in out20['pads']:
                self.assertEqual(len(pad['doseStageIndices']),1)
                self.assertEqual(recipe20['stages'][pad['doseStageIndices'][0]]['dwellMilliseconds'],2000)
            target['compensatedSequence'].update(doseDegrees=12,dwellMilliseconds=2000)
            fixture.json('eight-target.json',target);fixture.exp['doseDegrees']=12;experiment.write_text(json.dumps(fixture.exp))
            review.write_text(json.dumps({'reviewedBy':'reviewer','reviewedMs':now,'experimentEvidence':M.PREP.WIPE.evidence(experiment),'imageEvidence':M.PREP.WIPE.evidence(fixture.image)}))
            profiledata['measurementEvidence']=M.PREP.WIPE.evidence(review);fixture.profile.write_text(json.dumps(profiledata));args.output=str(fixture.root/'eight-out-dose12')
            with patch.object(M.subprocess,'run',side_effect=offline_run):M.build(args)
            recipe12=json.loads((fixture.root/'eight-out-dose12'/'recipe.json').read_text());out12=json.loads((fixture.root/'eight-out-dose12'/'targets.json').read_text())
            self.assertEqual(len(recipe12['stages']),len(recipe6['stages'])+8)
            self.assertEqual(recipe12['bAccounting']['grossChargedDegrees'],270)
            self.assertEqual(recipe12['bAccounting']['netDegrees'],-114)
            for pad in out12['pads']:
                a,b=pad['doseStageIndices'];self.assertEqual(b,a+1)
                self.assertEqual(recipe12['stages'][a]['target']-recipe12['stages'][pad['restoreStageIndex']]['target'],-6)
                self.assertEqual(recipe12['stages'][b]['target']-recipe12['stages'][a]['target'],-6)
                self.assertEqual([recipe12['stages'][i]['dwellMilliseconds'] for i in (a,b)],[0,2000])
            target['compensatedSequence']['retractDegrees']=3;fixture.json('eight-target.json',target)
            args.output=str(fixture.root/'eight-out-r3-mismatch')
            with self.assertRaisesRegex(ValueError,'Conditioner retraction'):
                M.build(args)
            fixture.exp['retractDegrees']=3;experiment.write_text(json.dumps(fixture.exp))
            review.write_text(json.dumps({'reviewedBy':'reviewer','reviewedMs':now,'experimentEvidence':M.PREP.WIPE.evidence(experiment),'imageEvidence':M.PREP.WIPE.evidence(fixture.image)}))
            profiledata['measurementEvidence']=M.PREP.WIPE.evidence(review);fixture.profile.write_text(json.dumps(profiledata));args.output=str(fixture.root/'eight-out-r3')
            with patch.object(M.subprocess,'run',side_effect=offline_run):M.build(args)
            r3=json.loads((fixture.root/'eight-out-r3'/'recipe.json').read_text());t3=json.loads((fixture.root/'eight-out-r3'/'targets.json').read_text())
            self.assertEqual(r3['bAccounting']['grossChargedDegrees'],287);self.assertEqual(r3['bAccounting']['netDegrees'],-113)
            self.assertEqual(len(r3['stages']),len(recipe12['stages']))
            for pad in t3['pads']:
                i=pad['restoreStageIndex'];j=pad['retractStageIndex']
                prior_b=next(s['target'] for s in reversed(r3['stages'][:i]) if s['axis']=='B')
                self.assertEqual(r3['stages'][i]['target']-prior_b,-3)
                self.assertEqual(r3['stages'][j]['target']-r3['stages'][j-1]['target'],3)
            fixture.exp['conditioningDoseDegrees']=6;experiment.write_text(json.dumps(fixture.exp))
            review.write_text(json.dumps({'reviewedBy':'reviewer','reviewedMs':now,'experimentEvidence':M.PREP.WIPE.evidence(experiment),'imageEvidence':M.PREP.WIPE.evidence(fixture.image)}))
            profiledata['measurementEvidence']=M.PREP.WIPE.evidence(review);fixture.profile.write_text(json.dumps(profiledata));args.output=str(fixture.root/'eight-out-condition6')
            with patch.object(M.subprocess,'run',side_effect=offline_run):M.build(args)
            c6=json.loads((fixture.root/'eight-out-condition6'/'recipe.json').read_text());ct=json.loads((fixture.root/'eight-out-condition6'/'targets.json').read_text())
            self.assertEqual(c6['bAccounting']['grossChargedDegrees'],273);self.assertEqual(c6['bAccounting']['netDegrees'],-99)
            self.assertEqual(len(c6['stages']),len(r3['stages']))
            i=ct['inlineConditioning']['retractionStageIndex']-1
            prior_b=next(s['target'] for s in reversed(c6['stages'][:i]) if s['axis']=='B')
            self.assertEqual(c6['stages'][i]['target']-prior_b,-6);self.assertEqual(c6['stages'][i]['dwellMilliseconds'],2000)
            for restore,expected in ((0,(279,-105)),(3,(282,-108))):
                fixture.exp.update(conditioningDoseDegrees=12,conditioningRestoreDegrees=restore);experiment.write_text(json.dumps(fixture.exp))
                review.write_text(json.dumps({'reviewedBy':'reviewer','reviewedMs':now,'experimentEvidence':M.PREP.WIPE.evidence(experiment),'imageEvidence':M.PREP.WIPE.evidence(fixture.image)}))
                profiledata['measurementEvidence']=M.PREP.WIPE.evidence(review);fixture.profile.write_text(json.dumps(profiledata));args.output=str(fixture.root/('eight-out-condition12-'+str(restore)))
                with patch.object(M.subprocess,'run',side_effect=offline_run):M.build(args)
                c12=json.loads((Path(args.output)/'recipe.json').read_text());ct12=json.loads((Path(args.output)/'targets.json').read_text())
                self.assertEqual((c12['bAccounting']['grossChargedDegrees'],c12['bAccounting']['netDegrees']),expected)
                self.assertEqual(len(c12['stages']),len(c6['stages'])+1+bool(restore))
                ri=ct12['inlineConditioning']['retractionStageIndex'];self.assertEqual([v['dwellMilliseconds'] for v in c12['stages'][ri-2:ri]],[0,2000])
                self.assertEqual(c12['stages'][ri-1]['target']-c12['stages'][ri-2]['target'],-6)
            fixture.exp.update(conditioningDoseDegrees=6,conditioningRestoreDegrees=0)
            fixture.exp.update(conditioningFinalWipeMm=1.5,conditioningFinalWipeReviewed=True);experiment.write_text(json.dumps(fixture.exp))
            review.write_text(json.dumps({'reviewedBy':'reviewer','reviewedMs':now,'attestations':{'conditioningFinalWipeReviewed':True},'experimentEvidence':M.PREP.WIPE.evidence(experiment),'imageEvidence':M.PREP.WIPE.evidence(fixture.image)}))
            profiledata['measurementEvidence']=M.PREP.WIPE.evidence(review);fixture.profile.write_text(json.dumps(profiledata));args.output=str(fixture.root/'eight-out-finalwipe')
            with patch.object(M.subprocess,'run',side_effect=offline_run):M.build(args)
            w=json.loads((fixture.root/'eight-out-finalwipe'/'recipe.json').read_text());wt=json.loads((fixture.root/'eight-out-finalwipe'/'targets.json').read_text());inline=wt['inlineConditioning'];i=inline['retractionStageIndex']
            self.assertEqual(inline['liftStageIndex'],i+2);self.assertEqual(w['stages'][i+1]['axis'],'X');self.assertTrue(w['stages'][i+1]['wipeReview'])
            self.assertEqual(w['stages'][i+1]['target'],fixture.exp['targetsXY'][1]['X']+1.5)
            self.assertEqual(w['bAccounting']['grossChargedDegrees'],273);self.assertEqual(w['bAccounting']['netDegrees'],-99)
            self.assertEqual(inline['prefixStageCount'],ct['inlineConditioning']['prefixStageCount']+1)
        finally:fixture.tearDown()
        self.target['pads'][1]['padId']='R1.2';self.target['compensatedSequence']['doseDegrees']=5
        with self.assertRaises(ValueError):M.validate_eight(self.target)

if __name__=='__main__':unittest.main()
