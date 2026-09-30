"""Incremental, read-only projection of one Codex task's visible conversation.

Only user messages and assistant final/commentary messages leave this module.
Never return reasoning, instructions, context snapshots, compaction summaries,
raw tool events or arbitrary files. The rollout path is configured locally.
"""
import json
from pathlib import Path
import re
import threading


def visible_message(record):
    if record.get('type') != 'response_item':
        return None
    item = record.get('payload', {})
    if item.get('type') != 'message':
        return None
    role = item.get('role')
    if role not in ('user', 'assistant'):
        return None
    if item.get('channel') not in (None, 'final', 'commentary'):
        return None
    if item.get('phase') not in (None, 'final_answer', 'commentary', 'final'):
        return None
    parts = []
    for block in item.get('content', []):
        if block.get('type') in ('input_text', 'output_text'):
            parts.append(block.get('text', ''))
        elif block.get('type') in ('input_image', 'image'):
            parts.append('[Image attachment — view in Codex]')
    text = '\n'.join(parts)
    if role == 'user':
        # Ambient app state can accompany a real user message; don't display it.
        for tag in ('in-app-browser-context', 'environment_context', 'recommended_plugins'):
            text = re.sub(r'<' + tag + r'\b[^>]*>[\s\S]*?</' + tag + r'>', '', text)
        text = re.sub(r'^\s*## My request:\s*', '', text)
        match = re.search(r'<send_user_message_question_reply>\s*([\s\S]*?)\s*</send_user_message_question_reply>', text)
        if match:
            try:
                replies = json.loads(match.group(1))
                text = '\n\n'.join(str(x.get('question', '')) + '\nAnswer: ' + str(x.get('answer', '')) for x in replies)
            except (ValueError, TypeError):
                text = '[Question reply — view in Codex]'
    text = text.strip()
    if not text:
        return None
    return {'role': role, 'phase': item.get('phase'), 'text': text,
            'timestamp': record.get('timestamp')}


class ChatMirror:
    def __init__(self, path):
        self.path = Path(path) if path else None
        self.offset = 0
        self.inode = None
        self.messages = []
        self.revision = 0
        self.lock = threading.Lock()

    def snapshot(self):
        with self.lock:
            if self.path is None:
                return {'messages': [], 'revision': 0, 'error': 'Conversation mirror is not configured.'}
            try:
                stat = self.path.stat()
                if stat.st_ino != self.inode or stat.st_size < self.offset:
                    self.offset = 0
                    self.inode = stat.st_ino
                    self.messages = []
                    self.revision += 1
                with self.path.open('rb') as stream:
                    stream.seek(self.offset)
                    while True:
                        line = stream.readline()
                        if not line or not line.endswith(b'\n'):
                            break  # Retry partially written records next poll.
                        self.offset = stream.tell()
                        try:
                            message = visible_message(json.loads(line))
                        except (ValueError, TypeError, AttributeError):
                            continue
                        if message:
                            message['id'] = str(self.offset)
                            self.messages.append(message)
                            self.revision += 1
                return {'messages': list(self.messages), 'revision': self.revision, 'error': None}
            except OSError:
                return {'messages': list(self.messages), 'revision': self.revision,
                        'error': 'Conversation source is temporarily unavailable.'}
