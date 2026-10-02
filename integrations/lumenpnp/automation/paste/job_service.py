#!/usr/bin/env python3
"""Server-side storage and orchestration for reviewed paste jobs.

Planning and status are offline/read-only. OpenPnP actions are explicit methods
and are delegated to the existing once-only prepared-batch runner.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREPARER = ROOT / 'automation/paste/prepare-contiguous-batch.py'
RUNNER = ROOT / 'automation/paste/run-prepared-contiguous-batch.py'
JOB_ID = re.compile(r'^[a-f0-9]{64}$')
UUID = re.compile(r'^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$')


def _json(path):
    return json.loads(Path(path).read_bytes())


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class PasteJobService:
    """Owns immutable CAD plans and server-bound prepared native artifacts."""
    def __init__(self, jobs_dir=None, root=ROOT, invoke=subprocess.run, clock=time.time):
        self.root = Path(root).resolve()
        self.jobs_dir = Path(jobs_dir or self.root / '.local-machine-backups/paste-jobs').resolve()
        self.jobs_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.invoke = invoke
        self.clock = clock

    def _job(self, job_id):
        if not isinstance(job_id, str) or not JOB_ID.fullmatch(job_id):
            raise ValueError('Invalid stored job identifier')
        directory = (self.jobs_dir / job_id).resolve(strict=True)
        if directory.parent != self.jobs_dir:
            raise ValueError('Job escaped server storage')
        job = _json(directory / 'job.json')
        if hashlib.sha256((json.dumps(job, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()).hexdigest() != job_id:
            raise ValueError('Stored job content hash mismatch')
        return directory, job

    def plan_upload(self, board_bytes, options):
        """Plan and persist a board upload; never invokes the OpenPnP bridge."""
        from importlib.util import module_from_spec, spec_from_file_location
        spec = spec_from_file_location('lumen_job_planner', Path(__file__).with_name('job_planner.py'))
        planner = module_from_spec(spec)
        spec.loader.exec_module(planner)
        if not isinstance(board_bytes, (bytes, bytearray)) or not board_bytes or len(board_bytes) > 32 * 1024 * 1024:
            raise ValueError('Board upload must be nonempty and at most 32 MiB')
        job = planner.plan_board(bytes(board_bytes), **dict(options))
        encoded = json.dumps(job, indent=2, sort_keys=True, allow_nan=False).encode() + b'\n'
        ident = hashlib.sha256(encoded).hexdigest()
        directory = self.jobs_dir / ident
        directory.mkdir(mode=0o700, exist_ok=True)
        for name, data in (('job.json', encoded), ('board.kicad_pcb', bytes(board_bytes))):
            target = directory / name
            if target.exists() and target.read_bytes() != data:
                raise ValueError('Immutable job artifact collision')
            if not target.exists():
                with target.open('xb') as stream:
                    stream.write(data)
                os.chmod(target, 0o600)
        return {'jobId': ident, 'padCount': len(job.get('pads', [])), 'executionAuthorized': False,
                'boardSha256': job['board']['sha256'], 'status': self.status(ident)}

    def bind_prepared(self, job_id, prepared_dir):
        """Bind a prepared directory supplied by trusted server code, never HTTP input."""
        directory, job = self._job(job_id)
        prepared = Path(prepared_dir).resolve(strict=True)
        allowed = (self.root / 'automation/evidence').resolve()
        if allowed not in prepared.parents or not (prepared / 'preview-request.json').is_file():
            raise ValueError('Prepared artifact must be a server-selected evidence directory')
        request_path = prepared / 'preview-request.json'
        request = _json(request_path)
        target = request.get('ftpTargetRecord') or {}
        cad = target.get('cadEvidence') or {}
        cad_path = Path(str(cad.get('path', ''))).resolve()
        if (self.root not in cad_path.parents or cad.get('sha256') != job['board'].get('sha256') or not cad_path.is_file()
                or _sha(cad_path) != cad.get('sha256')):
            raise ValueError('Prepared native target is not bound to this uploaded board')
        if request.get('enabled') is not False or not UUID.fullmatch(str(request.get('id', ''))):
            raise ValueError('Prepared native request must be disabled and have a valid ID')
        binding = {'preparedDir': str(prepared), 'requestSha256': _sha(request_path),
                   'requestId': request['id'], 'boardSha256': cad['sha256'],
                   'sessionId': request.get('sessionId'), 'jvmStartMs': request.get('jvmStartMs'),
                   'configurationSha256': request.get('liveConfigurationSha256')}
        if not binding['sessionId'] or not binding['jvmStartMs'] or not binding['configurationSha256']:
            raise ValueError('Prepared request lacks its current-session binding')
        binding_path = directory / 'prepared-binding.json'
        if binding_path.exists():
            existing = _json(binding_path)
            if existing != binding:
                raise ValueError('Job already has an immutable prepared binding; create a new job for a new run')
        else:
            with binding_path.open('x') as stream:
                stream.write(json.dumps(binding, indent=2) + '\n')
            os.chmod(binding_path, 0o600)
        return {'jobId': job_id, 'preparedId': hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest(),
                'requestId': request['id'], 'status': 'prepared-bound'}

    def _binding(self, job_id):
        directory, job = self._job(job_id)
        path = directory / 'prepared-binding.json'
        if not path.is_file():
            return directory, job, None
        binding = _json(path)
        prepared = Path(binding['preparedDir']).resolve(strict=True)
        req = prepared / 'preview-request.json'
        if _sha(req) != binding['requestSha256']:
            raise ValueError('Prepared request changed after binding')
        return directory, job, binding

    def status(self, job_id):
        """Read saved artifacts and canonical reports only; never queries OpenPnP."""
        directory, job, binding = self._binding(job_id)
        result = {'jobId': job_id, 'boardSha256': job['board']['sha256'],
                  'stage': 'planned', 'executionAuthorized': False, 'report': None, 'photos': []}
        if not binding:
            return result
        result['stage'] = 'prepared'
        request = _json(Path(binding['preparedDir']) / 'preview-request.json')
        ident = request['id']
        preview = self.root / 'automation/evidence' / ('paste-contiguous-batch-preview-' + ident) / 'report.json'
        execution = self.root / 'automation/evidence' / ('paste-contiguous-batch-' + ident) / 'report.json'
        if preview.is_file():
            p = _json(preview)
            if p.get('id') != ident:
                raise ValueError('Preview report ID mismatch')
            passed = (p.get('status') == 'completed-model-only-contiguous-batch-preview'
                      and p.get('noMotion') is True and p.get('noControllerAccess') is True)
            result['stage'] = 'previewed' if passed else 'preview-failed'
            result['preview'] = {'status': p.get('status'), 'noMotion': p.get('noMotion') is True,
                                 'noControllerAccess': p.get('noControllerAccess') is True,
                                 'passed': passed}
        if execution.is_file():
            r = _json(execution)
            if r.get('id') != ident:
                raise ValueError('Execution report ID mismatch')
            result['report'] = {'status': r.get('status'), 'uncertainCompletion': r.get('uncertainCompletion'),
                                'controllerPositionVerified': r.get('controllerPositionVerified')}
            status = str(r.get('status', ''))
            if r.get('error') or status.startswith(('failed', 'stopped', 'cancelled')):
                result['stage'] = 'faulted'
                result['fault'] = status or str(r.get('error'))
            else:
                result['stage'] = 'completed' if status.startswith('completed') else 'running'
            photos = r.get('afterImages') or {}
            if isinstance(photos, dict):
                photos = list(photos.items())
            elif isinstance(photos, list):
                photos = [(str(i), item) for i, item in enumerate(photos)]
            for side, photo in photos:
                if isinstance(photo, dict) and isinstance(photo.get('path'), str):
                    path = Path(photo['path'])
                    if not path.is_absolute():
                        path = execution.parent / path
                    path = path.resolve()
                    if execution.parent in path.parents and path.is_file():
                        result['photos'].append({'sha256': _sha(path), 'name': path.name, 'view': side})
        return result

    def preview(self, job_id):
        """Explicitly request the existing detached native model-only preview."""
        _, _, binding = self._binding(job_id)
        if not binding:
            raise ValueError('No server-bound prepared native request')
        current = self.status(job_id)
        if current.get('stage') in ('completed', 'running', 'faulted'):
            raise ValueError('Existing execution report must be observed; do not start or replay')
        prepared = Path(binding['preparedDir'])
        return self.invoke([sys.executable, str(RUNNER), '--prepared-dir', str(prepared), '--preview'],
                           cwd=self.root, check=True, text=True, capture_output=True)

    def start(self, job_id):
        """Explicitly start a fresh, board-bound request after a passing native preview."""
        _, _, binding = self._binding(job_id)
        if not binding:
            raise ValueError('No server-bound prepared native request')
        prepared = Path(binding['preparedDir'])
        q = _json(prepared / 'preview-request.json')
        age = self.clock() * 1000 - float(q.get('createdMs', 0))
        if age < 0 or age > 300_000:
            raise ValueError('Prepared request is not fresh; prepare it again in the current session')
        preview = self.root / 'automation/evidence' / ('paste-contiguous-batch-preview-' + q['id']) / 'report.json'
        if not preview.is_file():
            raise ValueError('Current native model-only preview is required before Start')
        p = _json(preview)
        if p.get('id') != q['id'] or p.get('status') != 'completed-model-only-contiguous-batch-preview' or p.get('noMotion') is not True or p.get('noControllerAccess') is not True:
            raise ValueError('Native preview failed its exact-ID, no-motion, or no-controller-access gate')
        return self.invoke([sys.executable, str(RUNNER), '--prepared-dir', str(prepared), '--execute'],
                           cwd=self.root, check=True, text=True, capture_output=True)

    def commissioning_descriptor(self, job_id, known_prepared_dir):
        """Read-only descriptor for an already consumed commissioning artifact."""
        binding_result = self.bind_prepared(job_id, known_prepared_dir)
        state = self.status(job_id)
        return {'jobId': job_id, 'preparedId': binding_result['preparedId'],
                'action': 'observe' if state.get('stage') in ('running', 'completed') else 'review',
                'status': state}
