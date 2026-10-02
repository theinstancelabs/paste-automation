#!/usr/bin/env python3
"""Prepare an offline, disabled XY fiducial route after manual homing.

Consumes an explicit, hash-bound surface/clearance review and delegates to the
existing contiguous-batch preparer. It does not author review attestations or
dispatch motion.
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
PREP = ROOT / 'automation/paste/prepare-contiguous-batch.py'
NORTH_REFERENCE_RAW_Z = 58.85
NORTH_REFERENCE_UNCERTAINTY_MM = 0.3
XY_STEP_MM = 9.9
Z_STEP_MM = 4.9
CLEARANCE_Z = 32.25


def fail(message):
    raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def load(path):
    p = Path(path).resolve(strict=True)
    data = p.read_bytes()
    return json.loads(data), p, data


def evidence(path):
    p = Path(path).resolve(strict=True)
    b = p.read_bytes()
    if not b:
        fail(f'Empty evidence: {p}')
    return {'path': str(p), 'sha256': hashlib.sha256(b).hexdigest()}


def chunks(start, end, limit):
    delta = end - start
    if abs(delta) <= 1e-9:
        return []
    count = math.ceil(abs(delta) / limit)
    return [round(start + delta * i / count, 2) for i in range(1, count)] + [round(end, 2)]


def route(raw, poses, target_x, target_y, target_z=None):
    if not isinstance(raw, dict) or set(raw) != set('XYZAB') or any(not finite(raw[k]) for k in 'XYZAB'):
        fail('Barrier raw pose must contain finite X/Y/Z/A/B')
    if not isinstance(poses, dict) or set(poses) != {'N1', 'N2', 'top', 'bottom'}:
        fail('Barrier must contain all four native poses')
    for head in ('N1', 'N2'):
        if not isinstance(poses[head], dict) or any(not finite(poses[head].get(k)) for k in ('x', 'y', 'z')):
            fail(f'Barrier {head} native XYZ pose must be finite')
    if not all(finite(v) for v in (target_x, target_y)):
        fail('Target X/Y must be finite numbers')
    if target_z is not None and not finite(target_z):
        fail('Optional final Z must be a finite number')
    if any(abs(raw[k] * 100 - round(raw[k] * 100)) > 1e-7 for k in ('X', 'Y', 'Z')):
        fail('Barrier X/Y/Z must lie on the 0.01 mm coordinate grid')
    if any(abs(v * 100 - round(v * 100)) > 1e-7 for v in (target_x, target_y)):
        fail('Target X/Y must lie on the 0.01 mm coordinate grid')
    target_x, target_y = round(target_x, 2), round(target_y, 2)
    final_z = CLEARANCE_Z if target_z is None else round(target_z, 2)
    if target_z is not None and abs(target_z * 100 - round(target_z * 100)) > 1e-7:
        fail('Optional final Z must lie on the 0.01 mm coordinate grid')
    if abs(raw['Z'] - CLEARANCE_Z) > 1e-7 and raw['Z'] < CLEARANCE_Z:
        fail('Barrier Z is below requested 32.25 mm clearance; automatic lowering is prohibited')
    at = dict(raw)
    stages = []
    route_points = [dict(at)]

    def add(axis, value):
        nonlocal at
        value = round(value, 2)
        end = dict(at)
        end[axis] = value
        stages.append({'axis': axis, 'target': value})
        at = end
        route_points.append(dict(at))

    # With this machine's raw-Z convention, 32.25 is the reviewed air transit
    # plane. Reach it before any XY change, then optionally set the final Z.
    for z in chunks(raw['Z'], CLEARANCE_Z, Z_STEP_MM):
        add('Z', z)
    for axis, target in (('X', target_x), ('Y', target_y)):
        for value in chunks(at[axis], target, XY_STEP_MM):
            add(axis, value)
    for z in chunks(CLEARANCE_Z, final_z, Z_STEP_MM):
        add('Z', z)
    if len(stages) > 40:
        fail('Route exceeds the existing 40-stage contiguous-batch limit')
    # Assert the one-axis sequence and all per-stage bounds from the resulting
    # snapshots, while preserving raw A/B exactly.
    previous = route_points[0]
    for stage, current in zip(stages, route_points[1:]):
        changed = [k for k in 'XYZAB' if current[k] != previous[k]]
        if changed != [stage['axis']] or current['A'] != raw['A'] or current['B'] != raw['B']:
            fail('Route must change only one XYZ axis and preserve A/B')
        limit = Z_STEP_MM if stage['axis'] == 'Z' else XY_STEP_MM
        if abs(current[stage['axis']] - previous[stage['axis']]) > limit + 1e-8:
            fail('Route stage exceeds its axis step bound')
        previous = current
    bounds = {axis: {'min': min(p[axis] for p in route_points),
                     'max': max(p[axis] for p in route_points)} for axis in 'XYZB'}
    head_bounds = {}
    for name in ('N1', 'N2'):
        h = {}
        for axis in 'XYZ':
            sign = -1 if axis == 'Z' and name == 'N2' else 1
            projected = [poses[name][axis.lower()] + sign * (p[axis] - raw[axis]) for p in route_points]
            h['min' + axis] = min(projected) - 0.001
            h['max' + axis] = max(projected) + 0.001
        head_bounds[name] = h
    return stages, route_points, bounds, head_bounds


def profile_record(template, barrier, raw, historical_measurement_evidence, clearance_review_evidence):
    request = barrier.get('request') or {}
    start_z = raw['Z']
    gap = NORTH_REFERENCE_RAW_Z - start_z
    if gap <= NORTH_REFERENCE_UNCERTAINTY_MM:
        fail('North-reference provisional gap lower bound must remain positive')
    basis = ('Provisional air-only gap estimate from north reference raw Z 58.85 mm '
             f'minus barrier start raw Z {start_z:.2f} mm; uncertainty ±0.30 mm. '
             'Reference estimate only; no contact or precision calibration is asserted. '
             f'Historical surface measurement evidence {historical_measurement_evidence["path"]} '
             f'({historical_measurement_evidence["sha256"]}) is retained unchanged from the original template profile; '
             'it is not a new measurement. Current route clearance relies only on the separately authored '
             f'clearance review {clearance_review_evidence["path"]} ({clearance_review_evidence["sha256"]}).')
    return {
        'provenance': 'commissioning-provisional', 'precisionCalibrated': False,
        'flowCalibrated': False, 'sessionId': template['sessionId'],
        'syringeId': template['syringeId'],
        'jvmStartMs': request.get('jvmStartMs'),
        'liveConfigurationSha256': barrier.get('liveConfigurationSha256'),
        'estimatedGapMm': gap, 'gapUncertaintyMm': NORTH_REFERENCE_UNCERTAINTY_MM,
        'basis': basis, 'rawPose': {k: raw[k] for k in 'XYZA'},
        'measurementEvidence': copy.deepcopy(historical_measurement_evidence),
    }


def prepare(args):
    template, template_path, template_bytes = load(args.template)
    # Accept either the historical request template or its completed report.
    if isinstance(template.get('request'), dict):
        template = template['request']
    barrier, barrier_path, barrier_bytes = load(args.barrier)
    wet_report, wet_path, wet_bytes = load(args.previous_report)
    ledger, ledger_path, ledger_bytes = load(args.ledger)
    review, review_path, review_bytes = load(args.clearance_review)
    manual_ev = evidence(args.manual_home_ledger_anchor_evidence)
    proof, proof_path, proof_bytes = load(manual_ev['path'])
    image_ev = evidence(args.image)
    image = Path(image_ev['path'])
    image_bytes = image.read_bytes()
    captured = image.stat().st_mtime_ns // 1_000_000
    now = int(time.time() * 1000)
    if not (image_bytes.startswith(b'\x89PNG\r\n\x1a\n') or image_bytes.startswith(b'\xff\xd8\xff')):
        fail('Review image must be PNG or JPEG')
    if captured > now or now - captured > 300_000:
        fail('Review image must be no more than five minutes old')
    if review.get('mode') != 'air' or not isinstance(review.get('reviewedBy'), str) or not review['reviewedBy'].strip():
        fail('A separately authored, named air clearance/surface review is required')
    if not isinstance(review.get('basis'), str) or len(review['basis'].strip()) < 30:
        fail('Explicit substantive clearance/surface review basis is required')
    if type(review.get('reviewedMs')) is not int or not captured <= review['reviewedMs'] <= now or now - review['reviewedMs'] > 300_000:
        fail('Explicit review timestamp must follow the image and be no more than five minutes old')
    if review.get('imageEvidence') != image_ev:
        fail('Explicit review must hash-bind the supplied image')
    expected_review_range = review.get('rawZRange')
    req = barrier.get('request') or {}
    snap = barrier.get('afterQuerySnapshot') or {}
    if (barrier.get('status') != 'completed-read-only-position-barrier'
            or barrier.get('controllerPositionVerified') is not True
            or barrier.get('noMotionCommandSubmitted') is not True
            or barrier.get('uncertainCompletion') is not False):
        fail('Current successful no-motion barrier required')
    raw = snap.get('raw')
    poses = snap.get('nativePoses')
    stages, points, bounds, heads = route(raw, poses, args.target_x, args.target_y, args.target_z)
    z_values = [p['Z'] for p in points]
    if expected_review_range != [min(z_values), max(z_values)]:
        fail('Explicit review rawZRange must exactly cover the route Z envelope')
    # The old air request is only an identity/provenance template. All pose and
    # route coordinates come from the fresh barrier and explicit new target.
    source_request = wet_report.get('request') or {}
    if (template.get('sessionId') != wet_report.get('request', {}).get('sessionId')
            or ledger.get('status') != 'verified'
            or ledger.get('sessionId') != template.get('sessionId')
            or ledger.get('syringeId') != template.get('syringeId')
            or wet_report.get('uncertainCompletion') is not False
            or wet_report.get('completedLedgerSha256') != hashlib.sha256(ledger_bytes).hexdigest()
            or wet_report.get('id') != source_request.get('id')):
        fail('Verified wet terminal report and ledger must match the immutable template identities')
    manual_review = proof
    if (manual_review.get('scope') not in ('manual-home-ledger-anchor-continuity', 'manual-home-ledger-anchor-continuation')
            or manual_review.get('sessionId') != template.get('sessionId')
            or manual_review.get('currentJvmStartMs') != barrier.get('request', {}).get('jvmStartMs')
            or manual_review.get('currentConfigurationSha256') != barrier.get('liveConfigurationSha256')
            or manual_review.get('currentBarrierEvidence') != evidence(barrier_path)
            or manual_review.get('currentLedgerEvidence') != {'path': str(ledger_path), 'sha256': hashlib.sha256(ledger_bytes).hexdigest()}
            or manual_review.get('latestTerminalReportEvidence') != {'path': str(wet_path), 'sha256': hashlib.sha256(wet_bytes).hexdigest()}):
        fail('Manual-home continuity proof must bind this exact wet report and ledger')
    profile_evidence = template.get('profileEvidence')
    if not isinstance(profile_evidence, dict) or not isinstance(profile_evidence.get('path'), str):
        fail('Historical template profile evidence is required')
    historical_profile, historical_profile_path, historical_profile_bytes = load(profile_evidence['path'])
    if hashlib.sha256(historical_profile_bytes).hexdigest() != profile_evidence.get('sha256'):
        fail('Historical template profile hash mismatch')
    if (historical_profile.get('sessionId') != template.get('sessionId')
            or historical_profile.get('syringeId') != template.get('syringeId')
            or historical_profile.get('provenance') != 'commissioning-provisional'
            or historical_profile.get('precisionCalibrated') is not False
            or historical_profile.get('flowCalibrated') is not False):
        fail('Historical profile must bind the template session/syringe and remain provisional')
    historical_measurement = historical_profile.get('measurementEvidence')
    if not isinstance(historical_measurement, dict) or not isinstance(historical_measurement.get('path'), str):
        fail('Historical profile must contain actual hash-bound surface measurement evidence')
    measurement_path = Path(historical_measurement['path']).resolve(strict=True)
    measurement_bytes = measurement_path.read_bytes()
    if not measurement_bytes or hashlib.sha256(measurement_bytes).hexdigest() != historical_measurement.get('sha256'):
        fail('Historical surface measurement evidence hash mismatch')
    clearance_ev = evidence(review_path)
    profile = profile_record(template, barrier, raw, historical_measurement, clearance_ev)
    gap = profile['estimatedGapMm']
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)

    def write(name, value):
        path = output / name
        with path.open('x', encoding='utf-8') as f:
            json.dump(value, f, indent=2, allow_nan=False)
            f.write('\n')
        return path

    profile_path = write('profile.json', profile)
    recipe = {
        'mode': 'air', 'stages': stages, 'rawBounds': bounds,
        'headClearanceBounds': heads, 'xyClearanceRawZ': CLEARANCE_Z,
        'clearanceReviewEvidence': evidence(review_path),
        'profileEvidence': evidence(profile_path),
        'previousReportEvidence': evidence(wet_path),
        'previousLedgerPath': str(ledger_path),
    }
    recipe_path = write('recipe.json', recipe)
    generated_template = write('template.json', template)
    prepared = output / 'prepared'
    cmd = [sys.executable, str(PREP), 'prepare', '--template', str(generated_template),
           '--barrier', str(barrier_path), '--image', str(image), '--recipe', str(recipe_path),
           '--output', str(prepared), '--manual-home-ledger-anchor-evidence', str(proof_path)]
    try:
        result = subprocess.run(cmd, cwd=ROOT, check=True, text=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        fail('Existing disabled contiguous-batch preparer rejected route: ' + (exc.stderr or exc.stdout or str(exc)).strip())
    for path, before in ((template_path, template_bytes), (barrier_path, barrier_bytes),
                         (wet_path, wet_bytes), (ledger_path, ledger_bytes),
                         (review_path, review_bytes), (proof_path, proof_bytes),
                         (image, image_bytes), (historical_profile_path, historical_profile_bytes),
                         (measurement_path, measurement_bytes)):
        if path.read_bytes() != before:
            fail('Evidence source changed during preparation: ' + str(path))
    print(json.dumps({
        'output': str(output), 'previewRequest': str(prepared / 'preview-request.json'),
        'mode': 'air', 'enabled': False, 'motionDispatched': False,
        'stageCount': len(stages), 'stages': stages,
        'startGapEstimateMm': gap, 'startGapUncertaintyMm': NORTH_REFERENCE_UNCERTAINTY_MM,
        'XYClearanceRawZ': CLEARANCE_Z, 'AandBPreserved': True,
        'preparerOutput': result.stdout.strip(),
    }, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--template', required=True, help='historical reviewed identity template/request or report')
    p.add_argument('--barrier', required=True, help='current read-only position barrier report')
    p.add_argument('--previous-report', required=True, help='verified current wet terminal report')
    p.add_argument('--ledger', required=True, help='current verified wet ledger')
    p.add_argument('--manual-home-ledger-anchor-evidence', required=True, help='current manual-home continuity proof')
    p.add_argument('--image', required=True, help='current reviewed stationary image')
    p.add_argument('--clearance-review', required=True, help='separately authored explicit surface/clearance review JSON')
    p.add_argument('--target-x', required=True, type=float)
    p.add_argument('--target-y', required=True, type=float)
    p.add_argument('--target-z', type=float, help='optional final Z after XY; defaults to 32.25')
    p.add_argument('--output', required=True, help='new exclusive output directory')
    args = p.parse_args()
    try:
        prepare(args)
    except Exception as exc:
        p.error(str(exc))


if __name__ == '__main__':
    main()
