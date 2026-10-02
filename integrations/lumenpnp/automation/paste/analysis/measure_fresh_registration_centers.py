#!/usr/bin/env python3
"""Offline threshold-sweep candidates for fresh camera registration centers.

The operator supplies a manifest of camera reports and manually selected ROIs.
This emits raw-frame pixel observations only; it does not assert feature identity,
review flags, physical calibration, registration acceptance, or machine offsets.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from needle_centroid import sweep


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measured_frame(item, session=None, fixed=None):
    path = Path(item['report']).resolve(strict=True)
    raw = path.read_bytes()
    report = json.loads(raw)
    request = report.get('request', {})
    if (report.get('status') != 'completed-camera-survey-awaiting-image-review'
            or report.get('controllerPositionVerified') is not True
            or report.get('uncertainCompletion') is not False or report.get('error')
            or report.get('id') != request.get('id')):
        raise ValueError(f"{path}: completed verified camera survey required")
    identity = (request.get('jvmStartMs'), request.get('liveConfigurationSha256'))
    axes = report.get('afterQuerySnapshot', {}).get('raw', {})
    if set(axes) != set('XYZAB') or any(type(v) not in (int, float) or not math.isfinite(v) for v in axes.values()):
        raise ValueError(f"{path}: complete finite raw after-position required")
    zab = [axes[k] for k in ('Z', 'A', 'B')]
    top = report.get('afterQuerySnapshot', {}).get('nativePoses', {}).get('top', {})
    camera_xy = [top.get('x'), top.get('y')]
    plane = [top.get('z'), top.get('rotation')]
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in camera_xy + plane):
        raise ValueError(f"{path}: finite top-camera pose required")
    if session is not None and identity != session:
        raise ValueError('All images must come from one JVM/configuration')
    if fixed is not None and zab != fixed:
        raise ValueError('All images must share fixed raw Z/A/B')
    image_path = (path.parent / report['afterImages']['top']['path']).resolve(strict=True)
    if image_path.parent != path.parent:
        raise ValueError('Image must belong to its camera report directory')
    image_data = image_path.read_bytes()
    measurement = sweep(image_data, item['roi'], item['thresholds'], item.get('channel', 'B'))
    rows = measurement['thresholds']
    if (not rows or any(row['selected'] is None or row['selected']['touchesRoiEdge']
                        or row['selected']['equalAreaAmbiguity'] for row in rows)):
        raise ValueError(f"{path}: missing, clipped, or equal-area ambiguous feature at a threshold")
    center = measurement['centroidSummary']
    if center is None:
        raise ValueError(f"{path}: no center candidates")
    return {
        'reportPath': str(path), 'reportSha256': hashlib.sha256(raw).hexdigest(),
        'reportId': report.get('id'), 'finishedAt': report.get('finishedAt'),
        'imagePath': str(image_path), 'imageSha256': hashlib.sha256(image_data).hexdigest(),
        'rawXY': [axes['X'], axes['Y']],
        'cameraXYMm': camera_xy, 'session': identity, 'fixedRawZAB': zab,
        'topCameraZRotation': plane,
        'observedCenterPixel': [center['x']['median'], center['y']['median']],
        'thresholdSpreadPixels': [center['x']['max']-center['x']['min'], center['y']['max']-center['y']['min']],
        'roi': measurement['roi'], 'channel': measurement['channel'],
        'thresholds': item['thresholds'], 'imageSizePixels': measurement['imageSize'],
        'featureIdentityConfirmed': False,
    }


def analyze(manifest):
    source = [measured_frame(v) for v in manifest['jacobianSamples']]
    if len(source) != 3 or [v['name'] for v in manifest['jacobianSamples']] != ['base', 'xplus', 'yplus']:
        raise ValueError('Jacobian samples must be ordered exactly base, xplus, yplus')
    ids = [s['reportId'] for s in source]
    if len(set(ids)) != 3:
        raise ValueError('Jacobian samples need three distinct camera reports')
    if (len({tuple(s['session']) for s in source}) != 1
            or len({tuple(s['fixedRawZAB']) for s in source}) != 1
            or len({tuple(s['topCameraZRotation']) for s in source}) != 1):
        raise ValueError('Jacobian samples must share one session, fixed Z/A/B, and top-camera plane')
    base = source[0]['cameraXYMm']
    expected = [[base[0], base[1]], [base[0]+1, base[1]], [base[0], base[1]+1]]
    if any(any(abs(s['cameraXYMm'][k]-expected[i][k]) > 0.011 for k in (0, 1)) for i, s in enumerate(source)):
        raise ValueError('Sample camera XY must be base, exact +1 mm X and exact +1 mm Y (within 0.011 mm report quantization)')
    sizes = {tuple(s['imageSizePixels']) for s in source}
    if len(sizes) != 1:
        raise ValueError('Jacobian image dimensions changed between samples')
    c0, cx, cy = [s['observedCenterPixel'] for s in source]
    pos0, posx, posy = [s['cameraXYMm'] for s in source]
    dx, dy = [posx[k]-pos0[k] for k in (0, 1)], [posy[k]-pos0[k] for k in (0, 1)]
    detp = dx[0]*dy[1]-dy[0]*dx[1]
    if abs(detp) < 1e-9:
        raise ValueError('Camera XY sample movements are degenerate')
    px, py = [cx[k]-c0[k] for k in (0, 1)], [cy[k]-c0[k] for k in (0, 1)]
    jac = [[(px[0]*dy[1]-py[0]*dx[1])/detp, (py[0]*dx[0]-px[0]*dy[0])/detp],
           [(px[1]*dy[1]-py[1]*dx[1])/detp, (py[1]*dx[0]-px[1]*dy[0])/detp]]
    det = jac[0][0]*jac[1][1]-jac[0][1]*jac[1][0]
    if not math.isfinite(det) or abs(det) < 1e-9:
        raise ValueError('Measured image Jacobian is degenerate')
    pads = []
    for item in manifest.get('heldOutPads', []):
        frame = measured_frame(item)
        if (frame['session'] != source[0]['session'] or frame['fixedRawZAB'] != source[0]['fixedRawZAB']
                or frame['topCameraZRotation'] != source[0]['topCameraZRotation']):
            raise ValueError('Held-out pad frames must share the Jacobian sample session, Z/A/B, and top-camera plane')
        frame['padId'] = item['padId']
        pads.append(frame)
    pad_ids = {p['padId'] for p in pads}
    allowed_sets = ({'R1.2', 'R16.1', 'R40.1'}, {'R1.2', 'R16.1', 'R24.1'})
    if pads and (len(pads) != 3 or pad_ids not in allowed_sets):
        raise ValueError('Held-out candidates must be exactly R1.2/R16.1 plus one approved R24.1 or R40.1 check')
    source_measurements = [{
        'report': {'path': s['reportPath'], 'sha256': s['reportSha256']},
        'image': {'path': s['imagePath'], 'sha256': s['imageSha256']},
        'rawXY': s['rawXY'], 'centerPixels': s['observedCenterPixel'],
        'thresholdSpreadPixels': s['thresholdSpreadPixels'], 'roi': s['roi'],
        'channel': s['channel'], 'thresholds': s['thresholds'],
        'reportId': s['reportId'], 'finishedAt': s['finishedAt'],
    } for s in source]
    pad_candidates = [{
        'padId': p['padId'], 'report': p['reportPath'], 'reportSha256': p['reportSha256'],
        'topImagePath': p['imagePath'], 'topImageSha256': p['imageSha256'],
        'observedCenterPixel': p['observedCenterPixel'],
        'thresholdSpreadPixels': p['thresholdSpreadPixels'], 'roi': p['roi'],
        'channel': p['channel'], 'thresholds': p['thresholds'],
        'reportId': p['reportId'], 'finishedAt': p['finishedAt'],
    } for p in pads]
    return {
        'schema': 1, 'kind': 'fresh-camera-registration-center-candidates',
        'coordinateFrame': 'raw camera PNG pixel indices; X right, Y down; pixel centers start at (0,0)',
        'session': {'jvmStartMs': source[0]['session'][0], 'liveConfigurationSha256': source[0]['session'][1]},
        'fixedRawZAB': source[0]['fixedRawZAB'],
        'topCameraZRotation': source[0]['topCameraZRotation'],
        'jacobianCandidate': {'pixelShiftPerCameraMm': jac, 'determinant': det,
                              'sourceMeasurements': source_measurements},
        'heldOutPadIds': sorted(p['padId'] for p in pads),
        'heldOutPadCenterCandidates': pad_candidates,
        'reviewRequired': ['confirm same physical FID2 disk in all three Jacobian frames',
                           'confirm each held-out pad identity and center visually',
                           'run existing fresh_ftp_registration analyzer with its unchanged limits'],
        'physicalCalibrationEstablished': False,
        'limitations': 'Threshold spread is segmentation sensitivity, not calibrated position uncertainty. This helper does not set review booleans or accept any gate.'
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manifest', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    result = analyze(json.loads(args.manifest.read_text()))
    with args.output.open('x') as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps({'output': str(args.output), 'jacobian': result['jacobianCandidate']['pixelShiftPerCameraMm'],
                      'padCandidates': len(result['heldOutPadCenterCandidates']), 'physicalCalibrationEstablished': False}))


if __name__ == '__main__':
    main()
