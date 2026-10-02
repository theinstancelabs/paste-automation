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
AFFINE_MODEL = 'three-fiducial-affine'
MAX_AFFINE_SKEW_DEGREES = 0.3
HELD_OUT_PADS = ('R1.2', 'R16.1', 'R40.1')
FAST_CAMERA_SCOPE = 'camera-only-registered-fast-inspection'


def finite_pair(value, label):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f'{label} must contain exactly two coordinates')
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in value):
        raise ValueError(f'{label} must be finite')
    return [float(value[0]), float(value[1])]


def exact_axes(value, label):
    if not isinstance(value, dict) or set(value) != {'X', 'Y', 'Z', 'A', 'B'}:
        raise ValueError(f'{label} must bind exactly X/Y/Z/A/B')
    if any(type(value[k]) not in (int, float) or not math.isfinite(value[k]) for k in value):
        raise ValueError(f'{label} contains a nonfinite axis')
    return value


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


def affine_from_three(design, measured):
    """Fit three points exactly; fit residuals are not independent validation."""
    p1,p2,p3 = [finite_pair(p, 'design fiducial') for p in design]
    q1,q2,q3 = [finite_pair(p, 'measured fiducial') for p in measured]
    dx1,dy1,dx2,dy2 = p2[0]-p1[0],p2[1]-p1[1],p3[0]-p1[0],p3[1]-p1[1]
    den = dx1*dy2-dx2*dy1
    if abs(den) < 1e-9:
        raise ValueError('Three fiducials must be noncollinear')
    ux1,uy1,ux2,uy2 = q2[0]-q1[0],q2[1]-q1[1],q3[0]-q1[0],q3[1]-q1[1]
    a,b,c,d = (ux1*dy2-ux2*dy1)/den,(-ux1*dx2+ux2*dx1)/den,(uy1*dy2-uy2*dy1)/den,(-uy1*dx2+uy2*dx1)/den
    det = a*d-b*c
    if not all(math.isfinite(v) for v in (a,b,c,d,det)) or det <= 0:
        raise ValueError('Affine orientation must be preserved')
    aa,bb,ab = a*a+c*c,b*b+d*d,a*b+c*d
    disc = math.hypot(aa-bb,2*ab)
    sv = [math.sqrt(max(0,(aa+bb-disc)/2)),math.sqrt(max(0,(aa+bb+disc)/2))]
    skew = abs(math.degrees(math.acos(max(-1,min(1,ab/math.sqrt(aa*bb)))))-90)
    if sv[0] < MIN_SCALE-1e-12 or sv[1] > MAX_SCALE+1e-12:
        raise ValueError('Affine singular values must remain in 0.99–1.01')
    if skew > MAX_AFFINE_SKEW_DEGREES+1e-12:
        raise ValueError('Affine axis skew exceeds 0.3 degrees')
    return dict(model=AFFINE_MODEL,matrix=[[a,b],[c,d]],translationMm=[q1[0]-a*p1[0]-b*p1[1],q1[1]-c*p1[0]-d*p1[1]],
                determinant=det,singularValues=sv,axisSkewDegrees=skew)


def apply(transform, point):
    a, neg_b = transform['matrix'][0]
    b, a2 = transform['matrix'][1]
    if transform.get('model') != AFFINE_MODEL and (abs(a-a2) > 1e-10 or abs(neg_b+b) > 1e-10):
        raise ValueError('Malformed similarity matrix')
    x, y = point
    t = transform['translationMm']
    return [a*x + neg_b*y + t[0], b*x + a2*y + t[1]]


def checked_json(evidence, label):
    if not isinstance(evidence, dict):
        raise ValueError(label+' evidence required')
    data, actual = bound(evidence['path'])
    if actual['sha256'] != evidence.get('sha256'):
        raise ValueError(label+' evidence hash changed')
    return json.loads(data), actual


def camera_evidence(report_ev, image_ev, session, now):
    from PIL import Image
    import io
    r, rp = checked_json(report_ev, 'camera report')
    q = r.get('request', {})
    if (r.get('status') not in ('completed-camera-survey-awaiting-image-review','completed-contiguous-air-batch-awaiting-observation')
            or r.get('controllerPositionVerified') is not True or r.get('uncertainCompletion') is not False
            or r.get('error') or r.get('id') != q.get('id')
            or q.get('jvmStartMs') != session['jvmStartMs'] or q.get('liveConfigurationSha256') != session['liveConfigurationSha256']):
        raise ValueError('Successful same-session camera report required')
    finished = iso_ms(r.get('finishedAt'))
    if finished > now or now-finished > MAX_REPORT_AGE_MS:
        raise ValueError('Camera proof must be no more than 30 minutes old')
    snap = r.get('afterQuerySnapshot', {}); raw = source.axes(snap.get('raw'), 'camera raw')
    top = snap.get('nativePoses', {}).get('top', {})
    xy = finite_pair([top.get('x'),top.get('y')], 'camera XY')
    plane = finite_pair([top.get('z'),top.get('rotation')], 'camera plane')
    if [raw[k] for k in ('Z','A','B')] != session['fixedRawZAB'] or plane != session['topCameraZRotation']:
        raise ValueError('Camera proof Z/A/B or imaging plane changed')
    path = (Path(rp['path']).parent/r.get('afterImages',{}).get('top',{}).get('path','')).resolve(strict=True)
    if path.parent != Path(rp['path']).parent or str(path) != image_ev.get('path'):
        raise ValueError('Proof image must belong to camera report')
    data, ip = bound(path)
    if ip['sha256'] != image_ev.get('sha256'):
        raise ValueError('Proof image hash changed')
    with Image.open(io.BytesIO(data)) as im:
        size = list(im.size)
    return r, rp, ip, raw, xy, size


def verified_centering_xy(report, ref, fast_request, now):
    """Resolve a fast-route FID target from its original native CV evidence."""
    from PIL import Image
    import io
    center = fast_request.get('fiducialCenteringReport')
    if not isinstance(center, dict) or center.get('reference') != ref:
        raise ValueError(f'{ref} centered fast-camera route needs its hash-bound native centering report')
    native, native_prov = checked_json({'path': center.get('path'), 'sha256': center.get('sha256')}, 'native FID centering report')
    if (native_prov['path'] != center.get('path') or native.get('schema') != 1
            or native.get('scope') != 'native-current-pose-fiducial-vision'
            or native.get('status') != 'completed-native-fiducial-detection-awaiting-review'
            or native.get('requestId') != center.get('id') or native.get('reference') != ref
            or native.get('noMotion') is not True or native.get('noActuation') is not True
            or native.get('noVacuum') is not True or native.get('jobSaved') is not False
            or native.get('configurationSaved') is not False
            or native.get('physicalRegistrationEstablished') is not False):
        raise ValueError(f'{ref} native centering report is not a completed no-motion CV observation')
    finished = iso_ms(native.get('finishedAt'))
    if finished > now or now-finished > MAX_REPORT_AGE_MS or center.get('finishedAt') != native.get('finishedAt'):
        raise ValueError(f'{ref} native centering evidence is stale or has a changed timestamp')
    if (center.get('jvmStartMs') != fast_request.get('jvmStartMs')
            or center.get('liveConfigurationSha256') != fast_request.get('liveConfigurationSha256')):
        raise ValueError(f'{ref} native centering evidence belongs to another controller session')
    expected_zab = [fast_request.get('expectedRaw', {}).get(k) for k in ('Z', 'A', 'B')]
    if center.get('fixedRawZAB') != expected_zab or native.get('jvmStartMs') != center.get('jvmStartMs') or native.get('liveConfigurationBeforeSha256') != center.get('liveConfigurationSha256'):
        raise ValueError(f'{ref} native centering Z/A/B or configuration differs from fast-camera request')
    detection = native.get('nativeFiducialDetection', {})
    detected = finite_pair(detection.get('detectedMachineXYMm'), f'{ref} detected FID center')
    if detection.get('reference') != ref or finite_pair(center.get('detectedMachineXYMm'), f'{ref} request detected center') != detected:
        raise ValueError(f'{ref} centering target is not the native CV detected fiducial')
    location = native.get('expectedCameraLocationMm', {})
    if (finite_pair([location.get('x'), location.get('y')], f'{ref} centering camera location') !=
            finite_pair([native.get('nativePose', {}).get('cameraLocationMm', {}).get('x'), native.get('nativePose', {}).get('cameraLocationMm', {}).get('y')], f'{ref} centering terminal camera pose')):
        raise ValueError(f'{ref} centering image was not acquired at the reviewed native camera pose')
    request_ev = native.get('requestEvidence', {})
    request, _ = checked_json(request_ev, 'native FID request')
    if (request.get('scope') != 'native-current-pose-fiducial-vision-request'
            or request.get('id') != native.get('requestId') or request.get('reference') != ref
            or request.get('sourceBarrier') != native.get('sourceBarrier')):
        raise ValueError(f'{ref} native centering request/source barrier binding is invalid')
    barrier, _ = checked_json(native.get('sourceBarrier'), 'native FID source barrier')
    snap = native.get('sourceBarrierSnapshot', {})
    barrier_snap = barrier.get('afterQuerySnapshot', {})
    if (barrier.get('id') != native.get('sourceBarrierId')
            or barrier.get('status') != 'completed-read-only-position-barrier'
            or barrier.get('controllerPositionVerified') is not True
            or barrier.get('noMotionCommandSubmitted') is not True
            or barrier.get('uncertainCompletion') is not False
            or barrier.get('liveConfigurationSha256') != center.get('liveConfigurationSha256')
            or snap != barrier_snap
            or snap.get('raw') != snap.get('driver')
            or [snap.get('raw', {}).get(k) for k in ('Z','A','B')] != expected_zab):
        raise ValueError(f'{ref} native centering source barrier does not bind the unchanged controller pose')
    image = native.get('images', {}).get('raw', {})
    image_ev = center.get('image', {})
    if (image.get('path') != image_ev.get('path') or image.get('sha256') != image_ev.get('sha256')
            or type(image.get('width')) is not int or type(image.get('height')) is not int):
        raise ValueError(f'{ref} native centering image binding is malformed')
    img_path = Path(image['path']).resolve(strict=True)
    if img_path.parent != Path(native_prov['path']).parent:
        raise ValueError(f'{ref} native centering image must remain beside its report')
    img_data, img_prov = bound(img_path)
    if img_prov['sha256'] != image['sha256']:
        raise ValueError(f'{ref} native centering image hash changed')
    with Image.open(io.BytesIO(img_data)) as im:
        if list(im.size) != [image['width'], image['height']]:
            raise ValueError(f'{ref} native centering image dimensions changed')
    return detected


def fast_camera_source(report, ref, report_path, allow_fiducial_offset=False, now=None):
    """Validate a completed fast-camera route as a genuine fiducial sample.

    This is deliberately a second evidence adapter, not a status/scope rewrite:
    the original request, route, terminal report, frame, and all five axes stay
    hash-bound to their camera-inspection report.
    """
    q = report.get('request', {})
    snap0, snap1 = report.get('beforeQuerySnapshot', {}), report.get('afterQuerySnapshot', {})
    raw0, driver0 = exact_axes(snap0.get('raw'), 'fast-camera initial raw'), exact_axes(snap0.get('driver'), 'fast-camera initial driver')
    raw, driver = exact_axes(snap1.get('raw'), 'fast-camera terminal raw'), exact_axes(snap1.get('driver'), 'fast-camera terminal driver')
    fiducial = bool(re.fullmatch(r'FID[123]', ref))
    expected_mode = 'registered-fiducials' if fiducial else 'registered-references'
    if (report.get('scope') != FAST_CAMERA_SCOPE or report.get('status') != 'completed-camera-survey-awaiting-image-review'
            or q.get('scope') != FAST_CAMERA_SCOPE or q.get('mode') != expected_mode
            or report.get('id') != q.get('id') or report.get('motionSubmitted') is not True
            or report.get('controllerPositionVerified') is not True or report.get('nativeMotionCompletionReported') is not True
            or report.get('uncertainCompletion') is not False or report.get('error')
            or report.get('physicalAcceptanceEstablished') is not False or report.get('calibrationEstablished') is not False):
        raise ValueError(f'{ref} must be a successful fast-camera fiducial route, not a relabeled survey')
    if (type(q.get('jvmStartMs')) is not int or not isinstance(q.get('liveConfigurationSha256'), str)
            or len(q['liveConfigurationSha256']) != 64 or q.get('enabled') is not True
            or q.get('operatorReviewed') is not True or not isinstance(q.get('reviewedBy'), str) or not q['reviewedBy'].strip()
            or q.get('speedFraction') != 1 or q.get('speedOverPrecision') is not True
            or q.get('maxSegmentMm') != 10 or type(q.get('maxTotalTravelMm')) not in (int, float)
            or q['maxTotalTravelMm'] > 120 or q.get('completionScope') != 'Camera frames and XY position reports only; no paste, calibration, or placement acceptance.'):
        raise ValueError(f'{ref} fast-camera policy/session fields are incomplete')
    if q.get('references') != [ref] or len(q.get('targets', [])) != 1 or q['targets'][0].get('reference') != ref:
        raise ValueError(f'{ref} fast-camera report must target only its identified reference')
    target = q['targets'][0]
    if fiducial:
        if target.get('pads') != [] or q.get('fiducialSample') not in (None, 'base', 'xplus', 'yplus') or (not allow_fiducial_offset and q.get('fiducialSample') not in (None, 'base')):
            raise ValueError(f'{ref} fitted fiducial sample must be centered base evidence')
        if q.get('fiducialSample') in ('xplus', 'yplus') and not allow_fiducial_offset:
            raise ValueError(f'{ref} offset sample may not be used as a fitted fiducial')
        if q.get('fiducialCenteringReport') is not None:
            detected = verified_centering_xy(report, ref, q, now if now is not None else int(datetime.datetime.now(datetime.timezone.utc).timestamp()*1000))
            offset = {'base': [0.0, 0.0], 'xplus': [1.0, 0.0], 'yplus': [0.0, 1.0]}[q['fiducialSample']]
            if (target.get('sample') != q['fiducialSample'] or target.get('offsetXYMm') != offset
                    or target.get('pads') != [] or abs(target.get('x', math.inf)-(detected[0]+offset[0])) > 1e-6
                    or abs(target.get('y', math.inf)-(detected[1]+offset[1])) > 1e-6):
                raise ValueError(f'{ref} fast-camera target differs from its native detected center and named offset')
            target_xy = [target['x'], target['y']]
        else:
            target_xy = None
    elif q.get('targetMode') != 'pad2' or not isinstance(target.get('pads'), list) or len(target['pads']) != 2 or any(p.get('padId') != f'{ref}.{i+1}' for i,p in enumerate(target['pads'])):
        raise ValueError(f'{ref} held-out fast-camera report must target its registered pad2')
    if raw0 != driver0 or raw != driver:
        raise ValueError(f'{ref} fast-camera raw and driver axes differ')
    if (raw0 != q.get('expectedRaw') or driver0 != q.get('expectedDriver')
            or report.get('beforeReported') != raw0 or report.get('afterReported') != raw):
        raise ValueError(f'{ref} fast-camera M114/controller endpoints differ from its request')
    if [raw[k] for k in ('Z', 'A', 'B')] != [raw0[k] for k in ('Z', 'A', 'B')]:
        raise ValueError(f'{ref} fast-camera route changed Z/A/B')
    before_poses, after_poses = snap0.get('nativePoses'), snap1.get('nativePoses')
    if not isinstance(before_poses, dict) or set(before_poses) != {'N1', 'N2', 'top', 'bottom'} or q.get('expectedNativePoses') != before_poses:
        raise ValueError(f'{ref} fast-camera initial native poses differ from the request')
    dx, dy = raw['X'] - raw0['X'], raw['Y'] - raw0['Y']
    for name in ('N1', 'N2', 'top', 'bottom'):
        before, after = before_poses.get(name), after_poses.get(name) if isinstance(after_poses, dict) else None
        if not isinstance(before, dict) or not isinstance(after, dict):
            raise ValueError(f'{ref} fast-camera native pose {name} is missing')
        ex, ey = (before['x'], before['y']) if name == 'bottom' else (before['x'] + dx, before['y'] + dy)
        if (any(type(after.get(k)) not in (int, float) or not math.isfinite(after[k]) for k in ('x', 'y', 'z', 'rotation'))
                or abs(after['x'] - ex) > .02 or abs(after['y'] - ey) > .02
                or after['z'] != before['z'] or after['rotation'] != before['rotation']):
            raise ValueError(f'{ref} fast-camera end native pose {name} differs from XY-only route')
    route = q.get('routeSteps')
    if not isinstance(route, list) or not 1 <= len(route) <= 32:
        raise ValueError(f'{ref} fast-camera route must contain 1–32 verified XY steps')
    previous = raw0
    total = 0.0
    captures = []
    for i, step in enumerate(route):
        if (not isinstance(step, dict) or step.get('index') != i
                or any(type(step.get(k)) not in (int, float) or not math.isfinite(step[k]) for k in ('x', 'y', 'z', 'a', 'b'))
                or any(step[k] != previous[axis] for k, axis in (('z', 'Z'), ('a', 'A'), ('b', 'B')))
                or abs(step['x'] * 100 - round(step['x'] * 100)) > 1e-6
                or abs(step['y'] * 100 - round(step['y'] * 100)) > 1e-6):
            raise ValueError(f'{ref} fast-camera step {i} is not a report-grid XY-only move')
        distance = math.hypot(step['x'] - previous['X'], step['y'] - previous['Y'])
        if not 0 < distance <= 10.0001:
            raise ValueError(f'{ref} fast-camera step {i} exceeds the 10 mm XY bound')
        total += distance
        if not isinstance(step.get('captureReferences'), list):
            raise ValueError(f'{ref} fast-camera capture binding is malformed')
        captures.extend(step['captureReferences'])
        previous = {'X': step['x'], 'Y': step['y'], 'Z': step['z'], 'A': step['a'], 'B': step['b']}
    if total > 120.0001 or abs(total - q.get('plannedDistanceMm', math.inf)) > 1e-5:
        raise ValueError(f'{ref} fast-camera route distance does not match its bounded request')
    expected_target = target_xy if target_xy else [target.get('x', math.inf), target.get('y', math.inf)]
    if (captures != [ref] or [raw[k] for k in ('X', 'Y', 'Z', 'A', 'B')] != [previous[k] for k in ('X', 'Y', 'Z', 'A', 'B')]
            or abs(raw['X'] - expected_target[0]) > .0051 or abs(raw['Y'] - expected_target[1]) > .0051):
        raise ValueError(f'{ref} fast-camera endpoint does not capture its hash-bound fiducial target')
    verified = [t.get('status') for t in report.get('transitions', []) if isinstance(t, dict) and isinstance(t.get('status'), str)]
    if any(verified.count(f'route-step-{i}-verified') != 1 for i in range(len(route))):
        raise ValueError(f'{ref} fast-camera report lacks one verified transition per route step')
    frames = report.get('frames')
    if not isinstance(frames, list) or len(frames) != 1:
        raise ValueError(f'{ref} fast-camera report must contain exactly one identified frame')
    frame = frames[0]
    snap_top = snap1.get('nativePoses', {}).get('top', {})
    if (frame.get('reference') != ref or frame.get('rawAxes') != raw
            or frame.get('nativePose') != snap_top or frame.get('path') != report.get('afterImages', {}).get('top', {}).get('path')
            or type(frame.get('width')) is not int or type(frame.get('height')) is not int):
        raise ValueError(f'{ref} fast-camera image is not bound to its terminal pose/frame')
    image_path = (Path(report_path).parent / frame['path']).resolve(strict=True)
    if image_path.parent != Path(report_path).parent:
        raise ValueError(f'{ref} fast-camera frame must remain beside its report')
    return q['jvmStartMs'], q['liveConfigurationSha256'], raw, snap1.get('nativePoses', {})


def inverse(matrix):
    if not isinstance(matrix,list) or len(matrix)!=2:
        raise ValueError('Finite 2x2 Jacobian required')
    a,b=finite_pair(matrix[0],'Jacobian row');c,d=finite_pair(matrix[1],'Jacobian row')
    det=a*d-b*c
    if abs(det)<1e-9:
        raise ValueError('Degenerate image Jacobian')
    return [[d/det,-b/det],[-c/det,a/det]]


def matrix_product(a,b):
    return [[sum(a[i][k]*b[k][j] for k in (0,1)) for j in (0,1)] for i in (0,1)]


def reviewed_jacobian(ev, session, now):
    j, prov = checked_json(ev,'image Jacobian')
    if (j.get('schema')!=1 or j.get('scope')!='measured-top-camera-image-jacobian'
            or j.get('session')!={k:session[k] for k in ('jvmStartMs','liveConfigurationSha256')}
            or j.get('fixedRawZAB')!=session['fixedRawZAB'] or not isinstance(j.get('reviewedBy'),str) or not j['reviewedBy'].strip()
            or type(j.get('reviewedMs')) is not int or not 0<=now-j['reviewedMs']<=MAX_REPORT_AGE_MS):
        raise ValueError('Fresh explicitly reviewed same-session image Jacobian required')
    samples=j.get('sourceMeasurements')
    if not isinstance(samples,list) or len(samples)!=3:
        raise ValueError('Three measured Jacobian source images required')
    centers=[];positions=[];ids=set()
    for item in samples:
        r,_,_,raw,xy,size=camera_evidence(item['report'],item['image'],session,now)
        if r['id'] in ids or iso_ms(r['finishedAt'])>j['reviewedMs'] or finite_pair(item['rawXY'],'Jacobian raw XY') != [raw['X'],raw['Y']]:
            raise ValueError('Jacobian source identity/pose/review time mismatch')
        ids.add(r['id']);center=finite_pair(item['centerPixels'],'Jacobian observed center')
        if any(not 0<=center[k]<size[k] for k in (0,1)):
            raise ValueError('Jacobian center lies outside image')
        centers.append(center);positions.append(xy)
    displacement=lambda points:[[points[1][k]-points[0][k],points[2][k]-points[0][k]] for k in (0,1)]
    derived=matrix_product(displacement(centers),inverse(displacement(positions)))
    supplied=j.get('pixelShiftPerCameraMm');inverse(supplied)
    if any(abs(derived[i][k]-supplied[i][k])>1e-7 for i in (0,1) for k in (0,1)):
        raise ValueError('Jacobian differs from measured report/image displacements')
    return supplied,prov


def held_out_checks(request, result, now):
    checks=request['heldOutPadChecks'];session=result['session']
    if not isinstance(checks,list) or len(checks)!=3 or sorted(c.get('padId','') for c in checks)!=sorted(HELD_OUT_PADS):
        raise ValueError('Exactly R1.2, R16.1 and R40.1 held-out image checks required')
    jac,prov=reviewed_jacobian(request.get('imageJacobianEvidence'),session,now);inv=inverse(jac)
    targets={p['padId']:p['machineXYMm'] for p in result['resistorPadMachineXYTargets']};out=[]
    used={m['reportId'] for m in result['measurements'].values()}
    for c in checks:
        if c.get('padIdentityReviewed') is not True or c.get('centerMeasurementReviewed') is not True:
            raise ValueError('Explicit held-out pad identity/center review required')
        report_ev=dict(path=c['report'],sha256=c['reportSha256'])
        r,_=checked_json(report_ev,'pad report');image_path=str((Path(c['report']).parent/r['afterImages']['top']['path']).resolve(strict=True))
        r,rp,ip,raw,xy,size=camera_evidence(report_ev,dict(path=image_path,sha256=c['topImageSha256']),session,now)
        if r['id'] in used:
            raise ValueError('Held-out pads require distinct reports independent of fitted fiducials')
        used.add(r['id']);observed=finite_pair(c.get('observedCenterPixel'),'observed pad center')
        if any(not 0<=observed[k]<size[k] for k in (0,1)):
            raise ValueError('Observed pad center lies outside image')
        center=[(n-1)/2 for n in size];delta=[observed[k]-center[k] for k in (0,1)]
        measured=[xy[i]-sum(inv[i][k]*delta[k] for k in (0,1)) for i in (0,1)]
        px=math.hypot(*delta);mm=math.dist(measured,targets[c['padId']])
        if px>8 or mm>0.08:
            raise ValueError('Independent held-out pad exceeds 8 pixels or 0.08 mm')
        out.append(dict(padId=c['padId'],report=rp,image=ip,reportId=r['id'],finishedAt=r['finishedAt'],
                        padIdentityReviewed=True,centerMeasurementReviewed=True,observedCenterPixel=observed,imageSizePixels=size,
                        imageCenterPixel=center,cameraXYMm=xy,measuredPadXYMm=measured,predictedMachineXYMm=targets[c['padId']],
                        imageCenterErrorPx=px,residualMm=mm))
    return out,prov


def analyze(request, now_ms=None):
    if not isinstance(request, dict) or request.get('schema') != 1 or request.get('scope') != 'fresh-ftp-top-camera-fiducials':
        raise ValueError('Expected schema-1 fresh-ftp-top-camera-fiducials request')
    model = request.get('registrationModel', 'two-fiducial-similarity')
    if model not in ('two-fiducial-similarity', AFFINE_MODEL):
        raise ValueError('Unsupported registration model')
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
        if report.get('request', {}).get('scope') == FAST_CAMERA_SCOPE:
            source_jvm, source_config, raw, poses = fast_camera_source(report, ref, report_path, now=now)
        else:
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

    if model == AFFINE_MODEL:
        transform = affine_from_three([design[r] for r in REFERENCES], [samples[r]['measuredTopCameraXYMm'] for r in REFERENCES])
        pred3, measured3, residual3 = None, None, None
    else:
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
    result = {'schema': 1, 'scope': 'offline-fresh-ftp-two-fiducial-transform-with-third-point-check',
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

    if model == AFFINE_MODEL:
        del result['transformFromFID1FID2'], result['independentFID3Check']
        result.update(scope='offline-fresh-ftp-three-fiducial-affine-candidate', transformFromThreeFiducials=transform,
                      fittedFiducials=list(REFERENCES), independentHeldOutPadChecks=[],
                      acceptance=dict(singularValueRange=[MIN_SCALE,MAX_SCALE],axisSkewDegreesMaximum=MAX_AFFINE_SKEW_DEGREES,
                                      fiducialCenterErrorPxMaximum=2.0,heldOutPadErrorPxMaximum=8.0,heldOutPadResidualMmMaximum=0.08,passed=False))
        result['limitations'][1] = 'All three fiducials are fitted; only separate held-out pad images can independently validate this model.'
        if request.get('heldOutPadChecks') is not None:
            checks, jacobian = held_out_checks(request, result, now)
            result.update(scope='offline-fresh-ftp-three-fiducial-affine-with-held-out-pad-checks', independentHeldOutPadChecks=checks,
                          imageJacobianEvidence=jacobian)
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
