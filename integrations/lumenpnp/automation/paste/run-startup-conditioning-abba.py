#!/usr/bin/env python3
"""Machine-specific scrap ABBA trial; preview by default, never a production recipe.

The reviewed schedule normalizes on D27/D28, then compares A1 R1/R2 after
D1/D2 (0.25 degrees), B1 R5/R6 after D5/D6 (90 degrees), B2 R3/R4 after
D3/D4 (90 degrees), and A2 R7/R8 after D7/D8 (0.25 degrees). Main pads all
use the same 90-degree dose and 10-percent per-pad retract.

Between blocks, the 60-second interval starts at the final verified main
motion stage's finishedAt, not at the end of photography. Survey capture,
camera travel, and preparation all count as idle time; the script waits only
for the remaining interval before the next dispatch. This file is a saved
copy of the reviewed experiment runner, not an unattended production path.
"""
import argparse
import datetime as dt
import fcntl
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path('/home/lumen/lumenpnp')
STEPS = (
    ('normalize', ('D27', 'D28'), (), None),
    ('A1', ('R1', 'R2'), ('D1', 'D2'), .25),
    ('B1', ('R5', 'R6'), ('D5', 'D6'), 90),
    ('B2', ('R3', 'R4'), ('D3', 'D4'), 90),
    ('A2', ('R7', 'R8'), ('D7', 'D8'), .25),
)
TERMINAL = {'completed-awaiting-image-review', 'failed-no-retry'}


def read(path):
    return json.loads(path.read_text())


def iso_ms(value):
    if not isinstance(value, str):
        raise ValueError('Missing terminal timestamp')
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp() * 1000


def unique_refs():
    refs = [ref for _, main, cond, _ in STEPS for ref in main + cond]
    if len(refs) != len(set(refs)):
        raise ValueError('ABBA schedule repeats a reference')
    return refs


def state(root, profile_id, session_id, expected_pending):
    p = read(root / 'automation/plans/paste-operator-profile.json')
    if p['id'] != profile_id or p['sessionId'] != session_id:
        raise ValueError('Profile or session changed')
    folder = root / 'automation/evidence/operator-paste-runs' / session_id
    ledger = read(folder / 'budget-ledger.json')
    if ledger['profileId'] != profile_id or ledger['sessionId'] != session_id or ledger['status'] != 'verified':
        raise ValueError('Unverified or mismatched ledger')
    if not ledger['entries'] or ledger['entries'][-1]['status'] != 'verified':
        raise ValueError('Last ledger entry is not verified')
    if abs(sum(e['plannedGrossDegrees'] for e in ledger['entries']) - ledger['usedAdditionalGrossDegrees']) > .0001:
        raise ValueError('Gross ledger mismatch')
    if abs(ledger['maximumAdditionalGrossDegrees'] - p['rodBudget']['maximumAdditionalGrossDegrees']) > .0001:
        raise ValueError('Rod ceiling changed')
    if not math.isclose(ledger['pendingRetractDegrees'], expected_pending, abs_tol=.0001):
        raise ValueError('Pending relief changed: expected %.2f, found %.2f' % (expected_pending, ledger['pendingRetractDegrees']))
    if abs(ledger['lastVerifiedRaw']['Z'] - 32.25) > .0001 or abs(ledger['lastVerifiedDriver']['Z'] - 32.25) > .005001:
        raise ValueError('Last verified raw/driver Z is not 32.25 clearance')
    for ref in unique_refs():
        if ref not in p['pads']:
            raise ValueError('Missing registered reference ' + ref)
    return p, ledger


def active_guard(root):
    path = root / 'automation/plans/operator-batch-request.json'
    if path.exists():
        previous = read(path)
        report = root / 'automation/evidence/operator-batches' / previous['id'] / 'report.json'
        if not report.exists() or read(report).get('status') not in TERMINAL:
            raise ValueError('Prior operator batch has no terminal report')


def command(root, name, main, cond, condition_dose, execute):
    cmd = [sys.executable, str(root / 'automation/paste/prepare-operator-experiment.py'),
           'dispense-and-survey', '--root', str(root), '--refs', *main,
           '--dose', '90', '--push-deg-s', '50', '--retract-percent', '10',
           '--retract-deg-s', '100', '--dwell-ms', '1000', '--retract-dwell-ms', '0',
           '--gap-mm', '.1', '--retract-each-pad']
    if cond:
        cmd += ['--condition-refs', *cond, '--condition-dose', str(condition_dose)]
    if execute:
        cmd += ['--execute']
    return cmd


def model_previews(root, blocks, ledger):
    spec = importlib.util.spec_from_file_location('operator_prepare', root / 'automation/paste/prepare-operator-experiment.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    main_recipe = {'doseDegrees': 90, 'bSpeedFraction': .5, 'retractPercent': 10,
                   'retractSpeedFraction': 1, 'dwellMs': 1000, 'retractDwellMs': 0,
                   'heightMode': 'gap', 'gapMm': .1, 'padMode': 'both', 'retractEachPad': True}
    total = 0
    for block in blocks:
        q = {'schema': 1, 'enabled': True, 'id': 'offline-abba-preview',
             'mode': 'dispense-and-survey', 'references': block['mainReferences'],
             'recipe': dict(main_recipe)}
        if block['conditioningReferences']:
            q['conditioning'] = {
                'references': block['conditioningReferences'],
                'recipe': {**main_recipe, 'doseDegrees': block['conditioningDoseDegrees'],
                           'retractPercent': 0, 'retractDegrees': 0,
                           'dwellMs': 0, 'retractDwellMs': 0}}
        preview = module.validate(root, q)
        block['modelPreview'] = {'plannedGrossDegrees': preview['plannedGrossDegrees'],
                                 'stageCount': preview['stageCount']}
        total += preview['plannedGrossDegrees']
    if ledger['usedAdditionalGrossDegrees'] + total > ledger['maximumAdditionalGrossDegrees'] + .0001:
        raise ValueError('Whole ABBA preview exceeds gross rod budget')
    return total


def persist(path, progress):
    temp = path.with_suffix('.tmp')
    with temp.open('x') as f:
        json.dump(progress, f, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)


def wait_report(root, request_id, profile_id, session_id, main, cond, condition_dose, deadline=None):
    report_path = root / 'automation/evidence/operator-batches' / request_id / 'report.json'
    if deadline is None:
        deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        if report_path.exists():
            report = read(report_path)
            if report.get('status') in TERMINAL:
                break
        time.sleep(.5)
    else:
        raise TimeoutError('Batch report did not become terminal within 180 seconds: ' + request_id)
    if report['status'] != 'completed-awaiting-image-review' or report.get('id') != request_id:
        raise ValueError('Batch failed or report ID changed: ' + str(report.get('status')))
    req = report['request']
    if req['id'] != request_id or req['profileId'] != profile_id or tuple(req['references']) != main:
        raise ValueError('Terminal report request differs from dispatched block')
    if tuple(req.get('conditioning', {}).get('references', ())) != cond:
        raise ValueError('Terminal conditioning differs from dispatched block')
    recipe = req['recipe']
    expected = {'doseDegrees': 90, 'bSpeedFraction': .5, 'retractPercent': 10,
                'retractSpeedFraction': 1, 'dwellMs': 1000, 'retractDwellMs': 0,
                'gapMm': .1, 'retractEachPad': True, 'padMode': 'both', 'heightMode': 'gap'}
    if any(recipe.get(key) != value for key, value in expected.items()):
        raise ValueError('Terminal main recipe differs from reviewed schedule')
    if cond:
        conditioning = req['conditioning']['recipe']
        if conditioning.get('doseDegrees') != condition_dose or conditioning.get('retractPercent') != 0 or conditioning.get('retractDegrees') != 0:
            raise ValueError('Terminal conditioning dose/retraction changed')
    if 'dispense' not in report or (cond and 'conditioning' not in report):
        raise ValueError('Missing completed native dispense record')
    if len(report.get('records', ())) != len(main + cond) or set(x['reference'] for x in report['records']) != set(main + cond):
        raise ValueError('Incomplete image survey')
    if any(not Path(x['image']).is_file() for x in report['records']):
        raise ValueError('Missing image evidence')
    record_id = report['dispense']['recordId']
    record = read(root / 'automation/evidence/operator-paste-runs' / session_id / record_id / 'record.json')
    if record['status'] != 'completed-awaiting-operator-inspection' or record['profileId'] != profile_id or record['sessionId'] != session_id:
        raise ValueError('Main native record is not verified terminal')
    if tuple(record['request']['references']) != main:
        raise ValueError('Native main references changed')
    if record.get('uncertainCompletion') is not False or not record.get('stages'):
        raise ValueError('Main native completion or stages are uncertain')
    # Native records carry terminal updatedAt; final stage finishedAt is the
    # exact end of motion and is preferred as the main-to-main interval anchor.
    main_finished_at = record['stages'][-1].get('finishedAt') or record['updatedAt']
    main_finished_ms = iso_ms(main_finished_at)
    if main_finished_ms > iso_ms(record['updatedAt']):
        raise ValueError('Main final-stage time exceeds terminal record time')
    if iso_ms(report['finishedAt']) < main_finished_ms:
        raise ValueError('Outer report finished before main motion')
    return report, record, main_finished_ms


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--execute', action='store_true', help='Dispatch sequentially; only root operator invokes')
    parser.add_argument('--profile-id', help='Exact reviewed profile ID, required with --execute')
    args = parser.parse_args()
    root = args.root.resolve()
    p = read(root / 'automation/plans/paste-operator-profile.json')
    session_id = p['sessionId']
    if args.execute and args.profile_id is None:
        parser.error('--execute requires --profile-id from reviewed preview')
    profile_id = args.profile_id or p['id']
    initial_pending = 9
    _, ledger = state(root, profile_id, session_id, initial_pending)
    active_guard(root)
    run_id = 'abba-' + str(uuid.uuid4())
    progress_path = root / 'automation/evidence/operator-abba' / run_id / 'progress.json'
    plan = [{'name': name, 'mainReferences': main, 'conditioningReferences': cond,
             'conditioningDoseDegrees': condition_dose,
             'command': command(root, name, main, cond, condition_dose, args.execute)}
            for name, main, cond, condition_dose in STEPS]
    total_gross = model_previews(root, plan, ledger)
    progress = {'schema': 1, 'id': run_id, 'profileId': profile_id, 'sessionId': session_id,
                'initialPendingDegrees': initial_pending, 'initialGrossUsedDegrees': ledger['usedAdditionalGrossDegrees'],
                'mode': 'execute' if args.execute else 'preview', 'status': 'planned', 'blocks': plan,
                'modelTotalGrossDegrees': total_gross,
                'modelRemainingAfterDegrees': ledger['maximumAdditionalGrossDegrees'] - ledger['usedAdditionalGrossDegrees'] - total_gross,
                'preconditioningIdleMilliseconds': 60000, 'terminalReportTimeoutSeconds': 180}
    if not args.execute:
        print(json.dumps(progress, indent=2))
        return
    progress_path.parent.mkdir(parents=True, exist_ok=False)
    with (root / 'automation/plans/operator-abba.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        persist(progress_path, progress)
        previous_main_ms = None
        try:
            progress['status'] = 'running'
            for block in progress['blocks']:
                name = block['name']
                state(root, profile_id, session_id, 9)
                active_guard(root)
                if previous_main_ms is not None:
                    wait_ms = max(0, previous_main_ms + 60000 - time.time() * 1000)
                    block['waitedBeforeDispatchMilliseconds'] = wait_ms
                    while time.time() * 1000 < previous_main_ms + 60000:
                        time.sleep(min(1, (previous_main_ms + 60000 - time.time() * 1000) / 1000))
                    state(root, profile_id, session_id, 9)
                    active_guard(root)
                prior_model_gross = block['modelPreview']['plannedGrossDegrees']
                current_ledger = state(root, profile_id, session_id, 9)[1]
                model_previews(root, [block], current_ledger)
                if abs(block['modelPreview']['plannedGrossDegrees'] - prior_model_gross) > .0001:
                    raise ValueError('Fresh block model differs from reviewed preview for ' + name)
                block['status'] = 'dispatching'
                block['dispatchStartedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
                block['actualIdleFromPriorMainMilliseconds'] = None if previous_main_ms is None else time.time() * 1000 - previous_main_ms
                persist(progress_path, progress)
                deadline = time.monotonic() + 180
                result = subprocess.run(block['command'], cwd=root, capture_output=True, text=True, timeout=45)
                block['cliExitCode'] = result.returncode
                block['cliOutputTail'] = (result.stdout + result.stderr)[-2000:]
                if result.returncode:
                    raise RuntimeError('Preparation CLI failed for ' + name)
                parsed = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{') and line.endswith('}')]
                requests = [x for x in parsed if isinstance(x, dict) and 'request' in x and 'id' in x]
                if len(requests) != 1:
                    raise ValueError('Cannot identify unique dispatched request ID for ' + name)
                if requests[0].get('executed') is not True:
                    raise ValueError('Preparation CLI did not confirm dispatch for ' + name)
                if abs(requests[0]['preview']['plannedGrossDegrees'] - block['modelPreview']['plannedGrossDegrees']) > .0001:
                    raise ValueError('Dispatch preview gross differs from frozen model for ' + name)
                request_id = requests[0]['id']
                block['requestId'] = request_id
                block['status'] = 'waiting-for-terminal-report'
                persist(progress_path, progress)
                report, record, previous_main_ms = wait_report(root, request_id, profile_id, session_id,
                                                                tuple(block['mainReferences']), tuple(block['conditioningReferences']),
                                                                block['conditioningDoseDegrees'], deadline)
                state(root, profile_id, session_id, 9)
                if abs(report['dispense']['raw']['B'] - record['after']['raw']['B']) > .0001:
                    raise ValueError('Outer/main B mismatch')
                block['mainRecordId'] = record['id']
                block['mainFinalStageFinishedAt'] = record['stages'][-1].get('finishedAt')
                block['mainTerminalUpdatedAt'] = record['updatedAt']
                block['batchFinishedAt'] = report['finishedAt']
                block['status'] = 'completed'
                persist(progress_path, progress)
            progress['status'] = 'completed'
        except BaseException as error:
            progress['status'] = 'stopped-no-retry'
            progress['error'] = repr(error)
            raise
        finally:
            progress['finishedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
            persist(progress_path, progress)
            print(json.dumps({'progress': str(progress_path), 'status': progress['status']}))


if __name__ == '__main__':
    main()
