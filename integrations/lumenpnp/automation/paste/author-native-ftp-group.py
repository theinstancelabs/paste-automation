#!/usr/bin/env python3
"""Author one reviewed four-pair FTP group from explicit fresh evidence.

This is an offline authorer: it does not capture images, read the machine, or
submit motion. Supply a fresh read-only barrier and fresh images from the
existing reviewed OpenPnP workflow. The checked-in author-conditioned-ftp-
eight-pad.py and preparer perform the remaining source and route checks.
"""
import argparse
import datetime
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'automation/evidence/small-dot-commissioning-20260930'
FTP = EVIDENCE / 'ftp-oct01'
NATIVE_RESUME = FTP / 'native-resume'
TEMPLATE = EVIDENCE / 'contiguous-coupon/travel-budget-review/cap-11800-reviewed-iso/template-11800.json'
BASE_TARGET = FTP / 'r37-dose6/run1/targets.json'
BEFORE_REPORTS = NATIVE_RESUME / 'before-reports.json'
EXAMPLE = ROOT / 'automation/paste/author-conditioned-ftp-eight-pad.inputs.example.json'
SCRAP_EXPERIMENT = EVIDENCE / 'contiguous-coupon/ftp-transfer-1/experiment.json'
SCRAP_PROFILE = EVIDENCE / 'contiguous-coupon/ftp-transfer-1/profile.json'
TIP_OFFSET = FTP / 'r40-first/tip-selection.json'

class InputError(ValueError):
    pass

def require(ok, message):
    if not ok:
        raise InputError(message)

def read_json(path):
    return json.loads(Path(path).read_text())

def evidence(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def finite(value):
    return type(value) in (int, float) and math.isfinite(value)

def authored_values(example, reviewer, review, raw, refs, prime_xy, dummy_xy, work_z, reviewed_ms):
    """Compose the fixed route fields only after explicit review-basis checks."""
    require(len(reviewer.strip()) >= 2 and len(review.strip()) >= 60,
            'Reviewer name and substantive --review basis are required')
    require(len(refs) == 4 and len(set(refs)) == 4
            and all(ref in {f'R{i}' for i in range(1, 41)} for ref in refs),
            'Exactly four distinct resistor references are required')
    controls = ('R1.2', 'R16.1', 'R40.1')
    required = list(controls) + [pad for ref in refs for pad in (ref + '.1', ref + '.2')] + [
        'boardCleaned', 'padsAvailable', 'boardUnmovedSinceRegistration',
        'bothHeadsClearanceReviewed', 'clearTransitCorridorReviewed',
        'scrapPrimeAndWipeReviewed', 'tipReviewedNoLongStrand']
    require(all(token in review for token in required),
            '--review must explicitly cover selected/control pad identities and all required physical attestations')
    require(isinstance(raw, dict) and set(raw) == set('XYZAB')
            and all(finite(v) for v in raw.values()), 'Complete finite raw pose required')
    require(all(finite(v) for v in (*prime_xy, *dummy_xy)), 'Prime and dummy XY must be finite')
    require(abs(raw['X'] - prime_xy[0]) <= .005 and abs(raw['Y'] - prime_xy[1]) <= .005
            and abs(raw['Z'] - 58.45) <= .005 and raw['A'] == 720,
            'Barrier must match prime XY, scrap Z=58.45 and A=720')
    require(finite(work_z) and 58 <= work_z <= 58.5, 'Reviewed work Z outside commissioning range')
    q = dict(example)
    q.update(reviewedBy=reviewer.strip(), reviewedMs=reviewed_ms, startRaw=raw,
             doseDegrees=6, retractDegrees=3, dwellMilliseconds=2000,
             conditioningDoseDegrees=6, conditioningRestoreDegrees=0,
             conditioningFinalWipeMm=0, surfaceRawZ=work_z, xyClearanceRawZ=53.45,
             scrapTargetsXY=[{'X': round(prime_xy[0] + 1.5, 2), 'Y': prime_xy[1]},
                             {'X': dummy_xy[0], 'Y': dummy_xy[1]}],
             reviewBasis=review.strip(),
             profileBasis='Supplied provisional group surface review; no precision contact calibration is claimed.')
    # All seven authorer attestations are asserted only after --review explicitly
    # names each gate and the selected/control pad identities above.
    q['attestations'] = {key: True for key in q['attestations']}
    return q

def find_ledger(session_id):
    matches = []
    for path in (ROOT / 'automation/evidence').glob('paste-commissioning-stroke-session-*/ledger.json'):
        try:
            if read_json(path).get('sessionId') == session_id:
                matches.append(path)
        except (OSError, ValueError):
            continue
    require(len(matches) == 1, 'Expected exactly one signed-B ledger for template session')
    return matches[0]

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True, help='new one-level folder beneath native-resume')
    p.add_argument('--barrier', required=True, help='fresh completed read-only barrier JSON')
    p.add_argument('--stationary-image', required=True, help='fresh stationary image captured at the reviewed start pose')
    p.add_argument('--registration', required=True)
    p.add_argument('--reports', required=True, help='JSON map of selected pair and optional control pad IDs to report paths')
    p.add_argument('--refs', required=True, help='four refs such as R40,R39,R38,R37')
    p.add_argument('--tip', required=True, help='fresh reviewed clean-tip image')
    p.add_argument('--prime-x', required=True, type=float)
    p.add_argument('--prime-y', required=True, type=float)
    p.add_argument('--dummy-x', required=True, type=float)
    p.add_argument('--dummy-y', required=True, type=float)
    p.add_argument('--surface', required=True, help='reviewed provisional surface JSON')
    p.add_argument('--previous-report', required=True, help='latest wet report JSON')
    p.add_argument('--review', required=True, help="explicit review basis, formatted 'Reviewer: ...'")
    args = p.parse_args(argv)
    outname = Path(args.output)
    require(not outname.is_absolute() and len(outname.parts) == 1 and outname.name not in ('', '.', '..'),
            '--output must be a single new folder name beneath native-resume')
    outdir = NATIVE_RESUME / outname
    require(not outdir.exists(), 'Refusing to reuse an existing output folder')
    require(':' in args.review, '--review must start with reviewer name and colon')
    reviewer, review = args.review.split(':', 1)
    reviewer, review = reviewer.strip(), review.strip()
    refs = [value.strip().upper() for value in args.refs.split(',')]
    pair_paths = json.loads(Path(args.reports).read_text())
    require(isinstance(pair_paths, dict), '--reports must be a JSON object')
    control_reports = read_json(BEFORE_REPORTS)
    report_map = dict(control_reports)
    report_map.update(pair_paths)
    pair_keys = {ref: next((key for key in (ref, ref + '.1', ref + '.2') if key in report_map), None) for ref in refs}
    require(all(pair_keys.values()), '--reports must include a report for each selected pair')
    controls = ('R1.2', 'R16.1', 'R40.1')
    require(all(key in report_map for key in controls), 'Control reports R1.2/R16.1/R40.1 are required')

    barrier_path = Path(args.barrier).resolve(strict=True)
    barrier = read_json(barrier_path)
    snap = barrier.get('afterQuerySnapshot') or {}
    raw = snap.get('raw')
    require(barrier.get('status') == 'completed-read-only-position-barrier'
            and barrier.get('controllerPositionVerified') is True
            and barrier.get('uncertainCompletion') is False
            and barrier.get('noMotionCommandSubmitted') is True,
            'Successful no-motion read-only barrier required')
    template = read_json(TEMPLATE)
    require(barrier.get('request', {}).get('jvmStartMs') == template.get('jvmStartMs')
            and barrier.get('liveConfigurationSha256') == template.get('liveConfigurationSha256'),
            'Barrier/template session mismatch')
    ledger_path = find_ledger(template.get('sessionId'))
    ledger = read_json(ledger_path)
    require(ledger.get('lastVerifiedB') == (raw or {}).get('B'),
            'Barrier B must equal current ledger lastVerifiedB')
    surface_path = Path(args.surface).resolve(strict=True)
    surface = read_json(surface_path)
    work_z = (surface.get('surface') or {}).get('rawZ')
    now_ms = int(time.time() * 1000)
    stationary_path = Path(args.stationary_image).resolve(strict=True)
    tip_path = Path(args.tip).resolve(strict=True)
    for path, label in ((stationary_path, 'stationary image'), (tip_path, 'tip image')):
        require(now_ms - path.stat().st_mtime_ns // 1_000_000 <= 300_000,
                label + ' must be fresh (within five minutes)')
    q = authored_values(read_json(EXAMPLE), reviewer, review, raw, refs,
                        (args.prime_x, args.prime_y), (args.dummy_x, args.dummy_y), work_z, now_ms)

    outdir.mkdir(parents=True, exist_ok=False)
    target_base = read_json(BASE_TARGET)
    target_base.pop('registrationRevalidationEvidence', None)
    target_base['knownExistingDefect'] = 'Existing board condition reviewed explicitly for this continuation group.'
    target_base['padChecks'] = []
    for padid in controls:
        path = Path(control_reports[padid]).resolve(strict=True)
        report = read_json(path)
        top = (report.get('afterImages') or {}).get('top')
        require(top and report.get('status') in ('completed-camera-survey-awaiting-image-review',
                                                 'completed-contiguous-air-batch-awaiting-observation'),
                'Control report is incomplete: ' + padid)
        target_base['padChecks'].append({'reference': padid.split('.')[0], 'padId': padid,
                                         'reviewedAligned': True, 'reportEvidence': evidence(path),
                                         'imageEvidence': evidence(path.parent / top['path'])})
    target_path = outdir / 'target-base.json'
    target_path.write_text(json.dumps(target_base, indent=2, allow_nan=False) + '\n')
    q['pairReviews'] = []
    for ref in refs:
        path = Path(report_map[pair_keys[ref]]).resolve(strict=True)
        report = read_json(path)
        require(report.get('status') in ('completed-contiguous-air-batch-awaiting-observation',
                                         'completed-camera-survey-awaiting-image-review')
                and report.get('controllerPositionVerified') is True
                and report.get('uncertainCompletion') is False,
                'Selected pair report must be complete and position-verified: ' + ref)
        top = (report.get('afterImages') or {}).get('top')
        require(top and top.get('path'), 'Selected report has no top image: ' + ref)
        q['pairReviews'].append({'reference': ref, 'padIds': [ref + '.1', ref + '.2'],
                                 'padIdentityReviewed': True, 'padsAvailableReviewed': True,
                                 'reportEvidence': evidence(path),
                                 'imageEvidence': evidence(path.parent / top['path']),
                                 'capturedMs': round(datetime.datetime.fromisoformat(
                                     report['finishedAt'].replace('Z', '+00:00')).timestamp() * 1000)})
    paths = {'template': TEMPLATE, 'barrier': barrier_path,
             'stationaryImage': stationary_path, 'tipImage': tip_path,
             'registration': Path(args.registration), 'targetBase': target_path,
             'scrapExperiment': SCRAP_EXPERIMENT, 'scrapProfile': SCRAP_PROFILE,
             'surface': surface_path, 'tipOffset': TIP_OFFSET,
             'previousReport': Path(args.previous_report), 'ledger': ledger_path}
    q['sources'] = {key: evidence(path) for key, path in paths.items()}
    inputs_path = outdir / 'reviewed-inputs.json'
    inputs_path.write_text(json.dumps(q, indent=2, allow_nan=False) + '\n')
    output = outdir / 'authored'
    subprocess.run([sys.executable, str(ROOT / 'automation/paste/author-conditioned-ftp-eight-pad.py'),
                    '--inputs', str(inputs_path), '--output', str(output)], check=True, cwd=ROOT)
    print(json.dumps({'authoringInput': str(inputs_path), 'authoredOutput': str(output),
                      'previewRequest': str(output / 'prepared/native/preview-request.json'),
                      'startRaw': raw, 'refs': refs, 'recipe': {'doseDegrees': 6,
                      'retractDegrees': 3, 'dwellMilliseconds': 2000,
                      'retractDwellMilliseconds': 500, 'workRawZ': work_z,
                      'primeWipeEndpoint': [round(args.prime_x + 1.5, 2), args.prime_y]},
                      'enabled': False, 'motionDispatched': False}, indent=2))

if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit('error: ' + str(exc))
