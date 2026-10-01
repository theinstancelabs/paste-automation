#!/usr/bin/env python3
"""Prepare a fresh, evidence-bound request for the model-only startup N2 restore.

This authorer reads an existing pure-model report and writes a request only. It
never opens OpenPnP, connects to a driver, or changes machine/configuration data.
"""
import argparse
import datetime
import hashlib
import json
import math
import uuid
from pathlib import Path

SCOPE = 'reviewed-startup-n2-manual-change-exclusion-restore'
REPORT_SCOPE = 'pure-model-state-no-controller-access'


def evidence(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def prepare(report_path, operator, review_basis, now_ms=None, request_id=None):
    report_path = Path(report_path).resolve(strict=True)
    report = json.loads(report_path.read_text())
    if report.get('scope') != REPORT_SCOPE:
        raise ValueError('source must be a pure-model/no-controller report')
    jvm = report.get('jvmStartMs')
    config = report.get('liveConfigurationSha256')
    if type(jvm) is not int or jvm <= 0 or not isinstance(config, str) or len(config) != 64 or any(c not in '0123456789abcdef' for c in config):
        raise ValueError('source JVM and live configuration hash required')
    captured = report.get('time')
    if not isinstance(captured, str):
        raise ValueError('source report capture time required')
    try:
        captured_ms = int(datetime.datetime.fromisoformat(captured.replace('Z', '+00:00')).timestamp() * 1000)
    except ValueError as exc:
        raise ValueError('invalid source report capture time') from exc
    if report.get('homed') is not False or report.get('busy') is not False:
        raise ValueError('source must show idle, unhomed startup')
    if type(report.get('enabled')) is not bool:
        raise ValueError('source enabled state must be explicit')
    drivers = report.get('drivers')
    if (not isinstance(drivers, list) or len(drivers) != 1
            or drivers[0].get('connected') is not False
            or drivers[0].get('motionPending') is not False):
        raise ValueError('source must show one disconnected driver with no pending motion')
    nozzles = report.get('nozzles')
    n2 = next((n for n in nozzles or [] if n.get('name') == 'N2'), None)
    if not n2 or n2.get('tip') is not None or n2.get('compatible') != 0 or n2.get('changer') is not False or n2.get('part') is not None:
        raise ValueError('source must show N2 already excluded and empty')
    if not operator.strip() or len(review_basis.strip()) < 30:
        raise ValueError('operator and substantive review basis are required')
    now_ms = now_ms if now_ms is not None else int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
    if type(now_ms) is not int or not math.isfinite(now_ms):
        raise ValueError('invalid request timestamp')
    if captured_ms > now_ms or now_ms - captured_ms > 300_000:
        raise ValueError('source report must be fresh within five minutes')
    return {
        'schema': 1,
        'scope': SCOPE,
        'id': request_id or str(uuid.uuid4()),
        'createdMs': now_ms,
        'jvmStartMs': jvm,
        'sourceCapturedMs': captured_ms,
        'operator': operator.strip(),
        'reviewBasis': review_basis.strip(),
        'action': 'unset-manual-nozzle-tip-change-location-only',
        'expectedEnabled': report['enabled'],
        'expectedHomed': False,
        'expectedBusy': False,
        'expectedDriverConnected': False,
        'expectedLiveConfigurationSha256': config,
        'sourceEvidence': evidence(report_path),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-report', required=True, help='fresh pure-model startup report')
    parser.add_argument('--operator', required=True)
    parser.add_argument('--review-basis', required=True)
    parser.add_argument('--output', required=True, help='new request path; refuses overwrite')
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise SystemExit('refusing to overwrite existing request')
    request = prepare(args.source_report, args.operator, args.review_basis)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(request, indent=2, allow_nan=False) + '\n')
    print(output)


if __name__ == '__main__':
    main()
