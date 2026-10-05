#!/usr/bin/env python3
"""Build a provisional FTP similarity candidate from hash-bound native fiducial reports."""
import argparse
import datetime
import hashlib
import json
import math
from pathlib import Path

from fiducial_registration import bound, cad, fiducials
from fresh_ftp_registration import (apply, similarity_from_pair, affine_from_three,
                                    held_out_checks, AFFINE_MODEL, MIN_SCALE,
                                    MAX_SCALE, MAX_THIRD_RESIDUAL_MM,
                                    MAX_AFFINE_SKEW_DEGREES)
from coarse_fiducial_check import require_bright_disk

REFERENCES = ('FID1', 'FID2', 'FID3')
MAX_REPORT_AGE_MS = 30 * 60 * 1000
BOARD = Path(__file__).resolve().parents[3] / 'pnp/pcb/ftp/ftp.kicad_pcb'


def pair(value, label):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(label + ' must contain exactly two coordinates')
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in value):
        raise ValueError(label + ' must be finite')
    return [float(value[0]), float(value[1])]


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('Native report completion time required')
    try:
        parsed = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('Timezone required')
        return int(parsed.timestamp() * 1000)
    except (ValueError, OverflowError) as exc:
        raise ValueError('Malformed native report completion time') from exc


def read_report(evidence):
    if not isinstance(evidence, dict) or not isinstance(evidence.get('path'), str):
        raise ValueError('Native report path/hash evidence required')
    data, prov = bound(evidence['path'])
    if evidence.get('sha256') != prov['sha256']:
        raise ValueError('Native report hash changed')
    return json.loads(data), prov


def axes(snapshot):
    if not isinstance(snapshot, dict) or set(snapshot) != set('XYZA'+'B'):
        raise ValueError('Native source pose must contain exactly model axes X/Y/Z/A/B')
    result = {}
    for axis, values in snapshot.items():
        if not isinstance(values, dict):
            raise ValueError('Native model pose axis record required')
        for key in ('model', 'driver'):
            v = values.get(key)
            if type(v) not in (int, float) or not math.isfinite(v):
                raise ValueError('Finite native source axis values required')
        result[axis] = {'model': float(values['model']), 'driver': float(values['driver'])}
    return result


def analyze(request, now_ms=None):
    if not isinstance(request, dict) or request.get('schema') != 1 or request.get('scope') != 'native-fiducial-registration-input':
        raise ValueError('Expected schema-1 native-fiducial-registration-input')
    operator = request.get('operator')
    if not isinstance(operator, str) or not operator.strip():
        raise ValueError('Named reviewer required')
    reports = request.get('reports')
    if not isinstance(reports, dict) or set(reports) != set(REFERENCES):
        raise ValueError('Exactly FID1, FID2 and FID3 native reports required')
    now = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000) if now_ms is None else now_ms
    board_path = Path(request.get('board', '')).resolve(strict=True)
    if board_path != BOARD.resolve(strict=True):
        raise ValueError('Only the canonical FTP KiCad board is accepted')
    board_bytes, board_prov = bound(board_path)
    cad_fids = fiducials(board_bytes)
    # The existing FTP registration contract uses front-board machine/design XY
    # with positive KiCad Y. Saved-job FID1 is separately recorded below.
    design = {ref: [cad_fids[ref][0], -cad_fids[ref][1]] for ref in REFERENCES}
    session = None
    fixed = None
    camera_id = None
    camera_location = None
    board_identity = None
    board_matrix = None
    job_path = None
    samples = {}
    seen = set()
    for ref in REFERENCES:
        report, prov = read_report(reports[ref])
        if (report.get('schema') != 1 or report.get('scope') != 'native-current-pose-fiducial-vision'
                or report.get('status') != 'completed-native-fiducial-detection-awaiting-review'
                or report.get('error') or report.get('physicalRegistrationEstablished') is not False
                or report.get('noMotion') is not True or report.get('noActuation') is not True
                or report.get('noVacuum') is not True or report.get('jobSaved') is not False
                or report.get('configurationSaved') is not False or report.get('modelPoseUnchanged') is not True
                or report.get('configurationRestored') is not True):
            raise ValueError(f'{ref} requires a completed, restored, no-motion native fiducial report')
        if report.get('requestId') in seen or not isinstance(report.get('requestId'), str) or not report['requestId']:
            raise ValueError('Each native fiducial requires a distinct request ID')
        seen.add(report['requestId'])
        finished = timestamp(report.get('finishedAt'))
        if finished > now or now - finished > MAX_REPORT_AGE_MS:
            raise ValueError('Native fiducial reports must be no more than 30 minutes old')
        before, after = axes(report.get('modelPoseBefore')), axes(report.get('modelPoseAfter'))
        source_pose = report.get('nativePose')
        if not isinstance(source_pose, dict) or axes(source_pose.get('rawAxes')) != before:
            raise ValueError('Native detection source pose does not match the same report snapshot')
        if before != after:
            raise ValueError('Native report model pose changed during detection')
        config_before, config_after = report.get('liveConfigurationBeforeSha256'), report.get('liveConfigurationAfterSha256')
        if not isinstance(config_before, str) or len(config_before) != 64 or config_before != config_after:
            raise ValueError('Native report configuration must be hash-bound and restored')
        zab = [before[k]['model'] for k in ('Z', 'A', 'B')]
        if session is None:
            session = (report.get('jvmStartMs'), config_before)
            fixed = zab
        elif (session != (report.get('jvmStartMs'), config_before) or fixed != zab):
            raise ValueError('Native fiducial reports must share JVM/configuration and fixed Z/A/B')
        barrier_ref = report.get('sourceBarrier') or {}
        barrier_data, barrier_prov = bound(barrier_ref.get('path', ''))
        if barrier_ref.get('sha256') != barrier_prov['sha256']:
            raise ValueError(f'{ref} source position barrier hash changed')
        barrier = json.loads(barrier_data)
        snap = barrier.get('afterQuerySnapshot') or {}
        if (barrier.get('schema') != 1 or barrier.get('status') != 'completed-read-only-position-barrier'
                or barrier.get('controllerPositionVerified') is not True or barrier.get('uncertainCompletion') is not False
                or barrier.get('noMotionCommandSubmitted') is not True or barrier.get('request', {}).get('scope') != 'read-only-native-position-barrier'
                or barrier.get('request', {}).get('jvmStartMs') != report.get('jvmStartMs')
                or barrier.get('request', {}).get('liveConfigurationSha256') != config_before
                or barrier.get('liveConfigurationSha256') != config_before or report.get('sourceBarrierId') != barrier.get('request', {}).get('id')
                or report.get('sourceBarrierSnapshot') != snap):
            raise ValueError(f'{ref} must bind a completed same-session read-only position barrier')
        axes_from_barrier = {k: {'model': snap.get('raw', {}).get(k), 'driver': snap.get('driver', {}).get(k)} for k in ('X','Y','Z','A','B')}
        if axes(axes_from_barrier) != before:
            raise ValueError(f'{ref} native report pose differs from source barrier')
        board = report.get('board') or {}
        camera = report.get('camera') or {}
        if not board.get('boardId') or not isinstance(board.get('fiducials'), list):
            raise ValueError('Native board identity and fiducials required')
        fids = {v.get('reference'): v for v in board['fiducials'] if isinstance(v, dict)}
        if set(fids) != set(REFERENCES):
            raise ValueError('Native report must bind all three saved board fiducials')
        matrix = board.get('localToGlobalMatrix')
        if not isinstance(matrix, list) or len(matrix) != 6 or any(type(x) not in (int, float) or not math.isfinite(x) for x in matrix):
            raise ValueError('Finite six-value saved board transform required')
        loc = camera.get('locationMm')
        if not isinstance(loc, dict) or any(type(loc.get(k)) not in (int, float) or not math.isfinite(loc[k]) for k in ('x', 'y', 'z', 'rotation')):
            raise ValueError('Exact native camera pose required')
        pose_loc = source_pose.get('cameraLocationMm')
        if not isinstance(pose_loc, dict) or any(abs(float(pose_loc.get(k, float('nan'))) - float(loc[k])) > 1e-9 for k in ('x', 'y', 'z', 'rotation')):
            raise ValueError('Native detector camera pose differs from report camera pose')
        if (camera.get('exposureRestored') is not True or camera.get('exposureUsed') != 36
                or report.get('camera', {}).get('locationAfterMm') != loc):
            raise ValueError('Native camera exposure/location restoration required')
        identity = (board['boardId'], board.get('side'), matrix, report.get('jobPath'), camera.get('id'), loc['z'], loc['rotation'])
        if board_identity is None:
            board_identity, board_matrix, job_path = identity, matrix, report.get('jobPath')
            camera_id, camera_location = camera.get('id'), loc
        elif identity != board_identity:
            raise ValueError('Native reports must share board/job/transform/camera identity and plane')
        fid = fids[ref]
        local = pair(fid.get('localXYMm'), f'{ref} saved local coordinates')
        if not fid.get('partId'):
            raise ValueError(f'{ref} native saved-job part identity required')
        detection = report.get('nativeFiducialDetection') or {}
        if detection.get('reference') != ref:
            raise ValueError(f'{ref} native report detected another fiducial')
        top = snap.get('nativePoses', {}).get('top', {})
        expected_from_barrier = [top.get('x'), top.get('y')]
        if detection.get('expectedMachineXYMm') != expected_from_barrier or report.get('expectedCameraLocationMm') != top:
            raise ValueError(f'{ref} native detector expected position differs from fresh camera barrier')
        measured = pair(detection.get('detectedMachineXYMm'), f'{ref} detected location')
        expected = pair(detection.get('expectedMachineXYMm'), f'{ref} expected location')
        residual = math.dist(measured, expected)
        if residual > 2.0:
            raise ValueError(f'{ref} native detector residual exceeds 2.0 mm')
        if abs(float(detection.get('cameraCenterResidualMm', float('nan'))) - residual) > 1e-6:
            raise ValueError(f'{ref} native camera-center residual metadata differs')
        keypoints = detection.get('keypoints')
        if not isinstance(keypoints, list) or not keypoints:
            raise ValueError(f'{ref} native detector keypoint provenance required')
        if not any(isinstance(k, dict) and pair(k.get('machineXYMm'), 'native keypoint location') == measured and abs(float(k.get('cameraCenterResidualMm', float('nan'))) - residual) <= 1e-6 for k in keypoints):
            raise ValueError(f'{ref} detected location is absent from native keypoints')
        images = report.get('images') or {}
        coarse_checks = []
        for name in ('raw', 'nativeInput'):
            item = images.get(name)
            if not isinstance(item, dict) or not isinstance(item.get('path'), str) or len(item.get('sha256', '')) != 64:
                raise ValueError(f'{ref} source {name} image provenance required')
            image_path = Path(item['path']).resolve(strict=True)
            if image_path.parent != Path(prov['path']).parent:
                raise ValueError(f'{ref} source images must remain beside the report')
            image_sha = hashlib.sha256(image_path.read_bytes()).hexdigest()
            if image_sha != item['sha256']:
                raise ValueError(f'{ref} source image hash changed')
            # Native keypoint coordinates belong to the transformed image supplied to
            # the vision pipeline (`nativeInput`), not necessarily captureRaw(). On
            # this camera captureRaw() is 180° from captureTransformed(); checking
            # those coordinates against raw pixels can reject a real disk (or accept
            # an unrelated feature at the mirrored point).
            if name == 'nativeInput':
                from PIL import Image
                with Image.open(image_path) as image:
                    for keypoint in keypoints:
                        pixel = keypoint.get('pixel') if isinstance(keypoint, dict) else None
                        if (not isinstance(pixel, list) or len(pixel) != 2
                                or any(type(v) not in (int, float) or not math.isfinite(v) for v in pixel)):
                            raise ValueError(f'{ref} native keypoint pixel coordinates required for coarse circle check')
                        check = require_bright_disk(image, pixel, radius_px=40, threshold=100, min_occupancy=.65)
                        if not check['passes']:
                            raise ValueError(f'{ref} native keypoint does not overlap a coarse bright circular fiducial mask')
                        coarse_checks.append({'image': 'nativeInput', 'pixel': pixel, **check})
        samples[ref] = {'designXYMm': design[ref], 'measuredTopCameraXYMm': measured,
                        'nativeFiducialDetection': detection, 'report': prov,
                        'coarseBrightDiskChecks': coarse_checks,
                        'reportId': report['requestId'], 'finishedAt': report['finishedAt'],
                        'partId': fid['partId'], 'savedJobLocalXYMm': local,
                        'sourceBarrier': barrier_prov}

    model = request.get('registrationModel', 'two-fiducial-similarity')
    if model not in ('two-fiducial-similarity', AFFINE_MODEL):
        raise ValueError('Unsupported native registration model')
    if model == AFFINE_MODEL:
        transform = affine_from_three([design[r] for r in REFERENCES],
                                      [samples[r]['measuredTopCameraXYMm'] for r in REFERENCES])
        pred3 = measured3 = residual3 = None
    else:
        # Keep the established similarity path and independent FID3 gate intact.
        transform = similarity_from_pair(design['FID1'], design['FID2'],
                                         samples['FID1']['measuredTopCameraXYMm'],
                                         samples['FID2']['measuredTopCameraXYMm'])
        if not MIN_SCALE <= transform['scale'] <= MAX_SCALE:
            raise ValueError('Native fiducial similarity scale is outside 0.99–1.01')
        pred3 = apply(transform, design['FID3'])
        measured3 = samples['FID3']['measuredTopCameraXYMm']
        residual3 = math.dist(pred3, measured3)
        if residual3 > MAX_THIRD_RESIDUAL_MM:
            raise ValueError('Independent native FID3 check exceeds 0.08 mm')
    cad_pads = cad.extract_kicad(board_bytes.decode())
    if len(cad_pads) != 80 or {p['reference'] for p in cad_pads} != {f'R{i}' for i in range(1, 41)}:
        raise ValueError('Expected exactly two resistor paste pads for each R1–R40')
    targets = [{'padId': p['id'], 'designXYMm': p['centerMm'], 'machineXYMm': apply(transform, p['centerMm'])} for p in cad_pads]
    parser_path = Path(cad.__file__).resolve()
    result = {'schema': 1, 'scope': 'offline-native-fresh-ftp-two-fiducial-transform-with-third-point-check',
              'operator': operator.strip(), 'board': board_prov,
              'parser': {'path': str(parser_path), 'sha256': hashlib.sha256(parser_path.read_bytes()).hexdigest()},
              'coordinateConvention': {'design': 'KiCad front-board Cartesian, X right / Y up',
                                       'conversion': 'x = KiCad X; y = KiCad Y',
                                       'machineTargets': 'native detected fiducial XY in the same OpenPnP machine frame'},
              'session': {'jvmStartMs': session[0], 'liveConfigurationSha256': session[1],
                          'fixedRawZAB': fixed, 'topCameraZRotation': [camera_location['z'], camera_location['rotation']]},
              'nativeSource': {'jobPath': job_path, 'boardId': board_identity[0], 'boardSide': board_identity[1],
                               'localToGlobalMatrix': board_matrix, 'cameraId': camera_id,
                               'reports': [{'reference': r, **samples[r]['report']} for r in REFERENCES],
                               'sourceBarriers': [samples[r]['sourceBarrier'] for r in REFERENCES],
                               'canonicalVsSavedJobFiducials': {r: {'canonicalKiCadXYMm': cad_fids[r], 'savedJobLocalXYMm': samples[r]['savedJobLocalXYMm']} for r in REFERENCES}},
              'measurements': samples, 'transformFromFID1FID2': transform,
              'independentFID3Check': {'predictedMachineXYMm': pred3, 'measuredTopCameraXYMm': measured3,
                                       'residualMm': residual3, 'maximumAllowedMm': MAX_THIRD_RESIDUAL_MM},
              'acceptance': {'scaleRange': [MIN_SCALE, MAX_SCALE], 'nativeFiducialResidualMmMaximum': 2.0,
                             'fiducial3ResidualMmMaximum': MAX_THIRD_RESIDUAL_MM, 'passed': True},
              'resistorPadMachineXYTargets': targets, 'machineConfigurationChanged': False,
              'jobChanged': False, 'motionDispatched': False, 'executionReady': False,
              'physicalRegistrationEstablished': False,
              'limitations': ['Offline coordinate candidate only; no OpenPnP board transform or placed flags changed.',
                              'Two native fiducials define the similarity transform; native FID3 is an independent held-out check.',
                              'Native detector locations inherit machine vision and current pose uncertainty.',
                              'No Z, nozzle offset, clearance, paste dose or physical pad availability is inferred.']}
    if model == AFFINE_MODEL:
        del result['transformFromFID1FID2'], result['independentFID3Check']
        result.update(scope='offline-native-fresh-ftp-three-fiducial-affine-candidate',
                      transformFromThreeFiducials=transform, fittedFiducials=list(REFERENCES),
                      independentHeldOutPadChecks=[],
                      acceptance={'singularValueRange': [MIN_SCALE, MAX_SCALE],
                                  'axisSkewDegreesMaximum': MAX_AFFINE_SKEW_DEGREES,
                                  'nativeFiducialResidualMmMaximum': 2.0,
                                  'heldOutPadErrorPxMaximum': 8.0,
                                  'heldOutPadResidualMmMaximum': 0.08,
                                  'passed': False})
        result['limitations'][1] = 'All three native fiducials are fitted; separate held-out pad checks are required for acceptance.'
        if request.get('heldOutPadChecks') is not None:
            checks, jacobian = held_out_checks(request, result, now)
            result.update(scope='offline-native-fresh-ftp-three-fiducial-affine-with-held-out-pad-checks',
                          independentHeldOutPadChecks=checks, imageJacobianEvidence=jacobian)
            result['acceptance']['passed'] = True
    return result


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
