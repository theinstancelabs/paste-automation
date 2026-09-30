#!/usr/bin/env python3
"""Offline request preparation and stream summaries. Never dispatches or infers contact."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import time
import uuid
from datetime import datetime

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('survey_prepare', HERE / 'prepare-survey-request.py')
survey = importlib.util.module_from_spec(spec)
spec.loader.exec_module(survey)


def bound(path):
    path = Path(path).resolve(strict=True)
    data = path.read_bytes()
    return json.loads(data), {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest()}


def timestamp(value):
    return int(datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp() * 1000)


def fresh(value, now, label):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= now-value <= 300000:
        raise ValueError(label + ' must be within five minutes')


def image(path, now):
    path = Path(path).resolve(strict=True)
    before = path.stat()
    data = path.read_bytes()
    after = path.stat()
    if (before.st_mtime_ns, before.st_size, before.st_ino) != (after.st_mtime_ns, after.st_size, after.st_ino):
        raise ValueError('Image changed during read')
    if not (data.startswith(b'\x89PNG\r\n\x1a\n') or data.startswith(b'\xff\xd8\xff')):
        raise ValueError('Reviewed image must be PNG or JPEG')
    captured = after.st_mtime_ns // 1000000
    fresh(captured, now, 'Image mtime')
    return {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(), 'capturedMs': captured}


def native_validate(policy, request):
    # Pure policy only; no adapter or machine API is evaluated.
    subprocess.run(['node', '-e', "const p=require(process.argv[1]);const q=JSON.parse(require('fs').readFileSync(0,'utf8'));p.validate(q,q.createdMs,q.jvmStartMs);", str(HERE / policy)], input=json.dumps(request), text=True, check=True, capture_output=True)


def prepare_baseline(report_path, image_path, operator, tip_id, reviewed, now=None):
    now = time.time_ns() // 1000000 if now is None else now
    if reviewed is not True or not operator.strip() or not tip_id.strip():
        raise ValueError('Explicit empty/free-air/both-head clearance review, operator and installed tip required')
    report, evidence = bound(report_path)
    if report.get('status') == survey.AUDIT_SUCCESS:
        raise ValueError('Latched audit is not a released current state')
    _, jvm, digest, raw, driver, poses = survey.source_snapshot(report)
    fresh(timestamp(report['finishedAt']), now, 'Verified state')
    if jvm > now:
        raise ValueError('Future JVM')
    q = json.loads((HERE / 'vacuum-baseline.pending.json').read_text())
    q.update(description='Offline prepared current-pose stationary stream; no pressure acceptance inferred.', id=str(uuid.uuid4()), createdMs=now, jvmStartMs=jvm, operator=operator.strip(), expectedLeftTipId=tip_id.strip(), liveConfigurationSha256=digest, expectedRaw=raw, expectedDriver=driver, expectedNativePoses=poses, stationaryEvidence=image(image_path, now), sourceEvidence=evidence, operatorVerifiedFreeAir=True, emptyNozzlesObserved=True, bothHeadsClear=True, motionAreaClear=True, sampleCountPerPhase=20, settleMs=2000, sampleIntervalMs=100, maxDurationMs=60000)
    native_validate('vacuum-baseline.cjs', q)
    return q


def summarize_baseline(path, now=None):
    now = time.time_ns() // 1000000 if now is None else now
    r, evidence = bound(path)
    if (r.get('status') != 'completed-free-air-baseline-awaiting-review' or r.get('motionSubmitted') is not False or r.get('controllerPositionVerified') is not True or r.get('normalOffAcknowledged') is not True or r.get('uncertainCompletion') is not False or r.get('error') or r.get('auditIncomplete')):
        raise ValueError('Only a successful stationary baseline with normal OFF may be reviewed')
    fresh(timestamp(r['finishedAt']), now, 'Baseline')
    q, b = r['request'], r['baseline']
    native_validate('vacuum-baseline.cjs', q)
    if b.get('finalOffAcknowledged') is not True:
        raise ValueError('Final OFF missing')
    result = {'schema': 1, 'scope': 'observed-free-air-distribution-only', 'sourceEvidence': evidence, 'jvmStartMs': q['jvmStartMs'], 'liveConfigurationSha256': q['liveConfigurationSha256'], 'expectedLeftTipId': q['expectedLeftTipId'], 'acceptanceEstablished': False, 'contactThresholdSelected': False, 'motionAuthorized': False, 'phases': {}}
    for phase in ('off', 'on'):
        samples = b[phase]
        if len(samples) != q['sampleCountPerPhase']:
            raise ValueError('Incomplete phase stream')
        values, times = [], []
        for s in samples:
            v, elapsed = s['value'], s['elapsedMs']
            if type(v) is not int or not 0 <= v <= 255 or str(s['raw']).strip() != str(v):
                raise ValueError('Malformed sensor byte')
            if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0 or elapsed > q['maxDurationMs'] or (times and elapsed <= times[-1]):
                raise ValueError('Invalid sample timeline')
            values.append(v); times.append(elapsed)
        mean = sum(values) / len(values)
        summary = {'count': len(values), 'mean': mean, 'min': min(values), 'max': max(values), 'spread': max(values)-min(values)}
        if any(b[phase+'Summary'].get(k) != v for k, v in summary.items()):
            raise ValueError('Summary disagrees with actual stream')
        summary.update(sampleStandardDeviation=(sum((v-mean)**2 for v in values)/(len(values)-1))**.5, firstHalfMean=sum(values[:len(values)//2])/(len(values)//2), secondHalfMean=sum(values[len(values)//2:])/(len(values)-len(values)//2), histogram={str(v): values.count(v) for v in sorted(set(values))}, values=values, elapsedMs=times)
        result['phases'][phase] = summary
    if result['phases']['on']['elapsedMs'][0] <= result['phases']['off']['elapsedMs'][-1]:
        raise ValueError('Phase ordering invalid')
    result['observedPumpResponseDelta'] = result['phases']['off']['mean']-result['phases']['on']['mean']
    return result


def prepare_probe(barrier_path, baseline_path, review_path, operator, tip_id, now=None):
    """Explicit reviewed contract only; current native validators remain authoritative."""
    now = time.time_ns() // 1000000 if now is None else now
    barrier, barrier_evidence = bound(barrier_path)
    if barrier.get('status') != 'completed-read-only-position-barrier':
        raise ValueError('Probe requires a fresh successful position barrier')
    _, jvm, digest, raw, driver, poses = survey.source_snapshot(barrier)
    fresh(timestamp(barrier['finishedAt']), now, 'Position barrier')
    baseline, baseline_evidence = bound(baseline_path)
    observed = summarize_baseline(baseline_path, now)
    if observed['sourceEvidence']['sha256'] != baseline_evidence['sha256']:
        raise ValueError('Baseline changed between binding and stream review')
    review, review_evidence = bound(review_path)
    if (review.get('scope') != 'explicit-current-stream-and-probe-envelope-review'
            or review.get('baselineSha256') != baseline_evidence['sha256']
            or review.get('operator') != operator or review.get('reviewed') is not True):
        raise ValueError('Explicit named review must bind this new baseline stream')
    fresh(review['reviewedMs'], now, 'Probe review')
    if observed['jvmStartMs'] != jvm or observed['liveConfigurationSha256'] != digest or observed['expectedLeftTipId'] != tip_id:
        raise ValueError('Baseline must match current JVM/config/tip')
    snap = baseline['afterQuerySnapshot']
    for axis in survey.AXES:
        if abs(snap['raw'][axis]-raw[axis]) > .0001:
            raise ValueError('Collect baseline at this exact probe pose')
    if baseline['request']['sampleCountPerPhase'] != 20:
        raise ValueError('New complete 20-sample-per-phase baseline required')
    if review['contract']['expectedEmptyMean'] != observed['phases']['on']['mean']:
        raise ValueError('Reviewed empty mean must come from actual new stream')
    q = json.loads((HERE/'vacuum-probe-native.pending.json').read_text())
    q.update(description='Prepared offline from explicit new-stream and envelope review; native validator remains authoritative.', id=str(uuid.uuid4()), createdMs=now, jvmStartMs=jvm, operator=operator, expectedLeftTipId=tip_id, liveConfigurationSha256=digest, expectedRaw=raw, expectedDriver=driver, expectedNativePoses=poses, baselineContractEvidence={**baseline_evidence, 'reviewedMs':review['reviewedMs']}, barrierEvidence=barrier_evidence, reviewEvidence=review_evidence)
    for key in ('targetSurfaceIdentity', 'reviewRecord', 'jointInterval', 'nativeZConfiguration', 'contract'):
        q[key] = review[key]
    for key in ('stationaryEvidence', 'targetEvidence', 'jointEnvelopeEvidence'):
        q[key] = image(review[key+'Path'], now)
    for key in ('operatorVerifiedEmptyFreeAirBaseline','operatorVerifiedProbeTarget','operatorVerifiedJointEnvelope','bothHeadsClearAlongEnvelope','motionAreaClear','noHeldPartsObserved','n2Quarantined'):
        if review.get(key) is not True:
            raise ValueError('Missing explicit '+key)
        q[key] = True
    native_validate('vacuum-probe-native.cjs', q)
    # Validate the actual bound stream separately; never infer acceptance from its mean.
    payload = {'q':q, 'record':baseline, 'sha256':baseline_evidence['sha256']}
    subprocess.run(['node','-e',"const p=require(process.argv[1]);const x=JSON.parse(require('fs').readFileSync(0,'utf8'));p.validateBaselineReference(x.record,x.q,x.sha256);p.barrier(x.barrier,x.q,x.q.createdMs,x.q.jvmStartMs);",str(HERE/'vacuum-probe-native.cjs')], input=json.dumps({**payload,'barrier':barrier}),text=True,check=True,capture_output=True)
    return q


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='mode', required=True)
    b = sub.add_parser('baseline')
    b.add_argument('--report', required=True); b.add_argument('--image', required=True)
    b.add_argument('--operator', required=True); b.add_argument('--tip-id', required=True)
    b.add_argument('--reviewed-empty-free-air-and-clearance', action='store_true')
    b.add_argument('--output', type=Path, required=True)
    v = sub.add_parser('probe'); v.add_argument('--barrier', required=True); v.add_argument('--baseline', required=True); v.add_argument('--review', required=True); v.add_argument('--operator', required=True); v.add_argument('--tip-id', required=True); v.add_argument('--output', type=Path, required=True)
    s = sub.add_parser('summarize'); s.add_argument('--report', required=True); s.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.mode == 'baseline':
        result = prepare_baseline(a.report, a.image, a.operator, a.tip_id, a.reviewed_empty_free_air_and_clearance)
    elif a.mode == 'probe':
        result = prepare_probe(a.barrier, a.baseline, a.review, a.operator, a.tip_id)
    else:
        result = summarize_baseline(a.report)
    with a.output.open('x') as f:
        json.dump(result, f, indent=2, allow_nan=False); f.write('\n')
    print(a.output)


if __name__ == '__main__':
    main()
