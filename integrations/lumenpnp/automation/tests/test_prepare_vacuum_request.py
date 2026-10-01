import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timezone
from test_prepare_survey_request import report, NOW

spec = importlib.util.spec_from_file_location('vacuum_prepare', Path(__file__).resolve().parents[1]/'paste/prepare-vacuum-request.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def iso(ms):
    return datetime.fromtimestamp(ms/1000, timezone.utc).isoformat()

class VacuumRequestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.image=self.root/'image.png'; self.source=self.root/'report.json'
        self.image.write_bytes(b'\x89PNG\r\n\x1a\nfixture')
        os.utime(self.image, ns=((NOW-500)*1000000,)*2)
        self.r=report(); self.r['finishedAt']=iso(NOW-1000)
    def prepare(self):
        self.source.write_text(json.dumps(self.r))
        return m.prepare_baseline(self.source,self.image,'reviewer','NT1',True,NOW)
    def test_current_stream_request_has_no_inferred_threshold(self):
        q=self.prepare()
        self.assertEqual(q['sampleCountPerPhase'],20); self.assertEqual(q['settleMs'],2000)
        self.assertNotIn('expectedEmptyMean',q); self.assertEqual(q['expectedRaw'],self.r['afterQuerySnapshot']['raw'])
    def test_old_failed_or_latched_state_refused(self):
        for change in ({'finishedAt':iso(NOW-300001)}, {'uncertainCompletion':True}, {'status':m.survey.AUDIT_SUCCESS}):
            original=self.r.copy(); self.r.update(change)
            with self.assertRaises((ValueError,KeyError)): self.prepare()
            self.r=original
    def baseline(self):
        q=self.prepare(); b={'finalOffAcknowledged':True}
        for phase,values,start in [('off',[255]*20,2000),('on',[225,226,227,226]*5,6000)]:
            b[phase]=[{'value':v,'raw':str(v),'elapsedMs':start+i*100} for i,v in enumerate(values)]
            b[phase+'Summary']={'count':20,'mean':sum(values)/20,'min':min(values),'max':max(values),'spread':max(values)-min(values),'acceptanceEstablished':False}
        return {'status':'completed-free-air-baseline-awaiting-review','motionSubmitted':False,'controllerPositionVerified':True,'normalOffAcknowledged':True,'uncertainCompletion':False,'physicalAcceptanceEstablished':False,'finishedAt':iso(NOW),'request':q,'baseline':b}
    def test_distribution_reports_spread_two_without_acceptance(self):
        r=self.baseline(); self.source.write_text(json.dumps(r)); s=m.summarize_baseline(self.source,NOW)
        self.assertEqual(s['phases']['on']['spread'],2); self.assertEqual(s['phases']['on']['mean'],226)
        self.assertFalse(s['acceptanceEstablished']); self.assertFalse(s['contactThresholdSelected'])
    def test_summary_tampering_and_bad_time_refused(self):
        for mutate in [lambda r:r['baseline']['onSummary'].update(mean=232.25),lambda r:r['baseline']['on'][2].update(elapsedMs=0),lambda r:r.update(normalOffAcknowledged=False)]:
            r=self.baseline();mutate(r);self.source.write_text(json.dumps(r))
            with self.assertRaises(ValueError):m.summarize_baseline(self.source,NOW)

    def test_probe_requires_conservative_review_and_cannot_reuse_stale_stream(self):
        import hashlib
        import subprocess
        baseline=self.baseline(); baseline['afterQuerySnapshot']=self.r['afterQuerySnapshot']
        bp=self.root/'baseline.json';bp.write_text(json.dumps(baseline))
        barrier=self.r.copy();barrier.update(status='completed-read-only-position-barrier',noMotionCommandSubmitted=True,reported=self.r['after']['reported'],liveConfigurationSha256=self.r['request']['liveConfigurationSha256'])
        barrier['request']={**self.r['request'],'scope':'read-only-native-position-barrier'}
        barrierp=self.root/'barrier.json';barrierp.write_text(json.dumps(barrier))
        template=json.loads((m.HERE/'vacuum-probe-native.pending.json').read_text())
        review={k:template[k] for k in ('targetSurfaceIdentity','reviewRecord','jointInterval','nativeZConfiguration','contract')}
        review.update(scope='explicit-current-stream-and-probe-envelope-review',baselineSha256=hashlib.sha256(bp.read_bytes()).hexdigest(),operator='reviewer',reviewed=True,reviewedMs=NOW)
        review.update(targetSurfaceIdentity='synthetic receiver', reviewRecord='synthetic offline test', jointInterval={'minRawZ':19,'maxRawZ':20,'reviewedForCurrentPose':True,'reviewRecord':'synthetic'}, nativeZConfiguration={k:(False if k.endswith('Enabled') else 0) for k in template['nativeZConfiguration']})
        review['contract'].update(expectedEmptyMean=226,responseDirection='decrease',startZmm=20,floorZmm=19,maxDescentMm=1,maxDurationMs=60000)
        for key in ('stationaryEvidence','targetEvidence','jointEnvelopeEvidence'):review[key+'Path']=str(self.image)
        for key in ('operatorVerifiedEmptyFreeAirBaseline','operatorVerifiedProbeTarget','operatorVerifiedJointEnvelope','bothHeadsClearAlongEnvelope','motionAreaClear','noHeldPartsObserved','n2Quarantined'):review[key]=True
        rp=self.root/'review.json';rp.write_text(json.dumps(review))
        with self.assertRaises(subprocess.CalledProcessError) as failure:m.prepare_probe(barrierp,bp,rp,'reviewer','NT1',NOW)
        self.assertIn('current stream exceeds conservative noise/pump bounds',failure.exception.stderr)
        # A newly measured stable mean different from the old232.25 succeeds.
        for sample in baseline['baseline']['on']:sample.update(raw='232',value=232)
        baseline['baseline']['onSummary'].update(mean=232,min=232,max=232,spread=0)
        bp.write_text(json.dumps(baseline));review['baselineSha256']=hashlib.sha256(bp.read_bytes()).hexdigest()
        review['contract']['expectedEmptyMean']=232;rp.write_text(json.dumps(review))
        barrier['afterQuerySnapshot']['driver']=barrier['reported'];barrierp.write_text(json.dumps(barrier))
        q=m.prepare_probe(barrierp,bp,rp,'reviewer','NT1',NOW)
        self.assertEqual(q['contract']['expectedEmptyMean'],232)
        self.assertEqual(q['baselineContractEvidence']['sha256'],review['baselineSha256'])
        self.assertEqual(q['speedFraction'],0.05)
        fast=m.prepare_probe(barrierp,bp,rp,'reviewer','NT1',NOW,speed_fraction=1)
        self.assertEqual(fast['speedFraction'],1.0)
        with self.assertRaises(ValueError):
            m.prepare_probe(barrierp,bp,rp,'reviewer','NT1',NOW,speed_fraction=0.5)
        baseline['finishedAt']=iso(NOW-300001);bp.write_text(json.dumps(baseline))
        with self.assertRaises(ValueError):m.prepare_probe(barrierp,bp,rp,'reviewer','NT1',NOW)
