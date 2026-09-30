#!/usr/bin/env python3
"""Extract/cross-check FTP resistor paste geometry. Offline; never machine coordinates."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

PINNED_FORK = 'c497bfbef2f7347538966c129bf7ac7bdc2c1a0f'
TOLERANCE_MM = 0.000002  # KiCad/Gerber six-decimal coordinate quantization only.
REFERENCES = {f'R{i}' for i in range(1, 41)}
MACRO = [
 '4,1,4,$2,$3,$4,$5,$6,$7,$8,$9,$2,$3,0',
 '1,1,$1+$1,$2,$3', '1,1,$1+$1,$4,$5', '1,1,$1+$1,$6,$7', '1,1,$1+$1,$8,$9',
 '20,1,$1+$1,$2,$3,$4,$5,0', '20,1,$1+$1,$4,$5,$6,$7,0',
 '20,1,$1+$1,$6,$7,$8,$9,0', '20,1,$1+$1,$8,$9,$2,$3,0',
]


def number(value):
    n = float(value)
    if not math.isfinite(n):
        raise ValueError('Nonfinite geometry')
    return n


def sexpr(text):
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+', text)
    stack, roots = [], []
    for token in tokens:
        if token == '(':
            node = []
            (stack[-1] if stack else roots).append(node)
            stack.append(node)
        elif token == ')':
            if not stack:
                raise ValueError('Unbalanced KiCad expression')
            stack.pop()
        else:
            if not stack:
                raise ValueError('Atom outside KiCad expression')
            stack[-1].append(json.loads(token) if token.startswith('"') else token)
    if stack or len(roots) != 1 or roots[0][0] != 'kicad_pcb':
        raise ValueError('Expected exactly one KiCad board')
    return roots[0]


def children(node, tag):
    return [x for x in node if isinstance(x, list) and x and x[0] == tag]


def one(node, tag, optional=False):
    found = children(node, tag)
    if len(found) != 1:
        if optional and not found:
            return None
        raise ValueError(f'Expected exactly one {tag}')
    return found[0]


def reject_paste_overrides(node):
    for tag in ('solder_paste_margin', 'solder_paste_margin_ratio', 'pad_to_paste_clearance', 'pad_to_paste_clearance_ratio'):
        value = one(node, tag, True)
        if value is not None and number(value[1]) != 0:
            raise ValueError('Nonzero paste override needs explicitly reviewed geometry support')


def rotate(x, y, angle):
    a = math.radians(angle)
    return (x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a))


def extract_kicad(text):
    board = sexpr(text)
    reject_paste_overrides(one(board, 'setup'))
    result = []
    seen = set()
    for footprint in children(board, 'footprint'):
        refs = [p[2] for p in children(footprint, 'property') if p[1] == 'Reference']
        if len(refs) != 1:
            raise ValueError('Footprint reference missing/ambiguous')
        ref = refs[0]
        if not re.fullmatch(r'R\d+', ref):
            continue
        if ref in seen:
            raise ValueError('Duplicate resistor reference')
        seen.add(ref)
        if footprint[1] != 'Resistor_SMD:R_0603_1608Metric' or one(footprint, 'layer')[1] != 'F.Cu':
            raise ValueError('Unexpected resistor footprint/side')
        reject_paste_overrides(footprint)
        at = one(footprint, 'at')
        fx, fy = map(number, at[1:3]); angle = number(at[3]) if len(at) > 3 else 0
        pads = children(footprint, 'pad')
        if len(pads) != 2 or {p[1] for p in pads} != {'1', '2'}:
            raise ValueError('Expected two uniquely numbered resistor pads')
        for pad in pads:
            reject_paste_overrides(pad)
            if pad[2:4] != ['smd', 'roundrect'] or 'F.Paste' not in one(pad, 'layers')[1:]:
                raise ValueError('Expected front paste roundrect SMD pad')
            pa = one(pad, 'at'); px, py = map(number, pa[1:3])
            # KiCad pad orientation is absolute; its local center is footprint-relative.
            pad_angle = number(pa[3]) if len(pa) > 3 else 0
            width, height = map(number, one(pad, 'size')[1:3])
            ratio = number(one(pad, 'roundrect_rratio')[1])
            if width <= 0 or height <= 0 or not 0 < ratio <= 0.5:
                raise ValueError('Invalid roundrect geometry')
            radius = min(width, height) * ratio
            dx, dy = rotate(px, -py, angle)
            center = (fx + dx, -fy + dy)
            corners = [rotate(x, y, pad_angle) for x in (-(width/2-radius), width/2-radius)
                       for y in (-(height/2-radius), height/2-radius)]
            result.append({'id': ref + '.' + pad[1], 'reference': ref, 'padNumber': pad[1],
                           'footprint': footprint[1], 'footprintUuid': one(footprint, 'uuid')[1],
                           'padUuid': one(pad, 'uuid')[1], 'centerMm': list(center),
                           'sizeMm': [width, height], 'rotationDeg': pad_angle,
                           'cornerRadiusMm': radius, 'cornerCentersRelativeMm': [list(p) for p in corners],
                           'areaMm2': width*height-(4-math.pi)*radius*radius,
                           'boundsMm': [center[0]+min(p[0] for p in corners)-radius,
                                        center[1]+min(p[1] for p in corners)-radius,
                                        center[0]+max(p[0] for p in corners)+radius,
                                        center[1]+max(p[1] for p in corners)+radius]})
    if seen != REFERENCES:
        raise ValueError('FTP board must contain exactly R1 through R40')
    return sorted(result, key=lambda p: (int(p['reference'][1:]), p['padNumber']))


def extract_gerber(text):
    if text.count('%FSLAX46Y46*%') != 1 or text.count('%MOMM*%') != 1 or '%TF.FileFunction,Paste,Top*%' not in text or text.count('%TF.FilePolarity,Positive*%') != 1:
        raise ValueError('Expected absolute leading-zero 4.6 millimeter top-paste Gerber')
    macro = re.search(r'%AMRoundRect\*(.*?)\*%', text, re.S)
    if macro is None:
        raise ValueError('RoundRect aperture macro missing')
    primitives = [x.strip() for x in macro[1].split('*') if x.strip() and not x.strip().startswith('0 ')]
    if primitives != MACRO:
        raise ValueError('Unsupported/changed RoundRect primitive definition')
    text = text[:macro.start()] + text[macro.end():]
    apertures, flashes = {}, []
    aperture, ref = None, None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('G04 ') or line.startswith('%TF.'):
            continue
        if line in ('%FSLAX46Y46*%', '%MOMM*%', '%LPD*%', 'G01*', 'M02*'):
            continue
        m = re.fullmatch(r'%ADD(\d+)RoundRect,([^*]+)\*%', line)
        if m:
            n = int(m[1]); v = [number(x) for x in m[2].split('X')]
            if n in apertures or len(v) != 10 or v[0] <= 0 or v[-1] != 0:
                raise ValueError('Unsupported roundrect aperture parameters')
            apertures[n] = {'radius': v[0], 'corners': [(v[i], v[i+1]) for i in (1, 3, 5, 7)]}
            continue
        m = re.fullmatch(r'D(\d+)\*', line)
        if m:
            aperture = int(m[1])
            if aperture not in apertures:
                raise ValueError('Undefined aperture')
            continue
        m = re.fullmatch(r'%TO\.C,([^*]+)\*%', line)
        if m:
            ref = m[1];continue
        if line == '%TD*%':
            ref = None;continue
        m = re.fullmatch(r'X(-?\d+)Y(-?\d+)D03\*', line)
        if m and aperture is not None and ref is not None:
            flashes.append({'reference': ref, 'center': (int(m[1])/1e6, int(m[2])/1e6),
                            'aperture': aperture, **apertures[aperture]})
            continue
        raise ValueError('Unsupported Gerber statement: ' + line)
    return flashes


def distance(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])


def crosscheck(pads, flashes):
    remaining = [f for f in flashes if re.fullmatch(r'R\d+', f['reference'])]
    if len(remaining) != len(pads):
        raise ValueError('Resistor pad/flash count mismatch')
    max_error = 0
    for pad in pads:
        candidates = [f for f in remaining if f['reference'] == pad['reference']
                      and distance(f['center'], pad['centerMm']) <= TOLERANCE_MM]
        if len(candidates) != 1:
            raise ValueError('Missing/ambiguous Gerber flash for ' + pad['id'])
        flash = candidates[0]
        if abs(flash['radius']-pad['cornerRadiusMm']) > TOLERANCE_MM:
            raise ValueError('Roundrect radius differs for ' + pad['id'])
        available = flash['corners'][:]
        for corner in pad['cornerCentersRelativeMm']:
            matches = [c for c in available if distance(c, corner) <= TOLERANCE_MM]
            if len(matches) != 1:
                raise ValueError('Roundrect shape/orientation differs for ' + pad['id'])
            available.remove(matches[0])
        error = distance(flash['center'], pad['centerMm']); max_error = max(error, max_error)
        pad['gerberMatch'] = {'aperture': flash['aperture'], 'centerMm': list(flash['center']), 'centerDifferenceMm': error}
        remaining.remove(flash)
    if remaining:
        raise ValueError('Unmatched resistor flashes')
    return max_error


def build(pcb, gerber):
    pcb, gerber = Path(pcb).resolve(strict=True), Path(gerber).resolve(strict=True)
    board_bytes, gerber_bytes = pcb.read_bytes(), gerber.read_bytes()
    pads = extract_kicad(board_bytes.decode()); flashes = extract_gerber(gerber_bytes.decode())
    max_error = crosscheck(pads, flashes)
    sources = [{'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
               for path, data in [(pcb, board_bytes), (gerber, gerber_bytes)]]
    return {'schema': 1, 'kind': 'FTP-resistor-paste-design-geometry', 'executionReady': False,
            'coordinateFrame': 'KiCad-file-origin-mm-X-right-Y-up; NOT machine coordinates',
            'kicadToDesignTransform': {'x': 'x', 'y': '-y', 'translationMm': [0, 0]},
            'sources': sources, 'comparisonToleranceMm': TOLERANCE_MM,
            'comparisonScope': 'center, exact roundrect corner centers/radius, count, component identity; quantization tolerance only',
            'maxCenterDifferenceMm': max_error, 'resistorCount': 40, 'pastePadCount': len(pads),
            'pads': pads, 'pending': {'freshPhysicalBoardRegistration': None, 'nativeN2TipTransform': None,
                'bothHeadClearanceEnvelope': None, 'measuredSurfaceAndTipHeights': None,
                'verifiedDoseRetractionAndCurrent': None, 'physicalBoardPadAvailabilityReview': None},
            'candidateDeposits': [{'padId': p['id'], 'designCenterMm': p['centerMm'], 'machineXYMm': None,
                                   'surfaceZMm': None, 'standoffMm': None, 'doseDegrees': None} for p in pads],
            'limitations': ['Candidate centers are offline geometry only; no motion order or G-code.',
                            'Existing placed flags, old registration and CAD geometry do not authorize paste on a physical board.',
                            'No paste volume, motor current, tip size or clearance inferred.']}


def verify_pinned_gerber(gerber):
    gerber = Path(gerber).resolve(strict=True)
    head = subprocess.check_output(['git', '-C', str(gerber.parent), 'rev-parse', 'HEAD'], text=True).strip()
    if head != PINNED_FORK:
        raise ValueError('Gerber checkout must remain at the pinned audited fork commit')
    fork_root = Path(subprocess.check_output(['git', '-C', str(gerber.parent), 'rev-parse', '--show-toplevel'], text=True).strip())
    if gerber != fork_root / 'test/ftp-F_Paste.gbr':
        raise ValueError('Expected the audited test/ftp-F_Paste.gbr path')
    pinned_bytes = subprocess.check_output(['git', '-C', str(fork_root), 'show', head + ':test/ftp-F_Paste.gbr'])
    if pinned_bytes != gerber.read_bytes():
        raise ValueError('Gerber working file differs from pinned commit blob')
    return {'commit': head, 'sha256': hashlib.sha256(pinned_bytes).hexdigest()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pcb', type=Path, required=True);p.add_argument('--gerber', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    try:
        verified = verify_pinned_gerber(args.gerber)
        report = build(args.pcb, args.gerber)
        if report['sources'][1]['sha256'] != verified['sha256']:
            raise ValueError('Gerber changed after pinned-blob verification')
        report['gerberForkCommit'] = verified['commit']
    except ValueError as exc:
        p.error(str(exc))
    with args.output.open('x') as f:
        json.dump(report, f, indent=2, allow_nan=False);f.write('\n')
    print(json.dumps({'output': str(args.output), 'resistors': report['resistorCount'], 'pads': report['pastePadCount'],
                      'maxCenterDifferenceMm': report['maxCenterDifferenceMm'], 'executionReady': False}))


if __name__ == '__main__':main()
