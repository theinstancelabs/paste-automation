import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).with_name('author-native-ftp-group.py')
spec = importlib.util.spec_from_file_location('author_native_ftp_group', SCRIPT)
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

class NativeFtpGroupAuthorTests(unittest.TestCase):
    def review(self):
        return ('R1.2 R16.1 R40.1 R40.1 R40.2 R39.1 R39.2 R38.1 R38.2 R37.1 R37.2 '
                'boardCleaned padsAvailable boardUnmovedSinceRegistration '
                'bothHeadsClearanceReviewed clearTransitCorridorReviewed '
                'scrapPrimeAndWipeReviewed tipReviewedNoLongStrand; root reviewed all evidence')

    def test_prime_plus_wipe_and_supplied_surface_are_used_with_fixed_recipe(self):
        example = {'attestations': {'boardCleaned': False}}
        raw = {'X': 300.36, 'Y': 305.1, 'Z': 58.45, 'A': 720, 'B': -3033}
        q = M.authored_values(example, 'root', self.review(), raw,
                              ['R40', 'R39', 'R38', 'R37'],
                              (300.36, 305.1), (303.88, 305.1), 58.15, 1234)
        self.assertEqual(q['scrapTargetsXY'], [{'X': 301.86, 'Y': 305.1}, {'X': 303.88, 'Y': 305.1}])
        self.assertEqual(q['surfaceRawZ'], 58.15)
        self.assertEqual(q['xyClearanceRawZ'], 53.45)
        self.assertEqual((q['doseDegrees'], q['retractDegrees'], q['dwellMilliseconds']), (6, 3, 2000))
        self.assertTrue(all(q['attestations'].values()))

    def test_canonical_paths_resolve_inside_repository_evidence(self):
        self.assertEqual(M.ROOT, Path(__file__).resolve().parents[2])
        self.assertTrue(str(M.TEMPLATE).endswith('cap-11800-reviewed-iso/template-11800.json'))
        self.assertTrue(str(M.SCRAP_EXPERIMENT).endswith('contiguous-coupon/ftp-transfer-1/experiment.json'))
        if not M.SCRAP_PROFILE.is_file():
            self.skipTest('private machine evidence is intentionally absent from the source-only export')
        self.assertTrue(M.SCRAP_PROFILE.is_file())

    def test_rejects_wrong_prime_pose_or_incomplete_explicit_review(self):
        example = {'attestations': {'boardCleaned': False}}
        raw = {'X': 300.36, 'Y': 305.1, 'Z': 58.45, 'A': 720, 'B': -3033}
        with self.assertRaisesRegex(ValueError, 'Barrier must match'):
            M.authored_values(example, 'root', self.review(), raw,
                              ['R40', 'R39', 'R38', 'R37'], (301, 305.1), (303.88, 305.1), 58.15, 1234)
        with self.assertRaisesRegex(ValueError, 'explicitly cover'):
            M.authored_values(example, 'root', 'generic review basis only with enough extra text to clear minimum length', raw,
                              ['R40', 'R39', 'R38', 'R37'], (300.36, 305.1), (303.88, 305.1), 58.15, 1234)

if __name__ == '__main__':
    unittest.main()
