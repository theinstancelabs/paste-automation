#!/usr/bin/env python3
"""Write continuity evidence for an application restart without power cycling.

The output binds the prior terminal fast-camera position, a prior M114 rotary
count anchor, the new JVM startup source, completed native home, and post-home
read-only barrier. It does not contact OpenPnP or control the machine.
"""
import argparse
import datetime
import hashlib
import json
import uuid
from pathlib import Path

def ref(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def read(e):
    p = Path(e['path']).resolve(strict=True)
    if hashlib.sha256(p.read_bytes()).hexdigest() != e['sha256']:
        raise ValueError('evidence hash changed: ' + str(p))
    return json.loads(p.read_text())

def prepare(old_path, rotary_anchor_path, home_path, barrier_path, session_id,
            reviewed_by, review_basis, output, now_ms=None,
            historical_request_path=None, historical_proof_path=None):
    old_ref, anchor_ref, home_ref, barrier_ref = map(ref,
        (old_path, rotary_anchor_path, home_path, barrier_path))
    old, anchor, home, barrier = map(read,
        (old_ref, anchor_ref, home_ref, barrier_ref))
    now_ms = now_ms if now_ms is not None else int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
    if not session_id.strip() or not reviewed_by.strip() or len(review_basis.strip()) < 40:
        raise ValueError('session, reviewer, and substantive continuity review required')
    if old.get('scope') != 'camera-only-registered-fast-inspection' or old.get('status') != 'executor-quarantined-after-uncertain-failure':
        raise ValueError('exact terminal fast-camera report required')
    old_req = old.get('request', {})
    if old_req.get('mode') != 'registered-references' or old.get('motionSubmitted') is not True or old.get('controllerPositionVerified') is not True or old.get('uncertainCompletion') is not False or old.get('nativeMotionCompletionReported') is not True or old.get('error') != 'Error: Existing top camera stream is not open':
        raise ValueError('old fast-camera report must have verified endpoint and exact camera capture failure')
    old_jvm, config = old_req.get('jvmStartMs'), old_req.get('liveConfigurationSha256')
    if type(old_jvm) is not int or len(config or '') != 64:
        raise ValueError('old JVM/configuration identity missing')
    if home.get('status') != 'completed-native-home-enabled-awaiting-image-review' or home.get('uncertainCompletion') is not False or home.get('controllerPositionVerified') is not True or home.get('nativeMotionCompletionReported') is not True or home.get('rotationUnchangedVerified') is not True or home.get('diskUnchanged') is not True:
        raise ValueError('successful same-JVM native home evidence required')
    home_req = home.get('request', {})
    startup_ref = home_req.get('sourceEvidence')
    if home_req.get('mode') != 'fresh-startup-home' or home_req.get('homeReason') != 'user-requested-home-after-application-restart' or not startup_ref:
        raise ValueError('home must bind a fresh application-restart startup snapshot')
    startup = read(startup_ref)
    new_jvm = startup.get('jvmStartMs')
    if type(new_jvm) is not int or new_jvm <= old_jvm or startup.get('scope') != 'pure-model-state-no-controller-access':
        raise ValueError('new startup JVM must advance from prior application')
    if home.get('liveConfigurationSha256') != config or home_req.get('liveConfigurationSha256') != config or startup.get('liveConfigurationSha256') != config:
        raise ValueError('live configuration changed across restart/home')
    if barrier.get('status') != 'completed-read-only-position-barrier' or barrier.get('uncertainCompletion') is not False or barrier.get('controllerPositionVerified') is not True or barrier.get('noMotionCommandSubmitted') is not True:
        raise ValueError('completed no-motion post-home position barrier required')
    b_req = barrier.get('request', {})
    inst = b_req.get('installerEvidence', {})
    if b_req.get('jvmStartMs') != new_jvm or b_req.get('liveConfigurationSha256') != config or inst.get('path') != home_ref['path'] or inst.get('sha256') != home_ref['sha256']:
        raise ValueError('post-home barrier must bind exact home report and same JVM/configuration')
    if not Path(output).parent.exists():
        Path(output).parent.mkdir(parents=True, exist_ok=True)
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('refusing to overwrite continuity record')
    record = {
        'schema': 1, 'scope': 'same-session-application-restart-continuity',
        'sessionId': session_id, 'liveConfigurationSha256': config,
        'reviewedBy': reviewed_by.strip(), 'reviewBasis': review_basis.strip(),
        'reviewedMs': now_ms, 'noControllerPowerCycleOrManualBDisplacement': True,
        'transitions': [{
            'oldJvmStartMs': old_jvm, 'newJvmStartMs': new_jvm,
            'oldPositionEvidence': old_ref, 'rotaryCountAnchorEvidence': anchor_ref,
            'startupModelEvidence': startup_ref, 'homeEvidence': home_ref,
            'postHomeBarrierEvidence': barrier_ref,
        }],
    }
    if bool(historical_request_path) != bool(historical_proof_path):
        raise ValueError('historical request and continuation proof must be supplied together')
    if historical_request_path:
        request_ref, proof_ref = map(ref, (historical_request_path, historical_proof_path))
        request, proof = map(read, (request_ref, proof_ref))
        if request.get('sessionId') != session_id or request.get('liveConfigurationSha256') != config or request.get('jvmStartMs') != proof.get('currentJvmStartMs') or request.get('manualHomeLedgerAnchorEvidence') != proof_ref:
            raise ValueError('historical request must hash-bind the matching continuation proof and session/configuration')
        record['historicalBudgetAnchorContinuity'] = {
            'requestEvidence': request_ref, 'proofEvidence': proof_ref,
        }
    output.write_text(json.dumps(record, indent=2, allow_nan=False) + '\n')
    app_ref = {'path': str(output), 'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
               'sessionId': session_id, 'newJvmStartMs': new_jvm,
               'liveConfigurationSha256': config,
               'allowedJvmStartMs': [old_jvm, new_jvm]}
    ref_path = output.with_name(output.stem + '-applicationRestartEvidence.json')
    if ref_path.exists():
        raise FileExistsError('refusing to overwrite applicationRestartEvidence reference')
    ref_path.write_text(json.dumps(app_ref, indent=2, allow_nan=False) + '\n')
    return output, ref_path

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--old-camera-report', required=True)
    p.add_argument('--rotary-count-anchor-report', required=True)
    p.add_argument('--home-report', required=True)
    p.add_argument('--post-home-barrier-report', required=True)
    p.add_argument('--session-id', required=True)
    p.add_argument('--reviewed-by', required=True)
    p.add_argument('--review-basis', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--historical-continuation-request')
    p.add_argument('--historical-continuation-proof')
    a = p.parse_args()
    record, ref_path = prepare(a.old_camera_report, a.rotary_count_anchor_report,
                               a.home_report, a.post_home_barrier_report,
                               a.session_id, a.reviewed_by, a.review_basis, a.output,
                               historical_request_path=a.historical_continuation_request,
                               historical_proof_path=a.historical_continuation_proof)
    print(record)
    print(ref_path)

if __name__ == '__main__':
    main()
