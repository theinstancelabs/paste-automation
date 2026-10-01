import copy
import contextlib
import io
import datetime
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest

SPEC = importlib.util.spec_from_file_location('retraction_coupon', Path(__file__).resolve().parents[1]/'prepare-retraction-coupon.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
H = 'a'*64
SID = 'abcd1234-1234-1234-1234-123456789abc'
RID = '12345678-1234-1234-1234-123456789abc'


def experiment(dose=6, retract=3):
    return dict(schema=1, scope='reviewed-scrap-retraction-coupon',
                startRaw=dict(X=100, Y=200, Z=58.25, A=720, B=-234),
                workRawZ=58.25, clearanceRawZ=53.25,
                targetsXY=[dict(X=98, Y=200), dict(X=104, Y=201), dict(X=103, Y=202),
                           dict(X=102, Y=203), dict(X=101, Y=204)],
                doseDegrees=dose, retractDegrees=retract, primeDegrees=40,
                preWipeReliefDegrees=20, idleReliefDegrees=20,
                conditioningDoseDegrees=20, dwellMilliseconds=2000)


class RetractionCouponTests(unittest.TestCase):
    def test_transfer_conditioning6_only_changes_explicit_dummy_dose(self):
        e=experiment(12,3);e.update(mode='transfer-preparation',maximumTransferElapsedMilliseconds=15000)
        e['targetsXY']=e['targetsXY'][:2]
        a,_,ac=M.stages_for(e,dict(path='/review',sha256=H),1.1,1.0)
        e['conditioningDoseDegrees']=6
        b,_,bc=M.stages_for(e,dict(path='/review',sha256=H),1.1,1.0)
        self.assertEqual(len(a),len(b));self.assertEqual(ac['grossCommandedDegrees']-bc['grossCommandedDegrees'],14)
        self.assertEqual(b[-2]['target']-b[-3]['target'],3);self.assertEqual(b[-3]['dwellMilliseconds'],2000)
        e['mode']='coupon';e['targetsXY']=experiment()['targetsXY']
        with self.assertRaises(ValueError):M.stages_for(e,dict(path='/review',sha256=H),1.1,1.0)

    def test_transfer_conditioner12_has_two_parts_and_explicit_restore(self):
        e=experiment(12,3);e.update(mode='transfer-preparation',maximumTransferElapsedMilliseconds=15000,conditioningDoseDegrees=12,conditioningDwellMilliseconds=2000,dwellMilliseconds=200,retractDwellMilliseconds=500)
        e['targetsXY']=e['targetsXY'][:2]
        stages,poses,base=M.stages_for(e,dict(path='/review',sha256=H),1.1,1.0)
        self.assertEqual([s['axis'] for s in stages[-4:]],['B','B','B','Z'])
        self.assertEqual([poses[i+1]['B']-poses[i]['B'] for i in range(len(stages)-4,len(stages)-1)],[-6,-6,3])
        self.assertEqual([s['dwellMilliseconds'] for s in stages[-4:-1]],[0,2000,500])
        e['conditioningRestoreDegrees']=3
        restored,rposes,acct=M.stages_for(e,dict(path='/review',sha256=H),1.1,1.0)
        self.assertEqual(len(restored),len(stages)+1);self.assertEqual(acct['grossCommandedDegrees'],base['grossCommandedDegrees']+3);self.assertEqual(acct['netDegrees'],base['netDegrees']-3)
        self.assertEqual([rposes[i+1]['B']-rposes[i]['B'] for i in range(len(restored)-5,len(restored)-1)],[-3,-6,-6,3])
        for key,value in [('conditioningRestoreDegrees',True),('conditioningRestoreDegrees',2),('conditioningDoseDegrees',6),('retractDegrees',2),('conditioningFinalWipeMm',1.5),('mode','coupon')]:
            bad=copy.deepcopy(e);bad[key]=value
            with self.assertRaises(ValueError):M.stages_for(bad,dict(path='/review',sha256=H),1.1,1.0)

    def test_transfer_final_wipe_is_exact_positive_X_after_retract_before_lift(self):
        e=experiment(12,3);e.update(mode='transfer-preparation',maximumTransferElapsedMilliseconds=15000,conditioningDoseDegrees=6,retractDwellMilliseconds=500)
        e['targetsXY']=e['targetsXY'][:2]
        base,_,acct=M.stages_for(e,dict(path='/review',sha256=H),1.1,1.0)
        e.update(conditioningFinalWipeMm=1.5,conditioningFinalWipeReviewed=True)
        stages,poses,after=M.stages_for(e,dict(path='/review',sha256=H),1.1,1.0)
        self.assertEqual(len(stages),len(base)+1);self.assertEqual(acct['grossCommandedDegrees'],after['grossCommandedDegrees']);self.assertEqual(acct['netDegrees'],after['netDegrees'])
        self.assertEqual([s['axis'] for s in stages[-3:]],['B','X','Z']);self.assertEqual(stages[-3]['dwellMilliseconds'],500)
        self.assertEqual(stages[-2]['target'],e['targetsXY'][1]['X']+1.5);self.assertTrue(stages[-2]['wipeReview'])
        self.assertEqual(poses[-3]['B'],poses[-2]['B']);self.assertEqual(poses[-2]['Z'],e['workRawZ'])
        for key,value in [('conditioningFinalWipeReviewed',False),('conditioningFinalWipeMm',-1.5),('conditioningDoseDegrees',20),('retractDegrees',2),('retractDwellMilliseconds',0)]:
            bad=copy.deepcopy(e);bad[key]=value
            with self.assertRaises(ValueError):M.stages_for(bad,dict(path='/review',sha256=H),1.1,1.0)

    def test_order_gross_and_fixed_speed_inputs(self):
        for dose, retract, expected in ((6, 3, 139), (20, 3, 181), (6, 6, 160), (20, 6, 202)):
            e = experiment(dose, retract)
            stages, poses, accounting = M.stages_for(e, dict(path='/review', sha256=H), 1.1, 1.0)
            self.assertEqual(accounting['grossCommandedDegrees'], expected)
            self.assertEqual(accounting['netDegrees'], -20+retract-3*dose)
            self.assertEqual(accounting['finalRaw']['Z'], 53.25)
            deltas = [right['B']-left['B'] for left, right in zip(poses, poses[1:]) if right['B'] != left['B']]
            self.assertEqual(deltas, [-20, -20, 20, -20, retract]+[-retract, -dose, retract]*3+[20])
            self.assertEqual([s.get('dwellMilliseconds') for s in stages if s['axis'] == 'B'],
                             [0, 2000, 1000, 2000, 0]+[0, 2000, 0]*3+[2000])
            self.assertEqual([s['axis'] for s in stages[:5]], ['B', 'B', 'B', 'X', 'Z'])
            for i, stage in enumerate(stages):
                if stage['axis'] in ('X', 'Y') and poses[i]['Z'] != 53.25:
                    self.assertEqual(i, 3)
                    self.assertTrue(stage['wipeReview'])
                if stage['axis'] == 'B' and i > 3 and stage['target'] > poses[i]['B'] and i != len(stages)-1:
                    self.assertEqual(stages[i+1], dict(axis='Z', target=53.25))
            self.assertTrue(all(p['A'] == 720 for p in poses))

    def test_idle_forty_and_post_retract_wait_preserve_stage_order_and_charge(self):
        for idle in (20,40):
            for wait in (0,200,500):
                e=experiment(4,2);e.update(primeDegrees=60,preWipeReliefDegrees=2,idleReliefDegrees=idle,
                    dwellMilliseconds=200,conditioningDwellMilliseconds=2000,retractDwellMilliseconds=wait)
                stages,poses,a=M.stages_for(e,dict(path='/review',sha256=H),1.1,1)
                strokes=[(right['B']-left['B'],stages[i]['dwellMilliseconds']) for i,(left,right) in enumerate(zip(poses,poses[1:])) if stages[i]['axis']=='B']
                self.assertEqual(strokes,[(-20,0),(-20,0),(-20,2000),(2,1000),(-20,2000),(2,wait)]+[(-2,0),(-4,200),(2,wait)]*3+([(20,2000)] if idle==20 else [(20,0),(20,2000)]))
                self.assertEqual(a['grossCommandedDegrees'],108+idle)
                self.assertEqual(a['netDegrees'],-88+idle)
                self.assertEqual(len(stages),34+(idle==40))
                for i,stage in enumerate(stages):
                    if stage['axis']=='B' and stage['target']-poses[i]['B']==2 and i>3:
                        self.assertEqual(stages[i+1],dict(axis='Z',target=53.25))
                self.assertTrue(all(poses[i]['Z']==53.25 for i in range(len(stages)-idle//20,len(stages))))
        original=experiment();explicit=copy.deepcopy(original);explicit['retractDwellMilliseconds']=0
        self.assertEqual(M.stages_for(original,dict(path='/review',sha256=H),1.1,1),M.stages_for(explicit,dict(path='/review',sha256=H),1.1,1))
        for key,values in [('idleReliefDegrees',[True,40.0,0,60]),('retractDwellMilliseconds',[True,200.0,-1,1000])]:
            for value in values:
                e=experiment();e[key]=value
                with self.assertRaises(ValueError):M.stages_for(e,dict(path='/review',sha256=H),1.1,1)
        e=experiment();e.update(mode='transfer-preparation',maximumTransferElapsedMilliseconds=120000,retractDwellMilliseconds=500,targetsXY=e['targetsXY'][:2])
        stages,poses,a=M.stages_for(e,dict(path='/review',sha256=H),1.1,1)
        self.assertEqual(stages[-2]['dwellMilliseconds'],500)
        self.assertEqual(stages[-1],dict(axis='Z',target=53.25))
        self.assertEqual(a['grossCommandedDegrees'],83)
        with tempfile.TemporaryDirectory() as d:
            args=self.fixture(d);e=experiment(4,2);e.update(primeDegrees=60,preWipeReliefDegrees=2,idleReliefDegrees=40,
                dwellMilliseconds=200,conditioningDwellMilliseconds=2000,retractDwellMilliseconds=500)
            Path(args.experiment).write_text(json.dumps(e))
            review=json.loads(Path(args.review).read_text());review['experimentEvidence']=M.WIPE.evidence(args.experiment)
            Path(args.review).write_text(json.dumps(review))
            profile=json.loads(Path(args.profile).read_text());profile['measurementEvidence']=M.WIPE.evidence(args.review)
            Path(args.profile).write_text(json.dumps(profile))
            recipe=M.build(args);self.assertEqual(recipe['bAccounting']['grossCommandedDegrees'],148)
            self.assertEqual(len(recipe['stages']),35)

    def test_conditioning_dwell_and_pre_wipe_relief_are_separate_bounded_choices(self):
        for before in (2,3,4,6,20):
            e=experiment(4,2);e.update(dwellMilliseconds=200,conditioningDwellMilliseconds=2000,preWipeReliefDegrees=before)
            stages,poses,a=M.stages_for(e,dict(path='/review',sha256=H),1.1,1)
            strokes=[(right['B']-left['B'],stages[i]['dwellMilliseconds']) for i,(left,right) in enumerate(zip(poses,poses[1:])) if stages[i]['axis']=='B']
            self.assertEqual(strokes,[(-20,0),(-20,2000),(before,1000),(-20,2000),(2,0)]+[(-2,0),(-4,200),(2,0)]*3+[(20,2000)])
            self.assertEqual(a['grossCommandedDegrees'],106+before)
            self.assertEqual(a['netDegrees'],-50+before)
        default=experiment();omitted=copy.deepcopy(default);del omitted['preWipeReliefDegrees']
        self.assertEqual(M.stages_for(default,dict(path='/review',sha256=H),1.1,1),M.stages_for(omitted,dict(path='/review',sha256=H),1.1,1))
        for key,values in [('conditioningDwellMilliseconds',[True,200.0,0,201,2001]),('preWipeReliefDegrees',[True,2.0,0,5,40])]:
            for value in values:
                e=experiment();e[key]=value
                with self.assertRaises(ValueError):M.stages_for(e,dict(path='/review',sha256=H),1.1,1)
        for mode in ('coupon','transfer-preparation'):
            with tempfile.TemporaryDirectory() as d:
                args=self.fixture(d);e=experiment(4,2);e.update(mode=mode,dwellMilliseconds=200,conditioningDwellMilliseconds=2000,preWipeReliefDegrees=2)
                if mode=='transfer-preparation':e.update(targetsXY=e['targetsXY'][:2],maximumTransferElapsedMilliseconds=120000)
                Path(args.experiment).write_text(json.dumps(e))
                review=json.loads(Path(args.review).read_text());review['experimentEvidence']=M.WIPE.evidence(args.experiment)
                Path(args.review).write_text(json.dumps(review))
                profile=json.loads(Path(args.profile).read_text());profile['measurementEvidence']=M.WIPE.evidence(args.review)
                Path(args.profile).write_text(json.dumps(profile))
                recipe=M.build(args)
                self.assertEqual(recipe['bAccounting']['grossCommandedDegrees'],108 if mode=='coupon' else 64)

    def test_explicit_transfer_preparation_stops_after_conditioning_retract_lift(self):
        e=experiment(4,2); e.update(mode='transfer-preparation',maximumTransferElapsedMilliseconds=120000)
        e['targetsXY']=e['targetsXY'][:2]
        stages,poses,accounting=M.stages_for(e,dict(path='/review',sha256=H),1.1,1)
        self.assertEqual([s['axis'] for s in stages[-3:]],['B','B','Z'])
        self.assertEqual([poses[-2]['B']-poses[-3]['B'], poses[-3]['B']-poses[-4]['B']],[2,-20])
        self.assertEqual(accounting['grossCommandedDegrees'],82)
        self.assertEqual(accounting['netDegrees'],-38)
        self.assertEqual(poses[-1]['Z'],53.25)
        for edit in (lambda v:v.update(maximumTransferElapsedMilliseconds=True),
                     lambda v:v.update(maximumTransferElapsedMilliseconds=300001),
                     lambda v:v.update(maximumTransferElapsedMilliseconds=0),
                     lambda v:v.update(mode='unknown'),lambda v:v.update(testWorkRawZ=[58]*3)):
            bad=copy.deepcopy(e);edit(bad)
            with self.assertRaises(ValueError):M.stages_for(bad,dict(path='/review',sha256=H),1.1,1)
        for wait in (0,200,500):
            with tempfile.TemporaryDirectory() as d:
                e['retractDwellMilliseconds']=wait;e['idleReliefDegrees']=40
                args=self.fixture(d);Path(args.experiment).write_text(json.dumps(e))
                review=json.loads(Path(args.review).read_text());review['experimentEvidence']=M.WIPE.evidence(args.experiment)
                Path(args.review).write_text(json.dumps(review))
                profile=json.loads(Path(args.profile).read_text());profile['measurementEvidence']=M.WIPE.evidence(args.review)
                Path(args.profile).write_text(json.dumps(profile))
                recipe=M.build(args)
                self.assertEqual(recipe['bAccounting']['grossCommandedDegrees'],82)
                self.assertEqual(recipe['bAccounting']['netDegrees'],-38)
                self.assertEqual(recipe['stages'][-2]['dwellMilliseconds'],wait)
                self.assertEqual(recipe['stages'][-1]['axis'],'Z')

    def test_low_doses_and_selected_retraction_restore_accounting(self):
        for dose in (2, 3, 4, 6, 12, 20):
            for retract in (2, 3, 4, 6):
                with self.subTest(dose=dose, retract=retract):
                    e = experiment(dose, retract)
                    stages, poses, accounting = M.stages_for(e, dict(path='/review', sha256=H), 1.1, 1)
                    strokes = [(right['B']-left['B'], stages[i]['dwellMilliseconds'])
                               for i, (left, right) in enumerate(zip(poses, poses[1:])) if stages[i]['axis']=='B']
                    forward = [(-6,0),(-6,2000)] if dose==12 else [(-dose,2000)]
                    self.assertEqual(strokes, [(-20,0),(-20,2000),(20,1000),(-20,2000),(retract,0)]
                                     + ([(-retract,0)]+forward+[(retract,0)])*3+[(20,2000)])
                    self.assertEqual(accounting['grossCommandedDegrees'],100+3*dose+7*retract)
                    self.assertEqual(accounting['netDegrees'],-20+retract-3*dose)
        for dose, retract in ((True,2),(2,True),(2.0,2),(2,4.0),(1,2),(2,5)):
            with self.assertRaises(ValueError):
                M.stages_for(experiment(dose,retract),dict(path='/review',sha256=H),1.1,1)
        for dose, retract in ((2,2),(3,3),(4,4),(2,4)):
            with tempfile.TemporaryDirectory() as d:
                args = self.fixture(d)
                Path(args.experiment).write_text(json.dumps(experiment(dose,retract)))
                review=json.loads(Path(args.review).read_text()); review['experimentEvidence']=M.WIPE.evidence(args.experiment)
                Path(args.review).write_text(json.dumps(review))
                profile=json.loads(Path(args.profile).read_text()); profile['measurementEvidence']=M.WIPE.evidence(args.review)
                Path(args.profile).write_text(json.dumps(profile))
                recipe=M.build(args)
                self.assertEqual(recipe['bAccounting']['grossCommandedDegrees'],100+3*dose+7*retract)

    def test_optional_test_heights_preserve_clearance_accounting_and_gap_origin(self):
        e = experiment()
        baseline = M.stages_for(e, dict(path='/review', sha256=H), 1.1, 1)
        e['testWorkRawZ'] = [58.25]*3
        self.assertEqual(M.stages_for(e, dict(path='/review', sha256=H), 1.1, 1), baseline)
        e['testWorkRawZ'] = [58.0, 58.15, 58.25]
        stages, poses, accounting = M.stages_for(e, dict(path='/review', sha256=H), 1.1, 1)
        self.assertEqual(accounting, baseline[2])
        self.assertEqual(len(stages), len(baseline[0]))
        working_z = [s['target'] for s in stages if s['axis'] == 'Z' and s['target'] != 53.25]
        self.assertEqual(working_z, [58.25, 58.0, 58.15, 58.25])
        for i, stage in enumerate(stages):
            if stage['axis'] == 'Z':
                self.assertLessEqual(abs(stage['target']-poses[i]['Z']), 5)
            if stage['axis'] in ('X', 'Y') and not stage.get('wipeReview'):
                self.assertEqual(poses[i]['Z'], 53.25)
            if stage['axis'] == 'B':
                self.assertAlmostEqual(stage['estimatedGapMm'], 1.1+58.25-poses[i]['Z'])
        for invalid in (None, [], [58]*2, [58]*4, [True,58,58], [float('nan'),58,58],
                        [float('inf'),58,58], [58.001,58,58], [58.26,58,58], [53.25,58,58]):
            e['testWorkRawZ'] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                M.stages_for(e, dict(path='/review', sha256=H), 1.1, 1)

    def test_height_sweep_passes_offline_gate_and_keeps_authored_evidence_required(self):
        with tempfile.TemporaryDirectory() as d:
            args = self.fixture(d)
            e = json.loads(Path(args.experiment).read_text()); e['testWorkRawZ'] = [58.0,58.15,58.25]
            Path(args.experiment).write_text(json.dumps(e))
            with self.assertRaises(ValueError): M.build(args)
            review = json.loads(Path(args.review).read_text()); review['experimentEvidence'] = M.WIPE.evidence(args.experiment)
            Path(args.review).write_text(json.dumps(review))
            with self.assertRaises(ValueError): M.build(args)
            profile = json.loads(Path(args.profile).read_text()); profile['measurementEvidence'] = M.WIPE.evidence(args.review)
            Path(args.profile).write_text(json.dumps(profile))
            result = M.build(args)
            self.assertEqual(result['rawBounds']['Z'], dict(min=53.25,max=58.25))
            self.assertEqual(result['bAccounting']['grossCommandedDegrees'],139)
            self.assertEqual([s['target'] for s in result['stages'] if s['axis']=='Z' and s['target']!=53.25],
                             [58.25,58.0,58.15,58.25])
            review['rawZRange'] = [53.25,58.15]
            Path(args.review).write_text(json.dumps(review))
            profile['measurementEvidence'] = M.WIPE.evidence(args.review)
            Path(args.profile).write_text(json.dumps(profile))
            with self.assertRaises(ValueError): M.build(args)

    def test_twelve_degree_dose_is_two_six_degree_stages_with_one_dwell(self):
        e = experiment(12, 3)
        stages, poses, accounting = M.stages_for(e, dict(path='/review', sha256=H), 1.1, 1)
        self.assertEqual(len(stages), 36)
        self.assertEqual(accounting['grossCommandedDegrees'], 157)
        self.assertEqual(accounting['netDegrees'], -53)
        b = [(right['B']-left['B'], stages[i]['dwellMilliseconds']) for i, (left, right) in enumerate(zip(poses, poses[1:])) if stages[i]['axis'] == 'B']
        self.assertEqual(b, [(-20,0),(-20,2000),(20,1000),(-20,2000),(3,0)]+[(-3,0),(-6,0),(-6,2000),(3,0)]*3+[(20,2000)])

    def test_optional_forward_dwell_defaults_and_only_follows_complete_doses(self):
        for dose in (6, 12, 20):
            for dwell in (200, 500, 2000, None):
                e = experiment(dose, 3)
                if dwell is None:
                    del e['dwellMilliseconds']
                else:
                    e['dwellMilliseconds'] = dwell
                expected = 2000 if dwell is None else dwell
                stages, poses, accounting = M.stages_for(e, dict(path='/review', sha256=H), 1.1, 1)
                values = [(right['B']-left['B'], stages[i]['dwellMilliseconds']) for i, (left, right) in enumerate(zip(poses, poses[1:])) if stages[i]['axis'] == 'B']
                split = [(-6,0),(-6,expected)] if dose == 12 else [(-dose,expected)]
                self.assertEqual(values, [(-20,0),(-20,2000),(20,1000),(-20,expected),(3,0)]+([(-3,0)]+split+[(3,0)])*3+[(20,2000)])
                self.assertEqual(accounting['forwardDwellMilliseconds'], expected)
                self.assertEqual(accounting['grossCommandedDegrees'],100+3*dose+21)
        for invalid in (0, 199, 201, 1000, 2001, 500.0, '500', True):
            e = experiment(); e['dwellMilliseconds'] = invalid
            with self.assertRaises(ValueError):
                M.stages_for(e, dict(path='/review', sha256=H), 1.1, 1)

    def test_sixty_degree_prime_preserves_wipe_lift_and_charges_all_three_chunks(self):
        e = experiment(20, 6); e['primeDegrees'] = 60
        stages, poses, accounting = M.stages_for(e, dict(path='/review',sha256=H),1.1,1)
        self.assertEqual(len(stages),34)
        self.assertEqual(accounting['grossCommandedDegrees'],222)
        self.assertEqual(accounting['netDegrees'],-94)
        self.assertEqual(accounting['primeDegrees'],60)
        self.assertEqual([s['axis'] for s in stages[:6]],['B','B','B','B','X','Z'])
        self.assertEqual([s['dwellMilliseconds'] for s in stages[:4]],[0,0,2000,1000])
        self.assertEqual([poses[i+1]['B']-poses[i]['B'] for i in range(4)],[-20,-20,-20,20])
        for i,s in enumerate(stages):
            if s['axis'] in ('X','Y') and poses[i]['Z'] != 53.25:
                self.assertEqual(i,4); self.assertTrue(s['wipeReview'])
        with tempfile.TemporaryDirectory() as d:
            args = self.fixture(d)
            Path(args.experiment).write_text(json.dumps(e))
            review = json.loads(Path(args.review).read_text()); review['experimentEvidence'] = M.WIPE.evidence(args.experiment)
            Path(args.review).write_text(json.dumps(review))
            profile = json.loads(Path(args.profile).read_text()); profile['measurementEvidence'] = M.WIPE.evidence(args.review)
            Path(args.profile).write_text(json.dumps(profile))
            result = M.build(args)
            self.assertEqual(len(result['stages']),34)
            self.assertEqual(result['bAccounting']['grossCommandedDegrees'],222)

    def test_unsafe_or_unreviewed_parameters_rejected(self):
        edits = [lambda e: e.update(doseDegrees=5), lambda e: e.update(retractDegrees=20),
                 lambda e: e.update(dwellMilliseconds=True), lambda e: e.update(primeDegrees=80),
                 lambda e: e.update(clearanceRawZ=52), lambda e: e['targetsXY'][0].update(Y=201),
                 lambda e: e['targetsXY'][1].update(X=120), lambda e: e['targetsXY'][1].update(X=float('nan')),
                 lambda e: e['targetsXY'][1].update(X=104.004), lambda e: e['targetsXY'].pop(), lambda e: e.update(scope='cleaned-ftp-demo')]
        for edit in edits:
            e = experiment(); edit(e)
            with self.assertRaises(ValueError):
                M.stages_for(e, dict(path='/review', sha256=H), 1.1, 1)
        with self.assertRaises(ValueError):
            M.stages_for(experiment(), {}, .5, .4)

    def fixture(self, directory):
        d = Path(directory); now = int(time.time()*1000)
        def save(name, value):
            p = d/name; p.write_text(json.dumps(value)+'\n'); return str(p)
        def stamp(ms): return datetime.datetime.fromtimestamp(ms/1000, datetime.timezone.utc).isoformat()
        exp = experiment(); raw = exp['startRaw']; epath = save('experiment.json', exp)
        image = d/'image.png'; image.write_bytes(b'\x89PNG\r\n\x1a\nsynthetic-only'); os.utime(image, ns=((now-2000)*1000000,)*2)
        review = dict(mode='wet', reviewedBy='synthetic-test', reviewedMs=now-1000,
                      rawZRange=[53.25, 58.25], experimentEvidence=M.WIPE.evidence(epath),
                      imageEvidence=M.WIPE.evidence(image), cleanTipImage=M.WIPE.evidence(image), priorTopImage=M.WIPE.evidence(image))
        rpath = save('review.json', review)
        profile = dict(provenance='commissioning-provisional', precisionCalibrated=False, flowCalibrated=False,
                       sessionId=SID, syringeId='synthetic', jvmStartMs=1, liveConfigurationSha256=H,
                       rawPose={k:raw[k] for k in ('X','Y','Z','A')}, estimatedGapMm=1.1, gapUncertaintyMm=1,
                       basis='Synthetic explicit uncertainty interval only', measurementEvidence=M.WIPE.evidence(rpath))
        ppath = save('profile.json', profile)
        poses = {name:dict(x=100, y=200, z=30, rotation=0) for name in ('N1','N2','top','bottom')}
        barrier = dict(status='completed-read-only-position-barrier', controllerPositionVerified=True,
                       noMotionCommandSubmitted=True, uncertainCompletion=False, request=dict(jvmStartMs=1),
                       liveConfigurationSha256=H, finishedAt=stamp(now-1000),
                       afterQuerySnapshot=dict(raw=raw, driver=raw, nativePoses=poses))
        bpath = save('barrier.json', barrier)
        dummy = save('carry-evidence.json', {'synthetic':True}); ce = M.WIPE.evidence(dummy)
        ledger = dict(schema=1, scope='signed-B-commissioning-strokes', status='verified', sessionId=SID,
                      syringeId='synthetic', primeLedgerSha256=ce['sha256'], carryoverSha256=ce['sha256'],
                      startB=-240, lastVerifiedB=-234, totalAbsoluteDegrees=6,
                      entries=[dict(requestId=RID, status='verified', startB=-240, targetB=-234, deltaDegrees=6, absoluteDegrees=6)])
        lpath = save('ledger.json', ledger)
        report = dict(id=RID, status='completed-commissioning-stroke-awaiting-observation', uncertainCompletion=False,
                      request=dict(id=RID, sessionId=SID, jvmStartMs=1, liveConfigurationSha256=H),
                      completedLedgerSha256=M.WIPE.evidence(lpath)['sha256'], finishedAt=stamp(now-3000))
        prior = save('prior.json', report)
        base = dict(sessionId=SID, syringeId='synthetic', jvmStartMs=1, liveConfigurationSha256=H,
                    primeLedgerSha256=ce['sha256'], carryoverSha256=ce['sha256'],
                    primeLedgerEvidence=ce, priorLedgerEvidence=ce, carryoverEvidence=ce)
        template = save('template.json', base)
        return SimpleNamespace(experiment=epath, template=template, barrier=bpath, profile=ppath, review=rpath,
                               image=str(image), previous_report=prior, ledger=lpath, output=str(d/'recipe.json'))

    def test_complete_recipe_passes_existing_offline_gate_and_does_not_write_request(self):
        with tempfile.TemporaryDirectory() as d:
            args = self.fixture(d); before = set(Path(d).iterdir()); result = M.build(args)
            self.assertEqual(set(Path(d).iterdir()), before)
            self.assertEqual(result['bAccounting']['grossCommandedDegrees'],139)
            self.assertEqual(result['rawBounds']['X'], dict(min=98,max=104))
            self.assertEqual(result['headClearanceBounds']['N2']['maxZ'],35.001)
            M.WIPE.write_exclusive(args.output,result)
            with self.assertRaises(FileExistsError): M.WIPE.write_exclusive(args.output,result)

    def test_3600_and_8400_preparer_hash_load_matching_travel_review_into_request_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            args = self.fixture(d)
            recipe = M.build(args); recipe_path = Path(d)/'recipe-input.json'
            M.WIPE.write_exclusive(recipe_path, recipe)
            def prepare(name):
                out = Path(d)/name
                with contextlib.redirect_stdout(io.StringIO()):
                    M.BATCH.prepare(SimpleNamespace(template=args.template,barrier=args.barrier,image=args.image,recipe=str(recipe_path),output=str(out)))
                return json.loads((out/'preview-request.json').read_text())
            for ceiling in (3600,8400):
                travel = Path(d)/f'travel-{ceiling}.json'; travel.write_text(json.dumps({'synthetic':'review only','ceiling':ceiling}))
                travel_ev = M.WIPE.evidence(travel)
                amendment = Path(d)/f'amendment-{ceiling}.json'
                amendment.write_text(json.dumps({'newMaximumAbsoluteDegrees':ceiling,'travelReviewEvidence':travel_ev}))
                base = json.loads(Path(args.template).read_text())
                base['budgetAmendmentEvidence'] = dict(M.WIPE.evidence(amendment),newMaximumAbsoluteDegrees=ceiling,travelReviewEvidence=travel_ev)
                Path(args.template).write_text(json.dumps(base))
                request = prepare(f'accepted-{ceiling}')
                self.assertIn(travel_ev,request['evidence'])
                base['budgetAmendmentEvidence']['travelReviewEvidence'] = dict(travel_ev,sha256='b'*64)
                Path(args.template).write_text(json.dumps(base))
                with self.assertRaises(ValueError): prepare(f'mismatch-{ceiling}')
                base['budgetAmendmentEvidence']['travelReviewEvidence'] = travel_ev
                Path(args.template).write_text(json.dumps(base))
                travel.write_text(json.dumps({'synthetic':'changed after review'}))
                with self.assertRaises(ValueError): prepare(f'changed-review-{ceiling}')

    def test_changed_experiment_or_ledger_and_stale_image_are_rejected(self):
        for changed in ('experiment', 'ledger', 'image'):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as d:
                args = self.fixture(d)
                if changed == 'image':
                    past = time.time()-301; os.utime(args.image,(past,past))
                else:
                    p = Path(getattr(args,changed)); value=json.loads(p.read_text())
                    value['doseDegrees' if changed=='experiment' else 'lastVerifiedB']=20
                    p.write_text(json.dumps(value))
                with self.assertRaises(ValueError): M.build(args)
                self.assertFalse(Path(args.output).exists())


if __name__ == '__main__':
    unittest.main()
