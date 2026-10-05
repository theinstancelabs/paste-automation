#!/usr/bin/env python3
"""Preview a cumulative allowance extension against the original measured-rod datum; never writes state."""
import argparse, hashlib, json, pathlib, subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_CUMULATIVE_ALLOWANCE = 3000

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
    if args.cumulative_allowance_degrees != DEFAULT_CUMULATIVE_ALLOWANCE:
        ap.error('This preview supports only the reviewed 3000-degree cumulative ceiling')

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
    if calibration.get('alignmentApplied') is not False or calibration.get('zApplied') is not False:
        raise ValueError('Calibration must remain invalidated for this lineage')
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
        'scope': 'measured-rod-cumulative-extension',
        'sessionId': session,
        'grossUsedAtMeasurement': measured_gross,
        'cumulativeAllowanceDegrees': args.cumulative_allowance_degrees,
        'newPhysicalMeasurement': False,
        'measurementSha256': profile['rodMeasuredRenewal']['sha256'],
        'ledgerSnapshotSha256': measurement['ledgerSnapshot']['sha256'],
    }
    payload = {'budget': candidate_budget, 'measurement': measurement, 'prior': prior,
               'current': ledger, 'session': session, 'extension': extension}
    code = "const P=require(process.argv[1]),q=JSON.parse(require('fs').readFileSync(0));console.log(JSON.stringify(P.validateMeasuredRenewal(q.budget,q.measurement,q.prior,q.current,q.session,q.extension)))"
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
        'extension': extension,
    }, indent=2, allow_nan=False))

if __name__ == '__main__':
    main()
