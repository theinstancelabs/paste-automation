#!/usr/bin/env python3
"""Review/execute an exclusive EMEET still capture and restore its known preview.

Default is read-only preflight. --execute briefly stops ONLY the validated preview.
No OpenPnP, serial, motor, or top/bottom camera interfaces are used.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import shlex
import signal
import subprocess
import tempfile
import time

ROOT = Path('/home/lumen/lumenpnp')
DEVICE = Path('/dev/v4l/by-id/usb-EMEET_EMEET_SmartCam_C960_A260311000111730-video-index0')
GST = '/usr/bin/gst-launch-1.0'
SESSION = 'lumen-webcam'
PREVIEW = [GST, 'v4l2src', f'device={DEVICE}', '!', 'image/jpeg,width=640,height=480,framerate=30/1', '!', 'jpegdec', '!', 'videoconvert', '!', 'ximagesink', 'sync=false']


def capture_command(directory):
    return [GST, '-e', 'v4l2src', f'device={DEVICE}', 'num-buffers=12', '!',
            'image/jpeg,width=1920,height=1080,framerate=30/1', '!', 'multifilesink',
            f'location={Path(directory) / "frame-%02d.jpg"}', 'next-file=buffer']


def validate_preview(executable, argv, environment, held_devices, resolved_device):
    if executable != GST or argv[1:] != PREVIEW[1:] or Path(argv[0]).name != 'gst-launch-1.0':
        raise ValueError('Preview executable/arguments differ from the exact audited EMEET pipeline')
    if held_devices != {resolved_device}:
        raise ValueError('Preview must hold only the expected EMEET video device')
    if not environment.get('DISPLAY') or not environment.get('XAUTHORITY'):
        raise ValueError('Preview lacks observed DISPLAY/XAUTHORITY; never guess replacements')
    return {key: environment[key] for key in ('DISPLAY', 'XAUTHORITY')}


def owners(device):
    result = subprocess.run(['/usr/bin/fuser', str(device)], capture_output=True, text=True, timeout=5)
    if result.returncode not in (0, 1):
        raise ValueError('Cannot establish exclusive USB video ownership')
    diagnostic = result.stderr.strip()
    if diagnostic and diagnostic != str(device) + ':':
        raise ValueError('Unexpected owner-probe diagnostic')
    if result.returncode == 1 and result.stdout.strip():
        raise ValueError('Inconsistent owner-probe response')
    return {int(v) for v in result.stdout.split()}


def inspect_preview(pid):
    proc = Path('/proc') / str(pid)
    argv = [x.decode() for x in (proc / 'cmdline').read_bytes().split(b'\0') if x]
    env = dict(x.decode().split('=', 1) for x in (proc / 'environ').read_bytes().split(b'\0') if b'=' in x)
    held = set()
    for fd in (proc / 'fd').iterdir():
        try:
            link = os.readlink(fd)
        except FileNotFoundError:
            continue
        if link.startswith('/dev/video'):
            held.add(link)
    device = str(DEVICE.resolve(strict=True))
    display_env = validate_preview(os.readlink(proc / 'exe'), argv, env, held, device)
    if not Path(display_env['XAUTHORITY']).is_file():
        raise ValueError('Observed XAUTHORITY file unavailable')
    if owners(device) != {pid}:
        raise ValueError('Expected preview is not the sole EMEET owner')
    panes = subprocess.check_output(['/usr/bin/tmux', 'list-panes', '-t', SESSION,
                                      '-F', '#{pane_pid} #{pane_dead}'], text=True, timeout=5).splitlines()
    # Existing shell pane invokes the exact gst child; either direct or one parent.
    ppid = int(next(x for x in (proc / 'status').read_text().splitlines() if x.startswith('PPid:')).split()[1])
    if len(panes) != 1 or panes[0] not in (f'{pid} 0', f'{ppid} 0'):
        raise ValueError('Known preview is not the sole live lumen-webcam pane process/child')
    return display_env, device


def restore_preview(env, device):
    if owners(device):
        raise ValueError('Cannot restore preview: another owner holds EMEET')
    # Original shell/pane normally exits after gst. Never kill/replace a live pane.
    deadline = time.monotonic() + 3
    while subprocess.run(['/usr/bin/tmux', 'has-session', '-t', SESSION], capture_output=True).returncode == 0:
        if time.monotonic() > deadline:
            raise ValueError('Existing lumen-webcam session remains; refusing to replace it')
        time.sleep(0.1)
    command = 'exec ' + shlex.join(PREVIEW)
    subprocess.run(['/usr/bin/tmux', 'new-session', '-d', '-s', SESSION, '-c', str(ROOT),
                    '-e', 'DISPLAY=' + env['DISPLAY'], '-e', 'XAUTHORITY=' + env['XAUTHORITY'], command], check=True, timeout=5)
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        pids = owners(device)
        if len(pids) == 1:
            restored = next(iter(pids))
            inspect_preview(restored)
            return restored
        time.sleep(0.1)
    raise ValueError('Restored preview did not acquire the expected EMEET device')


def execute(pid, output):
    from PIL import Image
    output = Path(output)
    if output.exists() or not output.parent.is_dir() or output.suffix.lower() not in ('.jpg', '.jpeg'):
        raise ValueError('Output must be a new JPEG path in an existing directory')
    # pidfd binds the signal to this exact process, not a recycled numeric PID.
    fd = os.pidfd_open(pid)
    report = {'scope': 'EMEET-overview-still-only', 'previewPid': pid, 'previewStopped': False,
              'captureSaved': False, 'previewRestored': False}
    try:
        env, device = inspect_preview(pid)
        signal.pidfd_send_signal(fd, signal.SIGTERM)
        report['previewStopped'] = True
        if not select.select([fd], [], [], 5)[0]:
            raise ValueError('Known preview did not stop; no escalation or broad kill')
        if owners(device):
            raise ValueError('EMEET still owned after preview exit')
        started_ms = time.time_ns() // 1_000_000
        with tempfile.TemporaryDirectory(prefix='emeeet-overview-') as temporary:
            subprocess.run(capture_command(temporary), check=True, capture_output=True, timeout=20)
            frame = Path(temporary) / 'frame-11.jpg'
            with Image.open(frame) as im:
                im.load()
                if im.size != (1920, 1080) or im.format != 'JPEG':
                    raise ValueError('Capture did not produce a full-HD JPEG')
            data = frame.read_bytes()
            with output.open('xb') as stream:
                stream.write(data)
            report.update(captureSaved=True, output=str(output.resolve()), width=1920, height=1080,
                          framesDiscarded=11, captureStartedMs=started_ms,
                          capturedMs=time.time_ns() // 1_000_000, sha256=hashlib.sha256(data).hexdigest())
    except Exception as exc:
        report['error'] = str(exc)
    finally:
        if report['previewStopped']:
            try:
                report['restoredPreviewPid'] = restore_preview(env, device)
                report['previewRestored'] = True
            except Exception as exc:
                report['restoreError'] = str(exc)
        os.close(fd)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview-pid', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.execute:
        report = execute(args.preview_pid, args.output)
    else:
        env, device = inspect_preview(args.preview_pid)
        report = {'dryRun': True, 'expectedPreviewPid': args.preview_pid, 'device': device,
                  'displayEnvironmentObserved': sorted(env), 'captureCommand': capture_command('<temporary>'),
                  'output': str(args.output), 'previewStopped': False}
    print(json.dumps(report, indent=2))
    if args.execute and not (report['captureSaved'] and report['previewRestored']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
