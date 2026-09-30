#!/usr/bin/env python3
"""Dispatch one explicitly confirmed reviewed action into the live OpenPnP UI.

The local Java Attach bridge has no network listener. The guarded JavaScript
dispatcher queues one allowlisted script on OpenPnP's UI. Optional evidence
waiting observes only fresh completion artifacts; it never retries an action.
"""

import argparse
from datetime import datetime
import json
import math
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ACTION_ALLOWLIST = ['paste-startup-quarantine', 'paste-waste-prime', 'paste-waste-prime-preview', 'paste-top-exposure', 'paste-bottom-exposure', 'paste-camera-led', 'paste-home-finalize', 'paste-reset-home', 'paste-reset-clearance', 'paste-reset-connect', 'paste-reset-invalidate', 'paste-model-state', 'paste-vacuum-probe', 'paste-b-config', 'paste-z-observe', 'paste-position-barrier', 'paste-error-latch', 'paste-vacuum-baseline', 'paste-survey-release', 'paste-prime-release', 'paste-prime-audit', 'paste-survey-audit', 'paste-survey', 'paste-measure', 'paste-connect-inspect', 'paste-quarantine', 'paste-air', 'paste-state', 'vacuum', 'adopt', 'discover', 'home','load','register', 'probe', 'reconcile', 'state', 'registration', 'index', 'opening',
                    'center', 'pick', 'place', 'record', 'review', 'empty', 'seal', 'recover']
PROCESS_MARKER = b'install4j.org.openpnp.Main'
EVIDENCE_WAIT_ACTIONS = {'index', 'pick', 'place', 'record', 'center', 'recover'}


def repo_root():
    return Path(__file__).resolve().parents[2]


def tool_path(name):
    value = shutil.which(name)
    if not value:
        raise RuntimeError(f'required Java tool not found on PATH: {name}')
    return value


def ensure_bridge_built(root):
    """Compile attach dispatcher and agent jar only when sources are newer."""
    source_dir = root / 'automation/scripts/java'
    sources = [source_dir / 'ReviewedCommandAgent.java', source_dir / 'DispatchReviewed.java']
    for source in sources:
        if not source.is_file():
            raise RuntimeError(f'missing Java bridge source: {source}')

    build = root / '.local-machine-backups/command-bridge-build'
    classes = build / 'classes'
    jar_file = build / 'reviewed-command-agent.jar'
    required_classes = [classes / 'ReviewedCommandAgent.class', classes / 'DispatchReviewed.class']
    outputs = [jar_file, *required_classes]
    rebuild = any(not p.is_file() for p in outputs)
    if not rebuild:
        newest_source = max(p.stat().st_mtime_ns for p in sources)
        rebuild = any(p.stat().st_mtime_ns < newest_source for p in outputs)
    if not rebuild:
        return build, classes, jar_file

    classes.mkdir(parents=True, exist_ok=True)
    javac, jar = tool_path('javac'), tool_path('jar')
    subprocess.run([javac, '--add-modules', 'jdk.attach', '-d', str(classes),
                    *(str(p) for p in sources)], check=True)
    manifest = build / 'reviewed-command-agent.mf'
    manifest.write_text('Manifest-Version: 1.0\n'
                        'Agent-Class: ReviewedCommandAgent\n'
                        'Can-Redefine-Classes: false\n'
                        'Can-Retransform-Classes: false\n\n')
    subprocess.run([jar, '--create', '--file', str(jar_file), '--manifest', str(manifest),
                    '-C', str(classes), 'ReviewedCommandAgent.class'], check=True)
    return build, classes, jar_file


def discover_openpnp_pid(proc_root=Path('/proc')):
    """Require exactly one live process whose cmdline identifies OpenPnP."""
    matches = []
    try:
        entries = list(proc_root.iterdir())
    except OSError as exc:
        raise RuntimeError(f'cannot inspect live process table {proc_root}: {exc}') from exc
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            cmdline = (entry / 'cmdline').read_bytes()
        except (OSError, PermissionError):
            continue
        if PROCESS_MARKER in cmdline:
            matches.append((int(entry.name), cmdline))
    if len(matches) != 1:
        raise RuntimeError(f'expected exactly one live OpenPnP PID containing '
                           f'{PROCESS_MARKER.decode()}, found {len(matches)}')
    pid, original = matches[0]
    if not original:
        raise RuntimeError('OpenPnP process command line became unavailable')
    return pid


def verify_pid(pid, proc_root=Path('/proc')):
    path = proc_root / str(pid) / 'cmdline'
    try:
        cmdline = path.read_bytes()
    except OSError as exc:
        raise RuntimeError(f'OpenPnP PID {pid} exited before dispatch: {exc}') from exc
    if PROCESS_MARKER not in cmdline:
        raise RuntimeError(f'PID {pid} no longer identifies the expected OpenPnP process')


def iso_time_ms(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return int(parsed.timestamp() * 1000)
    except ValueError:
        return None


def folder_time_ms(path):
    match = re.search(r'(\d+)$', path.name)
    return int(match.group(1)) if match else None


def load_report(path):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def fresh_report_time(report, dispatch_ms, *keys):
    return any((stamp := iso_time_ms(report.get(key))) is not None and stamp > dispatch_ms
               for key in keys)


def file_is_new(path, dispatch_ms):
    try:
        return path.stat().st_mtime_ns // 1_000_000 > dispatch_ms
    except OSError:
        return False


def action_evidence(root, action, dispatch_ms, selected_ref=None):
    evidence = root / 'automation/evidence'
    if action == 'recover':
        for folder in sorted(evidence.glob('2026-09-23/release-recovery-*'), key=lambda p: folder_time_ms(p) or -1, reverse=True):
            stamp=folder_time_ms(folder)
            report=load_report(folder/'report.json')
            if stamp and stamp>dispatch_ms and report and report.get('stage')=='awaiting-release-review' and (folder/'after.png').is_file():
                return {'action':action,'status':'complete','path':str(folder),**report}
    elif action == 'index':
        base = evidence / '2026-09-23'
        candidates = sorted(base.glob('recheck-index-*'), key=lambda p: folder_time_ms(p) or -1, reverse=True)
        for folder in candidates:
            stamp = folder_time_ms(folder)
            state, image = folder / 'state.txt', folder / 'opening.png'
            if (stamp is None or stamp <= dispatch_ms or not state.is_file() or not image.is_file()
                    or not file_is_new(state, dispatch_ms) or not file_is_new(image, dispatch_ms)):
                continue
            try:
                content = state.read_text(errors='replace')
            except OSError:
                continue
            match = re.search(r'^Time:\s*(.+)$', content, re.MULTILINE)
            if match and (state_ms := iso_time_ms(match.group(1))) is not None and state_ms > dispatch_ms:
                return {'action': action, 'status': 'complete', 'path': str(folder),
                        'state': content.strip()}
    elif action == 'pick':
        for folder in sorted(evidence.glob('2026-09-23/pocket-pick-*'),
                             key=lambda p: folder_time_ms(p) or -1, reverse=True):
            stamp = folder_time_ms(folder)
            report_path = folder / 'report.json'
            report = load_report(report_path)
            if stamp is None or stamp <= dispatch_ms or report is None or not file_is_new(report_path, dispatch_ms):
                continue
            image = next((folder / n for n in ('picked.png', 'unsealed-under-vacuum.png')
                          if (folder / n).is_file() and file_is_new(folder / n, dispatch_ms)), None)
            picked_complete = (image is not None and image.name == 'picked.png'
                               and bool(report.get('nozzle'))
                               and report.get('captureExposure') is not None)
            unsealed_complete = (image is not None and image.name == 'unsealed-under-vacuum.png'
                                 and report.get('stage') == 'awaiting-unsealed-review'
                                 and report.get('vacuumHeldOn') is True)
            if not (picked_complete or unsealed_complete or bool(report.get('error'))):
                continue
            return {'action': action, 'status': 'complete', 'path': str(folder),
                    'stage': report.get('stage'),
                    'sealZ': report.get('sealZ'), 'emptyPressure': report.get('emptyPressure'),
                    'loadedPressure': report.get('loadedPressure'), 'unsealedPressure': report.get('unsealedPressure'),
                    'partialContactZ': report.get('partialContactZ'), 'detected': report.get('detected'),
                    'image': str(image) if image else None, 'error': report.get('error')}
    elif action == 'place':
        for folder in sorted(evidence.glob('selected-placement-*'),
                             key=lambda p: folder_time_ms(p) or -1, reverse=True):
            stamp = folder_time_ms(folder)
            report = load_report(folder / 'report.json')
            report_path = folder / 'report.json'
            if stamp is None or stamp <= dispatch_ms or report is None or not file_is_new(report_path, dispatch_ms):
                continue
            if selected_ref and report.get('referenceId') != selected_ref:
                continue
            restored = report.get('restoredVisionExposure') is not None
            completed = (report.get('stage') == 'awaiting-physical-review' and restored) or (bool(report.get('error')) and restored)
            if not completed:
                continue
            return {'action': action, 'status': 'complete', 'path': str(folder),
                    'referenceId': report.get('referenceId'), 'stage': report.get('stage'),
                    'afterPressure': report.get('afterPressure'), 'retained': report.get('retained'),
                    'restoredVisionExposure': report.get('restoredVisionExposure'),
                    'error': report.get('error')}
    elif action == 'record':
        if not selected_ref:
            return None
        path = Path('/tmp') / f'{selected_ref.lower()}-reviewed-saved.txt'
        try:
            is_new = path.is_file() and path.stat().st_mtime_ns // 1_000_000 > dispatch_ms
        except OSError:
            is_new = False
        if is_new:
            try:
                text = path.read_text(errors='replace').strip()
            except OSError:
                text = ''
            return {'action': action, 'status': 'complete', 'path': str(path), 'detail': text}
    elif action == 'center':
        for folder in sorted(evidence.glob('pocket-center-*'),
                             key=lambda p: folder_time_ms(p) or -1, reverse=True):
            stamp = folder_time_ms(folder)
            report = load_report(folder / 'report.json')
            image = folder / 'after-center.png'
            if (stamp is None or stamp <= dispatch_ms or not image.is_file()
                    or not file_is_new(image, dispatch_ms) or report is None):
                continue
            if report.get('stage') == 'awaiting-visual-review' and fresh_report_time(report, dispatch_ms, 'timeCompleted'):
                return {'action': action, 'status': 'complete', 'path': str(folder),
                        'stage': report.get('stage'), 'correctionMm': report.get('correctionMm'),
                        'cameraAfter': report.get('cameraAfter'), 'pickAfter': report.get('pickAfter'),
                        'image': str(image), 'error': report.get('error')}
    return None


def wait_for_action_evidence(root, action, dispatch_ms, selected_ref, wait_seconds):
    if wait_seconds == 0:
        return {'action': action, 'status': 'request-consumed', 'evidenceWait': 'disabled'}
    if action not in EVIDENCE_WAIT_ACTIONS:
        raise RuntimeError(f'--wait-seconds is supported only for {", ".join(sorted(EVIDENCE_WAIT_ACTIONS))}')
    deadline = time.monotonic() + wait_seconds
    while True:
        result = action_evidence(root, action, dispatch_ms, selected_ref)
        if result:
            return result
        if time.monotonic() >= deadline:
            return {'action': action, 'status': 'ongoing', 'timeoutSeconds': wait_seconds,
                    'message': 'No complete new evidence found; no retry was sent.'}
        time.sleep(min(0.2, max(0.0, deadline - time.monotonic())))


def selected_reference(root):
    path = root / 'automation/plans/selected-placement.json'
    try:
        plan = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    reference = plan.get('referenceId')
    return reference if isinstance(reference, str) and re.fullmatch(r'R\d+', reference) else None


PASTE_INSTALLATION_ACTIONS = {'paste-startup-quarantine', 'paste-waste-prime', 'paste-waste-prime-preview', 'paste-top-exposure', 'paste-bottom-exposure', 'paste-camera-led', 'paste-home-finalize', 'paste-reset-home', 'paste-reset-clearance', 'paste-reset-connect', 'paste-reset-invalidate', 'paste-model-state', 'paste-vacuum-probe', 'paste-b-config', 'paste-z-observe', 'paste-position-barrier', 'paste-error-latch', 'paste-vacuum-baseline', 'paste-survey-release', 'paste-prime-release', 'paste-prime-audit', 'paste-survey-audit', 'paste-survey', 'paste-measure', 'paste-connect-inspect', 'paste-state', 'paste-quarantine', 'paste-air'}


def check_paste_installation_lock(root, action):
    """Installation suspends legacy motion without changing calibrated workflows."""
    if action in PASTE_INSTALLATION_ACTIONS:
        return
    path = root / 'automation/paste/installation-lock.json'
    try:
        lock = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError('Paste installation lock missing/malformed; legacy reviewed actions blocked') from exc
    if not isinstance(lock, dict) or lock.get('schema') != 1 or lock.get('locked') is not False:
        raise RuntimeError('Paste installation is locked; legacy reviewed actions are blocked until installation and both-head clearance are reviewed')


def dispatch(action, confirmed, wait_seconds=0):
    if not confirmed:
        raise RuntimeError('explicit --confirmed acknowledgement is required')
    if not math.isfinite(wait_seconds) or not 0 <= wait_seconds <= 45:
        raise RuntimeError('--wait-seconds must be between 0 and 45')
    if wait_seconds and action not in EVIDENCE_WAIT_ACTIONS:
        raise RuntimeError(f'--wait-seconds is supported only for {", ".join(sorted(EVIDENCE_WAIT_ACTIONS))}')

    root = repo_root()
    check_paste_installation_lock(root, action)
    request = root / 'automation/plans/operator-command.json'
    bridge_error = root / 'automation/plans/bridge-error.txt'
    if request.exists():
        raise RuntimeError(f'an earlier operator request is still present; inspect it before retry: {request}')
    selected_ref = selected_reference(root) if wait_seconds and action in {'place', 'record'} else None
    if wait_seconds and action in {'place', 'record'} and selected_ref is None:
        raise RuntimeError('selected-placement.json has no valid referenceId for evidence matching')

    build, classes, agent_jar = ensure_bridge_built(root)
    java = tool_path('java')
    pid = discover_openpnp_pid()
    verify_pid(pid)
    bridge_error.unlink(missing_ok=True)
    dispatch_ms = int(time.time() * 1000)
    request.write_text(json.dumps({'action': action,
                                   'reviewed': True,
                                   'createdMs': dispatch_ms}, separators=(',', ':')) + '\n')

    command = [java, '--add-modules', 'jdk.attach', '-cp', str(classes),
               'DispatchReviewed', str(pid), str(agent_jar.resolve())]
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except Exception:
        # Leave the one-shot request for inspection; never issue an automatic retry.
        raise

    deadline = time.monotonic() + 5.0
    consumed = False
    while time.monotonic() < deadline:
        if not request.exists():
            consumed = True
            break
        if process.poll() not in (None, 0):
            out, err = process.communicate()
            raise RuntimeError(f'Java attach dispatcher failed (exit {process.returncode}): {err or out}')
        time.sleep(0.05)

    # Collect client-side attach errors if the JVM has already returned. This does
    # not wait for the queued OpenPnP machine task to complete.
    if process.poll() is not None:
        out, err = process.communicate()
        if process.returncode:
            raise RuntimeError(f'Java attach dispatcher failed (exit {process.returncode}): {err or out}')
    if bridge_error.is_file():
        details = bridge_error.read_text(errors='replace')
        raise RuntimeError('OpenPnP bridge reported an error:\n' + details)
    if not consumed:
        raise RuntimeError('OpenPnP did not consume the one-shot request within 5 seconds; inspect request/UI before retrying')
    result = wait_for_action_evidence(root, action, dispatch_ms, selected_ref, wait_seconds)
    result['pid'] = pid
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=ACTION_ALLOWLIST)
    parser.add_argument('--confirmed', action='store_true',
                        help='confirm dispatch of this allowlisted action into the live machine UI')
    parser.add_argument('--wait-seconds', type=float, default=0,
                        help='wait after request consumption for fresh completion evidence (0–45; default 0)')
    args = parser.parse_args()
    try:
        dispatch(args.action, args.confirmed, args.wait_seconds)
    except (RuntimeError, OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
