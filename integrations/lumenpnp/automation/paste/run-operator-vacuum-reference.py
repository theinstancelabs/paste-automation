#!/usr/bin/env python3
"""Prepare, and optionally run, a fresh N1 vacuum surface-reference check.

Offline by default. Execution uses only the existing stationary baseline and
bounded probe OpenPnP scripts. A vacuum response is recorded as a candidate,
never as physical contact or calibrated surface Z.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / 'automation/paste/prepare-vacuum-request.py'

def load(path):
    return json.loads(Path(path).read_text())

def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')

def evidence(path):
    p = Path(path).resolve(strict=True)
    b = p.read_bytes()
    return {'path': str(p), 'sha256': hashlib.sha256(b).hexdigest()}

def wait_report(path, good_status, timeout=90):
    end = time.monotonic() + timeout
    p = Path(path)
    while time.monotonic() < end:
        if p.is_file():
            try:
                r = load(p)
            except (json.JSONDecodeError, OSError):
                time.sleep(.15)
                continue
            if r.get('error') or str(r.get('status', '')).startswith(('failed', 'executor-quarantined')):
                raise RuntimeError(f'{p}: {r.get("status")}: {r.get("error")}')
            if r.get('status') == good_status:
                return r
            if r.get('status') in ('stopped-policy-vacuum-off-position-verified',
                                   'completed-seal-candidate-held-at-z-awaiting-physical-review'):
                return r
        time.sleep(.15)
    raise TimeoutError(f'No verified terminal report at {p}; do not replay')

def dispatch(action):
    subprocess.run([sys.executable, str(ROOT/'automation/scripts/run_reviewed_action.py'),
                    action, '--confirmed'], cwd=ROOT, check=True)

def validate_baseline_policy(report, summary):
    off, on = summary['phases']['off'], summary['phases']['on']
    checks = {
        'offCount20': off.get('count') == 20,
        'onCount20': on.get('count') == 20,
        'offSpreadAtMost1': off.get('spread') <= 1,
        'onSpreadAtMost1': on.get('spread') <= 1,
        'pumpResponseAtLeast10': summary.get('observedPumpResponseDelta') >= 10,
        'normalOffAcknowledged': report.get('baseline',{}).get('finalOffAcknowledged') is True,
        'controllerPositionVerified': report.get('controllerPositionVerified') is True,
        'noMotionSubmitted': report.get('motionSubmitted') is False,
    }
    failed = [k for k,v in checks.items() if not v]
    if failed:
        raise ValueError('Fresh baseline did not pass explicit policy checks: '+', '.join(failed))
    return {'scope':'automated-fresh-vacuum-baseline-policy-check',
            'checkedAtMs':time.time_ns()//1_000_000,
            'reviewedBy':'automation: run-operator-vacuum-reference.py',
            'humanReviewClaimed':False, 'checks':checks,
            'observed':{'off':off,'on':on,'pumpResponseDelta':summary['observedPumpResponseDelta']},
            'meaning':'Fresh free-air pump/sensor policy check only; no surface contact or calibration proof.'}

def fresh_file(path, now_ms, label):
    p = Path(path).resolve(strict=True)
    ms = p.stat().st_mtime_ns // 1_000_000
    if ms > now_ms or now_ms-ms > 300_000:
        raise ValueError(f'{label} must be fresh within five minutes')
    return p, ms

def prepare(args):
    source_path = Path(args.source).resolve(strict=True)
    image_path, image_ms = fresh_file(args.image, time.time_ns()//1_000_000, 'Overview image')
    source = load(source_path)
    if (source.get('status') != 'completed-read-only-position-barrier'
            or source.get('controllerPositionVerified') is not True
            or source.get('noMotionCommandSubmitted') is not True
            or source.get('uncertainCompletion') is not False
            or source.get('error') or not source.get('afterQuerySnapshot')):
        raise ValueError('--source must be a successful verified read-only position barrier')
    request = source.get('request') or {}
    now = time.time_ns()//1_000_000
    # Native vacuum request preparation is intentionally same-session and fresh.
    import datetime
    finished = datetime.datetime.fromisoformat(source['finishedAt'].replace('Z','+00:00')).timestamp()*1000
    if not 0 <= now-finished <= 300_000:
        raise ValueError('--source barrier must be no older than five minutes')
    snap = source['afterQuerySnapshot']
    start = float(snap['raw']['Z'])
    floor = float(args.floor)
    if not math.isfinite(floor) or floor >= start or start-floor > 2.0+1e-9:
        raise ValueError('--floor must be below current Z by at most 2.00 mm')
    steps = (start-floor)/0.05
    if abs(steps-round(steps)) > 1e-7 or steps > 40:
        raise ValueError('--floor must be on the 0.05 mm grid and within 40 increments')
    review = load(args.review)
    operator = review.get('operator')
    if not isinstance(operator, str) or not operator.strip():
        raise ValueError('--review must name the reviewing operator')
    reviewed_ms = review.get('reviewedMs')
    if type(reviewed_ms) not in (int, float) or not math.isfinite(reviewed_ms) or not 0 <= now-reviewed_ms <= 300_000:
        raise ValueError('--review must have a fresh reviewedMs timestamp')
    for key in ('operatorVerifiedEmptyFreeAirBaseline','operatorVerifiedProbeTarget',
                'operatorVerifiedJointEnvelope','bothHeadsClearAlongEnvelope',
                'motionAreaClear','noHeldPartsObserved','n2Quarantined',
                'nativeZConfigurationReviewed'):
        if review.get(key) is not True:
            raise ValueError(f'--review must explicitly set {key}=true')
    record = review.get('reviewRecord')
    interval = review.get('jointInterval')
    if not isinstance(record, str) or not record.strip() or not isinstance(interval, dict):
        raise ValueError('--review must provide reviewRecord and jointInterval')
    if (interval.get('reviewedForCurrentPose') is not True
            or interval.get('minRawZ') != floor or interval.get('maxRawZ') != start
            or not isinstance(interval.get('reviewRecord'), str)
            or not interval['reviewRecord'].strip()):
        raise ValueError('--review jointInterval must explicitly cover floor through current Z')
    if args.execute and not args.operator_home_confirmed:
        raise ValueError('--execute requires --operator-home-confirmed for the fresh read-only barrier helper')
    if not isinstance(args.target, str) or not args.target.strip():
        raise ValueError('--target must identify the reviewed physical surface')
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out/'inputs').mkdir()
    shutil.copy2(source_path, out/'inputs/source-barrier.json')
    shutil.copy2(image_path, out/'inputs'/('overview'+image_path.suffix.lower()))
    shutil.copy2(Path(args.review).resolve(strict=True), out/'inputs/operator-review.json')

    # Reuse the repository's reviewed builders. They validate hashes, source
    # lineage, exact pose, sensor stream and the native policy contract.
    spec = importlib.util.spec_from_file_location('prepare_vacuum', PREP)
    prep = importlib.util.module_from_spec(spec); spec.loader.exec_module(prep)
    baseline_req = None
    baseline_req_path = out/'baseline-request.json'
    if not args.baseline_report:
        baseline_req = prep.prepare_baseline(source_path, image_path, operator, args.tip_id, True)
        save(baseline_req_path, baseline_req)
    if not args.execute:
        plan = {'offlineOnly': True, 'output': str(out),
                'baselineRequest': str(baseline_req_path) if baseline_req else None,
                'existingBaselineReport': str(Path(args.baseline_report).resolve()) if args.baseline_report else None,
                'nextActions': ['dispatch paste-vacuum-baseline', 'summarize its verified report',
                                'capture fresh manual-home read-only barrier',
                                'prepare and dispatch bounded probe'],
                'targetSurfaceIdentity': args.target, 'startRawZ': start, 'floorRawZ': floor,
                'maximumDescentMm': round(start-floor, 3), 'imageEvidence': evidence(image_path)}
        save(out/'plan.json', plan); print(json.dumps(plan, indent=2)); return

    # Fixed OpenPnP plan paths are backed up into the unique output directory.
    plans = ROOT/'automation/plans'
    plan_names = ('paste-vacuum-baseline-request.json','paste-position-barrier-request.json',
                  'paste-vacuum-probe-request.json')
    backup = out/'previous-plan-files'; backup.mkdir()
    for name in plan_names:
        p = plans/name
        if p.exists(): shutil.copy2(p, backup/name)
    if args.baseline_report:
        baseline_report_path = Path(args.baseline_report).resolve(strict=True)
        baseline_report = load(baseline_report_path)
        save(out/'baseline-report.json', baseline_report)
    else:
        save(plans/plan_names[0], baseline_req)
        baseline_report_path = ROOT/f"automation/evidence/paste-vacuum-baseline-{baseline_req['id']}/report.json"
        dispatch('paste-vacuum-baseline')
        baseline_report = wait_report(baseline_report_path, 'completed-free-air-baseline-awaiting-review')
    baseline_summary = prep.summarize_baseline(baseline_report_path)
    policy_review = validate_baseline_policy(baseline_report, baseline_summary)
    baseline_finished_ms = int(__import__('datetime').datetime.fromisoformat(
        baseline_report['finishedAt'].replace('Z', '+00:00')).timestamp() * 1000)
    if policy_review['checkedAtMs'] <= baseline_finished_ms:
        raise ValueError('Automated baseline policy check must be timestamped after baseline completion')
    baseline_request = baseline_report.get('request') or {}
    if (baseline_request.get('jvmStartMs') != request.get('jvmStartMs')
            or baseline_request.get('liveConfigurationSha256') != request.get('liveConfigurationSha256')):
        raise ValueError('Baseline JVM/configuration differs from the supplied source barrier')
    for axis in ('X','Y','Z','A','B'):
        if abs(float(baseline_request['expectedRaw'][axis])-float(snap['raw'][axis])) > 0.0001:
            raise ValueError('Baseline pose differs from supplied source barrier')
    policy_review['baselineReport'] = evidence(baseline_report_path)
    save(out/'baseline-policy-review.json', policy_review)
    save(out/'baseline-report.json', baseline_report)
    save(out/'baseline-summary.json', baseline_summary)

    # Capture a fresh read-only barrier using the existing manual-home helper.
    barrier_proc = subprocess.run([sys.executable, str(ROOT/'automation/paste/capture-manual-home-position.py'),
                                   '--operator-home-confirmed'], cwd=ROOT, check=True,
                                   capture_output=True, text=True)
    barrier_path = None
    for line in reversed(barrier_proc.stdout.splitlines()):
        candidate = Path(line.strip())
        if candidate.is_file(): barrier_path = candidate; break
    if barrier_path is None:
        raise RuntimeError('Fresh read-only barrier helper returned no report path; do not retry motion')
    barrier = load(barrier_path)
    if any(abs(float(barrier['afterQuerySnapshot']['raw'][a])-float(baseline_report['afterQuerySnapshot']['raw'][a])) > 1e-4
           for a in ('X','Y','Z','A','B')):
        raise ValueError('Post-baseline barrier differs from baseline pose')
    save(out/'fresh-barrier.json', barrier)

    z_request = load(plans/'paste-z-observation-request.json')
    pending = load(ROOT/'automation/paste/vacuum-probe-native.pending.json')
    c = dict(pending['contract'])
    c.update(startZmm=float(barrier['afterQuerySnapshot']['raw']['Z']), floorZmm=floor,
             maxDescentMm=round(float(barrier['afterQuerySnapshot']['raw']['Z'])-floor, 8),
             responseDirection='decrease', baselineIntervalMinMs=100, baselineIntervalMaxMs=1000,
             sampleIntervalMinMs=100, sampleIntervalMaxMs=1000, maxDurationMs=120000,
             expectedEmptyMean=float(baseline_summary['phases']['on']['mean']),
             expectedEmptyTolerance=1.5, minimumPumpResponseDelta=10,
             offBaselineSamples=3, offBaselineTolerance=1)
    iv = dict(interval)
    iv['minRawZ'], iv['maxRawZ'] = floor, c['startZmm']
    policy_review['checkedAtMs'] = time.time_ns()//1_000_000
    explicit_review = {
        'scope':'explicit-current-stream-and-probe-envelope-review', 'reviewed':True,
        'operator':operator, 'reviewedMs':reviewed_ms,
        'baselinePolicyReviewedMs':policy_review['checkedAtMs'],
        'envelopeReviewReviewedMs':reviewed_ms,
        'baselinePolicyReview':policy_review,
        'envelopeReviewEvidence':evidence(args.review),
        'baselineSha256':hashlib.sha256(baseline_report_path.read_bytes()).hexdigest(),
        'targetSurfaceIdentity':args.target, 'reviewRecord':record, 'jointInterval':iv,
        'nativeZConfiguration':z_request['nativeZConfiguration'], 'contract':c,
        'stationaryEvidencePath':str(image_path), 'targetEvidencePath':str(image_path),
        'jointEnvelopeEvidencePath':str(image_path),
    }
    for key in ('operatorVerifiedEmptyFreeAirBaseline','operatorVerifiedProbeTarget',
                'operatorVerifiedJointEnvelope','bothHeadsClearAlongEnvelope',
                'motionAreaClear','noHeldPartsObserved','n2Quarantined'):
        explicit_review[key] = True
    explicit_review_path = out/'explicit-probe-review.json'; save(explicit_review_path, explicit_review)
    probe_req = prep.prepare_probe(barrier_path, baseline_report_path, explicit_review_path,
                                   operator, args.tip_id, speed_fraction=1.0)
    probe_req_path = out/'probe-request.json'; save(probe_req_path, probe_req)
    save(plans/plan_names[1], load(barrier_path)['request'])
    save(plans/plan_names[2], probe_req)
    probe_report_path = ROOT/f"automation/evidence/paste-vacuum-probe-{probe_req['id']}/report.json"
    dispatch('paste-vacuum-probe')
    probe_report = wait_report(probe_report_path, 'completed-seal-candidate-held-at-z-awaiting-physical-review')
    save(out/'probe-report.json', probe_report)
    final_snapshot = probe_report.get('finalStationarySnapshot') or {}
    final_raw = final_snapshot.get('raw') or probe_report.get('currentRaw')
    terminal = {'status':probe_report['status'], 'report':str(probe_report_path),
                'sealCandidate':probe_report.get('sealCandidate'),
                'controlledStopReason':probe_report.get('controlledStopReason'),
                'raw':final_raw,
                'pumpOffAcknowledged':probe_report.get('normalVacuumOffAcknowledged') is True,
                'contactVerified':False, 'calibrationEstablished':False,
                'automaticLiftIssued':False, 'nextAction':'operator review; no automatic motion'}
    save(out/'result.json', terminal); print(json.dumps(terminal, indent=2))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True,help='successful verified read-only position barrier report')
    p.add_argument('--image',required=True,help='fresh operator-reviewed overview PNG/JPEG')
    p.add_argument('--floor',required=True,type=float,help='explicit reviewed raw-Z floor, at most 2 mm below source pose')
    p.add_argument('--target',required=True,help='named physical review target identity')
    p.add_argument('--review',required=True,help='fresh JSON with named reviewer, interval and explicit clearances/attestations')
    p.add_argument('--baseline-report',help='reuse a fresh completed normal-OFF twenty-sample baseline report')
    p.add_argument('--tip-id',default='NT1')
    p.add_argument('--output',required=True,help='new output directory; must not already exist')
    p.add_argument('--operator-home-confirmed',action='store_true')
    p.add_argument('--execute',action='store_true',help='dispatch existing baseline, read-only barrier and probe actions')
    a=p.parse_args()
    try: prepare(a)
    except subprocess.CalledProcessError as e:
        detail=(e.stderr or e.stdout or b'')
        if isinstance(detail,bytes): detail=detail.decode('utf-8','replace')
        p.error((str(e)+'\n'+str(detail).strip()).strip())
    except (ValueError,RuntimeError,OSError,TimeoutError) as e:
        p.error(str(e))

if __name__=='__main__': main()
