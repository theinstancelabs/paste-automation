#!/usr/bin/env python3
"""Read the existing owner's position after an operator-confirmed manual home.

Does not home, move, extrude, reconnect, or restore quarantine. Native guards
require the current machine to be idle, homed, and already quarantined.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]

def ensure_model_idle(model):
    if model.get('busy') is True:
        raise RuntimeError('Fresh model state reports the machine busy; wait for the native task to finish, then capture again')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operator-home-confirmed', action='store_true', required=True)
    parser.add_argument('--manual-jog-completion-confirmed', action='store_true', help='Explicitly wait for an already-issued manual jog using native M400 only before querying position; no new move')
    args = parser.parse_args()
    started = time.time_ns()
    subprocess.run(['python3', str(ROOT/'automation/scripts/run_reviewed_action.py'),
                    'paste-model-state', '--confirmed'], check=True, capture_output=True)
    deadline = time.monotonic()+10
    while True:
        fresh = [p for p in (ROOT/'.local-machine-backups').glob('paste-live-model-state-*/report.json')
                 if p.stat().st_mtime_ns >= started]
        if fresh:
            source = max(fresh, key=lambda p:p.stat().st_mtime_ns)
            model = json.loads(source.read_text())
            ensure_model_idle(model)
            break
        if time.monotonic() >= deadline:
            raise RuntimeError('No fresh model report; inspect bridge-error.txt, do not replay motion')
        time.sleep(.1)
    request = dict(schema=1, scope='read-only-native-position-barrier', id=str(uuid.uuid4()),
                   createdMs=time.time_ns()//1_000_000, jvmStartMs=model['jvmStartMs'],
                   operator='Root: operator confirmed manual home; verify position without motion',
                   manualHomeAcknowledgement=True, reviewedReadOnlyQuery=True,
                   manualJogCompletionAcknowledgement=args.manual_jog_completion_confirmed,
                   liveConfigurationSha256=model['liveConfigurationSha256'],
                   installerEvidence={'path':str(source.resolve()),'sha256':hashlib.sha256(source.read_bytes()).hexdigest()},
                   expectedRaw={a['letter']:a['raw'] for a in model['axes']},
                   expectedDriver={a['letter']:a['driver'] for a in model['axes']},
                   expectedNativePoses=model['nativePoses'])
    (ROOT/'automation/plans/paste-position-barrier-request.json').write_text(json.dumps(request,indent=2)+'\n')
    spec=importlib.util.spec_from_file_location('observe_z',Path(__file__).with_name('observe-z-step.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    report=ROOT/f"automation/evidence/paste-position-barrier-{request['id']}/report.json"
    module.dispatch('paste-position-barrier',report)
    print(report)

if __name__ == '__main__':
    main()
