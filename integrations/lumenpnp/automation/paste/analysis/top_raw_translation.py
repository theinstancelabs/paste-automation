#!/usr/bin/env python3
"""Estimate a 2-D image translation between same-size raw camera frames (Pillow only).

This reports image-plane translation and an optional known-move scale estimate.
It does not infer camera calibration, depth, or a physical axis transform.
"""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageStat


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def compare(a, b, dx, dy):
    """RMS edge difference; dx/dy are after-image feature displacement."""
    w, h = a.size
    ax0, ax1 = max(0, -dx), min(w, w - dx)
    ay0, ay1 = max(0, -dy), min(h, h - dy)
    # Ignore extreme frame edges; use the labeled feature/seam band.
    ay0 = max(ay0, int(h * 0.46))
    ay1 = min(ay1, int(h * 0.82))
    bx0, bx1 = ax0 + dx, ax1 + dx
    by0, by1 = ay0 + dy, ay1 + dy
    if ax0 >= ax1 or ay0 >= ay1 or bx0 >= bx1 or by0 >= by1:
        return float('inf')
    aa = a.crop((ax0, ay0, ax1, ay1))
    bb = b.crop((bx0, by0, bx1, by1))
    if aa.size != bb.size:
        return float('inf')
    return ImageStat.Stat(ImageChops.difference(aa, bb)).rms[0]


def estimate(before, after, max_shift_px=500):
    im_a, im_b = Image.open(before).convert('L'), Image.open(after).convert('L')
    if im_a.size != im_b.size:
        raise ValueError('Input image dimensions differ')
    a = im_a.filter(ImageFilter.FIND_EDGES)
    b = im_b.filter(ImageFilter.FIND_EDGES)
    # Coarse search, then full-resolution local refinement.
    scale = 4
    ac = a.resize((a.width // scale, a.height // scale), Image.Resampling.LANCZOS)
    bc = b.resize((b.width // scale, b.height // scale), Image.Resampling.LANCZOS)
    coarse = []
    for dy in range(-12, 13, 2):
        for dx in range(-(max_shift_px // scale), (max_shift_px // scale) + 1, 2):
            coarse.append((compare(ac, bc, dx, dy), dx, dy))
    _, cx, cy = min(coarse)
    fine = []
    for dy in range(cy * scale - 8, cy * scale + 9):
        for dx in range(cx * scale - 12, cx * scale + 13):
            fine.append((compare(a, b, dx, dy), dx, dy))
    fine.sort()
    best, dx, dy = fine[0]
    alternatives = [x for x in fine if abs(x[1] - dx) > 4 or abs(x[2] - dy) > 2]
    second = alternatives[0] if alternatives else None
    return {
        'width': im_a.width, 'height': im_a.height,
        'afterFeatureTranslationPx': {'x': dx, 'y': dy},
        'bestEdgeRms': best,
        'nextDistinctEdgeRms': second[0] if second else None,
        'nextDistinctTranslationPx': {'x': second[1], 'y': second[2]} if second else None,
        'localFitSpreadRulePx': {'x': 4, 'y': 2},
        'method': 'Pillow FIND_EDGES then coarse-to-fine minimum RMS difference over y=46%-82% overlap band',
        'caution': 'Repeated labels can create aliases; inspect both frames and corroborate with distinct features. Fit spread is a conservative local-match allowance, not a statistical confidence interval.'
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument('before', type=Path)
    p.add_argument('after', type=Path)
    p.add_argument('--known-x-move-mm', type=float)
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    result = estimate(args.before, args.after)
    result['inputs'] = [{'path': str(x.resolve()), 'sha256': sha256(x)} for x in (args.before, args.after)]
    if args.known_x_move_mm is not None:
        if args.known_x_move_mm == 0 or result['afterFeatureTranslationPx']['x'] == 0:
            raise ValueError('Known move and measured horizontal image shift must be nonzero')
        pixels = abs(result['afterFeatureTranslationPx']['x'])
        mm = abs(args.known_x_move_mm)
        spread = result['localFitSpreadRulePx']['x']
        result['knownMoveXmm'] = args.known_x_move_mm
        result['approximateLocalMmPerPixel'] = mm / pixels
        result['scaleSensitivityRangeMmPerPixel'] = [mm / (pixels + spread), mm / max(1, pixels - spread)]
        result['scaleScope'] = 'local image-plane X scale at the surveyed feature plane; not full XY, depth, or an extruder-tip transform'
    out = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(out)
    else:
        print(out, end='')


if __name__ == '__main__':
    main()
