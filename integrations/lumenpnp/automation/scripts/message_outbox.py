"""Durable, local-only queue for messages submitted through the live viewer.

The viewer cannot deliver to a Codex desktop task itself: Codex exposes task
messaging to its running agent, rather than an HTTP endpoint on the LAN.  A
trusted Codex-side bridge consumes this queue and records delivery results.
"""
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
import threading
import time


MAX_MESSAGE_CHARS = 4_000
MAX_PENDING = 100
MAX_RECORDS = 200
_IDEMPOTENCY_RE = re.compile(r'^[A-Za-z0-9._~-]{8,128}$')


class MessageOutbox:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.records = self._load()

    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if isinstance(data, list):
                return [record for record in data if self._valid_record(record)][-MAX_RECORDS:]
        except (OSError, ValueError, TypeError):
            pass
        return []

    @staticmethod
    def _valid_record(record):
        return (isinstance(record, dict) and isinstance(record.get('id'), str)
                and isinstance(record.get('idempotency_key'), str)
                and isinstance(record.get('message'), str)
                and record.get('status') in ('queued', 'dispatching', 'delivered', 'failed', 'unknown'))

    def _save(self):
        self.path.parent.mkdir(mode=0o700, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix='.messages-', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(self.records, stream, separators=(',', ':'))
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    @staticmethod
    def _message(value):
        if not isinstance(value, str):
            raise ValueError('Message must be text.')
        value = value.replace('\r\n', '\n').replace('\r', '\n').strip()
        if not value:
            raise ValueError('Message cannot be empty.')
        if len(value) > MAX_MESSAGE_CHARS:
            raise ValueError(f'Message is limited to {MAX_MESSAGE_CHARS} characters.')
        if any(ord(char) < 32 and char not in '\n\t' for char in value):
            raise ValueError('Message contains unsupported control characters.')
        return value

    def submit(self, message, idempotency_key):
        message = self._message(message)
        if not isinstance(idempotency_key, str) or not _IDEMPOTENCY_RE.fullmatch(idempotency_key):
            raise ValueError('Invalid idempotency key.')
        with self.lock:
            for record in self.records:
                if record['idempotency_key'] == idempotency_key:
                    if record['message'] != message:
                        raise ValueError('Idempotency key was already used for another message.')
                    return dict(record), False
            if sum(record['status'] == 'queued' for record in self.records) >= MAX_PENDING:
                raise ValueError('Message queue is full. Wait for delivery before sending more.')
            record = {'id': secrets.token_urlsafe(18), 'idempotency_key': idempotency_key,
                      'message': message, 'status': 'queued', 'submitted_at': time.time()}
            self.records.append(record)
            self.records = self.records[-MAX_RECORDS:]
            self._save()
            return dict(record), True

    def pending(self):
        with self.lock:
            return [dict(record) for record in self.records if record['status'] == 'queued']

    def claim(self, message_id):
        """Claim one queued message so duplicate HTTP retries never queue it twice."""
        with self.lock:
            for record in self.records:
                if record['id'] != message_id:
                    continue
                if record['status'] != 'queued':
                    return None
                record['status'] = 'dispatching'
                record['dispatching_at'] = time.time()
                self._save()
                return dict(record)
        return None

    def get(self, message_id):
        with self.lock:
            for record in self.records:
                if record['id'] == message_id:
                    return dict(record)
        return None

    def complete(self, message_id, status, error=None):
        if status not in ('delivered', 'failed', 'unknown'):
            raise ValueError('Status must be delivered, failed, or unknown.')
        if error is not None and (not isinstance(error, str) or len(error) > 300):
            raise ValueError('Invalid delivery error.')
        with self.lock:
            for record in self.records:
                if record['id'] != message_id:
                    continue
                if record['status'] not in ('queued', 'dispatching'):
                    return dict(record)
                record['status'] = status
                record['completed_at'] = time.time()
                if status in ('failed', 'unknown') and error:
                    record['error'] = error
                self._save()
                return dict(record)
        return None

    def retry(self, message_id):
        """Return a known failed message to the queue; never retry an uncertain dispatch."""
        with self.lock:
            for record in self.records:
                if record['id'] != message_id:
                    continue
                if record['status'] != 'failed':
                    return None
                record['status'] = 'queued'
                record.pop('error', None)
                self._save()
                return dict(record)
        return None
