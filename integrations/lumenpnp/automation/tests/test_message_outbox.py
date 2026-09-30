import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from message_outbox import MessageOutbox


class MessageOutboxTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'messages.json'
        self.outbox = MessageOutbox(self.path)

    def tearDown(self):
        self.directory.cleanup()

    def test_submit_is_durable_and_idempotent(self):
        record, created = self.outbox.submit('Please pause after this placement.', 'message-0001')
        duplicate, duplicate_created = self.outbox.submit('Please pause after this placement.', 'message-0001')
        self.assertTrue(created)
        self.assertFalse(duplicate_created)
        self.assertEqual(record['id'], duplicate['id'])
        self.assertEqual(MessageOutbox(self.path).pending()[0]['message'], record['message'])

    def test_delivery_completion_removes_pending_message(self):
        record, _ = self.outbox.submit('Status?', 'message-0002')
        completed = self.outbox.complete(record['id'], 'delivered')
        self.assertEqual(completed['status'], 'delivered')
        self.assertEqual(self.outbox.pending(), [])

    def test_rejects_empty_or_oversize_message(self):
        with self.assertRaises(ValueError):
            self.outbox.submit(' \n ', 'message-0003')
        with self.assertRaises(ValueError):
            self.outbox.submit('x' * 4001, 'message-0004')


if __name__ == '__main__':
    unittest.main()
