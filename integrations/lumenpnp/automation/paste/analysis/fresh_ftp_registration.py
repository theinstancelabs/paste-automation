#!/usr/bin/env python3
"""Offline fresh FTP board transform from two verified camera fiducials and a third-point check."""
import argparse
import datetime
import hashlib
import json
import math
from pathlib import Path
import re

from fiducial_registration import bound, cad, fiducials, source
from needle_centroid import sweep

REFERENCES = ('FID1', 'FID2', 'FID3')
MAX_REPORT_AGE_MS = 30 * 60 * 1000
MIN_SCALE, MAX_SCALE, MAX_THIRD_RESIDUAL_MM = 0.99, 1.01, 0.08


def finite_pair(value, label):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f'{label} must contain exactly two coordinates')
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in value):
        raise ValueError(f'{label} must be finite')
    return [float(value[0]), float(value[1])]


def iso_ms(value):
    if not isinstance(value, str):
        raise ValueError('Source report lacks a completion time')
    try:
        parsed = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('Timezone required')
        return int(parsed.timestamp() * 1000)
    except (ValueError, OverflowError) as exc:
        raise ValueError('Malformed source report completion time') from exc


def similarity_from_pair(p1, p2, q1, q2):
    """Fit orientation-preserving similarity from design XY to measured camera XY."""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    ux, uy = q2[0] - q1[0], q2[1] - q1[1]
    den = dx * dx + dy * dy
    if den < 1e-12 or math.hypot(ux, uy) < 1e-9:
        raise ValueError('Fiducial pair is degenerate')
    a = (dx * ux + dy * uy) / den
    b = (dx * uy - dy * ux) / den
    scale = math.hypot(a, b)
    tx = q1[0] - a * p1[0] + b * p1[1]
    ty = q1[1] - b * p1[0] - a * p1[1]
    return {'scale': scale, 'rotationDegrees': math.degrees(math.atan2(b, a)),
            'matrix': [[a, -b], [b, a]], 'translationMm': [tx, ty]}


def apply(transform, point):
    a, neg_b = transform['matrix'][0]
    b, a2 = transform['matrix'][1]
    if abs(a-a2) > 1e-10 or abs(neg_b+b) > 1e-10:
        raise ValueError('Malformed similarity matrix')
    x, y = point
    t = transform['translationMm']
    return [a*x + neg_b*y + t[0], b*x + a2*y + t[1]]


def analyze(request, now_ms=None):
    if not isinstance(request, dict) or request.get('schema') != 1 or request.get('scope') != 'fresh-ftp-top-camera-fiducials':
        raise ValueError('Expected schema-1 fresh-ftp-top-camera-fiducials request')
    operator = request.get('operator')
    if not isinstance(operator, str) or not operator.strip():
        raise ValueError('Named operator review is required')
    if set(request.get('measurements', {})) != set(REFERENCES):
        raise ValueError('Exactly FID1, FID2 and FID3 measurements are required')
    roi, thresholds = request.get('roi'), request.get('thresholds')
    if (not isinstance(roi, list) or len(roi) != 4 or any(type(v) is not int for v in roi)
            or not isinstance(thresholds, list) or len(thresholds) < 2
            or any(type(v) is not int or not 0 <= v <= 255 for v in thresholds)):
        raise ValueError('Explicit integer image ROI and at least two red thresholds are required')
    if len(set(thresholds)) != len(thresholds):
        raise ValueError('Image thresholds must be unique')

    now = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000) if now_ms is None else now_ms
    board_path = Path(request['board']).resolve(strict=True)
    canonical_board = Path(__file__).resolve().parents[3] / 'pnp/pcb/ftp/ftp.kicad_pcb'
    if board_path != canonical_board.resolve(strict=True):
        raise ValueError('Only the canonical FTP KiCad board is accepted as the local-coordinate source')
    board_bytes, board_prov = bound(board_path)
    board_fids = fiducials(board_bytes)
    # Front-side CAD convention is X right, Y up; KiCad source stores this Y down.
    design = {ref: [board_fids[ref][0], -board_fids[ref][1]] for ref in REFERENCES}
    config = jvm = fixed_zab = top_plane = None
    samples = {}
    seen_ids = set()
    for ref in REFERENCES:
        item = request['measurements'][ref]
        if not isinstance(item, dict) or item.get('fiducialIdentityReviewed') is not True or item.get('centeredInTopImageReviewed') is not True:
            raise ValueError(f'{ref} requires explicit visual identity and centering review')
        report_path = Path(item.get('report', '')).resolve(strict=True)
        report_bytes, report_prov = bound(report_path)
        if hashlib.sha256(report_bytes).hexdigest() != item.get('reportSha256'):
            raise ValueError(f'{ref} source report hash changed')
        report = json.loads(report_bytes)
        if report.get('status') != 'completed-camera-survey-awaiting-image-review':
            raise ValueError(f'{ref} requires a successful completed camera survey')
        if report.get('id') in seen_ids:
            raise ValueError('Each fiducial requires a distinct survey record')
        seen_ids.add(report.get('id'))
        finished = iso_ms(report.get('finishedAt'))
        if finished > now or now - finished > MAX_REPORT_AGE_MS:
            raise ValueError(f'{ref} survey must be no more than 30 minutes old')
        kind, source_jvm, source_config, raw, _driver, poses = source.source_snapshot(report)
        if kind != 'successful-survey' or report.get('request', {}).get('axis') not in ('X', 'Y'):
            raise ValueError(f'{ref} must come from a verified single-axis XY camera survey')
        source_fixed = tuple(raw[k] for k in ('Z', 'A', 'B'))
        source_plane = (poses['top']['z'], poses['top']['rotation'])
        if config is None:
            config, jvm, fixed_zab, top_plane = source_config, source_jvm, source_fixed, source_plane
        elif (source_config != config or source_jvm != jvm or source_fixed != fixed_zab
              or any(abs(a-b) > 1e-6 for a, b in zip(source_plane, top_plane))):
            raise ValueError('Fiducial surveys must share one JVM/configuration, fixed Z/A/B and top-camera imaging plane')

        images = report.get('afterImages', {}).get('top')
        if not isinstance(images, dict) or not isinstance(images.get('path'), str):
            raise ValueError(f'{ref} lacks a captured top-camera image')
        image_path = (report_path.parent / images['path']).resolve(strict=True)
        if image_path.parent != report_path.parent:
            raise ValueError(f'{ref} image must remain beside its source report')
        image_bytes, image_prov = bound(image_path)
        if image_prov['sha256'] != item.get('topImageSha256'):
            raise ValueError(f'{ref} top-camera image hash changed after review')
        metrics = sweep(image_bytes, roi, thresholds, 'R')
        selected = [t['selected'] for t in metrics['thresholds']]
        if any(s is None or s['touchesRoiEdge'] or s['equalAreaAmbiguity'] for s in selected):
            raise ValueError(f'{ref} image has a missing, clipped or ambiguous red fiducial')
        center = [metrics['centroidSummary'][k]['median'] for k in ('x', 'y')]
        image_center = [metrics['geometricImageCenterPixelIndex'][k] for k in ('x', 'y')]
        error_px = math.dist(center, image_center)
        if error_px > 2.0:
            raise ValueError(f'{ref} target is not centered in the top-camera image (error {error_px:.3f}px)')
        top = poses['top']
        camera_xy = finite_pair([top['x'], top['y']], f'{ref} top-camera center')
        samples[ref] = {'designXYMm': design[ref], 'measuredTopCameraXYMm': camera_xy,
                        'imageCenterErrorPx': error_px, 'report': report_prov, 'image': image_prov,
                        'reportId': report['id'], 'finishedAt': report['finishedAt']}

    transform = similarity_from_pair(design['FID1'], design['FID2'],
                                     samples['FID1']['measuredTopCameraXYMm'],
                                     samples['FID2']['measuredTopCameraXYMm'])
    if not MIN_SCALE <= transform['scale'] <= MAX_SCALE:
        raise ValueError('Two-fiducial scale is outside the 0.99–1.01 review gate')
    pred3 = apply(transform, design['FID3'])
    measured3 = samples['FID3']['measuredTopCameraXYMm']
    residual3 = math.dist(pred3, measured3)
    if residual3 > MAX_THIRD_RESIDUAL_MM:
        raise ValueError('Independent FID3 check exceeds 0.08 mm')

    pads = cad.extract_kicad(board_bytes.decode())
    if len(pads) != 80 or {p['reference'] for p in pads} != {f'R{i}' for i in range(1, 41)}:
        raise ValueError('Expected exactly two resistor paste pads for each R1–R40')
    targets = []
    for pad in pads:
        point = pad['centerMm']
        targets.append({'padId': pad['id'], 'designXYMm': point,
                        'machineXYMm': apply(transform, point)})
    parser_path = Path(cad.__file__).resolve()
    parser_bytes = parser_path.read_bytes()
    return {'schema': 1, 'scope': 'offline-fresh-ftp-two-fiducial-transform-with-third-point-check',
            'operator': operator.strip(), 'board': board_prov,
            'parser': {'path': str(parser_path), 'sha256': hashlib.sha256(parser_bytes).hexdigest()},
            'coordinateConvention': {'design': 'KiCad front-board Cartesian, X right / Y up',
                                     'conversion': 'x = KiCad X; y = -KiCad Y',
                                     'machineTargets': 'measured top-camera center XY in the same OpenPnP machine frame'},
            'session': {'jvmStartMs': jvm, 'liveConfigurationSha256': config,
                        'fixedRawZAB': list(fixed_zab), 'topCameraZRotation': list(top_plane)},
            'measurements': samples, 'transformFromFID1FID2': transform,
            'independentFID3Check': {'predictedMachineXYMm': pred3,
                                     'measuredTopCameraXYMm': measured3,
                                     'residualMm': residual3,
                                     'maximumAllowedMm': MAX_THIRD_RESIDUAL_MM},
            'acceptance': {'scaleRange': [MIN_SCALE, MAX_SCALE],
                           'fiducialCenterErrorPxMaximum': 2.0,
                           'fiducial3ResidualMmMaximum': MAX_THIRD_RESIDUAL_MM,
                           'passed': True},
            'resistorPadMachineXYTargets': targets,
            'machineConfigurationChanged': False, 'jobChanged': False,
            'motionDispatched': False, 'executionReady': False,
            'limitations': ['Offline coordinate candidates only; no OpenPnP board transform or placed flags changed.',
                            'Two fiducials define the similarity transform; FID3 is an independent held-out check.',
                            'Targets inherit camera-centering, board identity and imaging uncertainty.',
                            'No Z, nozzle offset, clearance, paste dose or physical pad-availability is inferred.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        request_bytes, request_prov = bound(args.request)
        result = analyze(json.loads(request_bytes))
        result['request'] = request_prov
        with args.output.open('x') as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write('\n')
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps({'output': str(args.output.resolve()), 'motionDispatched': False,
                      'executionReady': False, 'padTargetCount': len(result['resistorPadMachineXYTargets'])}, indent=2))


if __name__ == '__main__':
    main()
