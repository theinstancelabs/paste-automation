#!/usr/bin/env python3
"""Build an offline, disabled, compensated two-pad FTP recipe and run the generic validator.

This tool copies and augments only computed stage indices in an authored target
record. It never creates observations or attestations and never connects to a
machine.
"""
import argparse
import copy
import datetime
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path('/home/lumen/lumenpnp')
GENERIC = ROOT / 'automation/paste/prepare-contiguous-batch.py'
POLICY = ROOT / 'automation/paste/commissioning-stroke.cjs'


def fail(message):
    raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def read(path):
    path = Path(path).resolve(strict=True)
    data = path.read_bytes()
    return json.loads(data), path, data


def evidence(path):
    path = Path(path).resolve(strict=True)
    data = path.read_bytes()
    if not data:
        fail(f'Empty evidence file: {path}')
    return {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest()}


def require_evidence(item, label):
    if not isinstance(item, dict) or not isinstance(item.get('path'), str) or not isinstance(item.get('sha256'), str):
        fail(f'{label} must contain path and SHA-256')
    actual = evidence(item['path'])
    if actual['sha256'] != item['sha256']:
        fail(f'{label} hash changed')
    return actual


def q01(value):
    return math.floor(value * 100 + 0.5) / 100


def validate_pair(target):
    pads = target.get('pads')
    if not isinstance(pads, list) or len(pads) != 2:
        fail('Target record must contain exactly two pads')
    refs = []
    for pad in pads:
        if not isinstance(pad, dict) or not isinstance(pad.get('padId'), str):
            fail('Each target pad needs a padId')
        ref = pad['padId'].split('.')
        if len(ref) != 2 or ref[0] not in {f'R{i}' for i in range(1, 41)} or ref[1] not in ('1', '2'):
            fail('Targets must be two unique R1–R40 resistor pads')
        refs.append((ref[0], ref[1]))
    if refs[0][0] != refs[1][0] or refs[0][1] == refs[1][1]:
        fail('Target pads must be the unique pair from one resistor')
    return pads


def build_route(raw, poses, target, clearance):
    """Create generic stage inputs and annotate only derived indices in a deep copy."""
    seq = target.get('compensatedSequence')
    if not isinstance(seq, dict):
        fail('Authored compensatedSequence is required')
    pads = validate_pair(target)
    surface = target.get('surface') or {}
    work_z, gap, uncertainty = (surface.get(k) for k in ('rawZ', 'estimatedGapMm', 'gapUncertaintyMm'))
    if not all(finite(v) for v in (work_z, gap, uncertainty)) or gap - uncertainty < 0.1:
        fail('Reviewed board-specific surface gap lower bound must be at least 0.1 mm')
    if not finite(clearance) or not raw['Z'] - 5 <= clearance < work_z:
        fail('XY clearance must be below work Z and within 5 mm of fresh barrier Z')
    for key in ('cadEvidence', 'registrationEvidence', 'tipOffsetEvidence', 'surfaceEvidence', 'padAvailabilityImage'):
        require_evidence(target.get(key), key)
    registration, _, _ = read(target['registrationEvidence']['path'])
    registered = {entry['padId']: entry for entry in registration.get('resistorPadMachineXYTargets', [])}
    offset = target.get('cameraMinusTipXYMm')
    if not isinstance(offset, list) or len(offset) != 2 or not all(finite(x) for x in offset):
        fail('Explicit selected camera-minus-tip XY offset required')
    for pad in pads:
        pose = pad.get('rawPose') or {}
        source = registered.get(pad['padId'])
        if not source or not isinstance(source.get('machineXYMm'), list) or len(source['machineXYMm']) != 2:
            fail('Target pad is absent from the reviewed registration')
        if any(not finite(pose.get(k)) for k in 'XYZA') or pose['Z'] != work_z or pose['A'] != raw['A']:
            fail('Each authored pad pose must match work Z and barrier A')
        expected_xy = [q01(source['machineXYMm'][i] - offset[i]) for i in range(2)]
        if [pose['X'], pose['Y']] != expected_xy:
            fail('Authored head XY differs from 0.01 mm quantized registration minus selected offset')

    dose = seq.get('doseDegrees')
    retract = seq.get('retractDegrees')
    dose_wait = seq.get('dwellMilliseconds')
    retract_wait = seq.get('retractDwellMilliseconds', 0)
    idle = seq.get('idleReliefDegrees', 20)
    if dose not in (2, 3, 4, 6, 12, 20) or retract not in (2, 3, 4, 6):
        fail('Authored dose/retract amount is outside FTP policy')
    if type(dose_wait) is not int or not 0 <= dose_wait <= 2000:
        fail('Authored dose dwell must be an integer from 0 to 2000 ms')
    if retract_wait not in (0, 200, 500) or idle not in (20, 40):
        fail('Authored retract dwell or final idle relief is outside FTP policy')

    out_target = copy.deepcopy(target)
    out_pads = out_target['pads']
    out_seq = out_target['compensatedSequence']
    stages = []
    at = dict(raw)
    path = [dict(at)]
    index = 0

    def append(axis, value, **metadata):
        nonlocal at, index
        if at[axis] == value:
            return None
        nxt = dict(at)
        nxt[axis] = value
        stages.append({'axis': axis, 'target': value, **metadata})
        at = nxt
        path.append(dict(at))
        result = index
        index += 1
        return result

    def move(axis, value):
        if abs(value - q01(value)) > 1e-9:
            fail(f'{axis} endpoint must be on the controller 0.01 mm grid')
        start = at[axis]
        max_step = 9.9 if axis in ('X', 'Y') else 4.9
        count = max(1, math.ceil(abs(value - start) / max_step))
        while True:
            values = [q01(start + (value - start) * step / count)
                      for step in range(1, count)] + [value]
            if all(abs(next_value - prev) <= max_step + 1e-9
                   for prev, next_value in zip([start] + values[:-1], values)):
                break
            count += 1
        for target_value in values:
            if axis in ('X', 'Y') and at['Z'] != clearance:
                fail('All linear XY travel must stay at the reviewed clearance Z')
            if abs(target_value - at[axis]) > max_step + 1e-9:
                fail(f'Internal {axis} segmentation exceeded native per-stage bound')
            append(axis, target_value)

    def bstage(delta, pose, dwell, board_gap):
        return append('B', at['B'] + delta, gapEvidence=target['surfaceEvidence'],
                      estimatedGapMm=board_gap, gapUncertaintyMm=uncertainty,
                      dwellMilliseconds=dwell)

    dose_indices = []
    for pad, out_pad in zip(pads, out_pads):
        pose = pad['rawPose']
        if at['Z'] > clearance:
            move('Z', clearance)
        elif at['Z'] < clearance:
            fail('Barrier Z is below reviewed XY clearance; refuse to move up to it')
        move('X', pose['X'])
        move('Y', pose['Y'])
        move('Z', work_z)
        first = len(stages)
        restore_i = bstage(-retract, pose, 0, gap)
        part_doses = []
        dose_parts = [-6, -6] if dose == 12 else [-dose]
        for n, amount in enumerate(dose_parts):
            part_doses.append(bstage(amount, pose, dose_wait if n == len(dose_parts) - 1 else 0, gap))
        retract_i = bstage(retract, pose, retract_wait, gap)
        lift_i = move_index = append('Z', clearance)
        # The immediate lift uses the native 5.0 mm bound; tolerate only
        # floating-point subtraction noise, not another 0.01 mm grid step.
        if lift_i is None or len(stages) - 1 != lift_i or work_z - clearance > 5.0 + 1e-9:
            fail('Dispense-to-clearance lift must be one stage no greater than 5.0 mm')
        out_pad.pop('doseStageIndex', None)
        out_pad['restoreStageIndex'] = restore_i
        out_pad['doseStageIndices'] = part_doses
        out_pad['retractStageIndex'] = retract_i
        out_pad['liftStageIndex'] = lift_i
        dose_indices.extend(part_doses)
        if first != restore_i:
            fail('Internal stage index error')

    idle_indices = []
    for n in range(idle // 20):
        idx = bstage(20, at, 2000 if n == idle // 20 - 1 else 0,
                     round(gap + (work_z - clearance), 9))
        idle_indices.append(idx)
    if idle == 20:
        out_seq.pop('finalIdleStageIndices', None)
        out_seq['finalIdleStageIndex'] = idle_indices[0]
    else:
        out_seq.pop('finalIdleStageIndex', None)
        out_seq['finalIdleStageIndices'] = idle_indices

    bounds = {axis: {'min': min(p[axis] for p in path), 'max': max(p[axis] for p in path)}
              for axis in ('X', 'Y', 'Z', 'B')}
    heads = {}
    for name in ('N1', 'N2'):
        limits = {}
        for axis in 'XYZ':
            sign = -1 if axis == 'Z' and name == 'N2' else 1
            val = [poses[name][axis.lower()] + sign * (p[axis] - raw[axis]) for p in path]
            limits['min' + axis] = min(val) - 0.001
            limits['max' + axis] = max(val) + 0.001
        heads[name] = limits
    gross = 2 * dose + 4 * retract + idle
    b_accounting = {'initialB': raw['B'], 'restoreDegrees': 2 * retract,
                    'doseDegrees': -2 * dose, 'retractDegrees': 2 * retract,
                    'finalIdleDegrees': idle, 'grossChargedDegrees': gross,
                    'finalB': raw['B'] - 2 * dose + idle}
    return out_target, stages, bounds, heads, b_accounting


def node_previous(report, ledger, ledger_hash, captured_ms):
    js = "const P=require(process.argv[1]),v=JSON.parse(require('fs').readFileSync(0,'utf8'));P.validatePreviousReport(v.report,v.ledger,v.sha,v.capturedMs);"
    data = {'report': report, 'ledger': ledger, 'sha': ledger_hash, 'capturedMs': captured_ms}
    try:
        subprocess.run(['node', '-e', js, str(POLICY)], input=json.dumps(data), text=True,
                       check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        fail('Installed previous-report validator rejected source: ' + (exc.stderr or exc.stdout).strip())


def main(args):
    now = int(time.time() * 1000)
    template, tp, _ = read(args.template)
    barrier, bp, _ = read(args.barrier)
    target, source_target_path, source_target_bytes = read(args.target_record)
    profile, pp, _ = read(args.profile)
    review, rp, _ = read(args.clearance_review)
    report, rr, _ = read(args.previous_report)
    ledger, lp, ledger_bytes = read(args.ledger)
    image = Path(args.image).resolve(strict=True)
    image_bytes = image.read_bytes()
    captured_ms = image.stat().st_mtime_ns // 1_000_000
    if not (image_bytes.startswith(b'\x89PNG\r\n\x1a\n') or image_bytes.startswith(b'\xff\xd8\xff')) or not 0 <= now - captured_ms <= 300000:
        fail('Review image must be a fresh PNG/JPEG no more than five minutes old')
    if barrier.get('status') != 'completed-read-only-position-barrier' or barrier.get('controllerPositionVerified') is not True or barrier.get('noMotionCommandSubmitted') is not True or barrier.get('uncertainCompletion') is not False:
        fail('Successful read-only barrier required')
    try:
        barrier_ms = int(datetime.datetime.fromisoformat(barrier['finishedAt'].replace('Z', '+00:00')).timestamp() * 1000)
    except Exception:
        fail('Barrier finishedAt missing or invalid')
    if barrier_ms > now or now - barrier_ms > 300000:
        fail('Barrier must be no more than five minutes old')
    barrier_request = barrier.get('request') or {}
    snapshot = barrier.get('afterQuerySnapshot') or {}
    raw, driver, poses = snapshot.get('raw'), snapshot.get('driver'), snapshot.get('nativePoses')
    if barrier_request.get('jvmStartMs') != template.get('jvmStartMs') or barrier.get('liveConfigurationSha256') != template.get('liveConfigurationSha256'):
        fail('Barrier JVM/config differs from immutable template')
    if not all(isinstance(v, dict) for v in (raw, driver, poses)) or set(raw) != set('XYZAB') or set(driver) != set(raw) or set(poses) != {'N1', 'N2', 'top', 'bottom'}:
        fail('Barrier needs full raw/driver/native-pose snapshot')
    if profile.get('sessionId') != template.get('sessionId') or profile.get('jvmStartMs') != template.get('jvmStartMs') or profile.get('liveConfigurationSha256') != template.get('liveConfigurationSha256') or profile.get('provenance') != 'commissioning-provisional' or profile.get('precisionCalibrated') is not False or profile.get('flowCalibrated') is not False:
        fail('Profile identity/provisional status mismatch')
    for axis in 'XYZA':
        if not finite(profile.get('rawPose', {}).get(axis)) or abs(profile['rawPose'][axis] - raw[axis]) > 0.0001:
            fail(f'Profile is not anchored at fresh barrier {axis}')
    if review.get('mode') != 'wet' or not isinstance(review.get('reviewedBy'), str) or not review['reviewedBy'].strip() or type(review.get('reviewedMs')) is not int or not captured_ms <= review['reviewedMs'] <= now or now - review['reviewedMs'] > 300000:
        fail('Fresh authored wet clearance review required')
    image_hash = hashlib.sha256(image_bytes).hexdigest()
    if review.get('imageEvidence', {}).get('path') != str(image) or review.get('imageEvidence', {}).get('sha256') != image_hash:
        fail('Clearance review must bind supplied image/hash')
    if report.get('uncertainCompletion') is not False or report.get('completedLedgerSha256') != hashlib.sha256(ledger_bytes).hexdigest() or report.get('id') != report.get('request', {}).get('id'):
        fail('Previous terminal report must bind current ledger')
    node_previous(report, ledger, hashlib.sha256(ledger_bytes).hexdigest(), captured_ms)
    if ledger.get('status') != 'verified' or ledger.get('sessionId') != template.get('sessionId') or ledger.get('syringeId') != template.get('syringeId') or ledger.get('lastVerifiedB') != raw['B'] or not ledger.get('entries') or ledger['entries'][-1].get('status') != 'verified' or report['id'] not in (ledger['entries'][-1].get('requestId'), ledger['entries'][-1].get('cycleId'), ledger['entries'][-1].get('batchId')):
        fail('Previous report/ledger is not the current verified tail')
    if report.get('request', {}).get('jvmStartMs') != barrier_request.get('jvmStartMs') or report.get('request', {}).get('liveConfigurationSha256') != barrier.get('liveConfigurationSha256'):
        fail('Previous report session/config mismatch')
    if target.get('schema') != 1 or target.get('scope') != 'ftp-two-pad-commissioning-targets' or target.get('mode') not in (None, 'wet') or target.get('quantizationMm') != 0.01:
        fail('Authored same-session wet FTP target record required')
    if target.get('sessionId') != template.get('sessionId') or target.get('jvmStartMs') != template.get('jvmStartMs') or target.get('liveConfigurationSha256') != barrier.get('liveConfigurationSha256'):
        fail('Target record session/config mismatch')
    if target.get('boardUnmovedSinceRegistration') is not True or target.get('precisionCalibrated') is not False or target.get('flowCalibrated') is not False:
        fail('Target must retain explicit unmoved/provisional/uncalibrated status')
    if target.get('compensatedSequence', {}).get('conditioningReportEvidence') != evidence(rr) or target.get('compensatedSequence', {}).get('conditioningLedgerEvidence', {}).get('sha256') != hashlib.sha256(ledger_bytes).hexdigest():
        fail('Authored compensated sequence must bind preceding report and immutable ledger copy')

    out_target, stages, bounds, heads, b_accounting = build_route(raw, poses, target, args.xy_clearance_raw_z)
    if review.get('rawZRange') != [bounds['Z']['min'], bounds['Z']['max']]:
        fail('Clearance review rawZRange must exactly cover computed route')
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    target_copy = out / 'targets.json'
    target_copy.write_text(json.dumps(out_target, indent=2, allow_nan=False) + '\n')
    target_copy_ev = evidence(target_copy)
    recipe = {
        'mode': 'wet', 'stages': stages, 'rawBounds': bounds, 'headClearanceBounds': heads,
        'xyClearanceRawZ': args.xy_clearance_raw_z,
        'clearanceReviewEvidence': evidence(rp), 'profileEvidence': evidence(pp),
        'previousReportEvidence': evidence(rr), 'previousLedgerPath': str(lp),
        'targetSurface': 'cleaned-ftp-demo', 'ftpTargetEvidence': target_copy_ev,
        'computedDoseStageIndices': {p['padId']: p['doseStageIndices'] for p in out_target['pads']},
        'computedRestoreRetractLiftIndices': {p['padId']: [p['restoreStageIndex'], p['retractStageIndex'], p['liftStageIndex']] for p in out_target['pads']},
        'bAccounting': b_accounting,
        'sourceTargetEvidence': {'path': str(source_target_path),
                                 'sha256': hashlib.sha256(source_target_bytes).hexdigest()},
    }
    if source_target_path.read_bytes() != source_target_bytes:
        fail('Authored source target record changed during preparation')
    recipe_path = out / 'recipe.json'
    recipe_path.write_text(json.dumps(recipe, indent=2, allow_nan=False) + '\n')
    # Run the normal offline native preview builder. Its Node policies verify
    # recipe stages, every B movement, source hashes, affine registration,
    # independent pad checks, target indices, clearance and gross accounting.
    native_out = out / 'native'
    cmd = [sys.executable, str(GENERIC), 'prepare', '--template', str(tp), '--barrier', str(bp),
           '--image', str(image), '--recipe', str(recipe_path), '--output', str(native_out)]
    try:
        completed = subprocess.run(cmd, check=True, text=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        fail('Generic offline native validator rejected prepared pair: ' + (exc.stderr or exc.stdout).strip())
    print(json.dumps({'targets': str(target_copy), 'recipe': str(recipe_path),
                      'previewRequest': str(native_out / 'preview-request.json'),
                      'doseStageIndices': recipe['computedDoseStageIndices'],
                      'BAccounting': b_accounting, 'nativeValidator': completed.stdout.strip(),
                      'enabled': False, 'motionDispatched': False}, indent=2))


def main_cli():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('template', 'barrier', 'image', 'profile', 'clearance-review', 'target-record', 'previous-report', 'ledger', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--xy-clearance-raw-z', type=float, required=True)
    args = parser.parse_args()
    try:
        main(args)
    except Exception as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main_cli()
