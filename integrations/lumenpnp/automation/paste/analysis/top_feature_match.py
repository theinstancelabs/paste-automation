#!/usr/bin/env python3
"""Track one explicitly selected visible feature between same-size raw frames.

Uses thresholded green-channel masks and a caller-selected BEFORE-image ROI;
this avoids silently treating a repeated label as the same physical mark.
It reports image translation only, never a machine transform or calibration.
"""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageChops, ImageStat


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def match(before, after, roi, max_shift, thresholds=(65, 75, 85, 95, 105)):
    a = Image.open(before).convert('RGB')
    b = Image.open(after).convert('RGB')
    if a.size != b.size:
        raise ValueError('Raw frame dimensions must match')
    x0, y0, x1, y1 = roi
    if x0 < 0 or y0 < 0 or x1 <= x0 or y1 <= y0 or x1 > a.width or y1 > a.height:
        raise ValueError('Reference ROI must be a valid BEFORE-frame rectangle')
    if x1 - x0 < 80 or y1 - y0 < 60:
        raise ValueError('Reference ROI is too small for a stable feature match')
    results = []
    for threshold in thresholds:
        source = a.getchannel('G').point(lambda v: 255 if v > threshold else 0).crop(roi)
        source_coverage = ImageStat.Stat(source).mean[0] / 255.0
        if not 0.01 <= source_coverage <= 0.90:
            raise ValueError('Reference ROI has insufficient or saturated feature contrast')
        target = b.getchannel('G').point(lambda v: 255 if v > threshold else 0)
        scores = []
        for dy in range(-24, 25, 2):
            for dx in range(-max_shift, max_shift + 1, 2):
                tx0, ty0 = x0 + dx, y0 + dy
                if tx0 < 0 or ty0 < 0 or tx0 + source.width > b.width or ty0 + source.height > b.height:
                    continue
                candidate = target.crop((tx0, ty0, tx0 + source.width, ty0 + source.height))
                score = ImageStat.Stat(ImageChops.difference(source, candidate)).mean[0]
                scores.append((score, dx, dy))
        if not scores:
            raise ValueError('No target positions available inside the requested search bounds')
        scores.sort()
        best = scores[0]
        separated = [s for s in scores if abs(s[1] - best[1]) > 12 or abs(s[2] - best[2]) > 8]
        results.append({'thresholdGreen': threshold, 'dxPx': best[1], 'dyPx': best[2], 'maskDifferenceMean': best[0],
                        'nextSeparatedMatch': {'dxPx': separated[0][1], 'dyPx': separated[0][2], 'maskDifferenceMean': separated[0][0]} if separated else None,
                        'touchesSearchBoundary': abs(best[1]) >= max_shift - 2})
    xs = sorted(r['dxPx'] for r in results)
    ys = sorted(r['dyPx'] for r in results)
    if any(r['touchesSearchBoundary'] for r in results):
        raise ValueError('Best match touches search boundary; increase --max-shift-px and inspect aliases')
    for r in results:
        if r['maskDifferenceMean'] >= ImageStat.Stat(a.getchannel('G').point(lambda v: 255 if v > r['thresholdGreen'] else 0).crop(roi)).mean[0] * 0.80:
            raise ValueError('No convincing same-feature match inside the search bounds')
    return {'width': a.width, 'height': a.height, 'referenceRoiBeforePx': list(roi),
            'thresholdMatches': results, 'medianTranslationPx': {'x': xs[len(xs)//2], 'y': ys[len(ys)//2]},
            'thresholdSpreadPx': {'x': [xs[0], xs[-1]], 'y': [ys[0], ys[-1]]},
            'interpretation': 'Same selected visible feature mask; inspect the source and target crop. Threshold spread is a sensitivity range, not a statistical confidence interval.'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('before', type=Path)
    p.add_argument('after', type=Path)
    p.add_argument('--reference-roi', required=True, help='x0,y0,x1,y1 around a distinctive feature in BEFORE image')
    p.add_argument('--max-shift-px', type=int, default=1200)
    p.add_argument('--known-x-move-mm', type=float)
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    if args.max_shift_px < 1:
        p.error('--max-shift-px must be positive')
    roi = tuple(int(x) for x in args.reference_roi.split(','))
    if len(roi) != 4:
        p.error('--reference-roi must contain x0,y0,x1,y1')
    r = match(args.before, args.after, roi, args.max_shift_px)
    r['inputs'] = [{'path': str(x.resolve()), 'sha256': sha256(x)} for x in (args.before, args.after)]
    if args.known_x_move_mm is not None:
        dx = r['medianTranslationPx']['x']
        if dx == 0 or args.known_x_move_mm == 0:
            raise ValueError('Both the known move and image translation must be nonzero')
        r['knownRawXMoveMm'] = args.known_x_move_mm
        r['approximateAbsoluteLocalMmPerPixel'] = abs(args.known_x_move_mm / dx)
        r['scaleScope'] = 'local image-plane scale at selected feature plane only; not full XY, depth, or extruder-tip calibration'
    data = json.dumps(r, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data)
    else:
        print(data, end='')


if __name__ == '__main__':
    main()
