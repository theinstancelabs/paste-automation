#!/usr/bin/env python3
"""Author a disabled generic-scrap three-pad 6-degree/200 ms dwell comparison.

This script writes only a recipe for prepare-contiguous-batch.py. It never
connects to OpenPnP, creates evidence, previews, reserves budget, or dispatches.
"""
import argparse
import hashlib
import json
import math
import time
from pathlib import Path

WORK_Z = 58.45
CLEAR_Z = 53.45
ALLOWED_B = (-20, -6, -4, -3, -2, 2, 3, 4, 6, 20)


class InputError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise InputError(message)


def number(value, label):
    require(type(value) in (int, float) and math.isfinite(value), label + ' must be finite')
    return float(value)


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


def parse_doses(value):
    try:
        doses = [int(item.strip()) for item in value.split(',')]
    except (AttributeError, ValueError):
        raise InputError('--doses must be comma-separated whole degrees from 2,4,6')
    require(len(doses) == 3 and all(d in (2, 4, 6) for d in doses),
            '--doses must specify exactly three explicit values from 2,4,6')
    return doses


def parse_retractions(value):
    try:
        retractions = [int(item.strip()) for item in value.split(',')]
    except (AttributeError, ValueError):
        raise InputError('--retractions must be comma-separated whole degrees from 2,3,4,6')
    require(len(retractions) == 3 and all(r in (2, 3, 4, 6) for r in retractions),
            '--retractions must specify exactly three explicit values from 2,3,4,6')
    return retractions


def build_stages(raw, targets, gap_evidence, gap, uncertainty, doses, retractions=None):
    require(raw.get('Z') == WORK_Z and raw.get('A') == 720,
            'Fresh barrier must be at raw Z58.45 and A720')
    require(number(gap, 'estimated gap') - number(uncertainty, 'gap uncertainty') >= 0.1,
            'Provisional gap lower bound must remain at least 0.1 mm')
    require(isinstance(targets, dict) and set(targets) == {'wipe', 'conditioner', 'tests'},
            'Targets must name wipe, conditioner, and three test points only')
    wipe = xy_point(targets['wipe'], 'wipe')
    conditioner = xy_point(targets['conditioner'], 'conditioner')
    tests = [xy_point(p, 'test point') for p in targets['tests']]
    require(len(tests) == 3, 'Exactly three test points are required')
    require(len(doses) == 3 and all(type(d) is int and d in (2, 4, 6) for d in doses),
            'Exactly three explicit 2,4,6 degree doses are required')
    if retractions is None:
        retractions = [6, 6, 6]
    require(len(retractions) == 3 and all(type(r) is int and r in (2, 3, 4, 6) for r in retractions),
            'Exactly three explicit 2,3,4,6 degree retractions are required')
    points = [wipe, conditioner] + tests
    require(len({(p['X'], p['Y']) for p in points}) == 5, 'All five reviewed positions must be distinct')
    changed = [axis for axis in ('X', 'Y') if wipe[axis] != raw[axis]]
    require(len(changed) == 1 and abs(wipe[changed[0]] - raw[changed[0]]) <= 2,
            'Wipe point must differ from barrier by at most 2 mm on one XY axis')

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

    def move(point, wipe_move=False):
        if current['X'] != point['X']:
            extra = {}
            if wipe_move:
                extra = {'wipeReview': True, 'wipeReviewEvidence': gap_evidence,
                         'estimatedGapMm': gap, 'gapUncertaintyMm': uncertainty}
            add('X', point['X'], **extra)
        if current['Y'] != point['Y']:
            extra = {}
            if wipe_move:
                extra = {'wipeReview': True, 'wipeReviewEvidence': gap_evidence,
                         'estimatedGapMm': gap, 'gapUncertaintyMm': uncertainty}
            add('Y', point['Y'], **extra)

    # Prime 60 degrees, +20 relief, reviewed wipe, one 20-degree conditioner/R6.
    for i in range(3):
        stroke(-20, 2000 if i == 2 else 0)
    stroke(20, 1000)
    move(wipe, wipe_move=True)
    add('Z', CLEAR_Z)
    move(conditioner)
    add('Z', WORK_Z)
    stroke(-20, 2000)
    stroke(6, 500)
    add('Z', CLEAR_Z)

    for index, (point, dose, retract) in enumerate(zip(tests, doses, retractions)):
        # The conditioner retracts six degrees. At WORK_Z, undo it before
        # test one; at WORK_Z before tests two and three, undo the previous
        # retraction. The net dose advance accumulates across test points.
        move(point)
        add('Z', WORK_Z)
        stroke(-6 if index == 0 else -retractions[index - 1])
        stroke(-dose, 200)
        stroke(retract, 500)
        add('Z', CLEAR_Z)
    stroke(20)
    stroke(20, 2000)
    expected_gross = 152 + sum(doses) + sum(retractions) + sum(retractions[:2])
    require(gross == expected_gross, 'Internal gross accounting changed')
    require(len(stages) <= 40, 'Recipe exceeds the existing generic contiguous-batch 40-stage limit')
    return stages, gross, current


def make_parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True, help='new recipe JSON path; existing files are never overwritten')
    for name in ('template', 'barrier', 'profile', 'clearance-review', 'image', 'previous-report',
                 'previous-ledger', 'raw-bounds', 'head-clearance-bounds', 'targets'):
        p.add_argument('--' + name, required=True, help='explicit caller-supplied source path')
    p.add_argument('--reviewer', required=True)
    p.add_argument('--review', required=True, help='human-reviewed experimental question and route basis')
    p.add_argument('--doses', required=True, help='comma-separated per-pad degrees, for example 6,4,2')
    p.add_argument('--retractions', default='6,6,6', help='comma-separated per-pad return degrees (default 6,6,6)')
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
            barrier.get('controllerPositionVerified') is True and
            barrier.get('noMotionCommandSubmitted') is True and
            barrier.get('uncertainCompletion') is False,
            'Fresh successful no-motion position barrier required')
    raw = (barrier.get('afterQuerySnapshot') or {}).get('raw')
    require(isinstance(raw, dict) and set(raw) == set('XYZAB') and
            all(math.isfinite(number(raw[k], 'raw ' + k)) for k in 'XYZAB'),
            'Barrier must contain finite raw X/Y/Z/A/B')
    request = barrier.get('request') or {}
    require(request.get('jvmStartMs') == template.get('jvmStartMs') and
            barrier.get('liveConfigurationSha256') == template.get('liveConfigurationSha256'),
            'Barrier and template JVM/configuration mismatch')
    require(review.get('mode') == 'wet' and isinstance(review.get('basis'), str) and review.get('basis').strip(),
            'Fresh wet-mode human clearance review required')
    image_ev = evidence(image)
    require(review.get('imageEvidence') == image_ev, 'Clearance review must bind the supplied image')
    image_ms = image.stat().st_mtime_ns // 1_000_000
    require(0 <= now_ms - image_ms <= 300000, 'Reviewed image must be fresh within five minutes')
    require(review.get('rawZRange') == [CLEAR_Z, WORK_Z],
            'Clearance review must cover exact 53.45..58.45 raw Z interval')
    require(profile.get('provenance') == 'commissioning-provisional' and
            profile.get('precisionCalibrated') is False and profile.get('flowCalibrated') is False and
            profile.get('sessionId') == template.get('sessionId') and
            profile.get('jvmStartMs') == template.get('jvmStartMs') and
            profile.get('liveConfigurationSha256') == template.get('liveConfigurationSha256'),
            'Profile must remain same-session, provisional, and uncalibrated')
    prof_raw = profile.get('rawPose') or {}
    require(all(prof_raw.get(k) == raw[k] for k in ('X', 'Y', 'Z', 'A')),
            'Profile must bind exact barrier XYZ/A pose')
    gap = number(profile.get('estimatedGapMm'), 'profile estimated gap') + (raw['Z'] - WORK_Z)
    uncertainty = number(profile.get('gapUncertaintyMm'), 'profile gap uncertainty')
    require(gap - uncertainty >= 0.1, 'Work-height provisional gap lower bound must be at least 0.1 mm')
    require(previous.get('status') in ('completed-commissioning-stroke-awaiting-observation',
            'completed-dose-cycle-awaiting-observation', 'completed-contiguous-batch-awaiting-observation') and
            previous.get('uncertainCompletion') is False,
            'Previous verified terminal report required')
    require(ledger.get('status') == 'verified' and ledger.get('sessionId') == template.get('sessionId') and
            ledger.get('syringeId') == template.get('syringeId') and
            previous.get('completedLedgerSha256') == evidence(ledger_path)['sha256'],
            'Previous report must bind caller-supplied verified ledger')
    require(review.get('reviewedBy') and args.reviewer.strip() and len(args.review.strip()) >= 40,
            'Explicit reviewer and substantive route-review note required')

    clear_ev = evidence(review_path)
    doses = parse_doses(args.doses)
    retractions = parse_retractions(args.retractions)
    stages, gross, final_raw = build_stages(raw, targets, clear_ev, gap, uncertainty, doses, retractions)
    require(gross <= 238, 'Route exceeds requested gross ceiling')
    output = Path(args.output).resolve()
    require(not output.exists(), 'Refusing to overwrite existing output')
    recipe = {
        'mode': 'wet', 'targetSurface': 'scrap',
        'experimentQuestion': 'At fixed 4-degree dose, 200 ms dispense dwell, 500 ms retract dwell, and fixed 58.45 mm work height, compare explicit per-pad retract degrees while restoring each prior retraction before the next dose.',
        'doseDegrees': doses,
        'retractionDegrees': retractions,
        'routeReview': {'reviewer': args.reviewer.strip(), 'basis': args.review.strip(), 'reviewedMs': now_ms},
        'stages': stages, 'rawBounds': bounds, 'headClearanceBounds': head_bounds, 'xyClearanceRawZ': CLEAR_Z,
        'clearanceReviewEvidence': clear_ev, 'profileEvidence': evidence(profile_path),
        'previousReportEvidence': evidence(previous_path), 'previousLedgerPath': str(ledger_path),
        'targetsEvidence': evidence(args.targets), 'templateEvidence': evidence(template_path),
        'sourceBarrierEvidence': evidence(barrier_path),
        'routeAccounting': {'prefixGrossDegrees': 106, 'testSequenceGrossDegrees': gross - 146,
                            'finalIdleReliefGrossDegrees': 40, 'doseDegrees': doses,
                            'retractionDegrees': retractions, 'grossDegrees': gross,
                            'netBDegrees': final_raw['B'] - raw['B'], 'stageCount': len(stages),
                            'finalRaw': final_raw}
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        stream.write(json.dumps(recipe, indent=2, allow_nan=False) + '\n')
    return recipe


def main(argv=None):
    args = make_parser().parse_args(argv)
    recipe = build_recipe(args)
    print(json.dumps({'recipe': str(Path(args.output).resolve()),
                      'grossDegrees': recipe['routeAccounting']['grossDegrees'],
                      'netBDegrees': recipe['routeAccounting']['netBDegrees'],
                      'stageCount': recipe['routeAccounting']['stageCount'],
                      'enabled': False, 'previewCreated': False, 'motionDispatched': False}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit('error: ' + str(exc))
