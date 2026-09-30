#!/usr/bin/env python3
"""Offline threshold sweep of a manually selected needle-end image feature.

No automatic feature identity, lens calibration, machine commands or offsets.
"""
import argparse
import hashlib
import io
import json
import math
import statistics
from pathlib import Path
from PIL import Image
from deposit_metrics import components


def reference(path, data):
    return {'path': str(Path(path).resolve()), 'sha256': hashlib.sha256(data).hexdigest()}


def sweep(data, roi, thresholds, channel='G'):
    if channel not in ('R', 'G', 'B'):
        raise ValueError('Select an RGB channel')
    if len(roi) != 4 or any(type(x) is not int for x in roi):
        raise ValueError('ROI requires four integer pixel coordinates')
    if not thresholds or len(set(thresholds)) != len(thresholds) or any(
            type(t) is not int or not 0 <= t <= 255 for t in thresholds):
        raise ValueError('Unique byte thresholds required')
    with Image.open(io.BytesIO(data)) as source:
        if source.format != 'PNG':
            raise ValueError('Original raw PNG required')
        size = source.size
        x0, y0, x1, y1 = roi
        if not 0 <= x0 < x1 <= size[0] or not 0 <= y0 < y1 <= size[1]:
            raise ValueError('ROI outside image')
        values = list(source.convert('RGB').crop(roi).getchannel(channel).getdata())
    width, height = x1-x0, y1-y0
    rows = []
    for threshold in sorted(thresholds):
        groups = components({i for i, value in enumerate(values) if value >= threshold}, width, height)
        groups = sorted((g for g in groups if len(g) >= 3), key=lambda g: (-len(g), min(g)))
        row = {'threshold': threshold, 'componentCountAtLeast3Pixels': len(groups), 'selected': None}
        if groups:
            group = groups[0]
            row['selected'] = {
                'areaPixels': len(group),
                'centroidPixelIndex': {'x': x0+sum(i % width for i in group)/len(group),
                                       'y': y0+sum(i // width for i in group)/len(group)},
                'touchesRoiEdge': any(i % width in (0, width-1) or i // width in (0, height-1) for i in group),
                'equalAreaAmbiguity': len(groups) > 1 and len(groups[1]) == len(group),
            }
        rows.append(row)
    centers = [row['selected']['centroidPixelIndex'] for row in rows if row['selected']]
    return {
        'imageSize': list(size), 'geometricImageCenterPixelIndex': {'x': (size[0]-1)/2, 'y': (size[1]-1)/2},
        'roi': list(roi), 'channel': channel, 'componentConnectivity': 8,
        'selectionRule': 'largest connected component of at least 3 pixels within manually selected ROI',
        'coordinateFrame': 'raw pixel indices: X right, Y down; top-left pixel center is (0,0)',
        'thresholds': rows,
        'centroidSummary': None if not centers else {k: {'median': statistics.median(p[k] for p in centers),
                    'min': min(p[k] for p in centers), 'max': max(p[k] for p in centers)} for k in ('x', 'y')},
        'uncertaintyInterpretation': 'threshold spread is segmentation sensitivity, not calibrated positional uncertainty',
        'featureIdentityConfirmed': False, 'physicalCalibrationEstablished': False,
    }


def analyze_reports(paths, roi, thresholds, channel='G'):
    frames = []
    identity = None
    fixed = None
    for path in paths:
        path = Path(path).resolve()
        report_bytes = path.read_bytes()
        report = json.loads(report_bytes)
        if (report.get('status') != 'completed-camera-survey-awaiting-image-review'
                or report.get('controllerPositionVerified') is not True
                or report.get('independentFirmwareStepVerified') is not True
                or report.get('uncertainCompletion') is not False):
            raise ValueError('Only independently verified completed survey records accepted')
        raw = report['after']['reported']
        if set(raw) != set('XYZAB') or any(type(v) not in (float, int) or not math.isfinite(v) for v in raw.values()):
            raise ValueError('Five finite reported controller coordinates required')
        same = {k: raw[k] for k in ('Z', 'A', 'B')}
        request = report['request']
        session = (request['jvmStartMs'], request['liveConfigurationSha256'])
        if fixed is not None and same != fixed:
            raise ValueError('Z/A/B changed between frames; not a fixed-plane observation')
        if identity is not None and session != identity:
            raise ValueError('Session/configuration changed between frames')
        fixed, identity = same, session
        image_path = (path.parent / report['afterImages']['bottom']['path']).resolve()
        if image_path.parent != path.parent:
            raise ValueError('Bottom image must be within its survey evidence directory')
        image_bytes = image_path.read_bytes()
        frames.append({'reportReference': reference(path, report_bytes),
                       'imageReference': reference(image_path, image_bytes), 'reportedRaw': raw,
                       'measurement': sweep(image_bytes, roi, thresholds, channel)})
    if not frames:
        raise ValueError('At least one verified survey required')
    return {'schema': 1, 'kind': 'stationary-plane-needle-feature-threshold-sweep',
            'featureIdentityConfirmed': False, 'physicalCalibrationEstablished': False,
            'fixedRawAxes': fixed, 'jvmStartMs': identity[0], 'liveConfigurationSha256': identity[1],
            'frames': frames, 'limitations': [
                'Operator must identify the same physical needle end; highlights can move independently of the lumen.',
                'No automatic millimeter scale, native head-offset correction or substrate-plane registration.',
                'Unknown lens tilt, depth, focus and distortion remain; image center is geometric, not a calibrated principal point.',
                'Compare both travel directions and repeat returns to estimate repeatability separately from threshold sensitivity.']}


def fit_current_plane(result):
    """Local image response only; requires independently reviewed feature identity."""
    samples = []
    groups = {}
    center = None
    for frame in result['frames']:
        m = frame['measurement']
        if (not m['centroidSummary'] or any(not row['selected'] or row['selected']['touchesRoiEdge']
                or row['selected']['equalAreaAmbiguity'] for row in m['thresholds'])):
            raise ValueError('Fit requires present, unclipped, unambiguous components at every threshold')
        if center is not None and center != m['geometricImageCenterPixelIndex']:
            raise ValueError('Image dimensions changed during local fit')
        center = m['geometricImageCenterPixelIndex']
        x, y = frame['reportedRaw']['X'], frame['reportedRaw']['Y']
        px, py = (m['centroidSummary'][k]['median'] for k in ('x', 'y'))
        samples.append((x, y, px, py))
        groups.setdefault((x, y), []).append((px, py))
    n = len(samples)
    if n < 3:
        raise ValueError('Local 2D fit requires at least three observations')
    means = [sum(s[i] for s in samples)/n for i in range(4)]
    centered = [[s[i]-means[i] for i in range(4)] for s in samples]
    xx = sum(s[0]**2 for s in centered)
    yy = sum(s[1]**2 for s in centered)
    xy = sum(s[0]*s[1] for s in centered)
    det = xx*yy-xy*xy
    if det <= 1e-12:
        raise ValueError('Local 2D fit requires noncollinear observed X and Y movements')
    matrix = []
    for i in (2, 3):
        xp = sum(s[0]*s[i] for s in centered)
        yp = sum(s[1]*s[i] for s in centered)
        matrix.append([(xp*yy-yp*xy)/det, (yp*xx-xp*xy)/det])
    residuals = [[s[i+2] - sum(matrix[i][j]*s[j] for j in (0, 1)) for i in (0, 1)] for s in centered]
    jd = matrix[0][0]*matrix[1][1]-matrix[0][1]*matrix[1][0]
    if abs(jd) <= 1e-12:
        raise ValueError('Degenerate image response')
    ux, uy = center['x']-means[2], center['y']-means[3]
    return {'kind': 'provisional-current-plane-image-response',
            'pixelRowsRawXYColumns': matrix,
            'rmsRadialResidualPixels': math.sqrt(sum(x*x+y*y for x, y in residuals)/n),
            'maxRadialResidualPixels': max(math.hypot(x, y) for x, y in residuals),
            'estimatedRawAtGeometricImageCenter': {
                'X': means[0]+(ux*matrix[1][1]-uy*matrix[0][1])/jd,
                'Y': means[1]+(uy*matrix[0][0]-ux*matrix[1][0])/jd},
            'repeatReturns': [{'rawXY': list(key), 'count': len(points),
                'centroidRangePixels': {k: max(p[i] for p in points)-min(p[i] for p in points)
                                       for i, k in enumerate(('x', 'y'))}}
                              for key, points in sorted(groups.items()) if len(points) > 1],
            'physicalCalibrationEstablished': False,
            'limitations': 'Least-squares fit to selected bright feature at fixed unknown focal height; no command or head-offset correction.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, action='append', required=True)
    parser.add_argument('--roi', type=int, nargs=4, required=True)
    parser.add_argument('--thresholds', type=int, nargs='+', required=True)
    parser.add_argument('--channel', choices=['R', 'G', 'B'], default='G')
    parser.add_argument('--fit-current-plane', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = analyze_reports(args.report, args.roi, args.thresholds, args.channel)
    if args.fit_current_plane:
        result['localImageResponse'] = fit_current_plane(result)
    with args.output.open('x') as out:
        json.dump(result, out, indent=2, allow_nan=False)
        out.write('\n')
    print(json.dumps({'output': str(args.output), 'frames': len(result['frames']), 'physicalCalibrationEstablished': False}))


if __name__ == '__main__':
    main()
