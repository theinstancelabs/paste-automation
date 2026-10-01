#!/usr/bin/env python3
"""Build an offline generic-batch recipe for a reviewed 12/12/12 then 6/6/6 scrap sequence.

This script only writes a recipe JSON for prepare-contiguous-batch.py. It never reads
OpenPnP state, creates review evidence, previews, reserves budget, or dispatches motion.
All coordinates and source evidence are caller supplied and must be freshly reviewed.
"""
import argparse
import hashlib
import json
import math
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK_Z = 58.45
CLEAR_Z = 53.45
ALLOWED_B = (-20, -6, -2, 2, 6, 20)


class InputError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise InputError(message)


def number(x, label):
    require(type(x) in (int, float) and math.isfinite(x), label + ' must be finite')
    return float(x)


def read_json(path):
    p = Path(path).resolve(strict=True)
    return json.loads(p.read_text()), p


def evidence(path):
    p = Path(path).resolve(strict=True)
    data = p.read_bytes()
    require(bool(data), 'Evidence is empty: ' + str(p))
    return {'path': str(p), 'sha256': hashlib.sha256(data).hexdigest()}


def xy_point(value, label):
    require(isinstance(value, dict) and set(value) == {'X', 'Y'}, label + ' must contain X and Y only')
    point = {axis: number(value[axis], label + ' ' + axis) for axis in ('X', 'Y')}
    require(all(abs(v * 100 - round(v * 100)) < 1e-7 for v in point.values()), label + ' must use 0.01 mm grid')
    return point


def build_stages(raw, targets, gap_evidence, gap, uncertainty, work_z=WORK_Z, clear_z=CLEAR_Z):
    require(work_z == WORK_Z and clear_z == CLEAR_Z, 'This reviewed experiment is fixed at work Z 58.45 and clearance Z 53.45')
    require(raw.get('Z') == work_z and raw.get('A') == 720, 'Barrier must be at raw Z58.45 and A720')
    require(gap - uncertainty >= 0.1, 'Provisional gap lower bound must remain at least 0.1 mm')
    require(isinstance(targets, dict) and set(targets) == {'wipe', 'conditioner', 'sacrificial', 'tests'},
            'Targets must name wipe, conditioner, three sacrificial points, and three test points')
    wipe = xy_point(targets['wipe'], 'wipe')
    conditioner = xy_point(targets['conditioner'], 'conditioner')
    sacrificial = [xy_point(p, 'sacrificial point') for p in targets['sacrificial']]
    tests = [xy_point(p, 'test point') for p in targets['tests']]
    require(len(sacrificial) == len(tests) == 3, 'Exactly three sacrificial and three test points are required')
    all_points = [wipe, conditioner] + sacrificial + tests
    require(len({(p['X'], p['Y']) for p in all_points}) == 8, 'All eight reviewed positions must be distinct')
    changed = [axis for axis in ('X', 'Y') if wipe[axis] != raw[axis]]
    require(len(changed) == 1 and abs(wipe[changed[0]] - raw[changed[0]]) <= 2,
            'Wipe point must differ from barrier by at most 2 mm along exactly one XY axis')

    stages = []
    current = dict(raw)
    gross = 0

    def add(axis, target, **extra):
        nonlocal gross
        target = number(target, 'stage target')
        delta = target - current[axis]
        if delta == 0:
            return
        if axis == 'B':
            require(delta in ALLOWED_B, 'B stage outside existing admitted increments: ' + str(delta))
            extra.update(gapEvidence=gap_evidence, estimatedGapMm=gap, gapUncertaintyMm=uncertainty)
            gross += abs(delta)
        elif axis in ('X', 'Y'):
            require(abs(delta) <= 10, 'XY stage exceeds existing 10 mm bound')
        elif axis == 'Z':
            require(abs(delta) <= 5, 'Z stage exceeds existing 5 mm bound')
        stages.append({'axis': axis, 'target': target, **extra})
        current[axis] = target

    def stroke(delta, dwell=0):
        add('B', current['B'] + delta, dwellMilliseconds=dwell)

    def move_to(point):
        add('X', point['X'])
        add('Y', point['Y'])

    def deposit(point, dose):
        move_to(point)
        add('Z', work_z)
        stroke(-2)  # Restore the preceding R2 before each deposit.
        if dose == 12:
            stroke(-6)
            stroke(-6, 2000)
        else:
            stroke(-6, 2000)
        stroke(2, 500)
        add('Z', clear_z)

    # Existing 60-degree prime, +20 pre-wipe relief, reviewed wipe, and single 20-degree conditioner.
    for i in range(3):
        stroke(-20, 2000 if i == 2 else 0)
    stroke(20, 1000)
    wipe_axis = 'X' if wipe['X'] != raw['X'] else 'Y'
    add(wipe_axis, wipe[wipe_axis], wipeReview=True, wipeReviewEvidence=gap_evidence,
        estimatedGapMm=gap, gapUncertaintyMm=uncertainty)
    add('Z', clear_z)
    move_to(conditioner)
    add('Z', work_z)
    stroke(-20, 2000)
    stroke(2, 500)
    add('Z', clear_z)

    for point in sacrificial:
        deposit(point, 12)
    for point in tests:
        deposit(point, 6)

    stroke(20)
    stroke(20, 2000)
    require(gross == 220, 'Internal gross accounting changed')
    return stages, gross, current


def make_parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True, help='new recipe JSON path; existing files are never overwritten')
    for name in ('template', 'barrier', 'profile', 'clearance-review', 'image', 'previous-report',
                 'previous-ledger', 'raw-bounds', 'head-clearance-bounds', 'targets'):
        p.add_argument('--' + name, required=True, help='explicit caller-supplied source path')
    p.add_argument('--reviewer', required=True)
    p.add_argument('--review', required=True, help='human-reviewed experimental question and route basis')
    return p


def build_recipe(args, now_ms=None):
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    template, template_path = read_json(args.template)
    barrier, barrier_path = read_json(args.barrier)
    profile, profile_path = read_json(args.profile)
    review, review_path = read_json(args.clearance_review)
    previous, previous_path = read_json(args.previous_report)
    ledger, ledger_path = read_json(args.previous_ledger)
    bounds, _ = read_json(args.raw_bounds)
    head_bounds, _ = read_json(args.head_clearance_bounds)
    targets, _ = read_json(args.targets)
    image = Path(args.image).resolve(strict=True)

    require(barrier.get('status') == 'completed-read-only-position-barrier' and
            barrier.get('controllerPositionVerified') is True and barrier.get('noMotionCommandSubmitted') is True and
            barrier.get('uncertainCompletion') is False, 'Fresh successful no-motion barrier required')
    raw = (barrier.get('afterQuerySnapshot') or {}).get('raw')
    require(isinstance(raw, dict) and set(raw) == set('XYZAB') and all(math.isfinite(number(raw[k], 'raw ' + k)) for k in 'XYZAB'),
            'Barrier must contain finite raw X/Y/Z/A/B')
    request = barrier.get('request') or {}
    require(request.get('jvmStartMs') == template.get('jvmStartMs') and
            barrier.get('liveConfigurationSha256') == template.get('liveConfigurationSha256'),
            'Barrier and template JVM/configuration mismatch')
    require(review.get('mode') == 'wet' and isinstance(review.get('basis'), str) and review.get('basis').strip(),
            'Fresh wet-mode human clearance review required')
    image_ev = evidence(image)
    require(review.get('imageEvidence') == image_ev, 'Clearance review must bind the caller-supplied image')
    image_ms = image.stat().st_mtime_ns // 1_000_000
    require(0 <= now_ms - image_ms <= 300000, 'Reviewed image must be fresh within five minutes')
    require(review.get('rawZRange') == [CLEAR_Z, WORK_Z], 'Clearance review must cover exact 53.45..58.45 raw Z interval')
    require(profile.get('provenance') == 'commissioning-provisional' and profile.get('precisionCalibrated') is False and
            profile.get('flowCalibrated') is False and profile.get('sessionId') == template.get('sessionId') and
            profile.get('jvmStartMs') == template.get('jvmStartMs') and
            profile.get('liveConfigurationSha256') == template.get('liveConfigurationSha256'),
            'Profile must be same-session and explicitly provisional')
    prof_raw = profile.get('rawPose') or {}
    require(all(prof_raw.get(k) == raw[k] for k in ('X', 'Y', 'Z', 'A')), 'Profile must bind exact barrier XYZ/A pose')
    estimated_gap = number(profile.get('estimatedGapMm'), 'profile estimated gap') + raw['Z'] - WORK_Z
    uncertainty = number(profile.get('gapUncertaintyMm'), 'profile gap uncertainty')
    require(estimated_gap - uncertainty >= 0.1, 'Work-height provisional gap lower bound must be at least 0.1 mm')
    require(previous.get('status') in ('completed-commissioning-stroke-awaiting-observation',
            'completed-dose-cycle-awaiting-observation', 'completed-contiguous-batch-awaiting-observation') and
            previous.get('uncertainCompletion') is False, 'Previous verified terminal report required')
    require(ledger.get('status') == 'verified' and ledger.get('sessionId') == template.get('sessionId') and
            ledger.get('syringeId') == template.get('syringeId') and
            previous.get('completedLedgerSha256') == evidence(ledger_path)['sha256'],
            'Previous report must bind caller-supplied verified ledger')
    require(review.get('reviewedBy') and args.reviewer.strip() and len(args.review.strip()) >= 40,
            'Explicit reviewer and substantive route-review note required')

    clear_ev = evidence(review_path)
    stages, gross, final_raw = build_stages(raw, targets, clear_ev, estimated_gap, uncertainty)
    require(len(stages) <= 64, 'Route exceeds the dedicated 64-stage comparison scope')
    require(gross <= 238, 'Route exceeds the requested 238-degree gross ceiling')
    output = Path(args.output).resolve()
    require(not output.exists(), 'Refusing to overwrite existing output')
    recipe = {
        'mode': 'wet',
        'targetSurface': 'scrap-sequence-comparison',
        'sequenceProtocol': 'three-12-degree-sacrificial-then-three-6-degree-test-r2',
        'experimentQuestion': 'After three 12-degree sacrificial deposits, are three following 6-degree/R2 deposits repeatable in footprint at the same reviewed work height?',
        'routeReview': {'reviewer': args.reviewer.strip(), 'basis': args.review.strip(), 'reviewedMs': now_ms},
        'stages': stages,
        'rawBounds': bounds,
        'headClearanceBounds': head_bounds,
        'xyClearanceRawZ': CLEAR_Z,
        'clearanceReviewEvidence': clear_ev,
        'profileEvidence': evidence(profile_path),
        'previousReportEvidence': evidence(previous_path),
        'previousLedgerPath': str(ledger_path),
        'targetsEvidence': evidence(args.targets),
        'templateEvidence': evidence(template_path),
        'sourceBarrierEvidence': evidence(barrier_path),
        'routeAccounting': {'prefixGrossDegrees': 102, 'sacrificial12R2GrossDegrees': 48,
                            'test6R2GrossDegrees': 30, 'finalIdleReliefGrossDegrees': 40,
                            'grossDegrees': gross, 'stageCount': len(stages), 'finalRaw': final_raw}
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        stream.write(json.dumps(recipe, indent=2, allow_nan=False) + '\n')
    return recipe


def main(argv=None):
    args = make_parser().parse_args(argv)
    recipe = build_recipe(args)
    print(json.dumps({'recipe': str(Path(args.output).resolve()), 'grossDegrees': recipe['routeAccounting']['grossDegrees'],
                      'stageCount': recipe['routeAccounting']['stageCount'], 'enabled': False,
                      'previewCreated': False, 'motionDispatched': False}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit('error: ' + str(exc))
