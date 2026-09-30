#!/usr/bin/env python3
"""Offline same-XY side-view endpoint intervals. No camera, machine or configuration API."""
import argparse
import hashlib
import io
import itertools
import json
import math
from pathlib import Path
from PIL import Image
from deposit_metrics import components


def number(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(label + ' must be finite')
    return value


def positive(value, label):
    if number(value, label) <= 0:
        raise ValueError(label + ' must be positive')
    return value


def read_bound(ref):
    path = Path(ref['path']).resolve(strict=True)
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != ref['sha256']:
        raise ValueError('Evidence hash changed: ' + str(path))
    return data, {'path': str(path), 'sha256': digest}


def endpoint(data, roi, seed, thresholds, polarity, annotation_px):
    """Caller chooses physical feature identity; seed selects its connected component."""
    if len(roi) != 4 or any(type(v) is not int for v in roi):
        raise ValueError('Integer ROI required')
    if len(seed) != 2 or any(type(v) is not int for v in seed):
        raise ValueError('Integer full-image seed required')
    if len(thresholds) < 2 or len(set(thresholds)) != len(thresholds) or any(type(v) is not int or not 0 <= v <= 255 for v in thresholds):
        raise ValueError('At least two distinct byte thresholds required')
    if polarity not in ('dark', 'bright'):
        raise ValueError('Explicit dark or bright polarity required')
    if positive(annotation_px, 'annotation uncertainty') < .5:
        raise ValueError('Annotation interval must include at least half-pixel quantization')
    with Image.open(io.BytesIO(data)) as image:
        if image.format not in ('PNG', 'JPEG'):
            raise ValueError('PNG/JPEG camera frame required')
        width, height = image.size
        x0, y0, x1, y1 = roi
        if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
            raise ValueError('ROI outside image')
        if not (x0 < seed[0] < x1-1 and y0 <= seed[1] < y1-1):
            raise ValueError('Seed must be within unclipped ROI interior')
        values = list(image.convert('L').crop(roi).getdata())
    w, h = x1-x0, y1-y0
    seed_index = (seed[1]-y0)*w+seed[0]-x0
    rows = []
    for threshold in sorted(thresholds):
        mask = {i for i, value in enumerate(values) if (value <= threshold if polarity == 'dark' else value >= threshold)}
        groups = [g for g in components(mask, w, h) if seed_index in g]
        if len(groups) != 1 or len(groups[0]) < 3:
            raise ValueError('Selected endpoint absent/ambiguous at threshold')
        group = groups[0]
        if any(i % w in (0, w-1) or i // w == h-1 for i in group):
            raise ValueError('Selected endpoint touches side/bottom ROI boundary')
        bottom = max(i // w for i in group)
        rows.append({'threshold': threshold, 'endpointRowPx': y0+bottom, 'areaPixels': len(group)})
    bounds = [min(r['endpointRowPx'] for r in rows)-annotation_px,
              max(r['endpointRowPx'] for r in rows)+annotation_px]
    return {'size': [width, height], 'roi': roi, 'seed': seed, 'polarity': polarity,
            'thresholdResults': rows, 'endpointRowIntervalPx': bounds,
            'annotationUncertaintyPx': annotation_px, 'featureIdentityInferred': False}


def hull(intervals):
    return [min(i[0] for i in intervals), max(i[1] for i in intervals)]


def interpolate_interval(z0, y0, z1, y1, target):
    """All endpoint corners, after proving strict monotonicity and full bracketing."""
    if not z0 < z1 or not y0[1] < y1[0]:
        raise ValueError('Right endpoint must increase strictly with raw Z')
    if target[0] < y0[1] or target[1] > y1[0]:
        raise ValueError('Full target interval must be bracketed; extrapolation forbidden')
    values = [z0+(t-a)*(z1-z0)/(b-a) for a, b, t in itertools.product(y0, y1, target)]
    return [min(values), max(values)]


def report_state(ref):
    data, bound = read_bound(ref)
    report = json.loads(data)
    allowed = ('completed-camera-survey-awaiting-image-review', 'completed-Z-observation-awaiting-image-review',
               'completed-read-only-position-barrier', 'completed-stationary-LED-restore-awaiting-review',
               'completed-native-home-enabled-awaiting-image-review')
    if report.get('status') not in allowed:
        raise ValueError('Completed terminal native report required')
    if report.get('controllerPositionVerified') is not True or report.get('uncertainCompletion') is not False or report.get('error'):
        raise ValueError('Successful verified native position report required')
    raw = report.get('reported', report.get('after', {}).get('reported'))
    if not isinstance(raw, dict) or set(raw) != set('XYZAB'):
        raise ValueError('Full native XYZAB report required')
    for value in raw.values():
        number(value, 'reported coordinate')
    q = report['request']
    session = (q['jvmStartMs'], q['liveConfigurationSha256'])
    if not isinstance(session[1], str) or len(session[1]) != 64:
        raise ValueError('Native report configuration hash required')
    return raw, session, bound, report


def analyze(q):
    if q.get('schema') != 1 or q.get('scope') != 'same-world-XY-side-endpoint-height-interval':
        raise ValueError('Explicit differential endpoint request required')
    for key in ('fixedCameraAndLightingReviewed', 'sameWorldXYReviewed', 'stationaryCapturesReviewed', 'endpointIdentityReviewed'):
        if q.get(key) is not True:
            raise ValueError(key + ' required')
    for key in ('operator', 'cameraSetupId', 'sameWorldXYReview', 'n1DatumReview', 'localLinearityReview'):
        if not isinstance(q.get(key), str) or not q[key].strip():
            raise ValueError(key + ' required')
    raw_u = positive(q['rawZUncertaintyMm'], 'reported Z uncertainty')
    if raw_u < .02:
        raise ValueError('Reported Z bound must include native 0.02 mm tolerance')
    datum_u = positive(q['n1DatumUncertaintyMm'], 'N1 datum uncertainty')
    match_u = positive(q['sameWorldXYRowUncertaintyPx'], 'same-world-XY/parallax row uncertainty')
    linear_u = positive(q['localLinearityUncertaintyMm'], 'local linearity uncertainty')
    reference_height = number(q['referenceN1HeightMm'], 'N1 reference height')
    coupled_sum = number(q['coupledZSumMm'], 'coupled Z sum')
    # Evidence shows actual nozzle/needle centering at the same bottom-camera point;
    # raw XY need not match across heads. These images are reviewed, never identified here.
    alignment = {}
    for head in ('N1', 'N2'):
        item = q['bottomAlignmentEvidence'][head]
        raw_align, session_align, report_ref, record = report_state(item['positionEvidence'])
        data, image_ref = read_bound(item['image'])
        expected_path = (Path(report_ref['path']).parent / record['afterImages']['bottom']['path']).resolve()
        if expected_path != Path(image_ref['path']):
            raise ValueError('Bottom alignment image must be the native report capture')
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
        alignment[head] = {'image': image_ref, 'positionEvidence': report_ref, 'raw': raw_align, 'session': session_align}
    if alignment['N1']['image']['sha256'] == alignment['N2']['image']['sha256']:
        raise ValueError('Distinct N1 and N2 alignment images required')
    names = ('n1Reference', 'n1Dither', 'n1Return', 'rightLow', 'rightHigh')
    if set(q['poses']) != set(names):
        raise ValueError('Reference/dither/return and two right bracket poses required')
    groups, session, size, seen = {}, None, None, set()
    for name in names:
        pose = q['poses'][name]
        raw, identity, report_ref, _ = report_state(pose['positionEvidence'])
        if session is not None and session != identity:
            raise ValueError('Session/configuration changed')
        session = identity
        if len(pose['frames']) < 2:
            raise ValueError('At least two independent side frames per pose required')
        frames = []
        for frame in pose['frames']:
            data, image_ref = read_bound(frame['image'])
            if image_ref['sha256'] in seen:
                raise ValueError('Repeated image cannot establish independent frame evidence')
            seen.add(image_ref['sha256'])
            measured = endpoint(data, frame['roi'], frame['seed'], frame['thresholds'], frame['polarity'], frame['annotationUncertaintyPx'])
            if measured['size'][0] < 1280 or measured['size'][1] < 720:
                raise ValueError('HD side frames required')
            if size is not None and measured['size'] != size:
                raise ValueError('Camera dimensions changed')
            size = measured['size']
            frames.append({'image': image_ref, 'measurement': measured})
        groups[name] = {'raw': raw, 'positionEvidence': report_ref, 'frames': frames,
                        'endpointRowIntervalPx': hull([f['measurement']['endpointRowIntervalPx'] for f in frames])}
    for head, name in (('N1','n1Reference'),('N2','rightLow')):
        if alignment[head]['session'] != session or any(alignment[head]['raw'][a] != groups[name]['raw'][a] for a in ('X','Y','A','B')):
            raise ValueError('Bottom alignment session or head XY/A/B does not match side sequence')
    raw = lambda name: groups[name]['raw']
    row = lambda name: groups[name]['endpointRowIntervalPx']
    for name in names:
        if any(raw(name)[axis] != raw('n1Reference')[axis] for axis in ('A', 'B')):
            raise ValueError('A/B changed between observations')
    for cluster in (names[:3], names[3:]):
        if any(raw(name)[axis] != raw(cluster[0])[axis] for name in cluster for axis in ('X', 'Y')):
            raise ValueError('Raw XY changed within one head sequence')
    zref = raw('n1Reference')['Z']
    if raw('n1Return')['Z'] != zref:
        raise ValueError('N1 return must have identical raw Z')
    dz = raw('n1Dither')['Z']-zref
    n1_interval = q['reviewedN1RawZIntervalMm']
    if len(n1_interval) != 2 or number(n1_interval[0], 'N1 interval minimum') != zref or number(n1_interval[1], 'N1 interval maximum') != raw('n1Dither')['Z']:
        raise ValueError('Reviewed N1 interval must equal the observed reference-to-dither segment')
    if not 2*raw_u < dz <= 5:
        raise ValueError('Reviewed local N1 dither must be positive and at most 5 mm')
    target = hull([row('n1Reference'), row('n1Return')])
    slopes = [(a-b)/d for a,b,d in itertools.product(row('n1Dither'), target, (dz-2*raw_u, dz+2*raw_u))]
    left_slope = [min(slopes),max(slopes)]
    if left_slope[1] >= 0:
        raise ValueError('N1 dither must resolve decreasing image row with increasing Z')
    z0, z1 = raw('rightLow')['Z'], raw('rightHigh')['Z']
    bracket = q['reviewedRightRawZIntervalMm']
    if len(bracket) != 2 or not number(bracket[0], 'right lower bound') < number(bracket[1], 'right upper bound'):
        raise ValueError('Explicit reviewed right raw-Z interval required')
    if not bracket[0] <= z0 < z1 <= bracket[1] or not z0+2*raw_u < z1:
        raise ValueError('Right observations outside reviewed bracket or unresolved Z separation')
    target = [target[0]-match_u, target[1]+match_u]
    matched = interpolate_interval(z0, row('rightLow'), z1, row('rightHigh'), target)
    matched = [matched[0]-raw_u, matched[1]+raw_u]
    right_slope = [(row('rightHigh')[0]-row('rightLow')[1])/(z1-z0+2*raw_u), (row('rightHigh')[1]-row('rightLow')[0])/(z1-z0-2*raw_u)]
    if max(-left_slope[1], right_slope[0]) > min(-left_slope[0], right_slope[1]):
        raise ValueError('Opposing local pixel/Z slope magnitudes do not overlap')
    delta = [reference_height+matched[0]-coupled_sum-datum_u-linear_u,
             reference_height+matched[1]-coupled_sum+datum_u+linear_u]
    return {'schema': 1, 'scope': q['scope'], 'status': 'offline-interval-awaiting-physical-review',
            'jvmStartMs': session[0], 'liveConfigurationSha256': session[1],
            'assumptions': {key: q[key] for key in ('operator', 'cameraSetupId', 'sameWorldXYReview', 'n1DatumReview', 'localLinearityReview')},
            'bottomAlignmentEvidence': alignment, 'poses': groups, 'referenceEndpointRowIntervalPx': target,
            'reviewedRightRawZIntervalMm': bracket, 'reviewedN1RawZIntervalMm': n1_interval,
            'n1PixelsPerRawZInterval': left_slope, 'rightPixelsPerRawZInterval': right_slope,
            'rightRawZAtReferenceHeightIntervalMm': matched, 'rightTipOffsetIntervalMm': delta,
            'formula': 'right offset = reference N1 height + matching right raw Z - coupled Z sum',
            'uncertaintyBounds': {'reportedRawZMm': raw_u, 'n1DatumMm': datum_u, 'sameXYRowPx': match_u, 'localLinearityMm': linear_u},
            'physicalCalibrationEstablished': False, 'motionAuthorized': False, 'configurationChanged': False,
            'limitations': ['Intervals are conditional on reviewed feature identity, fixed camera and lighting, local linearity, and actual same-world XY.',
                           'Threshold/repeat spread and declared uncertainty bounds are not a statistical confidence interval.',
                           'Saved bottom camera Z and focus are not an absolute tip datum; N1 datum remains explicit.',
                           'Camera movement or changed rotation/assembly invalidates this evidence; no extrapolation or automatic offset update.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = args.request.read_bytes()
    result = analyze(json.loads(data))
    result['requestEvidence'] = {'path': str(args.request.resolve()), 'sha256': hashlib.sha256(data).hexdigest()}
    with args.output.open('x') as out:
        json.dump(result, out, indent=2, allow_nan=False)
        out.write('\n')
    print(json.dumps({'output': str(args.output), 'rightTipOffsetIntervalMm': result['rightTipOffsetIntervalMm'], 'physicalCalibrationEstablished': False}))


if __name__ == '__main__':
    main()
