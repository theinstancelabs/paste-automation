#!/usr/bin/env python3
"""Preview by default; execute a reviewed constant-Z route through existing paste-survey actions."""
import argparse
import copy
import fcntl
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('survey_prepare', Path(__file__).with_name('prepare-survey-request.py'))
prepare = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prepare)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def milliseconds():
    return time.time_ns() // 1_000_000


def read_bound(path, expected):
    data = Path(path).resolve(strict=True).read_bytes()
    if not isinstance(expected, str) or digest(data) != expected:
        raise ValueError('Bound source bytes changed')
    return data


def plan(spec, now=None):
    now = milliseconds() if now is None else now
    if (not isinstance(spec, dict) or type(spec.get('schema')) is not int or spec.get('schema') != 1
            or spec.get('scope') != 'reviewed-constant-Z-XY-survey-route'
            or not isinstance(spec.get('id'), str) or not prepare.re.fullmatch(prepare.UUID_PATTERN, spec['id'])
            or spec.get('reviewedEntireCorridor') is not True
            or not isinstance(spec.get('operator'), str) or not spec['operator'].strip()):
        raise ValueError('Explicit named operator, route UUID and full-corridor review required')
    source = json.loads(read_bound(spec['sourceReport'], spec['sourceSha256']))
    kind, jvm, config, raw, driver, poses = prepare.source_snapshot(source)
    if kind == 'successful-stop-audit':
        raise ValueError('A stop audit cannot authorize an automatic route')
    image = spec['corridorEvidence']
    read_bound(image['path'], image['sha256'])
    # The existing preparer establishes actual file mtime/image format and source state.
    sample, provenance = prepare.prepare(spec['sourceReport'], image['path'], spec['operator'], True, now, 'X', 1)
    if sample['corridorEvidence'] != image:
        raise ValueError('Image hash/path/actual capture mtime differs from full-route evidence')
    if provenance['sourceSha256'] != spec['sourceSha256'] or sample['jvmStartMs'] != jvm or sample['liveConfigurationSha256'] != config or sample['expectedRaw'] != raw:
        raise ValueError('Source changed during planning')
    points = spec.get('waypoints')
    if not isinstance(points, list) or not 1 <= len(points) <= 32:
        raise ValueError('One to 32 explicit one-axis waypoints required')
    cursor, steps, distance = dict(raw), [], 0.0
    for point in points:
        if not isinstance(point, dict) or set(point) != {'axis', 'targetMm'} or point['axis'] not in ('X', 'Y'):
            raise ValueError('Each waypoint has exactly one X or Y axis and targetMm')
        axis, target = point['axis'], prepare.finite(point['targetMm'], 'waypoint target')
        delta = target - cursor[axis]
        if delta == 0:
            raise ValueError('No-op waypoint is not a reviewed step')
        distance += abs(delta)
        if distance > 240 + 1e-9:
            raise ValueError('Route exceeds 240 mm total travel')
        # Leave room for native report rounding without ever requesting >10 mm.
        count = math.ceil(abs(delta) / 9.9)
        start = cursor[axis]
        for index in range(1, count + 1):
            end = target if index == count else start + delta * index / count
            before = dict(cursor)
            cursor[axis] = end
            steps.append({'axis': axis, 'targetMm': end, 'before': before, 'after': dict(cursor)})
            if len(steps) > 32:
                raise ValueError('Route exceeds 32 bounded survey steps')
    return {'schema': 1, 'id': spec['id'], 'steps': steps, 'distanceMm': distance,
            'jvmStartMs': jvm, 'liveConfigurationSha256': config, 'startRaw': raw,
            'fixedAxes': {k: raw[k] for k in ('Z', 'A', 'B')}, 'startNativePoses': poses, 'corridorEvidence': image,
            'expiresMs': image['capturedMs'] + 300000, 'dispatchPerformed': False}


def verify_state(source, route, expected):
    kind, jvm, config, raw, driver, poses = prepare.source_snapshot(source)
    if kind == 'successful-stop-audit' or jvm != route['jvmStartMs'] or config != route['liveConfigurationSha256']:
        raise ValueError('Route session/configuration changed')
    for axis in prepare.AXES:
        tolerance = .3 if axis in ('A', 'B') else .02
        raw_tolerance = .0001 if axis in ('Z', 'A', 'B') else .02
        if abs(raw[axis] - expected[axis]) > raw_tolerance or abs(driver[axis] - expected[axis]) > tolerance:
            raise ValueError(f'Route position changed on {axis}')
    for name, pose in poses.items():
        for key in ('z', 'rotation'):
            if abs(pose[key] - route['startNativePoses'][name][key]) > .0001:
                raise ValueError('Route native head/camera clearance changed')
    return raw, driver, poses


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def native_dispatch(root):
    if Path(root).resolve() != Path('/home/lumen/lumenpnp'):
        raise RuntimeError('Physical dispatch is restricted to the canonical automation repository')
    return subprocess.run([sys.executable, str(root/'automation/scripts/run_reviewed_action.py'), 'paste-survey', '--confirmed'],
                          capture_output=True, text=True, timeout=15, check=True).stdout


def await_terminal(path, deadline_ms, now=milliseconds):
    while now() < deadline_ms:
        if path.exists():
            try:
                data = path.read_bytes()
                report = json.loads(data)
            except (json.JSONDecodeError, UnicodeDecodeError):
                time.sleep(.1)
                continue
            status = str(report.get('status', ''))
            if report.get('error') or status.startswith(('failed', 'enqueue-failed')):
                raise RuntimeError('Native survey failed; no next step or retry')
            if status == prepare.SUCCESS:
                return data
        time.sleep(.1)
    raise TimeoutError('Survey terminal report timeout; last command may still be running; no retry/recovery')


def execute(spec, root=ROOT, dispatch=native_dispatch, wait=await_terminal, now=milliseconds):
    root = Path(root)
    route = plan(spec, now())
    private = root/'.local-machine-backups'
    if not private.is_dir():
        raise ValueError('Private lock directory missing')
    with (private/'paste-survey-route.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        out = root/'automation/evidence'/('paste-survey-route-' + spec['id'])
        out.mkdir()  # Exclusive UUID claim, including failed routes.
        record = {'schema': 1, 'id': spec['id'], 'status': 'claimed', 'spec': spec, 'route': route,
                  'steps': [], 'commandedDistanceMm': 0.0, 'noReplay': True, 'physicalAcceptanceEstablished': False}
        save(out/'report.json', record)
        source_path, source_hash = Path(spec['sourceReport']), spec['sourceSha256']
        request_path = root/'automation/plans/paste-survey-request.json'
        try:
            for index, step in enumerate(route['steps']):
                if now() >= route['expiresMs']:
                    raise TimeoutError('Full-route corridor evidence expired')
                source_data = read_bound(source_path, source_hash)
                raw, _, _ = verify_state(json.loads(source_data), route, step['before'])
                q, provenance = prepare.prepare(source_path, route['corridorEvidence']['path'], spec['operator'], True,
                                                now(), step['axis'], step['targetMm'] - raw[step['axis']])
                if provenance['sourceSha256'] != source_hash or q['corridorEvidence'] != route['corridorEvidence']:
                    raise ValueError('Source or full-route evidence changed')
                if (root/'automation/plans/operator-command.json').exists():
                    raise RuntimeError('Another dispatcher request exists')
                # Never overwrite an unknown/uncompleted survey request.
                if request_path.exists():
                    old_data = request_path.read_bytes()
                    old = json.loads(old_data)
                    if not isinstance(old.get('id'), str) or not prepare.re.fullmatch(prepare.UUID_PATTERN, old['id']):
                        raise ValueError('Existing request identity invalid')
                    old_report = root/'automation/evidence'/('paste-survey-' + old['id'])/'report.json'
                    old_result = json.loads(old_report.read_bytes())
                    if old_result.get('status') != prepare.SUCCESS or old_result.get('request') != old:
                        raise ValueError('Existing survey request is not verified completed')
                    prepare.source_snapshot(old_result)
                    (out/f'prior-request-{index:02}.json').write_bytes(old_data)
                    if request_path.read_bytes() != old_data:
                        raise ValueError('Existing request changed while archiving')
                    request_path.unlink()
                prepare.write_request(request_path, q)
                request_data = request_path.read_bytes()
                (out/f'request-{index:02}.json').write_bytes(request_data)
                entry = {'index': index, 'requestId': q['id'], 'requestSha256': digest(request_data),
                         'sourceReport': str(source_path), 'sourceSha256': source_hash, 'planned': step,
                         'status': 'dispatching-once'}
                record['steps'].append(entry); record['status'] = 'running'; save(out/'report.json', record)
                if now() >= route['expiresMs'] or record['commandedDistanceMm'] + abs(q['deltaMm']) > 240 + 1e-9:
                    raise RuntimeError('Route time/distance budget exhausted before dispatch')
                record['commandedDistanceMm'] += abs(q['deltaMm']);entry['dispatchAttempted'] = True;save(out/'report.json', record)
                entry['dispatcherOutput'] = dispatch(root)
                report_path = root/'automation/evidence'/('paste-survey-' + q['id'])/'report.json'
                terminal_data = wait(report_path, min(route['expiresMs'], now() + 75000), now)
                terminal = json.loads(terminal_data)
                if terminal.get('id') != q['id'] or terminal.get('request') != q or terminal.get('status') != prepare.SUCCESS:
                    raise ValueError('Unexpected terminal survey identity')
                verify_state(terminal, route, step['after'])
                entry.update(status='verified-terminal', report=str(report_path), reportSha256=digest(terminal_data))
                save(out/'report.json', record)
                source_path, source_hash = report_path, digest(terminal_data)
            record['status'] = 'completed-route-awaiting-image-review'
        except Exception as exc:
            record.update(status='failed-no-retry-no-recovery', error=str(exc), completionUncertain=True)
            save(out/'report.json', record)
            raise
        save(out/'report.json', record)
        return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('route_spec', type=Path)
    parser.add_argument('--execute', action='store_true', help='Dispatch this explicitly reviewed complete route once')
    args = parser.parse_args()
    try:
        spec = json.loads(args.route_spec.read_bytes())
        result = execute(spec) if args.execute else plan(spec)
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
