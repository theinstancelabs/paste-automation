"""Cross-engine arithmetic and guard test; evaluates only pure policy files."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

AUTOMATION = Path(__file__).resolve().parents[1]
POLICY = AUTOMATION / 'paste/commissioning-stroke.cjs'
GROUP = AUTOMATION / 'paste/ftp-pad-group.cjs'
TRACES = AUTOMATION / 'paste/fractional-retraction.traces.js'
LIBS = '/opt/openpnp/lib/*'


class FractionalRetractionNashornTests(unittest.TestCase):
    @unittest.skipUnless(Path('/opt/openpnp/lib').is_dir(), 'Requires installed OpenPnP Nashorn libraries')
    def test_fractional_targets_and_ledger_count_guards_match_node(self):
        node = """const fs=require('fs'),vm=require('vm'),c=vm.createContext({});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);
vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),c);
vm.runInContext(fs.readFileSync(process.argv[3],'utf8'),c);
process.stdout.write(JSON.stringify(c.FractionalRetractionTraces));"""
        expected = subprocess.check_output(['node', '-e', node, str(GROUP), str(POLICY), str(TRACES)], text=True, timeout=10)
        with tempfile.TemporaryDirectory(prefix='fractional-retract-nashorn-') as temp:
            subprocess.run(['javac', '-d', temp, str(AUTOMATION / 'tests/java/EvaluateFractionalRetractionPolicy.java')], check=True, timeout=20)
            observed = subprocess.check_output(['java', '-cp', f'{temp}:{LIBS}', 'EvaluateFractionalRetractionPolicy', str(GROUP), str(POLICY), str(TRACES)], text=True, timeout=20)
        self.assertEqual(json.loads(observed), json.loads(expected))
        result = json.loads(observed)
        self.assertEqual([x['roundedSteps'] for x in result['settings']], [4, 5, 7, 8])
        self.assertEqual(result['stageSteps'], [4, 5, 7, 8])
        self.assertEqual(result['phaseDependentCount'], 5)
        self.assertTrue(result['malformedComparisonRejected'])
        self.assertTrue(result['ledgerCountMismatchRejected'])


if __name__ == '__main__':
    unittest.main()
