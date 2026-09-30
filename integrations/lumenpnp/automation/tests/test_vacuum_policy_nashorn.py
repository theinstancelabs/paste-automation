"""Cross-engine synthetic policy test; never loads OpenPnP machine classes."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

AUTOMATION = Path(__file__).resolve().parents[1]
POLICY = AUTOMATION / 'paste/vacuum-probe-policy.cjs'
TRACES = AUTOMATION / 'paste/vacuum-probe-policy.traces.js'
LIBS = '/opt/openpnp/lib/*'


class VacuumPolicyNashornTests(unittest.TestCase):
    @unittest.skipUnless(Path('/opt/openpnp/lib').is_dir(), 'Requires installed Nashorn libraries')
    def test_identical_node_and_nashorn_synthetic_transitions(self):
        node = """const fs=require('fs'),vm=require('vm');const c=vm.createContext({});
vm.runInContext('Number.isFinite=undefined;Number.isInteger=undefined;Object.assign=undefined;Array.prototype.includes=undefined;',c);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);
vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),c);
process.stdout.write(JSON.stringify(c.VacuumProbeTraces));"""
        expected = subprocess.check_output(['node', '-e', node, str(POLICY), str(TRACES)], text=True, timeout=10)
        with tempfile.TemporaryDirectory(prefix='pure-policy-java-') as temporary:
            subprocess.run(['javac', '-d', temporary, str(AUTOMATION / 'tests/java/EvaluatePurePolicy.java')], check=True, timeout=20)
            observed = subprocess.check_output(['java', '-cp', f'{temporary}:{LIBS}', 'EvaluatePurePolicy', str(POLICY), str(TRACES)], text=True, timeout=20)
        self.assertEqual(json.loads(observed), json.loads(expected))
        self.assertEqual(len(json.loads(observed)), 18)


if __name__ == '__main__':
    unittest.main()
