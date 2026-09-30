#!/usr/bin/env python3
"""One manually observed 100-degree prime continuation; no loops or retries."""
import argparse
import hashlib
import json
import pathlib
import subprocess
import time
import urllib.request
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(path.read_text())


def bound(path):
    path = path.resolve()
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('previous_report', type=pathlib.Path)
    parser.add_argument('reviewed_image', type=pathlib.Path)
    parser.add_argument('--result', required=True,
                        choices=['no-visible-paste', 'emerging-not-consistent'])
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    report = read(args.previous_report)
    if (report.get('status') != 'completed-waste-prime-awaiting-observation'
            or report.get('controllerPositionVerified') is not True
            or report.get('countsVerified') is not True
            or report.get('uncertainCompletion') is not False):
        raise ValueError('Previous physical increment lacks verified terminal completion')
    request = report['request']
    ledger_path = ROOT / 'automation/evidence/paste-waste-prime-session/ledger.json'
    ledger = read(ledger_path)
    ledger_evidence = bound(ledger_path)
    if (ledger['status'] != 'verified'
            or ledger_evidence['sha256'] != report['completedLedgerSha256']
            or ledger['entries'][-1]['requestId'] != report['id']
            or ledger['profileSha256'] != request['profileEvidence']['sha256']
            or ledger['sessionId'] != request['sessionId']):
        raise ValueError('Current durable ledger does not match previous terminal report')
    profile_path = pathlib.Path(request['profileEvidence']['path'])
    if bound(profile_path)['sha256'] != request['profileEvidence']['sha256']:
        raise ValueError('Original profile changed')
    profile = read(profile_path)
    now = int(time.time() * 1000)
    if not 0 <= now - args.reviewed_image.stat().st_mtime_ns // 1_000_000 < 300_000:
        raise ValueError('Fresh reviewed outlet/receiver image required')
    charged = ledger['reservedDegrees']
    if charged < 340 or (charged - 340) % 100 or charged + 100 > 2000:
        raise ValueError('Next100-degree step outside reviewed cumulative bound')
    if not args.execute:
        print(json.dumps({'dispatch': False, 'degrees': 100,
                          'previousReservedDegrees': charged,
                          'nextReservedDegrees': charged + 100,
                          'nextB': ledger['lastVerifiedB'] - 100}))
        return
    out = ROOT / 'automation/evidence' / ('paste-observed-step-' + str(uuid.uuid4()))
    out.mkdir()
    amendment = {
        'schema': 1, 'scope': 'single-waste-prime-budget-extension',
        'sessionId': request['sessionId'],
        'profileSha256': request['profileEvidence']['sha256'],
        'jvmStartMs': request['jvmStartMs'],
        'liveConfigurationSha256': request['liveConfigurationSha256'],
        'syringeId': profile['syringeId'], 'originalMaximumDegrees': 300,
        'previousReservedDegrees': charged, 'extendedMaximumDegrees': charged + 100,
        'additionalDegrees': 100, 'previousLedgerSha256': ledger_evidence['sha256'],
        'previousReportEvidence': bound(args.previous_report),
        'userAuthorizedSingleIncrement': True,
        'authorizationRecord': 'User directed: keep turning until paste extrudes; each increment requires a fresh manual image review.',
        'operator': 'codex-parent', 'reviewedMs': now,
    }
    amendment_path = out / 'budget-amendment.json'
    amendment_path.write_text(json.dumps(amendment, indent=2) + '\n')
    result = subprocess.run([
        'python3', str(ROOT / 'automation/paste/continue-waste-prime.py'),
        str(args.previous_report.resolve()), str(args.reviewed_image.resolve()),
        '--result', args.result, '--degrees', '100',
        '--budget-amendment', str(amendment_path), '--execute',
    ], cwd=ROOT, capture_output=True, text=True)
    (out / 'continuation.stdout').write_text(result.stdout)
    (out / 'continuation.stderr').write_text(result.stderr)
    if result.returncode:
        raise RuntimeError('Continuation failed or completion uncertain. Do not replay; inspect ' + str(out))
    terminal = json.loads(result.stdout.strip().splitlines()[-1])
    print(json.dumps({'report': terminal['report'], 'status': terminal['status'],
                      'reservedDegrees': terminal['reservedDegrees']}), flush=True)
    # Viewer is a separate existing reader. Never open the USB camera or serial port.
    # Let its 1Hz cache refresh after the terminal report before saving one frame.
    time.sleep(1.2)
    token = (ROOT / '.local-viewer/token').read_text().strip()
    request_image = urllib.request.Request('http://127.0.0.1:8765/frame/webcam',
                                           headers={'Authorization': 'Bearer ' + token})
    with urllib.request.urlopen(request_image, timeout=10) as response:
        frame = response.read()
    if not frame.startswith(b'\xff\xd8'):
        raise RuntimeError('Post-step viewer image unavailable; inspect terminal report before further motion')
    after_image = out / 'after-webcam.jpg'
    after_image.write_bytes(frame)
    print(json.dumps({'report': terminal['report'], 'afterImage': str(after_image),
                      'freshManualReviewRequired': True}))


if __name__ == '__main__':
    main()
