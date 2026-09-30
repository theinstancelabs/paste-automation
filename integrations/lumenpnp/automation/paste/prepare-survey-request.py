#!/usr/bin/env python3
"""Prepare, never dispatch, one new reviewed bounded single-axis XY camera-survey request."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import time
import uuid

AXES = {'X', 'Y', 'Z', 'A', 'B'}
POSES = {'N1', 'N2', 'top', 'bottom'}
LEGACY_SCOPE = 'camera-survey-raw-X-plus10-only'
SCOPE = 'camera-survey-single-raw-XY-axis'
UUID_PATTERN = r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'
SUCCESS = 'completed-camera-survey-awaiting-image-review'
AUDIT_SUCCESS = 'audit-complete-awaiting-separate-reviewed-latch-clear'


def finite(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f'{label} must be finite')
    return value


def axes(value, label):
    if not isinstance(value, dict) or set(value) != AXES:
        raise ValueError(f'{label} must contain exactly X/Y/Z/A/B')
    return {key: finite(value[key], f'{label} {key}') for key in ('X', 'Y', 'Z', 'A', 'B')}


def source_snapshot(report):
    if not isinstance(report, dict) or type(report.get('schema')) is not int or report['schema'] != 1:
        raise ValueError('Expected explicit source report schema 1')
    if report.get('error') or report.get('uncertainCompletion') is True or report.get('auditIncomplete') is True:
        raise ValueError('Failed, uncertain or incomplete reports cannot prepare a continuation')
    request = report.get('request')
    if report.get('status') in (SUCCESS, 'completed-Z-observation-awaiting-image-review'):
        allowed_scopes = (SCOPE, LEGACY_SCOPE) if report['status'] == SUCCESS else ('single-positive-raw-Z-observation', 'bounded-signed-raw-Z-observation')
        if (not isinstance(request, dict) or request.get('scope') not in allowed_scopes
                or not isinstance(report.get('id'), str) or not re.fullmatch(UUID_PATTERN, report['id'])
                or report.get('id') != request.get('id')
                or any(report.get(key) is not True for key in ('motionSubmitted', 'nativeMotionCompletionReported', 'controllerPositionVerified', 'independentFirmwareStepVerified'))
                or report.get('uncertainCompletion') is not False):
            raise ValueError('Survey lacks explicit verified completion')
        frame = report.get('after')
        if not isinstance(frame, dict):
            raise ValueError('Successful survey lacks independent after-M114 record')
        reported = frame.get('reported')
        jvm, config_hash = request.get('jvmStartMs'), request.get('liveConfigurationSha256')
        kind = 'successful-survey'
    elif report.get('status') == 'completed-read-only-position-barrier':
        if (not isinstance(request, dict) or request.get('scope') != 'read-only-native-position-barrier'
                or not isinstance(report.get('id'), str) or not re.fullmatch(UUID_PATTERN, report['id']) or request.get('id') != report['id']
                or report.get('noMotionCommandSubmitted') is not True
                or report.get('controllerPositionVerified') is not True or report.get('uncertainCompletion') is not False):
            raise ValueError('Barrier lacks explicit verified read-only completion')
        reported = report.get('reported')
        jvm, config_hash = request.get('jvmStartMs'), report.get('liveConfigurationSha256')
        if config_hash != request.get('liveConfigurationSha256'):
            raise ValueError('Barrier configuration mismatch')
        kind = 'successful-position-barrier'
    elif report.get('status') == AUDIT_SUCCESS:
        if (report.get('scope') != 'read-only-specific-survey-stop-audit'
                or not isinstance(report.get('faultId'), str) or not re.fullmatch(UUID_PATTERN, report['faultId'])
                or not isinstance(report.get('faultSha256'), str) or not re.fullmatch(r'[a-f0-9]{64}', report['faultSha256'])
                or report.get('positionVerified') is not True
                or report.get('stationaryImagesCaptured') is not True
                or report.get('motionIssued') is not False
                or report.get('latchCleared') is not False):
            raise ValueError('Source is not a completed narrow stationary stop audit')
        reported = report.get('reported')
        jvm, config_hash = report.get('jvmStartMs'), report.get('liveConfigurationSha256')
        kind = 'successful-stop-audit'
    else:
        raise ValueError('Only successful survey or completed narrow stop-audit reports are accepted; no failed-survey replay')
    if type(jvm) is not int or jvm <= 0 or not isinstance(config_hash, str) or not re.fullmatch(r'[a-f0-9]{64}', config_hash):
        raise ValueError('Source lacks exact JVM identity/live configuration digest')
    snap = report.get('afterQuerySnapshot')
    if not isinstance(snap, dict):
        raise ValueError('Source lacks verified terminal model snapshot')
    raw, driver = axes(snap.get('raw'), 'terminal raw'), axes(reported, 'terminal M114')
    for axis in AXES:
        tolerance = 0.3 if axis in ('A', 'B') else 0.02
        if abs(raw[axis] - driver[axis]) > tolerance:
            raise ValueError(f'Source terminal raw/firmware mismatch on {axis}')
    native = snap.get('nativePoses')
    if not isinstance(native, dict) or set(native) != POSES:
        raise ValueError('Source must include all four terminal native poses')
    poses = {}
    for name in ('N1', 'N2', 'top', 'bottom'):
        if not isinstance(native[name], dict):
            raise ValueError('Malformed native pose')
        poses[name] = {key: finite(native[name].get(key), f'{name} {key}') for key in ('x', 'y', 'z', 'rotation')}
    return kind, jvm, config_hash, raw, driver, poses


def prepare(report_path, image_path, operator, reviewed, now_ms=None, axis='X', delta_mm=10):
    if reviewed is not True or not isinstance(operator, str) or not operator.strip():
        raise ValueError('Named operator and explicit --reviewed-clear-corridor are required; this attests all four corridor/clearance/empty-part checks')
    if axis not in ('X', 'Y') or not 0 < abs(finite(delta_mm, 'delta_mm')) <= 10:
        raise ValueError('Select X or Y and a nonzero signed delta of magnitude at most 10 mm')
    now = time.time_ns() // 1_000_000 if now_ms is None else now_ms
    finite(now, 'current time')
    report_path, image_path = Path(report_path).resolve(strict=True), Path(image_path).resolve(strict=True)
    report_bytes = report_path.read_bytes()
    kind, jvm, config_hash, raw, driver, poses = source_snapshot(json.loads(report_bytes))
    before = image_path.stat()
    image = image_path.read_bytes()
    after = image_path.stat()
    if (before.st_mtime_ns, before.st_size, before.st_ino) != (after.st_mtime_ns, after.st_size, after.st_ino):
        raise ValueError('Corridor image changed while reading')
    captured_ms = after.st_mtime_ns // 1_000_000
    if captured_ms > now or now - captured_ms > 300000:
        raise ValueError('Corridor image file mtime must be no more than five minutes old and not future-dated')
    if not (image.startswith(b'\x89PNG\r\n\x1a\n') or image.startswith(b'\xff\xd8\xff')):
        raise ValueError('Corridor evidence must be a PNG or JPEG image')
    if jvm > now:
        raise ValueError('Source JVM start is future-dated')
    template = json.loads(Path(__file__).with_name('survey-request.pending.json').read_text())
    request = copy.deepcopy(template)
    request.update(description='Prepared offline from a verified terminal pose. This does not dispatch, clear a latch, or authorize any other motion.',
                   schema=2, scope=SCOPE, axis=axis, deltaMm=delta_mm, speedFraction=1.0, speedOverPrecision=True,
                   id=str(uuid.uuid4()), createdMs=now, jvmStartMs=jvm, operator=operator.strip(),
                   liveConfigurationSha256=config_hash,
                   operatorVerified10mmCorridor=True, bothHeadsClearAlongCorridor=True,
                   motionAreaClear=True, noHeldPartsObserved=True,
                   corridorEvidence={'path': str(image_path), 'sha256': hashlib.sha256(image).hexdigest(), 'capturedMs': captured_ms},
                   expectedRaw=raw, expectedDriver=driver, expectedNativePoses=poses)
    provenance = {'sourceReport': str(report_path), 'sourceSha256': hashlib.sha256(report_bytes).hexdigest(),
                  'sourceKind': kind, 'id': request['id'], 'dispatchPerformed': False,
                  'separateLatchReleaseRequiredForAuditSource': kind == 'successful-stop-audit'}
    return request, provenance


def write_request(path, request):
    with Path(path).open('x') as stream:
        stream.write(json.dumps(request, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_report', type=Path)
    parser.add_argument('corridor_image', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--operator', required=True)
    parser.add_argument('--axis', choices=('X', 'Y'), default='X')
    parser.add_argument('--delta-mm', type=float, default=10)
    parser.add_argument('--reviewed-clear-corridor', action='store_true',
                        help='explicitly attest fresh image review, clear selected signed XY corridor for both heads, clear motion area and no held parts')
    args = parser.parse_args()
    try:
        request, provenance = prepare(args.source_report, args.corridor_image, args.operator, args.reviewed_clear_corridor, axis=args.axis, delta_mm=args.delta_mm)
        write_request(args.output, request)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.error(str(exc))
    print(json.dumps({'output': str(args.output), **provenance}, indent=2))


if __name__ == '__main__':
    main()
