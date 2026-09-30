#!/usr/bin/env python3
"""Read-only ownership check for the identified Marlin USB device; never opens it."""
import json
from pathlib import Path
import re
import subprocess

DEVICE = Path('/dev/serial/by-id/usb-STMicroelectronics_MARLIN_OPULO_LUMEN_REV5_CDC_in_FS_Mode_387932683335-if00')


def classify_probe(returncode, stdout, stderr):
    """fuser writes PIDs to stdout, its human table/errors to stderr."""
    if returncode == 1 and not stdout.strip() and not stderr.strip():
        return 'unowned', []
    pids = stdout.split()
    if returncode == 0 and pids and all(re.fullmatch(r'\d+', pid) for pid in pids):
        return 'owned', sorted(set(map(int, pids)))
    return 'inconclusive', []


def inspect():
    report = {'deviceById': str(DEVICE), 'readOnly': True, 'serialOpened': False}
    if not DEVICE.is_symlink():
        return {**report, 'status': 'missing-device'}, 3
    try:
        target = DEVICE.resolve(strict=True)
    except OSError:
        return {**report, 'status': 'missing-device'}, 3
    if not re.fullmatch(r'/dev/ttyACM\d+', str(target)):
        return {**report, 'status': 'unexpected-device-target'}, 3
    report['resolvedDevice'] = str(target)
    try:
        result = subprocess.run(['/usr/bin/fuser', '-v', str(target)], capture_output=True, text=True, timeout=3, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return {**report, 'status': 'ownership-probe-failed'}, 3
    try:
        if DEVICE.resolve(strict=True) != target:
            return {**report, 'status': 'device-changed'}, 3
    except OSError:
        return {**report, 'status': 'device-changed'}, 3
    status, pids = classify_probe(result.returncode, result.stdout, result.stderr)
    owners = []
    for pid in pids:
        try:
            # comm contains a process name only; never expose process arguments,
            # environment, browser URL, or page contents.
            name = (Path('/proc') / str(pid) / 'comm').read_text().strip()[:64]
        except OSError:
            name = 'exited-or-unavailable'
        owners.append({'pid': pid, 'processName': name})
    report.update(status=status, owners=owners)
    report['meaning'] = ('No owner observed at this instant; native script repeats its own check immediately before connect.'
                         if status == 'unowned' else 'Do not connect OpenPnP; resolve the existing owner or inconclusive probe first.')
    return report, {'unowned': 0, 'owned': 2, 'inconclusive': 3}[status]


if __name__ == '__main__':
    report, code = inspect()
    print(json.dumps(report, indent=2))
    raise SystemExit(code)
