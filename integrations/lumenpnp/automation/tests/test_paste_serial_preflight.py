import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('paste_serial_preflight', Path(__file__).resolve().parents[1] / 'scripts/paste_serial_preflight.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class SerialPreflightTests(unittest.TestCase):
    def test_no_owner_requires_unambiguous_empty_probe(self):
        self.assertEqual(module.classify_probe(1, '', ''), ('unowned', []))
        for code, out, err in [(0, '', ''), (1, '', 'Permission denied'), (2, '', ''), (1, '1234', '')]:
            self.assertEqual(module.classify_probe(code, out, err), ('inconclusive', []))

    def test_owner_names_are_resolved_only_from_numeric_pid_list(self):
        self.assertEqual(module.classify_probe(0, ' 27176 42 27176', 'table'), ('owned', [42, 27176]))
        self.assertEqual(module.classify_probe(0, 'bad 1234', 'error'), ('inconclusive', []))

if __name__ == '__main__':
    unittest.main()
