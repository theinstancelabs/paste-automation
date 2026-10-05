import importlib.util
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).with_name('preview_measured_rod_extension.py')
spec = importlib.util.spec_from_file_location('preview_measured_rod_extension', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RebindProfileIdsTest(unittest.TestCase):
    def test_rebinds_nested_calibration_provenance_only(self):
        old, new = 'old-profile', 'new-profile'
        sidecar = {
            'profileId': old,
            'alignmentImportProvenance': {'profileId': old, 'sourceProfileId': old},
            'tipXYCorrection': {'profileId': old, 'sessionId': 'keep'},
            'alignmentSamples': [{'ref': 'R1', 'profileId': old}],
        }
        updated = module.rebind_profile_ids(sidecar, old, new)
        self.assertEqual(updated['profileId'], new)
        self.assertEqual(updated['alignmentImportProvenance']['profileId'], new)
        self.assertEqual(updated['tipXYCorrection']['profileId'], new)
        self.assertEqual(updated['alignmentSamples'][0]['profileId'], new)
        self.assertEqual(updated['alignmentImportProvenance']['sourceProfileId'], old)
        self.assertEqual(updated['tipXYCorrection']['sessionId'], 'keep')
        self.assertEqual(sidecar['profileId'], old)  # helper is non-mutating


if __name__ == '__main__':
    unittest.main()
