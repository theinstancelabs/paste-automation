import importlib.util
import unittest
from pathlib import Path

PATH = Path(__file__).with_name('prepare-air-fiducial-route.py')
SPEC = importlib.util.spec_from_file_location('prepare_air_fiducial_route', PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
PREP_PATH = PATH.with_name('prepare-contiguous-batch.py')
PREP_SPEC = importlib.util.spec_from_file_location('prepare_contiguous_batch', PREP_PATH)
PREP = importlib.util.module_from_spec(PREP_SPEC)
PREP_SPEC.loader.exec_module(PREP)


class AirFiducialRouteTest(unittest.TestCase):
    def setUp(self):
        self.raw = {'X': 300.0, 'Y': 232.27, 'Z': 58.45, 'A': 720.0, 'B': -3526.0}
        self.poses = {
            'N1': {'x': 275.8555, 'y': 168.2830, 'z': 58.45},
            'N2': {'x': 323.615, 'y': 168.323, 'z': 56.95},
            'top': {}, 'bottom': {},
        }

    def test_lifts_before_bounded_xy_and_optional_final_z(self):
        stages, points, bounds, heads = MODULE.route(self.raw, self.poses, 322.4, 190.3, 34.2)
        first_xy = next(i for i, stage in enumerate(stages) if stage['axis'] in ('X', 'Y'))
        self.assertEqual(points[first_xy]['Z'], MODULE.CLEARANCE_Z)
        self.assertTrue(all(stage['axis'] == 'Z' for stage in stages[:first_xy]))
        self.assertEqual(stages[-1]['axis'], 'Z')
        self.assertEqual(points[-1]['Z'], 34.2)
        self.assertTrue(all(abs(points[i + 1][stage['axis']] - points[i][stage['axis']]) <=
                            (MODULE.Z_STEP_MM if stage['axis'] == 'Z' else MODULE.XY_STEP_MM) + 1e-8
                            for i, stage in enumerate(stages)))
        self.assertTrue(all(p['A'] == self.raw['A'] and p['B'] == self.raw['B'] for p in points))
        self.assertEqual(bounds['B'], {'min': -3526.0, 'max': -3526.0})
        self.assertAlmostEqual(heads['N1']['minX'], self.poses['N1']['x'] - 0.001)
        self.assertAlmostEqual(heads['N2']['minZ'], self.poses['N2']['z'] - 0.001)

    def test_rejects_lower_start_or_off_grid_targets(self):
        with self.assertRaises(ValueError):
            MODULE.route({**self.raw, 'Z': 30.0}, self.poses, 300.0, 232.27)
        with self.assertRaises(ValueError):
            MODULE.route(self.raw, self.poses, 300.001, 232.27)

    def test_application_restart_route_lifts_verified_31_5_pose_before_xy(self):
        start = {**self.raw, 'X': 0.0, 'Y': 0.0, 'Z': 31.5}
        stages, points, bounds, _ = MODULE.route(
            start, self.poses, 170.0, 170.0, 32.25,
            allow_initial_clearance_lift=True)
        first_xy = next(i for i, stage in enumerate(stages) if stage['axis'] in ('X', 'Y'))
        self.assertEqual(stages[0], {'axis': 'Z', 'target': 32.25})
        self.assertEqual(points[first_xy]['Z'], 32.25)
        self.assertEqual(len(stages), 37)
        self.assertEqual(points[-1]['X'], 170.0)
        self.assertEqual(points[-1]['Y'], 170.0)
        self.assertEqual(points[-1]['Z'], 32.25)
        self.assertTrue(all(p['A'] == start['A'] and p['B'] == start['B'] for p in points))
        self.assertEqual(bounds['Z'], {'min': 31.5, 'max': 32.25})

    def test_application_restart_lift_is_limited_to_exact_homed_pose_and_no_below_clearance_final(self):
        start = {**self.raw, 'X': 0.0, 'Y': 0.0, 'Z': 31.4}
        with self.assertRaisesRegex(ValueError, '31.50 mm application-restart pose'):
            MODULE.route(start, self.poses, 170.0, 170.0, 32.25, allow_initial_clearance_lift=True)
        start['Z'] = 31.5
        with self.assertRaisesRegex(ValueError, '31.50 mm application-restart pose'):
            MODULE.route(start, self.poses, 170.0, 170.0, 31.5, allow_initial_clearance_lift=True)

    def test_restart_record_must_bind_session_configuration_and_current_jvm(self):
        record = {
            'schema': 1, 'scope': 'same-session-application-restart-continuity',
            'sessionId': 'session', 'liveConfigurationSha256': 'a' * 64,
            'transitions': [{'newJvmStartMs': 123}],
        }
        self.assertTrue(MODULE.restart_record_matches(record, 'session', 'a' * 64, 123))
        self.assertFalse(MODULE.restart_record_matches(record, 'other', 'a' * 64, 123))
        self.assertFalse(MODULE.restart_record_matches(record, 'session', 'b' * 64, 123))
        self.assertFalse(MODULE.restart_record_matches(record, 'session', 'a' * 64, 124))

    def test_air_identity_template_drops_only_wet_budget_amendment(self):
        template = {'sessionId': 'session', 'syringeId': 'syringe',
                    'previousLedgerSha256': 'a' * 64,
                    'budgetAmendmentEvidence': {'path': '/wet-only.json'},
                    'profileEvidence': {'path': '/profile.json'}}
        air = MODULE.air_identity_template(template)
        self.assertNotIn('budgetAmendmentEvidence', air)
        self.assertEqual(air['previousLedgerSha256'], template['previousLedgerSha256'])
        self.assertEqual(air['profileEvidence'], template['profileEvidence'])
        self.assertIn('budgetAmendmentEvidence', template)

    def test_contiguous_preparer_accepts_only_same_jvm_or_exact_bound_continuity(self):
        base = {'sessionId': 'session', 'jvmStartMs': 100, 'liveConfigurationSha256': 'a' * 64}
        ref = {'path': '/barrier.json', 'sha256': 'b' * 64}
        self.assertTrue(PREP.barrier_continuity_allowed(base, 100, 'a' * 64, ref, None, None))
        self.assertFalse(PREP.barrier_continuity_allowed(base, 200, 'b' * 64, ref, None, None))
        self.assertTrue(PREP.barrier_continuity_allowed(base, 200, 'b' * 64, ref, None, {'path': '/restart.json'}))
        proof = {'scope': 'manual-home-ledger-anchor-continuity', 'sessionId': 'session',
                 'currentJvmStartMs': 200, 'currentConfigurationSha256': 'b' * 64,
                 'currentBarrierEvidence': ref}
        self.assertTrue(PREP.barrier_continuity_allowed(base, 200, 'b' * 64, ref, proof, None))
        proof['currentBarrierEvidence'] = {'path': '/other.json', 'sha256': 'c' * 64}
        self.assertFalse(PREP.barrier_continuity_allowed(base, 200, 'b' * 64, ref, proof, None))

    def test_native_batch_profile_schema_uses_template_identity_and_historical_surface_evidence(self):
        template = {'sessionId': 'template-session', 'syringeId': 'template-syringe'}
        barrier = {
            'request': {'jvmStartMs': 1790898122720},
            'liveConfigurationSha256': 'a' * 64,
        }
        historical = {'path': '/historical/surface-measurement.json', 'sha256': 'b' * 64}
        review = {'path': '/current/clearance-review.json', 'sha256': 'c' * 64}
        profile = MODULE.profile_record(template, barrier, self.raw, historical, review)
        self.assertNotIn('sessionId', barrier['request'])
        self.assertEqual(profile['sessionId'], 'template-session')
        self.assertEqual(profile['syringeId'], 'template-syringe')
        self.assertEqual(profile['jvmStartMs'], 1790898122720)
        self.assertEqual(profile['liveConfigurationSha256'], 'a' * 64)
        self.assertEqual(profile['measurementEvidence'], historical)
        self.assertFalse(profile.get('measured', False))
        self.assertIn(review['path'], profile['basis'])
        self.assertIn(historical['path'], profile['basis'])

    def test_gap_rounding_preserves_exact_point_four_mm_clearance_boundary(self):
        template = {'sessionId': 'template-session', 'syringeId': 'template-syringe'}
        barrier = {'request': {'jvmStartMs': 1790898122720}, 'liveConfigurationSha256': 'a' * 64}
        profile = MODULE.profile_record(
            template, barrier, self.raw,
            {'path': '/historical/surface-measurement.json', 'sha256': 'b' * 64},
            {'path': '/current/clearance-review.json', 'sha256': 'c' * 64})
        self.assertEqual(profile['estimatedGapMm'], 0.4)
        self.assertGreater(profile['estimatedGapMm'], MODULE.NORTH_REFERENCE_UNCERTAINTY_MM)


if __name__ == '__main__':
    unittest.main()
