#!/usr/bin/env python3
"""Compare same-pose top-camera coupon images for quick human review.

This reports local pixel changes and creates paired crops. It cannot establish
deposit acceptance, volume, or physical success, and never controls hardware.
"""
import argparse
import hashlib
import io
import json
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw

EXPECTED_SIZE = (1920, 1080)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def analyze(before_path, after_path, targets, crop_width=160):
    if type(crop_width) is not int or crop_width < 40 or crop_width % 2:
        raise ValueError('crop width must be an even integer >= 40')
    before_path, after_path = Path(before_path), Path(after_path)
    before_bytes, after_bytes = before_path.read_bytes(), after_path.read_bytes()
    before = Image.open(io.BytesIO(before_bytes)).convert('RGB')
    after = Image.open(io.BytesIO(after_bytes)).convert('RGB')
    if before.size != EXPECTED_SIZE or after.size != EXPECTED_SIZE:
        raise ValueError('before and after images must both be 1920x1080')
    if not isinstance(targets, list) or not targets:
        raise ValueError('targets must be a nonempty list')
    bgray, agray = before.convert('L'), after.convert('L')
    results = []
    half = crop_width // 2
    for item in targets:
        if not isinstance(item, dict) or not isinstance(item.get('label'), str) or not item['label'].strip():
            raise ValueError('each target needs a nonempty label and integer x,y')
        x, y = item.get('x'), item.get('y')
        if type(x) is not int or type(y) is not int or not (20 <= x < 1900 and 20 <= y < 1060):
            raise ValueError(f"target {item.get('label')!r} needs integer center x,y within the image")
        box40 = (x - 20, y - 20, x + 20, y + 20)
        bp = list(bgray.crop(box40).getdata())
        ap = list(agray.crop(box40).getdata())
        changed = sum(1 for b, a in zip(bp, ap) if b - a >= 15)
        crop_box = (max(0, x-half), max(0, y-half), min(1920, x+half), min(1080, y+half))
        results.append({
            'label': item['label'], 'center': {'x': x, 'y': y},
            'central40x40': {'pixels': 1600, 'darkenedByAtLeast15Luminance': changed,
                             'fraction': changed / 1600},
            'cropBox': list(crop_box),
        })
    # Paired, labeled rows keep the original views available for visual judgment.
    row_h = crop_width + 26
    sheet = Image.new('RGB', (crop_width * 2, row_h * len(results)), 'white')
    draw = ImageDraw.Draw(sheet)
    for i, r in enumerate(results):
        x, y = r['center']['x'], r['center']['y']
        box = tuple(r['cropBox'])
        left = before.crop(box).resize((crop_width, crop_width))
        right = after.crop(box).resize((crop_width, crop_width))
        top = i * row_h + 20
        sheet.paste(left, (0, top))
        sheet.paste(right, (crop_width, top))
        draw.text((3, i * row_h + 3), f"{r['label']} | before                         after", fill='black')
    report = {
        'schema': 1, 'kind': 'offline-coupon-image-comparison',
        'imageSize': {'width': 1920, 'height': 1080},
        'sources': [
            {'role': 'before', 'path': str(before_path.resolve()), 'sha256': sha256(before_bytes)},
            {'role': 'after', 'path': str(after_path.resolve()), 'sha256': sha256(after_bytes)},
        ],
        'threshold': 'per-pixel grayscale luminance decrease >= 15 (8-bit L)',
        'poseAssumption': 'Images are assumed aligned at the same pose; no registration or alignment is performed.',
        'physicalAcceptanceEstablished': False, 'executionEnabled': False,
        'limitations': [
            'Lighting, exposure, focus, shadows, reflections, and pose changes can alter pixel statistics.',
            'The fraction is a quick comparison aid, not a deposition verdict or a measure of paste volume/height.',
            'Review paired crops and original images; verify pose alignment independently.',
        ],
        'targets': results,
    }
    return report, sheet


def self_check():
    before = Image.new('L', EXPECTED_SIZE, 200)
    after = before.copy()
    # A 10x12 synthetic blob is wholly within the central 40x40 window.
    for yy in range(534, 546):
        for xx in range(955, 965):
            after.putpixel((xx, yy), 180)
    with tempfile.TemporaryDirectory() as directory:
        before_path = Path(directory) / 'before.png'
        after_path = Path(directory) / 'after.png'
        before.save(before_path)
        after.save(after_path)
        report, _ = analyze(before_path, after_path, [{'label': 'blob', 'x': 960, 'y': 540}])
    stats = report['targets'][0]['central40x40']
    assert stats['darkenedByAtLeast15Luminance'] == 120
    assert stats['fraction'] == 0.075


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', nargs='?', type=Path)
    parser.add_argument('after', nargs='?', type=Path)
    parser.add_argument('targets', nargs='?', type=Path, help='JSON file containing [{"label":...,"x":...,"y":...}]')
    parser.add_argument('--json-out', type=Path)
    parser.add_argument('--sheet-out', type=Path)
    parser.add_argument('--crop-width', type=int, default=160)
    parser.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    if args.self_check:
        self_check()
        print('synthetic blob self-check passed: 120/1600 = 0.075')
        return
    if not all((args.before, args.after, args.targets, args.json_out, args.sheet_out)):
        parser.error('before, after, targets, --json-out and --sheet-out are required')
    report, sheet = analyze(args.before, args.after,
                            json.loads(args.targets.read_text()), args.crop_width)
    # Exclusive creation preserves evidence from prior runs.
    with args.json_out.open('x', encoding='utf-8') as f:
        json.dump(report, f, indent=2, allow_nan=False)
        f.write('\n')
    with args.sheet_out.open('xb') as f:
        sheet.save(f, format='PNG')
    print(json.dumps({'json': str(args.json_out), 'contactSheet': str(args.sheet_out),
                      'physicalAcceptanceEstablished': False}))


if __name__ == '__main__':
    main()
