#!/usr/bin/env python3
"""Measure image-darkening footprints inside explicitly reviewed pad ROIs.

Offline image aid only. Results are pixel footprints, not paste volume or
acceptance. The caller supplies paired same-pose images, each pad rectangle,
thresholds, pixel scale, and capture metadata; mismatched metadata is flagged.
"""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
from PIL import Image


def _source(path):
    p = Path(path).resolve()
    data = p.read_bytes()
    return {'path': str(p), 'sha256': hashlib.sha256(data).hexdigest()}, data


def _centroid_bounds(pixels):
    if not pixels:
        return None, None
    xs = [p[0] for p in pixels]
    ys = [p[1] for p in pixels]
    return ({'x': sum(xs) / len(xs), 'y': sum(ys) / len(ys)},
            {'xMin': min(xs), 'yMin': min(ys), 'xMax': max(xs), 'yMax': max(ys)})


def compare(before_path, after_path, request):
    if not isinstance(request, dict) or request.get('schema') != 1:
        raise ValueError('schema 1 request required')
    if request.get('samePoseReviewed') is not True:
        raise ValueError('explicit same-pose review required')
    scale = request.get('mmPerPixel')
    if not isinstance(scale, dict):
        raise ValueError('explicit X/Y pixel scale required')
    for axis in ('x', 'y'):
        value = scale.get(axis)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError('positive finite X/Y pixel scale required')
    settings = request.get('captureSettings')
    if not isinstance(settings, dict) or not settings:
        raise ValueError('before/after captureSettings required')
    settings_match = settings.get('before') == settings.get('after')
    delta = request.get('darkeningThreshold', 18)
    bright = request.get('padBrightnessThreshold', 160)
    if type(delta) is not int or not 1 <= delta <= 255 or type(bright) is not int or not 0 <= bright <= 255:
        raise ValueError('valid integer luminance thresholds required')
    before_ref, before_bytes = _source(before_path)
    after_ref, after_bytes = _source(after_path)
    with Image.open(io.BytesIO(before_bytes)) as im:
        before = im.convert('L')
    with Image.open(io.BytesIO(after_bytes)) as im:
        after = im.convert('L')
    if before.size != after.size:
        raise ValueError('paired images must have matching dimensions')
    width, height = before.size
    rois = request.get('padRois')
    if not isinstance(rois, list) or not rois:
        raise ValueError('one or more explicit padRois required')
    results = []
    for roi in rois:
        if not isinstance(roi, dict) or not isinstance(roi.get('padId'), str) or not roi['padId'].strip():
            raise ValueError('each ROI needs a padId')
        x0, y0, x1, y1 = (roi.get(k) for k in ('x0', 'y0', 'x1', 'y1'))
        if any(type(v) is not int for v in (x0, y0, x1, y1)) or not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
            raise ValueError('ROI must be an in-bounds nonempty integer rectangle')
        ellipse = roi.get('ellipse')
        if ellipse is not None:
            if not isinstance(ellipse, dict):
                raise ValueError('ellipse mask must contain cx,cy,rx,ry')
            cx0, cy0, rx, ry = (ellipse.get(k) for k in ('cx', 'cy', 'rx', 'ry'))
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                   for v in (cx0, cy0, rx, ry)) or rx <= 0 or ry <= 0:
                raise ValueError('ellipse mask requires finite center and positive radii')
        pad, changed = [], []
        for y in range(y0, y1):
            for x in range(x0, x1):
                if ellipse is not None and ((x + .5 - cx0) / rx) ** 2 + ((y + .5 - cy0) / ry) ** 2 > 1:
                    continue
                b = before.getpixel((x, y))
                a = after.getpixel((x, y))
                if b >= bright:
                    pad.append((x, y))
                    if b - a >= delta:
                        changed.append((x, y))
        if not pad:
            raise ValueError('ROI has no baseline bright-pad pixels: ' + roi['padId'])
        cx, bounds = _centroid_bounds(changed)
        results.append({
            'padId': roi['padId'], 'roi': [x0, y0, x1, y1],
            'padMask': {'shape': 'caller-supplied ellipse', **ellipse} if ellipse is not None else {'shape': 'rectangle'},
            'baselineBrightPadPixelCount': len(pad),
            'darkenedPixelCountInsideBaselinePad': len(changed),
            'fractionOfBaselinePadDarkened': len(changed) / len(pad),
            'footprintCentroidPx': cx, 'footprintBoundsPx': bounds,
            'footprintAreaMm2': len(changed) * scale['x'] * scale['y'],
            'footprintCentroidMmFromRoiOrigin': None if cx is None else {
                'x': (cx['x'] - x0) * scale['x'], 'y': (cx['y'] - y0) * scale['y']},
        })
    return {
        'schema': 1, 'kind': 'offline-pad-footprint-image-comparison',
        'sources': {'before': before_ref, 'after': after_ref},
        'imageSize': {'width': width, 'height': height},
        'settingsMatch': settings_match,
        'manualReviewRequired': not settings_match,
        'physicalAcceptanceEstablished': False, 'executionEnabled': False,
        'measurementMeaning': 'Pixels darkened relative to the before image, intersected with baseline-bright pixels inside caller-supplied pad ROIs.',
        'limitations': [
            'Footprint area is a 2-D image statistic, not paste volume, height, transfer, or reflow quality.',
            'ROI geometry and pixel scale are caller supplied; no pad detection, image registration, or calibration is performed.',
            'Illumination, exposure, focus, pose, reflection, and threshold choices can change the measured footprint.',
            'Pixels outside baseline-bright pad pixels are omitted; paste extending beyond the pad is not quantified.',
            'Review source images and each ROI manually; settings mismatch requires manual review.',
        ],
        'thresholds': {'baselineBrightLuminanceAtLeast': bright, 'darkeningLuminanceAtLeast': delta},
        'scaleMmPerPixel': scale, 'pads': results,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('before', type=Path)
    ap.add_argument('after', type=Path)
    ap.add_argument('request', type=Path, help='JSON with reviewed ROIs, scale, pose, and capture settings')
    ap.add_argument('output', type=Path)
    a = ap.parse_args()
    result = compare(a.before, a.after, json.loads(a.request.read_text()))
    with a.output.open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps({'output': str(a.output), 'manualReviewRequired': result['manualReviewRequired'],
                      'physicalAcceptanceEstablished': False}))


if __name__ == '__main__':
    main()
