#!/usr/bin/env python3
"""Preview or explicitly run one operator batch followed by verified +5 relief steps.

Preview is the default. Each executed batch requires an explicit reference list,
complete dose recipe, and (optionally) a separate explicit conditioning/waste
reference list. No request is retried after uncertain completion.
"""
import argparse
import fcntl
import hashlib
import json
import math
import pathlib
import subprocess
import sys
import time
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
PREPARE = ROOT / 'automation/paste/prepare-operator-experiment.py'
DISPATCH = ROOT / 'automation/scripts/run_reviewed_action.py'
RELIEF_API_PLAN_CAP_DEGREES = 300.0


def read_json(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def validate_refs(refs: list[str], label: str) -> list[str]:
    result = [ref.strip() for ref in refs]
    if not result or any(not ref for ref in result):
        raise ValueError(f'{label} must contain explicit non-empty references')
    if len(set(result)) != len(result):
        raise ValueError(f'{label} contains duplicate references')
    return result


def command_for(args: argparse.Namespace, execute: bool | None = None) -> list[str]:
    command = [sys.executable, str(PREPARE), 'dispense-and-survey', '--refs', *args.refs,
               '--dose', str(args.dose), '--push-deg-s', str(args.push_deg_s),
               '--retract-percent', str(args.retract_percent), '--retract-deg-s', str(args.retract_deg_s),
               '--dwell-ms', str(args.dwell_ms), '--retract-dwell-ms', str(args.retract_dwell_ms),
               '--gap-mm', str(args.gap_mm)]
    if args.retract_degrees is not None:
        command.extend(['--retract-degrees', str(args.retract_degrees)])
    if args.retract_each_pad:
        command.append('--retract-each-pad')
    if args.waste_refs:
        command.extend(['--condition-refs', *args.waste_refs,
                        '--condition-dose', str(args.waste_dose),
                        '--condition-pad-mode', args.waste_pad_mode])
    should_execute = args.execute if execute is None else execute
    if should_execute:
        command.append('--execute')
    return command


def result_id(stdout: str) -> str:
    for line in reversed(stdout.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and isinstance(value.get('id'), str):
            return value['id']
    raise RuntimeError('Preparation did not return a batch id; inspect its output before proceeding')


def preview_result(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and isinstance(value.get('preview'), dict):
            return value
    raise RuntimeError('Preparation did not return its reviewed preview; no execution started')


def expected_pending_after_batch(args: argparse.Namespace) -> float:
    requested = args.retract_degrees
    if requested is None:
        requested = args.dose * args.retract_percent / 100
    if not math.isfinite(requested) or requested < 0:
        raise ValueError('The effective per-pad retraction must be finite and non-negative')
    return math.floor(requested * 100 + 0.5) / 100


def validate_preflight_budget(preview: dict[str, Any], pending_after_batch: float,
                              post_run_relief_degrees: float) -> None:
    remaining = preview.get('remainingAfter')
    if not isinstance(remaining, (int, float)) or not math.isfinite(remaining) or remaining < 0:
        raise RuntimeError('Reviewed preview lacks a valid remaining gross budget')
    if not math.isfinite(pending_after_batch) or pending_after_batch < 0:
        raise RuntimeError('Reviewed preview has invalid expected pending relief')
    if remaining + 1e-7 < post_run_relief_degrees:
        raise RuntimeError('Combined batch and post-run relief exceed the remaining gross budget')
    if pending_after_batch + post_run_relief_degrees > RELIEF_API_PLAN_CAP_DEGREES + 1e-7:
        raise RuntimeError('Expected pending relief after the batch exceeds the API planRelief 300-degree cap')


def profile_binding(profile_path: pathlib.Path) -> dict[str, str]:
    raw = profile_path.read_bytes()
    profile = json.loads(raw)
    if not isinstance(profile.get('id'), str) or not isinstance(profile.get('sessionId'), str):
        raise RuntimeError('Operator profile is missing its profile/session identity')
    return {'id': profile['id'], 'sessionId': profile['sessionId'],
            'sha256': hashlib.sha256(raw).hexdigest()}


def require_profile_unchanged(profile_path: pathlib.Path, binding: dict[str, str]) -> None:
    if profile_binding(profile_path) != binding:
        raise RuntimeError('Profile/session changed after the batch; no post-run relief dispatched')


def validate_post_action_ledger(ledger: dict[str, Any], binding: dict[str, str],
                                remaining_relief_degrees: float) -> None:
    if ledger.get('status') != 'verified' or ledger.get('profileId') != binding['id'] or ledger.get('sessionId') != binding['sessionId']:
        raise RuntimeError('Verified ledger identity changed after the batch; no post-run relief dispatched')
    used = ledger.get('usedAdditionalGrossDegrees')
    maximum = ledger.get('maximumAdditionalGrossDegrees')
    pending = ledger.get('pendingRetractDegrees')
    if any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in (used, maximum, pending)):
        raise RuntimeError('Post-run relief budget fields are invalid; no action dispatched')
    if used + remaining_relief_degrees > maximum + 1e-7:
        raise RuntimeError('Post-run relief no longer fits the remaining gross budget; no action dispatched')
    if pending + remaining_relief_degrees > RELIEF_API_PLAN_CAP_DEGREES + 1e-7:
        raise RuntimeError('Pending plus post-run relief exceeds the API planRelief 300-degree cap; no action dispatched')


def wait_for_batch(report: pathlib.Path, timeout: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if report.is_file():
            current = read_json(report)
            status = current.get('status')
            if status == 'completed-awaiting-image-review':
                return current
            if status == 'failed-no-retry':
                raise RuntimeError(f'Batch failed without retry; inspect {report}')
        time.sleep(0.25)
    raise TimeoutError(f'No terminal batch report within {timeout:g}s; no replay; inspect {report}')


def verified_relief_step(profile_path: pathlib.Path, binding: dict[str, str], relief_index: int,
                         remaining_relief_degrees: float, timeout: float) -> dict[str, Any]:
    require_profile_unchanged(profile_path, binding)
    ledger_path = ROOT / 'automation/evidence/operator-paste-runs' / binding['sessionId'] / 'budget-ledger.json'
    before = read_json(ledger_path)
    validate_post_action_ledger(before, binding, remaining_relief_degrees)
    prior_count = len(before['entries'])
    prior_b = float(before['lastVerifiedRaw']['B'])
    require_profile_unchanged(profile_path, binding)
    result = subprocess.run([sys.executable, str(DISPATCH), 'operator-pressure-relief', '--confirmed'],
                            cwd=ROOT, capture_output=True, text=True, check=True)
    if result.stdout:
        print(result.stdout.rstrip())
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        after = read_json(ledger_path)
        if (len(after.get('entries', [])) == prior_count + 1
                and after['entries'][-1].get('status') == 'verified'
                and after.get('status') == 'verified'):
            delta = float(after['lastVerifiedRaw']['B']) - prior_b
            if not math.isclose(delta, 5.0, rel_tol=0, abs_tol=0.001):
                raise RuntimeError(f'Relief step {relief_index} did not verify exactly +5 B degrees; inspect ledger')
            print(f'Verified idle relief {relief_index}: +5 B degrees; pending restoration {after.get("pendingRetractDegrees")}')
            return after
        time.sleep(0.25)
    raise TimeoutError(f'Relief step {relief_index} has no fresh verified ledger entry; no retry; inspect ledger')


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refs', nargs='+', required=True, help='explicit target pad/resistor references')
    parser.add_argument('--waste-refs', nargs='+', help='separate explicit waste/conditioning references; never inferred')
    parser.add_argument('--waste-dose', type=float, help='dose for the waste/conditioning stage; required with --waste-refs')
    parser.add_argument('--waste-pad-mode', choices=['both', '1', '2'], default='both')
    parser.add_argument('--dose', type=float, required=True)
    parser.add_argument('--push-deg-s', type=float, required=True)
    parser.add_argument('--retract-percent', type=float, required=True)
    parser.add_argument('--retract-degrees', type=float, help='optional absolute per-pad retraction, overriding percent')
    parser.add_argument('--retract-each-pad', action='store_true')
    parser.add_argument('--retract-deg-s', type=float, required=True)
    parser.add_argument('--dwell-ms', type=float, required=True)
    parser.add_argument('--retract-dwell-ms', type=float, required=True)
    parser.add_argument('--gap-mm', type=float, required=True)
    parser.add_argument('--post-run-relief-degrees', type=int, default=15,
                        help='additional stationary relief after a completed batch, in +5-degree steps (default: 15; use 0 to skip)')
    parser.add_argument('--timeout-seconds', type=float, default=600,
                        help='maximum wait for each fresh terminal report (default: 600)')
    parser.add_argument('--execute', action='store_true', help='explicitly stage and execute; omitted means preview only')
    args = parser.parse_args(argv)
    args.refs = validate_refs(args.refs, '--refs')
    if args.waste_refs:
        args.waste_refs = validate_refs(args.waste_refs, '--waste-refs')
        if args.waste_dose is None or not math.isfinite(args.waste_dose) or args.waste_dose <= 0:
            parser.error('--waste-refs requires a positive --waste-dose')
        if set(args.refs) & set(args.waste_refs):
            parser.error('--waste-refs must be separate from --refs')
    elif args.waste_dose is not None:
        parser.error('--waste-dose requires --waste-refs')
    if args.post_run_relief_degrees < 0 or args.post_run_relief_degrees > 100 or args.post_run_relief_degrees % 5:
        parser.error('--post-run-relief-degrees must be 0..100 in multiples of 5')
    if not math.isfinite(args.timeout_seconds) or args.timeout_seconds <= 0:
        parser.error('--timeout-seconds must be positive and finite')
    return args


def run_post_run_relief(profile_path: pathlib.Path, binding: dict[str, str],
                        total_degrees: int, timeout: float) -> dict[str, Any] | None:
    last = None
    for index in range(1, total_degrees // 5 + 1):
        require_profile_unchanged(profile_path, binding)
        remaining = total_degrees - (index - 1) * 5
        last = verified_relief_step(profile_path, binding, index, remaining, timeout)
    return last


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    profile_path = ROOT / 'automation/plans/paste-operator-profile.json'
    binding = profile_binding(profile_path)
    preview_process = subprocess.run(command_for(args, execute=False), cwd=ROOT, capture_output=True, text=True, check=True)
    if preview_process.stderr:
        print(preview_process.stderr, file=sys.stderr, end='')
    preview = preview_result(preview_process.stdout)
    require_profile_unchanged(profile_path, binding)
    validate_preflight_budget(preview['preview'], expected_pending_after_batch(args), args.post_run_relief_degrees)
    print(preview_process.stdout, end='')
    if not args.execute:
        return 0

    lock_path = ROOT / 'automation/plans/repeat-with-idle-relief.lock'
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        started = subprocess.run(command_for(args, execute=True), cwd=ROOT, capture_output=True, text=True, check=True)
        print(started.stdout, end='')
        if started.stderr:
            print(started.stderr, file=sys.stderr, end='')
        batch_id = result_id(started.stdout)
        report = ROOT / 'automation/evidence/operator-batches' / batch_id / 'report.json'
        wait_for_batch(report, args.timeout_seconds)
        if args.post_run_relief_degrees:
            last = run_post_run_relief(profile_path, binding, args.post_run_relief_degrees, args.timeout_seconds)
            if last is not None:
                print(json.dumps({'postRunReliefDegrees': args.post_run_relief_degrees,
                                  'pendingRetractDegrees': last.get('pendingRetractDegrees'),
                                  'grossUsedDegrees': last.get('usedAdditionalGrossDegrees')}, indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, TimeoutError, subprocess.CalledProcessError, BlockingIOError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(2)
