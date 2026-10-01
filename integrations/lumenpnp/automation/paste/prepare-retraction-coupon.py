#!/usr/bin/env python3
"""Prepare one reviewed scrap retraction recipe offline; no camera, controller or dispatch access."""
import argparse
import contextlib
import importlib.util
import io
import json
import math
import tempfile
from pathlib import Path
from types import SimpleNamespace


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


WIPE = module('purge_wipe_recipe', 'prepare-purge-wipe-recipe.py')
BATCH = module('contiguous_batch', 'prepare-contiguous-batch.py')


def number(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(label + ' must be finite numeric')
    return value


def stages_for(experiment, review_evidence, gap, uncertainty):
    e = experiment
    if e.get('schema') != 1 or e.get('scope') != 'reviewed-scrap-retraction-coupon':
        raise ValueError('Explicit scrap retraction experiment required')
    fixed = {'primeDegrees': 40, 'preWipeReliefDegrees': 20, 'idleReliefDegrees': 20,
             'conditioningDoseDegrees': 20}
    for key, expected in fixed.items():
        if type(e.get(key)) is not int or e[key] != expected:
            raise ValueError('Fixed experiment parameter changed: ' + key)
    dwell = e.get('dwellMilliseconds', 2000)
    if type(dwell) is not int or dwell not in (200, 500, 2000):
        raise ValueError('Forward-dose dwell must be 200, 500 or 2000 milliseconds')
    if type(e.get('doseDegrees')) is not int or e['doseDegrees'] not in (6, 12, 20):
        raise ValueError('Dose must be 6, 12 or 20 degrees')
    if type(e.get('retractDegrees')) is not int or e['retractDegrees'] not in (3, 6):
        raise ValueError('Retraction must be 3 or 6 degrees')
    raw = e.get('startRaw')
    if not isinstance(raw, dict) or set(raw) != {'X', 'Y', 'Z', 'A', 'B'}:
        raise ValueError('Exact five-axis startRaw required')
    for axis, value in raw.items():
        number(value, axis)
    work = number(e.get('workRawZ'), 'workRawZ')
    clear = number(e.get('clearanceRawZ'), 'clearanceRawZ')
    if any(abs(v*100-round(v*100)) > 1e-7 for v in (work, clear)):
        raise ValueError('Working and clearance Z must use the 0.01 mm reporting grid')
    if raw['Z'] != work or work-clear != 5:
        raise ValueError('Start must be at reviewed working Z; clearance is exactly 5 mm higher')
    targets = e.get('targetsXY')
    if not isinstance(targets, list) or len(targets) != 5:
        raise ValueError('Five ordered XY targets required: wipe end, conditioning point, three tests')
    for target in targets:
        if not isinstance(target, dict) or set(target) != {'X', 'Y'}:
            raise ValueError('Each target must contain exactly X and Y')
        for axis in ('X', 'Y'):
            value = number(target[axis], 'target ' + axis)
            if abs(value*100-round(value*100)) > 1e-7:
                raise ValueError('Target XY must use the 0.01 mm reporting grid')
    if len({(target['X'], target['Y']) for target in targets}) != 5:
        raise ValueError('Five distinct target points required')
    changed = [axis for axis in ('X', 'Y') if targets[0][axis] != raw[axis]]
    if len(changed) != 1:
        raise ValueError('Named wipe must change exactly one XY axis')
    axis = changed[0]
    stages = WIPE.recipe_stages(raw, review_evidence, axis, targets[0][axis]-raw[axis],
                               clear, gap, uncertainty, 40, 20, 0)
    at = dict(raw)
    poses = [dict(at)]
    for stage in stages:
        at[stage['axis']] = stage['target']
        poses.append(dict(at))

    def add(axis, target, **extra):
        if target == at[axis]:
            return
        if axis != 'B' and abs(target-at[axis]) > (5 if axis == 'Z' else 10):
            raise ValueError('Linear stage exceeds existing reviewed batch limit')
        if axis in ('X', 'Y') and at['Z'] != clear:
            raise ValueError('Only the named initial wipe permits working-height XY')
        stages.append({'axis': axis, 'target': target, **extra})
        at[axis] = target
        poses.append(dict(at))

    def stroke(delta, dwell=0):
        add('B', at['B']+delta, gapEvidence=review_evidence,
            estimatedGapMm=gap+(work-at['Z']), gapUncertaintyMm=uncertainty,
            dwellMilliseconds=dwell)

    for index, target in enumerate(targets[1:]):
        add('X', target['X'])
        add('Y', target['Y'])
        add('Z', work)
        if index:
            stroke(-e['retractDegrees'])
        dose = 20 if index == 0 else e['doseDegrees']
        # Twelve degrees uses two existing -6 stages, with dwell only after the second.
        if dose == 12:
            stroke(-6)
            stroke(-6, dwell)
        else:
            stroke(-dose, dwell)
        stroke(e['retractDegrees'])
        add('Z', clear)
    stroke(20, 2000)
    gross = sum(abs(right['B']-left['B']) for left, right in zip(poses, poses[1:]))
    return stages, poses, {'grossCommandedDegrees': gross, 'netDegrees': at['B']-raw['B'],
                           'finalRaw': dict(at), 'doseDegrees': e['doseDegrees'],
                           'retractDegrees': e['retractDegrees'], 'forwardDwellMilliseconds': dwell,
                           'testRetractionRatio': e['retractDegrees']/e['doseDegrees']}


def build(args):
    experiment, ep, _ = WIPE.load(args.experiment)
    profile, pp, _ = WIPE.load(args.profile)
    review, rp, _ = WIPE.load(args.review)
    barrier, bp, _ = WIPE.load(args.barrier)
    if WIPE.checked_evidence(review.get('experimentEvidence'), 'review experiment') != WIPE.evidence(ep):
        raise ValueError('Review does not bind supplied experiment')
    if WIPE.checked_evidence(review.get('imageEvidence'), 'review image') != WIPE.evidence(args.image):
        raise ValueError('Review does not bind supplied image')
    if WIPE.checked_evidence(profile.get('measurementEvidence'), 'profile review') != WIPE.evidence(rp):
        raise ValueError('Profile does not bind supplied authored review')
    raw = barrier.get('afterQuerySnapshot', {}).get('raw')
    if not BATCH.same(experiment.get('startRaw'), raw):
        raise ValueError('Experiment startRaw differs from supplied barrier')
    gap = number(profile.get('estimatedGapMm'), 'profile gap')
    uncertainty = number(profile.get('gapUncertaintyMm'), 'profile uncertainty')
    stages, poses, accounting = stages_for(experiment, WIPE.evidence(rp), gap, uncertainty)
    wipe = stages[3]
    # Reuse existing identity, reviewed image, provisional profile and current-ledger checks.
    recipe = WIPE.build(bp, pp, rp, args.previous_report, args.ledger, wipe['axis'],
                        wipe['target']-raw[wipe['axis']], experiment['clearanceRawZ'],
                        gap, uncertainty, 40, 20, 0)
    bounds = {axis: {'min': min(p[axis] for p in poses), 'max': max(p[axis] for p in poses)}
              for axis in ('X', 'Y', 'Z', 'B')}
    heads = {}
    for name in ('N1', 'N2'):
        heads[name] = {}
        native = barrier['afterQuerySnapshot']['nativePoses'][name]
        for axis in ('X', 'Y', 'Z'):
            sign = -1 if name == 'N2' and axis == 'Z' else 1
            values = [native[axis.lower()]+sign*(p[axis]-raw[axis]) for p in poses]
            heads[name]['min'+axis] = min(values)-0.001
            heads[name]['max'+axis] = max(values)+0.001
    recipe.update(targetSurface='scrap', stages=stages, rawBounds=bounds,
                  headClearanceBounds=heads, bAccounting=accounting,
                  experimentEvidence=WIPE.evidence(ep), templateEvidence=WIPE.evidence(args.template))
    recipe['limitations'] = ['Recipe only; fresh native preview, runtime gates and physical review remain required.',
                            'Retraction ratio is motor travel, not measured paste volume or firmware pressure advance.']
    # Exercise the installed offline request gate without retaining or dispatching a request.
    with tempfile.TemporaryDirectory(prefix='paste-retraction-prepare-') as temporary:
        staged = Path(temporary)/'recipe.json'
        WIPE.write_exclusive(staged, recipe)
        with contextlib.redirect_stdout(io.StringIO()):
            BATCH.prepare(SimpleNamespace(template=args.template, barrier=str(bp), image=args.image,
                                          recipe=str(staged), output=str(Path(temporary)/'validation')))
    # Fail if any consumed evidence changed during validation; never rely on a cached ledger.
    for key in ('experimentEvidence', 'profileEvidence', 'clearanceReviewEvidence',
                'previousReportEvidence', 'previousLedgerEvidence', 'barrierEvidence', 'templateEvidence'):
        WIPE.checked_evidence(recipe[key], key)
    WIPE.checked_evidence(review['imageEvidence'], 'image')
    return recipe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ('experiment', 'template', 'barrier', 'profile', 'review', 'image',
                     'previous-report', 'ledger', 'output'):
        parser.add_argument('--'+argument, required=True)
    args = parser.parse_args()
    try:
        result = build(args)
        WIPE.write_exclusive(args.output, result)
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.error(str(error))
    print(json.dumps({'recipe': str(Path(args.output).resolve()), 'bAccounting': result['bAccounting']}))


if __name__ == '__main__':
    main()
