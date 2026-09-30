#!/usr/bin/env python3
"""Offline 2-D deposit measurements from reviewed, aligned binary masks.

No camera/control interfaces; masks are segmentation evidence, not ground truth.
"""
import argparse
import hashlib
import io
import json
import math
from collections import deque
from pathlib import Path
from PIL import Image


def binary_mask(path):
    return binary_mask_bytes(Path(path).read_bytes())


def binary_mask_bytes(data):
    with Image.open(io.BytesIO(data)) as im:
        if im.format != 'PNG' or im.mode != 'L':
            raise ValueError('Masks must be 8-bit grayscale PNGs with only 0 and 255')
        values = list(im.getdata())
        if not set(values) <= {0, 255}:
            raise ValueError('Mask contains values other than 0 and 255')
        return im.size, {i for i, value in enumerate(values) if value == 255}


def components(pixels, width, height):
    remaining = set(pixels)
    result = []
    while remaining:
        seed = remaining.pop()
        part = {seed}
        queue = deque([seed])
        while queue:
            i = queue.popleft()
            x, y = i % width, i // width
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    xx, yy = x + dx, y + dy
                    n = yy * width + xx
                    if 0 <= xx < width and 0 <= yy < height and n in remaining:
                        remaining.remove(n)
                        part.add(n)
                        queue.append(n)
        result.append(part)
    return result


def measure(size, pad_masks, paste, mm_per_pixel_x, mm_per_pixel_y):
    if not isinstance(size, (tuple, list)) or len(size) != 2 or any(
            type(v) is not int or v <= 0 for v in size):
        raise ValueError('Image dimensions must be two positive integers')
    width, height = size
    for v in (mm_per_pixel_x, mm_per_pixel_y):
        if isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) or v <= 0:
            raise ValueError('Positive finite measured X/Y pixel scales required')
    if not pad_masks:
        raise ValueError('At least one pad mask required')
    union = set()
    for name, mask in pad_masks.items():
        if not isinstance(name, str) or not name.strip() or not mask:
            raise ValueError('Unique nonempty pad IDs and masks required')
        if union & mask:
            raise ValueError('Pad masks overlap')
        union |= mask
    if any(type(i) is not int or not 0 <= i < width * height for i in union | paste):
        raise ValueError('Mask coordinates outside image')
    area = mm_per_pixel_x * mm_per_pixel_y
    groups = components(paste, width, height)
    bridge_candidates = []
    for group in groups:
        touched = sorted(name for name, mask in pad_masks.items() if group & mask)
        if len(touched) > 1:
            bridge_candidates.append({'padIds': touched, 'componentAreaMm2': len(group) * area})
    def centroid(mask):
        return (sum(i % width + .5 for i in mask) / len(mask),
                sum(i // width + .5 for i in mask) / len(mask))
    per_pad = []
    for name, mask in sorted(pad_masks.items()):
        inside = paste & mask
        cx, cy = centroid(mask)
        dx, dy = centroid(inside) if inside else (None, None)
        # Full touching components expose tails/spill. Shared components remain
        # shared; never assign a bridge arbitrarily to one of its pads.
        touching = set().union(*(g for g in groups if g & mask))
        per_pad.append({
            'padId': name, 'padAreaMm2': len(mask) * area,
            'coveredAreaMm2': len(inside) * area,
            'coverageFraction': len(inside) / len(mask),
            'coveredCentroidOffsetMm': None if not inside else {
                'x': (dx-cx)*mm_per_pixel_x, 'y': (dy-cy)*mm_per_pixel_y},
            'touchingDepositAreaMm2': len(touching) * area,
            'touchingDepositSpillOutsideAllPadsMm2': len(touching-union) * area,
            'touchingComponentCount': sum(bool(g & mask) for g in groups),
            'sharedComponent': any(name in g['padIds'] for g in bridge_candidates),
        })
    touches_edge = any(i % width in (0, width-1) or i // width in (0, height-1) for i in paste)
    return {
        'schema': 1, 'kind': 'offline-deposit-mask-metrics',
        'physicalAcceptanceEstablished': False, 'executionEnabled': False,
        'pasteVolumeMm3': None, 'pasteHeightMm': None,
        'imageWidth': width, 'imageHeight': height,
        'scaleMmPerPixel': {'x': mm_per_pixel_x, 'y': mm_per_pixel_y},
        'coordinateFrame': 'aligned mask image: X right, Y down; not machine coordinates',
        'pixelConvention': 'top-left origin; pixel centers at (column+0.5, row+0.5)',
        'componentConnectivity': 8,
        'depositAreaMm2': len(paste)*area,
        'spillOutsideAllPadsMm2': len(paste-union)*area,
        'depositComponentCount': len(groups),
        'depositTouchesImageEdge': touches_edge,
        'bridgeCandidates': bridge_candidates, 'pads': per_pad,
        'limitations': [
            'Metrics depend on reviewed segmentation, alignment and surface-plane scale.',
            'Two pixel scales assume orthogonal rectified image axes; they do not correct perspective or shear.',
            'Connected mask pixels flag possible bridges; inspect original images.',
            'Shared touching-component areas appear on each touched pad and must not be summed across pads.',
            '2-D area does not measure deposited volume, height or solder joint quality.',
            'Image-edge deposits may be cropped; areas then are lower bounds.',
        ],
    }


def source(path, data=None):
    p = Path(path).resolve()
    return {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes() if data is None else data).hexdigest()}


def load_mask(path):
    p = Path(path).resolve()
    data = p.read_bytes()
    size, pixels = binary_mask_bytes(data)
    return size, pixels, source(p, data)


def analyze(request):
    if request.get('schema') != 1 or request.get('masksReviewedAndAligned') is not True:
        raise ValueError('Explicit reviewed/aligned mask declaration required')
    for name in ('reviewer', 'segmentationMethod', 'registrationRecord', 'scaleRecord'):
        if not isinstance(request.get(name), str) or not request[name].strip():
            raise ValueError(f'{name} required')
    image_refs = request.get('sourceImages')
    if not isinstance(image_refs, list) or not image_refs:
        raise ValueError('Original source image hash references required')
    for ref in image_refs:
        if source(ref['path']) != ref:
            raise ValueError('Source image reference/hash mismatch')
    size, paste, paste_ref = load_mask(request['pasteMask'])
    masks = {}
    refs = {'paste': paste_ref, 'pads': []}
    for p in request['pads']:
        if p['id'] in masks:
            raise ValueError('Duplicate pad ID')
        pad_size, mask, pad_ref = load_mask(p['mask'])
        if pad_size != size:
            raise ValueError('Mask dimensions differ')
        masks[p['id']] = mask
        refs['pads'].append({'id': p['id'], **pad_ref})
    result = measure(size, masks, paste, request['mmPerPixelX'], request['mmPerPixelY'])
    result['provenance'] = {k: request[k] for k in (
        'reviewer', 'segmentationMethod', 'registrationRecord', 'scaleRecord', 'sourceImages')}
    result['maskReferences'] = refs
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    request_bytes = args.request.read_bytes()
    result = analyze(json.loads(request_bytes))
    result['requestReference'] = source(args.request, request_bytes)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'output': str(args.output), 'physicalAcceptanceEstablished': False}))


if __name__ == '__main__':
    main()
