#!/usr/bin/env python3
"""Preview a cumulative allowance extension against the original measured-rod datum; never writes state."""
import argparse, hashlib, json, pathlib, subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_CUMULATIVE_ALLOWANCE = 3000
ALLOWED_CUMULATIVE_ALLOWANCES = (3000, 5000, 7500, 8000, 12000, 15000)

def rebind_profile_ids(value, old_id, new_id):
    """Rebind calibration-sidecar profile identities after a profile revision."""
    if isinstance(value, dict):
        return {key: (new_id if key == 'profileId' and item == old_id else
                      rebind_profile_ids(item, old_id, new_id))
                for key, item in value.items()}
    if isinstance(value, list):
        return [rebind_profile_ids(item, old_id, new_id) for item in value]
    return value

def bound(ref):
    path = pathlib.Path(ref['path'])
    if not path.is_absolute():
        path = ROOT / path
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != ref['sha256']:
        raise ValueError(f"Hash mismatch for {path}")
    return path, json.loads(data)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cumulative-allowance-degrees', type=int, default=DEFAULT_CUMULATIVE_ALLOWANCE)
    args = ap.parse_args()
    if args.cumulative_allowance_degrees not in ALLOWED_CUMULATIVE_ALLOWANCES:
        ap.error('Choose a policy-approved cumulative ceiling: ' + ', '.join(map(str, ALLOWED_CUMULATIVE_ALLOWANCES)))

    profile_path = ROOT / 'automation/plans/paste-operator-profile.json'
    profile = json.loads(profile_path.read_text())
    session = profile['sessionId']
    run_dir = ROOT / 'automation/evidence/operator-paste-runs' / session
    ledger = json.loads((run_dir / 'budget-ledger.json').read_text())
    calibration = json.loads((run_dir / f"calibration-{profile['id']}.json").read_text())
    if profile['id'] != ledger['profileId'] or profile['id'] != calibration['profileId']:
        raise ValueError('Profile, ledger, or calibration identity changed')
    if ledger.get('status') != 'verified' or not ledger.get('entries') or ledger['entries'][-1].get('status') != 'verified':
        raise ValueError('A verified, terminal ledger is required')
    if not isinstance(ledger.get('lastVerifiedRaw'), dict) or not all(k in ledger['lastVerifiedRaw'] for k in ('X','Y','Z','A','B')):
        raise ValueError('Full verified stationary pose is required')

    measurement_path, measurement = bound(profile['rodMeasuredRenewal'])
    snapshot_path, prior = bound(measurement['ledgerSnapshot'])
    if prior.get('sessionId') != session or prior.get('status') != 'verified':
        raise ValueError('Original measurement ledger snapshot is stale or invalid')
    measured_gross = measurement['grossUsedAtMeasurement']
    cap = measured_gross + args.cumulative_allowance_degrees
    candidate_budget = dict(profile['rodBudget'], maximumAdditionalGrossDegrees=cap)
    extension = {
        'schema': 1,
        'scope': 'measured-rod-cumulative-extension',
        'sessionId': session,
        'grossUsedAtMeasurement': measured_gross,
        'cumulativeAllowanceDegrees': args.cumulative_allowance_degrees,
        'newPhysicalMeasurement': False,
        'engineeringAllowanceUnchangedMm': measurement['engineeringAllowanceMm'],
        'measurementSha256': profile['rodMeasuredRenewal']['sha256'],
        'ledgerSnapshotSha256': measurement['ledgerSnapshot']['sha256'],
        'originalMeasurement': profile['rodMeasuredRenewal'],
        'previousExtension': profile.get('rodMeasuredExtension'),
    }
    # Preview a prospective new profile identity and update every sidecar
    # profileId reference. No files are written by this workflow.
    candidate = json.loads(json.dumps(profile))
    candidate['rodBudget'] = candidate_budget
    candidate['rawBounds']['B'] = {'min': ledger['baselineB'] - cap, 'max': ledger['baselineB'] + cap}
    candidate['rodMeasuredExtension'] = {'path': '/preview-only/extension.json', 'sha256': '0' * 64}
    old_id = profile['id']
    candidate['id'] = hashlib.sha256(json.dumps(candidate, sort_keys=True).encode()).hexdigest()
    candidate_calibration = rebind_profile_ids(calibration, old_id, candidate['id'])
    payload = {'profile': profile, 'candidate': candidate, 'calibration': calibration,
               'candidateCalibration': candidate_calibration, 'budget': candidate_budget,
               'measurement': measurement, 'prior': prior, 'current': ledger,
               'session': session, 'extension': extension}
    code = """const P=require(process.argv[1]),q=JSON.parse(require('fs').readFileSync(0));
P.validateProfile(q.candidate);
const before=P.withCalibration(q.profile,q.calibration),after=P.withCalibration(q.candidate,q.candidateCalibration);
if(JSON.stringify(before.pads)!==JSON.stringify(after.pads))throw Error('Calibrated pad coordinates changed across budget-only profile revision');
const renewal=P.validateMeasuredRenewal(q.budget,q.measurement,q.prior,q.current,q.session,q.extension);
console.log(JSON.stringify(renewal));"""
    result = subprocess.run(['node', '-e', code, str(ROOT / 'automation/paste/operator-console-policy.cjs')],
                            input=json.dumps(payload), text=True, capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.strip() or 'Measured extension policy rejected this snapshot')
    check = json.loads(result.stdout)
    used = ledger['usedAdditionalGrossDegrees']
    if used > cap or abs(sum(e['plannedGrossDegrees'] for e in ledger['entries']) - used) > 0.0001:
        raise ValueError('Current charged ledger exceeds candidate cap or does not reconcile')
    print(json.dumps({
        'previewOnly': True, 'applied': False, 'profileId': profile['id'], 'sessionId': session,
        'measurementPath': str(measurement_path), 'measurementSha256': profile['rodMeasuredRenewal']['sha256'],
        'ledgerSnapshotPath': str(snapshot_path), 'ledgerSnapshotSha256': measurement['ledgerSnapshot']['sha256'],
        'currentLedgerEntries': len(ledger['entries']), 'currentUsedGrossDegrees': used,
        'grossChargedSinceMeasurement': used - measured_gross,
        'cumulativeAllowanceFromOriginalMeasurement': args.cumulative_allowance_degrees,
        'proposedMaximumAdditionalGrossDegrees': cap,
        'remainingGrossAllowance': cap - used,
        'physicalAvailableAfterReservesDegrees': check['availableDegrees'],
        'pendingRetractDegrees': ledger['pendingRetractDegrees'],
        'currentVerifiedRaw': ledger['lastVerifiedRaw'],
        'alignmentApplied': calibration['alignmentApplied'], 'zApplied': calibration['zApplied'],
        'previewProfileIdForValidation': candidate['id'],
        'previewProfileIdUsesPlaceholderExtensionBinding': True,
        'calibrationProfileIdsRebound': candidate_calibration.get('profileId') == candidate['id'],
        'extension': extension,
    }, indent=2, allow_nan=False))

if __name__ == '__main__':
    main()
