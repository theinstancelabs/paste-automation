#!/usr/bin/env python3
"""Dispatch one explicitly selected prepared batch action, or observe its existing ID."""
import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXECUTE_IMAGE_MAX_AGE_MS = 240_000
SCOPES = {
    'contiguous-native-scrap-batch-preview',
    'contiguous-native-scrap-sequence-comparison-preview',
    'contiguous-native-ftp-two-pad-preview',
    'contiguous-native-ftp-conditioned-two-pad-preview',
    'contiguous-native-ftp-conditioned-eight-pad-preview',
    'contiguous-native-ftp-selected-pads-preview',
    'contiguous-native-ftp-selected-pads-up-to-40-preview',
    'contiguous-native-ftp-retraction-comparison-preview',
    'contiguous-native-ftp-minimum-travel-eight-pad-preview',
    'contiguous-native-ftp-one-pad-cleanup-preview',
}


def read(path):
    return json.loads(path.read_bytes())


def validate_execute_image_freshness(request, now_ms=None):
    """Leave one minute of headroom before the native 300-second image gate."""
    captured = request.get('imageCapturedMs')
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    if isinstance(captured, bool) or not isinstance(captured, (int, float)) or captured < 0:
        raise ValueError('Reviewed image timestamp is missing; capture and review a new image, then prepare a new request')
    age = now_ms - captured
    if age < 0 or age > EXECUTE_IMAGE_MAX_AGE_MS:
        raise ValueError('Reviewed image is too old for dispatch (age {} ms; limit {} ms); capture and review a new image, then prepare a new request'.format(age, EXECUTE_IMAGE_MAX_AGE_MS))
    return age


def wait_report(report, ident, preview, seconds, clock=time.monotonic, sleep=time.sleep,
                bridge_error=None, dispatch_started_ns=None):
    end = clock() + seconds
    terminal = 'completed-model-only-contiguous-batch-preview' if preview else 'completed-contiguous-batch-awaiting-observation'
    while clock() < end:
        # The attach agent writes this file only when the reviewed JavaScript
        # fails before it can create the normal per-ID report. Its contents have
        # no request ID, so associate it only by a fresh filesystem timestamp
        # recorded immediately before this runner's one-shot dispatch. Treat an
        # unrelated fresh bridge error as a stop too; fail closed, never replay.
        if bridge_error is not None and dispatch_started_ns is not None:
            try:
                if bridge_error.stat().st_mtime_ns >= dispatch_started_ns:
                    detail = bridge_error.read_text(errors='replace')
                    raise RuntimeError('Fresh OpenPnP bridge error after this one-shot dispatch; do not replay: '
                                       + str(bridge_error) + '\n' + detail)
            except FileNotFoundError:
                pass
        if report.exists():
            try:
                r = read(report)
            except json.JSONDecodeError:
                sleep(.1)
                continue
            if r.get('id') != ident:
                raise RuntimeError('Report ID mismatch; do not replay: ' + str(report))
            status = r.get('status', '')
            if r.get('error') or status.startswith(('failed', 'stopped')):
                raise RuntimeError('Failed/stopped existing action; do not replay: ' + str(report))
            if status == terminal or (not preview and status == 'completed-contiguous-air-batch-awaiting-observation' and r.get('request', {}).get('mode') == 'air'):
                verified = (r.get('noControllerAccess') is True and r.get('noMotion') is True) if preview else (r.get('controllerPositionVerified') is True and r.get('uncertainCompletion') is False)
                if not verified:
                    raise RuntimeError('Unverified terminal; do not replay: ' + str(report))
                return r
        sleep(.1)
    raise TimeoutError('No verified terminal; observe this ID, do not replay: ' + str(report))


def terminal_wait_seconds(scope):
    """Set a report polling window without changing the native stage timeout."""
    if scope in ('contiguous-native-ftp-selected-pads-up-to-40-preview','contiguous-native-ftp-retraction-comparison-preview'):
        return 600
    if scope == 'contiguous-native-ftp-minimum-travel-eight-pad-preview':
        return 300
    if scope in ('contiguous-native-scrap-sequence-comparison-preview',
                 'contiguous-native-ftp-conditioned-eight-pad-preview',
                 'contiguous-native-ftp-selected-pads-preview'):
        return 300
    return 60


def save_runner_error(prepared, mode, ident, binding, report, error,
                      bridge_error=None, dispatch_started_ns=None):
    """Keep a small durable failure record; the one-shot receipt remains authoritative."""
    record = dict(schema=1, id=ident, mode=mode,
                  requestSha256=binding['requestSha256'], report=str(report),
                  recordedAt=time.time(), error=str(error))
    if bridge_error is not None:
        try:
            if dispatch_started_ns is None or bridge_error.stat().st_mtime_ns >= dispatch_started_ns:
                raw = bridge_error.read_bytes()
                record['bridgeError'] = dict(path=str(bridge_error),
                                             sha256=hashlib.sha256(raw).hexdigest(),
                                             text=raw.decode('utf-8', errors='replace'))
        except OSError:
            pass
    path = prepared / ('runner-' + mode + '-error.json')
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w') as f:
        json.dump(record, f, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)
    directory_fd = os.open(prepared, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def run(prepared_dir, preview, root=ROOT, invoke=subprocess.run, wait=wait_report):
    prepared = Path(prepared_dir).resolve(strict=True)
    request = prepared / 'preview-request.json'
    original = request.read_bytes()
    q = json.loads(original)
    if q.get('scope') not in SCOPES or q.get('enabled') is not False or not isinstance(q.get('id'), str) or not re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', q['id']):
        raise ValueError('Existing disabled native preview request with UUID required')
    mode = 'preview' if preview else 'execute'
    action = 'paste-contiguous-batch-preview' if preview else 'paste-contiguous-batch'
    report = root / 'automation/evidence' / (action + '-' + q['id']) / 'report.json'
    receipt = prepared / ('runner-' + mode + '-attempt.json')
    dispatch_meta = prepared / ('runner-' + mode + '-dispatch.json')
    binding = dict(schema=1, id=q['id'], mode=mode, requestSha256=hashlib.sha256(original).hexdigest(), report=str(report))
    print('Report: ' + str(report), file=sys.stderr, flush=True)
    # Serializes this runner's use of the fixed bridge plan files. It does not
    # acquire or create a separate machine/controller connection.
    lock_path = root / '.local-machine-backups/contiguous-batch-runner.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        existing = receipt.exists() or report.exists()
        if receipt.exists():
            if read(receipt) != binding:
                raise ValueError('Existing attempt binds different request bytes; do not replay')
        if not existing:
            if not preview:
                validate_execute_image_freshness(q)
            runtime_bytes = original
            if not preview:
                native_preview = root / 'automation/evidence' / ('paste-contiguous-batch-preview-' + q['id']) / 'report.json'
                cmd = [sys.executable, str(root / 'automation/paste/prepare-contiguous-batch.py'), 'finalize', '--request', str(request), '--preview', str(native_preview)]
                try:
                    result = invoke(cmd, cwd=root, check=True, text=True, capture_output=True)
                except subprocess.CalledProcessError as exc:
                    raise ValueError('Native finalize rejected request: ' + (exc.stderr or exc.stdout or str(exc)).strip()) from exc
                runtime = Path(result.stdout.strip()).resolve(strict=True)
                if runtime != native_preview.parent / 'runtime-request.json':
                    raise ValueError('Finalizer returned an unexpected runtime path')
                runtime_bytes = runtime.read_bytes()
                rq = json.loads(runtime_bytes)
                if rq.get('id') != q['id'] or rq.get('scope') != q['scope'].removesuffix('-preview') or rq.get('enabled') is not False:
                    raise ValueError('Finalized identity/scope differs from prepared request')
            if request.read_bytes() != original:
                raise ValueError('Prepared request changed during finalization')
            # Once this durable marker exists, even an interrupted or uncertain
            # bridge call must never be submitted again by this runner.
            with receipt.open('x') as f:
                json.dump(binding, f, indent=2)
                f.write('\n')
                f.flush()
                os.fsync(f.fileno())
            directory_fd = os.open(prepared, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            plan = root / 'automation/plans' / (action + '-request.json')
            plan.write_bytes(runtime_bytes)
            dispatch_started_ns = time.time_ns()
            # Persist the time boundary before entering the bridge. This makes
            # a later bridge-error file attributable without making retry safe.
            with dispatch_meta.open('x') as f:
                json.dump(dict(schema=1, id=q['id'], mode=mode,
                               requestSha256=binding['requestSha256'],
                               dispatchStartedNs=dispatch_started_ns), f, indent=2)
                f.write('\n')
                f.flush()
                os.fsync(f.fileno())
            directory_fd = os.open(prepared, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            try:
                invoke([sys.executable, str(root / 'automation/scripts/run_reviewed_action.py'), action, '--confirmed'], cwd=root, check=True, stdout=subprocess.DEVNULL)
            except Exception as exc:
                save_runner_error(prepared, mode, q['id'], binding, report, exc,
                                  root / 'automation/plans/bridge-error.txt', dispatch_started_ns)
                raise
        else:
            dispatch_started_ns = None
            if dispatch_meta.exists():
                meta = read(dispatch_meta)
                if (meta.get('id') != q['id'] or meta.get('mode') != mode or
                        meta.get('requestSha256') != binding['requestSha256']):
                    raise ValueError('Existing dispatch metadata binds another request; do not replay')
                dispatch_started_ns = meta.get('dispatchStartedNs')
                if not isinstance(dispatch_started_ns, int):
                    raise ValueError('Existing dispatch metadata has no valid time boundary')
        seconds = terminal_wait_seconds(q['scope'])
        bridge_error = root / 'automation/plans/bridge-error.txt'
        try:
            r = wait(report, q['id'], preview, seconds,
                     bridge_error=bridge_error, dispatch_started_ns=dispatch_started_ns)
        except Exception as exc:
            save_runner_error(prepared, mode, q['id'], binding, report, exc,
                              bridge_error if dispatch_started_ns is not None else None,
                              dispatch_started_ns)
            raise
        summary = dict(report=str(report), id=q['id'], status=r['status'], existingIdObserved=existing, dispatchedThisInvocation=not existing)
        (prepared / ('runner-' + mode + '-result.json')).write_text(json.dumps(summary, indent=2) + '\n')
        return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared-dir', type=Path, required=True)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--preview', action='store_true')
    choice.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.prepared_dir, args.preview), indent=2))
    except Exception as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
