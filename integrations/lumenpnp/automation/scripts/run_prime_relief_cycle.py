#!/usr/bin/env python3
"""Preview by default; optionally run one verified prime segment then fixed +5° relief.

The 5° relief is experimental sequencing scaffolding, not a calibrated pressure
cutoff. Physical ooze can continue after relief; review camera evidence and the
actual dispensing state before deciding what to do next.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import pathlib
import subprocess
import sys
import time
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
CAPTURE = ROOT / 'automation/scripts/capture_viewer_usb_series.py'
DISPATCH = ROOT / 'automation/scripts/run_reviewed_action.py'
AXES = ('X', 'Y', 'Z', 'A', 'B')
PURGE_XY_ENVELOPE = {'X': (0.0, 433.0), 'Y': (0.0, 487.0)}
SURVEY_STATUSES = {
    'completed-camera-survey-awaiting-image-review',
    'completed-Z-observation-awaiting-image-review',
    'completed-read-only-position-barrier',
}


def read_json(path):
    return json.loads(pathlib.Path(path).read_text())


def digest(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def finite_raw(raw, label):
    if not isinstance(raw, dict) or set(raw) != set(AXES):
        raise ValueError(f'{label} must contain exactly X/Y/Z/A/B')
    if any(type(raw[a]) not in (int, float) or not math.isfinite(raw[a]) for a in AXES):
        raise ValueError(f'{label} contains a non-finite axis')
    return {a: float(raw[a]) for a in AXES}


def timestamp_ms(value):
    if not isinstance(value, str):
        return None
    try:
        return int(dt.datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp() * 1000)
    except ValueError:
        return None


def profile_and_ledger(root=ROOT):
    profile = read_json(root / 'automation/plans/paste-operator-profile.json')
    ledger_path = root / 'automation/evidence/operator-paste-runs' / profile['sessionId'] / 'budget-ledger.json'
    ledger = read_json(ledger_path)
    if (ledger.get('profileId') != profile.get('id') or ledger.get('sessionId') != profile.get('sessionId')
            or ledger.get('status') != 'verified' or not ledger.get('entries')
            or ledger['entries'][-1].get('status') != 'verified'):
        raise ValueError('Current profile and terminal verified ledger must agree')
    calibration_path = root / 'automation/evidence/operator-paste-runs' / profile['sessionId'] / ('calibration-' + profile['id'] + '.json')
    calibration = read_json(calibration_path)
    if calibration.get('profileId') != profile['id']:
        raise ValueError('Current calibration sidecar does not match the profile')
    raw = finite_raw(ledger.get('lastVerifiedRaw'), 'ledger terminal pose')
    used = ledger.get('usedAdditionalGrossDegrees')
    if type(used) not in (int, float) or not math.isfinite(used) or used < 0:
        raise ValueError('Ledger gross usage is invalid')
    if len({e.get('id') for e in ledger['entries'] if isinstance(e, dict)}) != len(ledger['entries']):
        raise ValueError('Ledger record IDs must be unique')
    charged_parts = []
    for entry in ledger['entries']:
        gross = entry.get('plannedGrossDegrees')
        if (entry.get('status') not in ('verified', 'stopped-charged')
                or type(gross) not in (int, float) or not math.isfinite(gross) or gross < 0):
            raise ValueError('Ledger contains an unverified or invalid charged entry')
        charged_parts.append(gross)
    charged = sum(charged_parts)
    if abs(charged - used) > 0.0001:
        raise ValueError('Ledger entries do not reconcile to charged gross')
    cap = profile.get('rodBudget', {}).get('maximumAdditionalGrossDegrees')
    pending = ledger.get('pendingRetractDegrees')
    if type(cap) not in (int, float) or not math.isfinite(cap) or type(pending) not in (int, float) or not math.isfinite(pending) or pending < 0:
        raise ValueError('Profile cap or pending-pressure accounting is invalid')
    if used > cap + 1e-8 or pending > cap + 1e-8:
        raise ValueError('Ledger usage exceeds current profile allowance')
    return profile, ledger_path, ledger


def normalize_source(source, profile, ledger, now_ms=None, max_age_ms=300_000):
    """Accept a fresh verified survey/Z barrier or the latest stationary native record."""
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    if source.get('schema') != 1 or not isinstance(source.get('id'), str) or not source.get('id'):
        raise ValueError('Source report identity/schema is missing')
    status = source.get('status')
    if source.get('uncertainCompletion') is not False or source.get('error'):
        raise ValueError('Source must have certain successful completion')
    if status in SURVEY_STATUSES:
        req = source.get('request') or {}
        if (source.get('controllerPositionVerified') is not True
                or req.get('id') != source.get('id')
                or req.get('jvmStartMs') != profile.get('jvmStartMs')
                or req.get('liveConfigurationSha256') != profile.get('liveConfigurationSha256')
                or source.get('liveConfigurationSha256', req.get('liveConfigurationSha256')) != profile.get('liveConfigurationSha256')):
            raise ValueError('Survey/Z source must bind verified pose, current JVM, and configuration')
        snap = source.get('afterQuerySnapshot') or {}
        raw = finite_raw(snap.get('raw'), 'survey terminal pose')
        driver = finite_raw(snap.get('driver'), 'survey terminal driver pose')
        if any(abs(raw[a] - driver[a]) > 0.005001 for a in AXES):
            raise ValueError('Survey terminal raw and driver endpoints disagree')
        finished = timestamp_ms(source.get('finishedAt') or source.get('updatedAt'))
        if finished is None or finished > now_ms or now_ms - finished > max_age_ms:
            raise ValueError('Verified survey/Z source is stale')
        source_kind = 'verified-survey-or-z-report'
    elif status == 'completed-awaiting-operator-inspection':
        if (source.get('profileId') != profile.get('id') or source.get('sessionId') != profile.get('sessionId')
                or source.get('liveConfigurationSha256') != profile.get('liveConfigurationSha256')
                or not (source.get('noXYZMotion') is True or
                        (source.get('motionSubmitted') is False and source.get('noMotionCommandSubmitted') is True))
                or source.get('stationaryOnly') is not True
                or source.get('id') != ledger.get('lastRecordId')):
            raise ValueError('Only the latest profile-bound stationary native record is accepted')
        raw = finite_raw((source.get('after') or {}).get('raw'), 'stationary record endpoint')
        before = finite_raw((source.get('before') or {}).get('raw'), 'stationary record start')
        if any(abs(raw[a] - before[a]) > 0.005001 for a in ('X', 'Y', 'Z', 'A')):
            raise ValueError('Stationary native record changed a held XYZ/A axis')
        if any(abs(raw[a] - ledger['lastVerifiedRaw'][a]) > 0.005001 for a in AXES):
            raise ValueError('Stationary native record is not at the current ledger endpoint')
        finished = timestamp_ms(source.get('finishedAt') or source.get('updatedAt'))
        if finished is None or finished > now_ms or now_ms - finished > max_age_ms:
            raise ValueError('Stationary native record is stale')
        source_kind = 'latest-stationary-native-record'
    else:
        raise ValueError('Source must be a verified survey/Z report or latest stationary native record')
    if raw['B'] != ledger['lastVerifiedRaw']['B']:
        raise ValueError('Source B must exactly match the verified ledger endpoint used by the prime API')
    if any(abs(raw[a] - ledger['lastVerifiedRaw'][a]) > 0.005001 for a in AXES):
        raise ValueError('Source endpoint must match the current verified ledger pose on every axis')
    # Match the native `purgePose` envelope: XY uses the explicit stationary
    # machine envelope, while Z/A/B use the current profile bounds. Board-pad
    # XY bounds are intentionally irrelevant for a stationary purge location.
    for axis in ('X', 'Y'):
        low, high = PURGE_XY_ENVELOPE[axis]
        if raw[axis] < low - 1e-8 or raw[axis] > high + 1e-8:
            raise ValueError(f'Source {axis} endpoint is outside the stationary purge envelope')
    for axis in ('Z', 'A', 'B'):
        bounds = profile.get('rawBounds', {}).get(axis, {})
        if raw[axis] < bounds.get('min', float('-inf')) - 1e-8 or raw[axis] > bounds.get('max', float('inf')) + 1e-8:
            raise ValueError(f'Source {axis} endpoint is outside the current profile bounds')
    return {'kind': source_kind, 'raw': raw}


def policy_preview(profile, ledger, raw, degrees, speed):
    payload = {'profile': profile, 'ledger': ledger, 'raw': raw, 'degrees': degrees, 'speed': speed}
    code = """const P=require(process.argv[1]),q=JSON.parse(require('fs').readFileSync(0));
P.validateProfile(q.profile);
const p=P.planPurge(q.degrees,q.speed/100,q.profile,q.raw,q.ledger.usedAdditionalGrossDegrees);
const next={...q.raw,B:p.endB};
const pending=Math.max(0,q.ledger.pendingRetractDegrees-p.grossDegrees);
const r=P.planRelief(5,1,q.profile,next,q.ledger.usedAdditionalGrossDegrees+p.grossDegrees,pending);
console.log(JSON.stringify({prime:p,relief:r,pendingAfterPrime:pending}));"""
    run = subprocess.run(['node', '-e', code, str(ROOT / 'automation/paste/operator-console-policy.cjs')],
                         input=json.dumps(payload), text=True, capture_output=True)
    if run.returncode:
        raise ValueError(run.stderr.strip() or 'Existing policy rejected the requested prime/relief cycle')
    return json.loads(run.stdout)


def verified_initial_capture(output, run=subprocess.run):
    sys.path.insert(0, str(ROOT / 'automation/scripts'))
    from run_observed_prime_segment import verified_initial_capture as check_capture
    return check_capture(output, run)


def verify_action(root, ledger_path, before, start_raw, expected_raw, requested_gross,
                  kind, timeout=40, sleep=time.sleep, clock=time.monotonic):
    deadline = clock() + timeout
    while clock() < deadline:
        current = read_json(ledger_path)
        if len(current.get('entries', [])) > len(before.get('entries', [])) + 1:
            raise RuntimeError('Unexpected concurrent ledger entries; no retry')
        if len(current.get('entries', [])) == len(before.get('entries', [])) + 1:
            entry = current['entries'][-1]
            if entry.get('status') in ('stopped-charged', 'failed', 'faulted'):
                raise RuntimeError('Action stopped or failed; no retry')
            record_path = ledger_path.parent / entry['id'] / 'record.json'
            if not record_path.is_file():
                sleep(0.1); continue
            record = read_json(record_path)
            if record.get('uncertainCompletion') is True or record.get('error'):
                raise RuntimeError('Native action outcome is uncertain; no retry')
            if record.get('status') != 'completed-awaiting-operator-inspection':
                sleep(0.1); continue
            current_used = current.get('usedAdditionalGrossDegrees')
            current_pending = current.get('pendingRetractDegrees')
            entry_gross = entry.get('plannedGrossDegrees')
            if any(type(value) not in (int, float) or not math.isfinite(value)
                   for value in (current_used, current_pending, entry_gross)):
                raise RuntimeError('Native action ledger contains non-finite accounting; no retry')
            if (current.get('status') != 'verified' or entry.get('status') != 'verified'
                    or entry.get('kind') != kind or abs(entry_gross - requested_gross) > 0.005001
                    or entry.get('id') != record.get('id')
                    or record.get('profileId') != current.get('profileId')
                    or record.get('sessionId') != current.get('sessionId')
                    or record.get('noXYZMotion') is not True):
                raise RuntimeError('Completed action did not reconcile to the expected profile/ledger; no retry')
            if (current.get('profileId') != before.get('profileId') or current.get('sessionId') != before.get('sessionId')
                    or current.get('entries', [])[:len(before.get('entries', []))] != before.get('entries', [])
                    or abs(current_used - before['usedAdditionalGrossDegrees'] - requested_gross) > 0.005001):
                raise RuntimeError('Action did not preserve and increment the charged ledger exactly; no retry')
            actual_before = finite_raw((record.get('before') or {}).get('raw'), 'native action start')
            actual_after = finite_raw((record.get('after') or {}).get('raw'), 'native action endpoint')
            for axis in AXES:
                if abs(actual_before[axis] - start_raw[axis]) > 0.005001 or abs(actual_after[axis] - expected_raw[axis]) > 0.005001:
                    raise RuntimeError(f'Action endpoint mismatch on {axis}; no retry')
            if any(abs(current['lastVerifiedRaw'][axis] - expected_raw[axis]) > 0.005001 for axis in AXES):
                raise RuntimeError('Ledger terminal pose differs from native report; no retry')
            expected_pending = (before['pendingRetractDegrees'] + requested_gross if kind == 'stationary-pressure-relief'
                                else max(0, before['pendingRetractDegrees'] - requested_gross))
            if abs(current_pending - expected_pending) > 0.005001:
                raise RuntimeError('Pending-pressure ledger does not match the verified action; no retry')
            return {'recordId': entry['id'], 'grossDegrees': entry_gross,
                    'pendingRetractDegrees': current_pending,
                    'before': actual_before, 'after': actual_after}
        sleep(0.1)
    raise RuntimeError('No terminal verified record before timeout; no retry')


def write_progress(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def remove_own_unconsumed_request(path, payload):
    """Remove a request only when dispatch returned and the exact file is still ours."""
    try:
        if path.is_file() and path.read_bytes() == payload:
            path.unlink()
            return True
    except OSError:
        return False
    return False


def main(argv=None, *, root=ROOT, dispatch=subprocess.run, popen=subprocess.Popen,
         capture_runner=subprocess.run, clock=time.monotonic, sleep=time.sleep,
         state_loader=profile_and_ledger):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=pathlib.Path,
                        help='fresh verified survey/Z report or latest stationary native record JSON')
    parser.add_argument('--degrees', type=int, default=10)
    parser.add_argument('--speed', type=float, default=5, help='nominal requested prime B degrees/second')
    parser.add_argument('--observe-seconds', type=int, default=25)
    parser.add_argument('--output-root', type=pathlib.Path,
                        help='evidence parent (default: automation/evidence/operator-prime-relief-cycles)')
    parser.add_argument('--execute', action='store_true', help='explicitly dispatch; default is preview only')
    args = parser.parse_args(argv)
    if not 1 <= args.degrees <= 30 or not 5 <= args.speed <= 20:
        parser.error('Prime segment must be 1..30 degrees at 5..20 nominal B degrees/second')
    if not 8 <= args.observe_seconds <= 120 or args.observe_seconds < args.degrees / args.speed + 2:
        parser.error('Observation must be 8..120 seconds and cover nominal stroke plus 2 seconds')
    source_path = args.source.resolve(strict=True)
    source_bytes = source_path.read_bytes()
    source = json.loads(source_bytes)
    profile, ledger_path, ledger = state_loader(root)
    endpoint = normalize_source(source, profile, ledger)
    plan = policy_preview(profile, ledger, endpoint['raw'], args.degrees, args.speed)
    preview = {
        'previewOnly': not args.execute, 'sourceKind': endpoint['kind'],
        'sourceSha256': hashlib.sha256(source_bytes).hexdigest(), 'profileId': profile['id'],
        'sessionId': profile['sessionId'], 'startRaw': endpoint['raw'],
        'requestedPrimeDegrees': args.degrees, 'primeSpeedDegreesPerSecond': args.speed,
        'requestedReliefDegrees': 5, 'primePlan': plan['prime'],
        'reliefPlan': plan['relief'], 'pendingAfterPrime': plan['pendingAfterPrime'],
        'observeSeconds': args.observe_seconds, 'execute': args.execute,
    }
    print(json.dumps(preview, indent=2, allow_nan=False), flush=True)
    if not args.execute:
        return 0

    output_root = args.output_root or (root / 'automation/evidence/operator-prime-relief-cycles')
    output_root.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid.uuid4())
    out = output_root / run_id
    out.mkdir(exist_ok=False)
    (out / 'source.json').write_bytes(source_bytes)
    result = {'schema': 1, 'id': run_id, 'status': 'preflight', **preview,
              'requestedReliefDegrees': 5, 'reliefResult': None, 'primeResult': None}
    progress = out / 'result.json'
    write_progress(progress, result)
    camera = None
    request_path = root / 'automation/plans/operator-prime-segment-request.json'
    request_bytes = None
    dispatch_attempted = False
    try:
        if digest(source_path) != preview['sourceSha256']:
            raise RuntimeError('Source changed after preview')
        capture_preflight = out / 'camera-preflight'
        verified_initial_capture(capture_preflight, capture_runner)
        fresh_profile, fresh_ledger_path, fresh_ledger = state_loader(root)
        fresh_source = json.loads(source_path.read_bytes())
        fresh_endpoint = normalize_source(fresh_source, fresh_profile, fresh_ledger)
        if (fresh_profile != profile or fresh_ledger_path != ledger_path or fresh_ledger != ledger
                or fresh_endpoint != endpoint or digest(source_path) != preview['sourceSha256']):
            raise RuntimeError('Profile, source, or ledger changed during camera preflight; no dispatch')
        camera = popen([sys.executable, str(CAPTURE), '--output', str(out / 'camera-series'),
                        '--seconds', str(args.observe_seconds)], cwd=root)
        dispatch_profile, dispatch_ledger_path, dispatch_ledger = state_loader(root)
        if (dispatch_profile != profile or dispatch_ledger_path != ledger_path or dispatch_ledger != ledger
                or digest(source_path) != preview['sourceSha256']):
            raise RuntimeError('Profile, source, or ledger changed before prime request; no dispatch')
        q = {'schema': 1, 'scope': 'operator-prime-segment', 'profileId': profile['id'],
             'nonce': str(uuid.uuid4()), 'currentB': endpoint['raw']['B'],
             'createdAt': int(time.time() * 1000), 'degrees': args.degrees,
             'speedDegreesPerSecond': args.speed}
        request_bytes = json.dumps(q, indent=2, allow_nan=False).encode()
        with request_path.open('xb') as f:
            f.write(request_bytes)
        (out / 'prime-request.json').write_bytes(request_bytes)
        result['status'] = 'prime-dispatch-started'
        write_progress(progress, result)
        dispatch_attempted = True
        run = dispatch([sys.executable, str(DISPATCH), 'operator-prime-segment', '--confirmed'],
                       capture_output=True, text=True, cwd=root)
        (out / 'prime-dispatch.txt').write_text(run.stdout + run.stderr)
        if run.returncode:
            remove_own_unconsumed_request(request_path, request_bytes)
            raise RuntimeError('Prime dispatcher returned failure; no replay')
        prime_expected = dict(endpoint['raw'], B=endpoint['raw']['B'] - args.degrees)
        result['primeResult'] = verify_action(root, ledger_path, ledger, endpoint['raw'],
                                              prime_expected, args.degrees, 'operator-prime-segment',
                                              clock=clock, sleep=sleep)
        result['status'] = 'prime-verified-relief-dispatch-started'
        write_progress(progress, result)
        after_prime = read_json(ledger_path)
        next_profile, next_ledger_path, next_ledger = state_loader(root)
        if next_profile != profile or next_ledger_path != ledger_path or next_ledger != after_prime:
            raise RuntimeError('Profile or ledger changed after prime; no relief dispatch')
        # Validate the fixed relief against the post-prime ledger before its one dispatch.
        result['reliefPlan'] = _relief_preview(profile, after_prime, prime_expected)
        write_progress(progress, result)
        dispatch_attempted = True
        run = dispatch([sys.executable, str(DISPATCH), 'operator-pressure-relief', '--confirmed'],
                       capture_output=True, text=True, cwd=root)
        (out / 'relief-dispatch.txt').write_text(run.stdout + run.stderr)
        if run.returncode:
            raise RuntimeError('Relief dispatcher returned failure; no replay')
        relief_expected = dict(prime_expected, B=prime_expected['B'] + 5)
        result['reliefResult'] = verify_action(root, ledger_path, after_prime, prime_expected,
                                               relief_expected, 5, 'stationary-pressure-relief',
                                               clock=clock, sleep=sleep)
        result['status'] = 'both-segments-verified-awaiting-visual-review'
    except Exception as exc:
        if result['primeResult'] is None and request_bytes is not None:
            remove_own_unconsumed_request(request_path, request_bytes)
        result.update(status='failed-no-replay', error=f'{type(exc).__name__}: {exc}')
    finally:
        if not dispatch_attempted and request_bytes is not None and request_path.exists():
            try:
                if request_path.read_bytes() == request_bytes:
                    request_path.unlink()
            except OSError as exc:
                result['requestCleanupError'] = f'{type(exc).__name__}: {exc}'
        if camera is not None:
            try:
                if camera.poll() is None and result['status'] == 'failed-no-replay':
                    camera.terminate()
                result['cameraExitCode'] = camera.wait(timeout=10 if result['status'] == 'failed-no-replay' else args.observe_seconds + 15)
            except Exception as exc:
                result['cameraCleanupError'] = f'{type(exc).__name__}: {exc}'
                try:
                    camera.kill(); result['cameraExitCode'] = camera.wait(timeout=5)
                except Exception as final_exc:
                    result['cameraCleanupError'] += f'; {type(final_exc).__name__}: {final_exc}'
            if result['status'] == 'both-segments-verified-awaiting-visual-review':
                try:
                    manifest = read_json(out / 'camera-series/manifest.json')
                    captures = manifest.get('captures', [])
                    if (result.get('cameraExitCode') != 0 or manifest.get('status') != 'complete'
                            or manifest.get('errors') or len(captures) != args.observe_seconds):
                        raise ValueError('Camera series is incomplete or has errors')
                    for capture in captures:
                        image = (out / 'camera-series' / capture['file']).resolve(strict=True)
                        if image.parent != (out / 'camera-series').resolve() or not image.read_bytes().startswith(b'\xff\xd8\xff'):
                            raise ValueError('Camera series contains a missing or malformed image')
                    result['cameraCaptureCount'] = len(captures)
                    result['cameraManifestStatus'] = 'complete'
                except Exception as exc:
                    result['cameraManifestStatus'] = 'incomplete'
                    result['cameraError'] = f'{type(exc).__name__}: {exc}'
                    result['status'] = 'both-segments-verified-camera-evidence-incomplete-review-required'
        write_progress(progress, result)
        print(json.dumps({'output': str(out), 'result': result}, indent=2), flush=True)
    return 0 if result['status'] == 'both-segments-verified-awaiting-visual-review' else 1


def _relief_preview(profile, ledger, raw):
    payload = {'profile': profile, 'ledger': ledger, 'raw': raw}
    code = "const P=require(process.argv[1]),q=JSON.parse(require('fs').readFileSync(0));P.validateProfile(q.profile);console.log(JSON.stringify(P.planRelief(5,1,q.profile,q.raw,q.ledger.usedAdditionalGrossDegrees,q.ledger.pendingRetractDegrees)))"
    run = subprocess.run(['node', '-e', code, str(ROOT / 'automation/paste/operator-console-policy.cjs')],
                         input=json.dumps(payload), text=True, capture_output=True)
    if run.returncode:
        raise ValueError(run.stderr.strip() or 'Fixed pressure relief exceeds the current profile/ledger bounds')
    return json.loads(run.stdout)


if __name__ == '__main__':
    raise SystemExit(main())
