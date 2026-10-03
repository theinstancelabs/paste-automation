#!/usr/bin/env python3
"""Build a local operator-console profile from accepted machine evidence; no motion."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def build(registration, barrier, tip, surface, rod, output, job, work_z=58.2):
    if type(work_z) not in (float,int) or not math.isfinite(work_z) or not 55 <= work_z <= 60 or abs(work_z/.05-round(work_z/.05))>1e-8:
        raise ValueError("Work Z must be finite 55..60 mm on the 0.05 mm grid")
    paths = [Path(p).resolve() for p in (registration, barrier, tip, surface, rod)]
    reg, state, offset, plane_source, travel = [json.loads(p.read_text()) for p in paths]
    if reg.get('scope') != 'offline-fresh-ftp-three-fiducial-affine-with-held-out-pad-checks' or reg.get('acceptance', {}).get('passed') is not True:
        raise ValueError('An accepted registration is required')
    def bound(e):
        path = Path(e['path']).resolve(strict=True)
        if hashlib.sha256(path.read_bytes()).hexdigest() != e['sha256']:
            raise ValueError('Bound source changed: '+str(path))
        paths.append(path)
        return path
    bound(reg['board'])
    targets = reg['resistorPadMachineXYTargets']
    expected_ids = {f'R{ref}.{pad}' for ref in range(1, 41) for pad in (1, 2)}
    if len(targets) != 80 or {t['padId'] for t in targets} != expected_ids:
        raise ValueError('Exactly 80 unique FTP resistor pad targets required')
    if not state.get('controllerPositionVerified') or state.get('uncertainCompletion'):
        raise ValueError('A certain verified controller position is required')
    snap = state['afterQuerySnapshot']
    raw = snap['raw']
    if raw != snap['driver']:
        raise ValueError('Native and driver coordinates differ')
    session = reg['session']
    if session['jvmStartMs'] != state['request']['jvmStartMs'] or session['liveConfigurationSha256'] != state['liveConfigurationSha256']:
        raise ValueError('Registration and live controller must share JVM/configuration')
    if offset.get('jvmStartMs') != session['jvmStartMs'] or offset.get('liveConfigurationSha256') != session['liveConfigurationSha256'] or not offset.get('reviewedBy') or offset.get('provenance') != 'commissioning-provisional':
        raise ValueError('Reviewed same-session installed tip offset required')
    bound(offset['basisEvidence'])
    if plane_source.get('liveConfigurationSha256') != session['liveConfigurationSha256'] or not plane_source.get('reviewedBy') or plane_source.get('provenance') != 'commissioning-provisional' or plane_source.get('surface', {}).get('gapUncertaintyMm') != .3:
        raise ValueError('Reviewed retained provisional surface with 0.30 mm uncertainty required')
    if travel.get('scope') != 'operator-measured-rod-travel-assessment' or travel.get('reportedApproximateExposureMm') != 41 or travel.get('engineeringAllowanceMm') != 10 or not travel.get('reviewedBy') or travel.get('grossLedgerReset') is not False:
        raise ValueError('Reviewed approximate rod measurement and retained ledger required')
    bound(travel['measurementEvidence'])
    if abs(travel['planningRemainingMm']-(41-travel['cadNearBottomExposureMm']-10)) > 1e-6 or travel['planningRemainingMm'] < 1000*travel['mmPerMotorDegreeNominal']:
        raise ValueError('Remaining travel calculation or 1000-degree planning allowance invalid')
    source = Path(plane_source['basisEvidence']['path'])
    if hashlib.sha256(source.read_bytes()).hexdigest() != plane_source['basisEvidence']['sha256']:
        raise ValueError('Surface source hash changed')
    plane = json.loads(source.read_text())['newPlaneCoefficients']
    paths.append(source)
    job_path = Path(job).resolve(strict=True)
    paths.append(job_path)
    safe_z, travel_z = 32.25, 53.45
    pads = {}
    points = [[raw['X'], raw['Y']]]
    dx, dy = offset['cameraMinusTipXYMm']
    for target in reg['resistorPadMachineXYTargets']:
        ref, pad = target['padId'].split('.')
        x, y = target['machineXYMm']
        gap = 64.25 - work_z - (plane['a'] * x + plane['b'] * y + plane['c'])
        if gap - .3 < .1 - 1e-9:
            raise ValueError('Selected work Z violates provisional clearance at '+target['padId'])
        camera, tip_xy = [round(x, 2), round(y, 2)], [round(x-dx, 2), round(y-dy, 2)]
        pads.setdefault(ref, {})[pad] = dict(cameraXY=camera, tipXY=tip_xy, gapAtWorkZ=gap)
        points.extend([camera, tip_xy])
    bounds = {'X': {'min': min(p[0] for p in points)-0.1, 'max': max(p[0] for p in points)+0.1},
              'Y': {'min': min(p[1] for p in points)-0.1, 'max': max(p[1] for p in points)+0.1},
              'Z': {'min': safe_z, 'max': work_z},
              'A': {'min': raw['A'], 'max': raw['A']},
              'B': {'min': raw['B']-1000, 'max': raw['B']+1000}}
    head_bounds = {}
    for head in ('N1', 'N2'):
        pose = snap['nativePoses'][head]
        h = {}
        for axis in ('X', 'Y'):
            delta = pose[axis.lower()] - raw[axis]
            h['min'+axis] = bounds[axis]['min'] + delta - .001
            h['max'+axis] = bounds[axis]['max'] + delta + .001
        zs = [pose['z'] + (z-raw['Z'])*(1 if head == 'N1' else -1) for z in (safe_z, work_z)]
        h.update(minZ=min(zs)-.001, maxZ=max(zs)+.001)
        head_bounds[head] = h
    evidence = [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]
    identity = hashlib.sha256(json.dumps({'evidence': evidence, 'workZ': work_z}, sort_keys=True).encode()).hexdigest()
    profile = dict(schema=1, id=identity, name='FTP demo resistor pads', pads=pads,
                   jvmStartMs=session['jvmStartMs'], liveConfigurationSha256=session['liveConfigurationSha256'],
                   sessionId=offset['sessionId'], expectedRaw=raw, expectedDriver=snap['driver'],
                   nativePoses=snap['nativePoses'], expectedNativePoses=snap['nativePoses'],
                   safeZ=safe_z, travelZ=travel_z, xyClearanceRawZ=safe_z, workZ=work_z,
                   gapUncertaintyMm=.3, rawBounds=bounds, headClearanceBounds=head_bounds,
                   cameraMinusTipXYMm=[dx,dy], sourceEvidence=evidence,
                   rodBudget=dict(baselineGrossDegrees=travel['lastVerifiedGrossDegrees'], baselineB=travel['lastVerifiedB'],
                                  maximumAdditionalGrossDegrees=1000),
                   boardEvidence=reg['board'], inspectionJob=str(job_path), operatorSupervised=True, precisionCalibrated=False,
                   notes='Human operator confirms unchanged board and clearance when arming. Saved provisional surface/offset retained. No automatic home or actuation.')
    if abs(raw['B'] - travel['lastVerifiedB']) > .001:
        raise ValueError('Rod assessment baseline B does not match current controller')
    out = Path(output); out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise ValueError('Profile already exists; retain it and choose a new output or archive it explicitly')
    out.write_text(json.dumps(profile, indent=2)+'\n')
    return profile


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('registration', 'barrier', 'tip', 'surface', 'rod', 'output', 'job'):
        p.add_argument('--'+name, required=True)
    p.add_argument('--work-z', type=float, default=58.2, help='Explicit measured-profile maximum work Z, 55..60 mm on 0.05 mm grid; does not move hardware')
    a = p.parse_args()
    q = build(**vars(a))
    print(json.dumps({'profile': a.output, 'id': q['id'], 'resistors': len(q['pads']), 'motionDispatched': False}))
