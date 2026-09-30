#!/usr/bin/env python3
"""Offline integer edge matching of explicitly selected image regions.

Reports image displacement only. It cannot establish physical clearance,
feature identity, optical scale, or motion acceptance.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
from PIL import Image, ImageChops, ImageFilter, ImageStat


def match(before, after, regions, radius_x=3, radius_y=6):
    if any(type(r) is not int or not 1 <= r <= 50 for r in (radius_x, radius_y)):
        raise ValueError('Search radii must be integers in 1..50 pixels')
    a = Image.open(io.BytesIO(before)).convert('L').filter(ImageFilter.FIND_EDGES)
    b = Image.open(io.BytesIO(after)).convert('L').filter(ImageFilter.FIND_EDGES)
    if a.size != b.size:
        raise ValueError('Images must have the same dimensions')
    result = {}
    if not regions:
        raise ValueError('Explicit regions required')
    for name, roi in regions.items():
        if len(roi) != 4 or any(type(v) is not int for v in roi):
            raise ValueError('Integer rectangular ROI required')
        x0, y0, x1, y1 = roi
        if not (radius_x <= x0 < x1 <= a.width-radius_x and radius_y <= y0 < y1 <= a.height-radius_y):
            raise ValueError('ROI and full search window must be inside image')
        reference = a.crop(roi)
        scores = []
        for dy in range(-radius_y, radius_y+1):
            for dx in range(-radius_x, radius_x+1):
                target = b.crop((x0+dx, y0+dy, x1+dx, y1+dy))
                score = ImageStat.Stat(ImageChops.difference(reference, target)).rms[0]
                scores.append((score, dx, dy))
        scores.sort()
        best = scores[0]
        result[name] = {'roi': roi, 'best': {'edgeRms': best[0], 'dxPx': best[1], 'dyPx': best[2]},
                        'topMatches': [{'edgeRms': s, 'dxPx': x, 'dyPx': y} for s, x, y in scores[:3]],
                        'touchesSearchBoundary': abs(best[1]) == radius_x or abs(best[2]) == radius_y}
    return {'schema': 1, 'regions': result, 'imageSize': list(a.size),
            'searchRadiusPx': {'x': radius_x, 'y': radius_y},
            'coordinateFrame': 'after-feature displacement relative to before; X right, Y down',
            'method': 'Pillow grayscale FIND_EDGES, integer exhaustive minimum RMS difference',
            'limitations': 'Manual feature identity; integer-pixel and lighting sensitivity; boundary matches need inspection. No calibrated physical distance or clearance.',
            'physicalAcceptanceEstablished': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('before', type=Path)
    p.add_argument('after', type=Path)
    p.add_argument('--regions', required=True, help='JSON object mapping labels to [x0,y0,x1,y1]')
    p.add_argument('--radius-x', type=int, default=3)
    p.add_argument('--radius-y', type=int, default=6)
    p.add_argument('--output', required=True, type=Path)
    q = p.parse_args()
    data = [q.before.read_bytes(), q.after.read_bytes()]
    r = match(*data, json.loads(q.regions), q.radius_x, q.radius_y)
    r['inputs'] = [{'path': str(path.resolve()), 'sha256': hashlib.sha256(blob).hexdigest()}
                   for path, blob in zip((q.before, q.after), data)]
    with q.output.open('x') as f:
        json.dump(r, f, indent=2)
        f.write('\n')


if __name__ == '__main__':
    main()
