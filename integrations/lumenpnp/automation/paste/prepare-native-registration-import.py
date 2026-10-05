#!/usr/bin/env python3
"""Stage a reviewed native fiducial transform as derived alignment references.

Preview only: writes a new proposed sidecar and manifest; never edits the live
profile, sidecar, ledger, OpenPnP configuration, or job.
"""
import argparse
import copy
import datetime
import hashlib
import json
import math
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / 'automation/paste/operator-console-policy.cjs'
NATIVE_SIMILARITY_SCOPE = 'offline-native-fresh-ftp-two-fiducial-transform-with-third-point-check'
NATIVE_AFFINE_SCOPES = {
    'offline-native-fresh-ftp-three-fiducial-affine-with-held-out-pad-checks',
    'offline-fresh-ftp-three-fiducial-affine-with-held-out-pad-checks',
}
DERIVED = 'derived component centers from fresh three-fiducial registration, not direct pad observations'
REFS = ('R1', 'R16', 'R40')
NATIVE_JOB = ROOT / 'automation/jobs/ftp-20260924.job.xml'
NATIVE_DETECTOR = ROOT / 'automation/scripts/Read_Paste_Fiducial_Vision.js'
FTP_BOARD = ROOT / 'pnp/pcb/ftp/ftp.kicad_pcb'


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def evidence(path):
    p = Path(path).resolve(strict=True)
    return {'path': str(p), 'sha256': digest(p)}


def verify_tip_xy_correction_evidence(sidecar):
    correction = sidecar.get('tipXYCorrection')
    if correction is None:
        return
    item = correction.get('evidence') if isinstance(correction, dict) else None
    if not isinstance(item, dict) or not isinstance(item.get('path'), str):
        raise ValueError('Tip XY correction evidence path missing')
    path = Path(item['path'])
    if not path.is_file() or digest(path) != item.get('sha256'):
        raise ValueError('Tip XY correction evidence changed')


def finite_pair(value, label):
    if (not isinstance(value, list) or len(value) != 2
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise ValueError(label + ' must be a finite XY pair')
    return [float(value[0]), float(value[1])]


def load_targets(reg):
    expected = {f'R{i}.{pad}' for i in range(1, 41) for pad in ('1', '2')}
    targets = reg.get('resistorPadMachineXYTargets')
    if not isinstance(targets, list) or len(targets) != 80:
        raise ValueError('Registration must contain exactly 80 resistor pad targets')
    out = {}
    for target in targets:
        if not isinstance(target, dict) or target.get('padId') in out:
            raise ValueError('Pad targets must have unique pad IDs')
        out[target['padId']] = finite_pair(target.get('machineXYMm'), target.get('padId', 'target'))
    if set(out) != expected:
        raise ValueError('Registration must cover exactly R1..R40 pads 1 and 2')
    return out


def validate_candidate(reg):
    scope = reg.get('scope')
    if (reg.get('schema') != 1 or scope not in ({NATIVE_SIMILARITY_SCOPE} | NATIVE_AFFINE_SCOPES)
            or reg.get('acceptance', {}).get('passed') is not True
            or reg.get('physicalRegistrationEstablished') is not False
            or reg.get('executionReady') is not False
            or reg.get('motionDispatched') is not False
            or reg.get('machineConfigurationChanged') is not False
            or reg.get('jobChanged') is not False):
        raise ValueError('Accepted, offline-only native fiducial candidate required')
    session = reg.get('session') or {}
    if (type(session.get('jvmStartMs')) not in (int, float)
            or not isinstance(session.get('liveConfigurationSha256'), str)
            or len(session['liveConfigurationSha256']) != 64):
        raise ValueError('Registration session identity required')
    for ref in (reg.get('board'), reg.get('parser')):
        if (not isinstance(ref, dict) or not isinstance(ref.get('path'), str)
                or digest(ref['path']) != ref.get('sha256')):
            raise ValueError('Registration board/parser source hash changed')
    if Path(reg['parser']['path']).resolve(strict=True) != (ROOT / 'automation/paste/pads/extract_ftp_pads.py').resolve(strict=True):
        raise ValueError('Registration must use the current canonical FTP parser')
    native = reg.get('nativeSource') or {}
    if native.get('jobPath') and Path(native['jobPath']).resolve() != NATIVE_JOB.resolve():
        raise ValueError('Native fiducial candidate must use the reviewed saved-pattern detector job')
    sources = native.get('reports')
    if not isinstance(sources, list) or len(sources) != 3:
        sources = [((reg.get('measurements') or {}).get(ref) or {}).get('nativeReport')
                   or ((reg.get('measurements') or {}).get(ref) or {}).get('report')
                   for ref in ('FID1', 'FID2', 'FID3')]
    if any(not isinstance(source, dict) for source in sources) or len(sources) != 3:
        raise ValueError('Three hash-bound native source reports required')
    for source in sources + native.get('sourceBarriers', []):
        if not isinstance(source, dict) or digest(source.get('path', '')) != source.get('sha256'):
            raise ValueError('Native report/barrier source hash changed')
    for ref, source in zip(('FID1', 'FID2', 'FID3'), sources):
        report = read(source['path'])
        measurement = (reg.get('measurements') or {}).get(ref) or {}
        if (report.get('scope') != 'native-current-pose-fiducial-vision'
                or report.get('status') != 'completed-native-fiducial-detection-awaiting-review'
                or report.get('jobPath') != str(NATIVE_JOB)
                or report.get('requestId') != measurement.get('reportId')
                or report.get('finishedAt') != measurement.get('finishedAt')):
            raise ValueError(f'{ref} must bind its fresh native report to the reviewed detector job')
    if not NATIVE_JOB.is_file() or not NATIVE_DETECTOR.is_file():
        raise ValueError('Reviewed native detector job/script must remain available')
    if scope in NATIVE_AFFINE_SCOPES:
        held = reg.get('independentHeldOutPadChecks')
        if not isinstance(held, list) or not held:
            raise ValueError('Native affine candidate requires independent held-out pad checks')
        if any(item.get('padIdentityReviewed') is not True or item.get('centerMeasurementReviewed') is not True
               for item in held):
            raise ValueError('Every native affine held-out pad must be reviewed')
    measurements = reg.get('measurements') or {}
    now = datetime.datetime.now(datetime.timezone.utc)
    if set(measurements) != {'FID1', 'FID2', 'FID3'}:
        raise ValueError('Three fresh native fiducial measurements required')
    for measurement in measurements.values():
        try:
            finished = datetime.datetime.fromisoformat(measurement['finishedAt'].replace('Z', '+00:00'))
        except (KeyError, TypeError, ValueError):
            raise ValueError('Native fiducial completion timestamps are required')
        if finished.tzinfo is None or finished > now or now - finished > datetime.timedelta(minutes=30):
            raise ValueError('Native fiducial registration must be no more than 30 minutes old')
    return load_targets(reg)


def job_board_inventory(job_path, require_disabled):
    tree = ET.parse(job_path)
    job = tree.getroot()
    locations = job.findall(".//object[@class='org.openpnp.model.BoardLocation']")
    if len(locations) != 1:
        raise ValueError('Inspection/source job must contain exactly one board location')
    loc = locations[0]
    if loc.get('side') != 'Top':
        raise ValueError('Only the FTP top-side board is supported')
    board_path = Path(loc.get('file-name', '')).resolve(strict=True)
    board = ET.parse(board_path).getroot()
    placements = board.findall('./placements/placement')
    expected = {f'{prefix}{i}' for prefix, count in (('R', 40), ('D', 40)) for i in range(1, count + 1)} | {'FID1', 'FID2', 'FID3'}
    if len(placements) != 83 or {p.get('id') for p in placements} != expected:
        raise ValueError('Inspection/source board must contain exact R1..R40, D1..D40, and FID1..FID3 inventory')
    inventory = {}
    for placement in placements:
        if require_disabled and placement.get('enabled') != 'false':
            raise ValueError('Every placement in the profile inspection board must remain disabled')
        inventory[placement.get('id')] = (placement.get('part-id'), placement.get('side'))
    return inventory, evidence(board_path), loc.get('side')


def prepare(registration, profile_path, sidecar_path, output):
    reg_path = Path(registration).resolve(strict=True)
    profile_path = Path(profile_path).resolve(strict=True)
    sidecar_path = Path(sidecar_path).resolve(strict=True)
    out = Path(output).resolve()
    if out.exists():
        raise ValueError('Output directory must be new; staging never overwrites')
    reg = read(reg_path)
    targets = validate_candidate(reg)
    profile = read(profile_path)
    sidecar = read(sidecar_path)
    session = reg['session']
    if (profile.get('jvmStartMs') != session['jvmStartMs']
            or profile.get('liveConfigurationSha256') != session['liveConfigurationSha256']
            or sidecar.get('profileId') != profile.get('id')
            or sidecar.get('sessionId') != profile.get('sessionId')
            or sidecar.get('jvmStartMs') != profile.get('jvmStartMs')
            or sidecar.get('configurationSha256') != profile.get('liveConfigurationSha256')):
        raise ValueError('Registration, current profile, and calibration sidecar identity must match')
    if ((sidecar.get('zApplied') or sidecar.get('needleTouchPlane') or sidecar.get('needleTouchMeasurement'))
            and not (sidecar.get('boardTouchReference') or sidecar.get('coplanarTouchReference'))):
        raise ValueError('Active height calibration is tied to the prior XY frame; retain a board datum or recalibrate height')
    if set(profile.get('pads', {})) != {f'R{i}' for i in range(1, 41)} | {f'D{i}' for i in range(1, 41)}:
        raise ValueError('Current profile must contain exact R1..R40 and D1..D40 pads')
    if not isinstance(profile.get('cameraMinusTipXYMm'), list) or len(profile['cameraMinusTipXYMm']) != 2:
        raise ValueError('Current measured camera-minus-tip vector required')
    # The native candidate must refer to this exact board source.
    board_path = FTP_BOARD
    if Path(reg['board']['path']).resolve(strict=True) != board_path.resolve(strict=True):
        raise ValueError('Registration must use the canonical FTP board')
    board_evidence = profile.get('boardEvidence') or {}
    if (Path(board_evidence.get('path', '')).resolve() != board_path.resolve()
            or board_evidence.get('sha256') != reg['board']['sha256']):
        raise ValueError('Current profile and native registration must bind the same board hash')
    job_path = profile.get('inspectionJob')
    if job_path:
        job_evidence = next((e for e in profile.get('sourceEvidence', []) if e.get('path') == job_path), None)
        if not job_evidence or digest(job_path) != job_evidence.get('sha256'):
            raise ValueError('Current inspection job is missing or differs from its profile-bound hash')
        inspection_inventory, inspection_board_ref, inspection_side = job_board_inventory(job_path, True)
        native_inventory, native_board_ref, _ = job_board_inventory(NATIVE_JOB, False)
        if inspection_inventory != native_inventory or inspection_side != 'Top':
            raise ValueError('Current inspection job board inventory differs from native detector FTP board')
    else:
        raise ValueError('Current profile must bind its non-placeable inspection job')
    current_pad_ids = {f'{ref}.{pad}' for ref in profile['pads'] if ref.startswith('R') for pad in ('1', '2')}
    if current_pad_ids != {f'R{i}.{pad}' for i in range(1, 41) for pad in ('1', '2')}:
        raise ValueError('Current profile resistor pad coverage is incomplete')

    samples = []
    for ref in REFS:
        pads = profile['pads'][ref]
        new_center = [(targets[ref + '.1'][i] + targets[ref + '.2'][i]) / 2 for i in (0, 1)]
        samples.append({'ref': ref, 'cameraXY': new_center, 'provenance': DERIVED})

    payload = json.dumps({'profile': profile, 'samples': samples})
    script = ("const p=require(process.argv[1]),x=JSON.parse(require('fs').readFileSync(0,'utf8'));"
              "const f=p.fitAlignment(x.samples,x.profile);p.validateProfile(f.profile);"
              "process.stdout.write(JSON.stringify({profile:f.profile,transform:f.transform,fitNote:f.fitNote}));")
    result = subprocess.run(['node', '-e', script, str(POLICY)], input=payload, text=True,
                            check=False, capture_output=True)
    if result.returncode:
        raise ValueError('Existing alignment policy rejected import: ' + result.stderr.strip())
    fitted = json.loads(result.stdout)
    proposed_profile = fitted['profile']
    maximum_error = 0.0
    for pad_id, target in targets.items():
        ref, pad = pad_id.split('.')
        actual = proposed_profile['pads'][ref][pad]['cameraXY']
        err = math.dist(actual, target)
        maximum_error = max(maximum_error, err)
        if err > 0.03 + 1e-9:
            raise ValueError(f'Existing affine alignment does not reproduce {pad_id} within 0.03 mm')
        tip = proposed_profile['pads'][ref][pad]['tipXY']
        expected_tip = [actual[i] - float(profile['cameraMinusTipXYMm'][i]) for i in (0, 1)]
        if any(abs(tip[i] - expected_tip[i]) > 0.011 for i in (0, 1)):
            raise ValueError(f'Current camera-minus-tip vector was not preserved at {pad_id}')
    xy_points = []
    for refs in proposed_profile['pads'].values():
        for pad in refs.values():
            xy_points.extend((finite_pair(pad['cameraXY'], 'fitted camera target'),
                              finite_pair(pad['tipXY'], 'fitted tip target')))
    fit_bounds = {
        'X': {'min': min(p[0] for p in xy_points), 'max': max(p[0] for p in xy_points),
              'profileMin': profile['rawBounds']['X']['min'], 'profileMax': profile['rawBounds']['X']['max']},
        'Y': {'min': min(p[1] for p in xy_points), 'max': max(p[1] for p in xy_points),
              'profileMin': profile['rawBounds']['Y']['min'], 'profileMax': profile['rawBounds']['Y']['max']},
    }

    proposed = copy.deepcopy(sidecar)
    proposed['alignmentSamples'] = samples
    proposed['alignmentApplied'] = True
    proposed['zApplied'] = bool(sidecar.get('boardTouchReference') or sidecar.get('coplanarTouchReference'))
    proposed['transform'] = fitted['transform']
    proposed['fitNote'] = 'Three derived component-center references from accepted native fiducial registration; not direct pad observations; all 80 target centers checked within 0.03 mm.'
    proposed['alignmentImportProvenance'] = {
        'mode': 'native-fiducial-derived-center-import',
        'registration': evidence(reg_path), 'basis': DERIVED,
        'derivedReferenceIds': list(REFS),
        'board': reg['board'], 'parser': reg['parser'],
        'nativeDetectorScript': evidence(NATIVE_DETECTOR),
        'nativePatternJob': evidence(NATIVE_JOB),
        'profileInspectionJob': evidence(job_path),
        'profileInspectionBoard': inspection_board_ref,
        'nativePatternBoard': native_board_ref,
        'profileId': profile['id'], 'sessionId': profile['sessionId'],
        'maximumPadTargetErrorMm': maximum_error,
    }
    # Check ordinary sidecar identity and invariants byte-for-byte at the data level.
    for key in ('profileId', 'sessionId', 'jvmStartMs', 'configurationSha256'):
        if proposed.get(key) != sidecar.get(key):
            raise ValueError('Importer changed sidecar identity')
    for key in ('boardTouchReference', 'coplanarTouchReference', 'needleTouchPlane',
                'needleTouchMeasurement', 'ztouchSamples', 'zSamples', 'vacuumReference'):
        if proposed.get(key) != sidecar.get(key):
            raise ValueError('Importer changed existing height/calibration lineage: ' + key)
    verify_tip_xy_correction_evidence(proposed)
    policy_check = ("const p=require(process.argv[1]),x=JSON.parse(require('fs').readFileSync(0,'utf8'));"
                    "const q=p.withCalibration(x.profile,x.sidecar);p.validateProfile(q);")
    checked = subprocess.run(['node', '-e', policy_check, str(POLICY)],
                             input=json.dumps({'sidecar': proposed, 'profile': profile}), text=True,
                             check=False, capture_output=True)
    if checked.returncode:
        raise ValueError('Alignment import metadata rejected by existing policy: ' + checked.stderr.strip())

    out.mkdir(parents=True)
    (out / 'calibration-sidecar.json').write_text(json.dumps(proposed, indent=2) + '\n')
    manifest = {
        'mode': 'preview-only; sidecar is staged and not installed',
        'registration': evidence(reg_path), 'sourceProfile': evidence(profile_path),
        'sourceSidecar': evidence(sidecar_path), 'profileId': profile['id'],
        'sessionId': profile['sessionId'], 'ledgerOrProfileMutation': False,
        'motionDispatched': False, 'physicalRegistrationClaimed': False,
        'alignmentSampleProvenance': DERIVED, 'derivedReferenceIds': list(REFS),
        'padTargetCount': len(targets), 'maximumPadTargetErrorMm': maximum_error,
        'allFittedProfileTargetsWithinRawBounds': True, 'fittedCameraAndTipBoundsMm': fit_bounds,
        'preservedCameraMinusTipXYMm': profile['cameraMinusTipXYMm'],
        'nativeDetectorScript': evidence(NATIVE_DETECTOR),
        'nativePatternJob': evidence(NATIVE_JOB),
        'profileInspectionBoard': inspection_board_ref,
        'stagedSidecar': evidence(out / 'calibration-sidecar.json'),
    }
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--registration', required=True, help='reviewed accepted native fiducial candidate JSON')
    p.add_argument('--current-profile', default=str(ROOT / 'automation/plans/paste-operator-profile.json'))
    p.add_argument('--sidecar', help='current session/profile calibration sidecar; derived by default')
    p.add_argument('--output', required=True, help='new preview staging directory; must not exist')
    a = p.parse_args()
    profile = read(a.current_profile)
    sidecar = a.sidecar or str(ROOT / f"automation/evidence/operator-paste-runs/{profile['sessionId']}/calibration-{profile['id']}.json")
    print(json.dumps(prepare(a.registration, a.current_profile, sidecar, a.output), indent=2))


if __name__ == '__main__':
    main()
