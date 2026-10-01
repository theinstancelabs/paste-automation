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
        edits = [lambda e: e.update(doseDegrees=3), lambda e: e.update(retractDegrees=20),
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

    def test_3600_preparer_hash_loads_matching_travel_review_into_request_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            args = self.fixture(d)
            recipe = M.build(args); recipe_path = Path(d)/'recipe-input.json'
            M.WIPE.write_exclusive(recipe_path, recipe)
            travel = Path(d)/'travel.json'; travel.write_text(json.dumps({'synthetic':'review only'}))
            travel_ev = M.WIPE.evidence(travel)
            amendment = Path(d)/'amendment.json'
            amendment.write_text(json.dumps({'newMaximumAbsoluteDegrees':3600,'travelReviewEvidence':travel_ev}))
            base = json.loads(Path(args.template).read_text())
            base['budgetAmendmentEvidence'] = dict(M.WIPE.evidence(amendment),newMaximumAbsoluteDegrees=3600,travelReviewEvidence=travel_ev)
            Path(args.template).write_text(json.dumps(base))
            def prepare(name):
                out = Path(d)/name
                with contextlib.redirect_stdout(io.StringIO()):
                    M.BATCH.prepare(SimpleNamespace(template=args.template,barrier=args.barrier,image=args.image,recipe=str(recipe_path),output=str(out)))
                return json.loads((out/'preview-request.json').read_text())
            request = prepare('accepted')
            self.assertIn(travel_ev,request['evidence'])
            base['budgetAmendmentEvidence']['travelReviewEvidence'] = dict(travel_ev,sha256='b'*64)
            Path(args.template).write_text(json.dumps(base))
            with self.assertRaises(ValueError): prepare('mismatch')
            base['budgetAmendmentEvidence']['travelReviewEvidence'] = travel_ev
            Path(args.template).write_text(json.dumps(base))
            travel.write_text(json.dumps({'synthetic':'changed after review'}))
            with self.assertRaises(ValueError): prepare('changed-review')

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
