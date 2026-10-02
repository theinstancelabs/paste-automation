import importlib.util
import math
import unittest
from pathlib import Path

MODULE = Path(__file__).with_name('job_planner.py')
SPEC = importlib.util.spec_from_file_location('job_planner', MODULE)
P = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(P)


class PlannerTests(unittest.TestCase):
    def board(self):
        return b'''(kicad_pcb (version 20240108) (net 1 "GND")
        (footprint "Test:Fine" (layer "F.Cu") (at 10 20 90)
          (property "Reference" "U1") (property "Value" "Fine")
          (pad "1" smd rect (at -0.25 0) (size 0.2 0.5) (layers "F.Cu" "F.Paste") (net 1 "GND"))
          (pad "2" smd circle (at 0.25 0) (size 0.2 0.2) (layers "F.Cu" "F.Paste") (net 1 "GND")))
        (footprint "Fiducial:Fiducial_1mm" (layer "F.Cu") (at 2 3) (property "Reference" "FID1"))
        (gr_line (start 0 0) (end 20 0) (layer "Edge.Cuts")))'''

    def test_geometry_hash_and_missing_calibration_are_explicit(self):
        job=P.plan_board(self.board(),paste_thickness_mm=0.1)
        self.assertEqual(len(job['pads']),2)
        self.assertAlmostEqual(job['pads'][0]['centerMm'][0],10)
        self.assertAlmostEqual(job['pads'][0]['centerMm'][1],-20.25)
        self.assertAlmostEqual(job['pads'][0]['pasteVolumeMm3'],0.01)
        self.assertEqual(job['pads'][0]['doseBDegrees'],None)
        self.assertEqual(job['pads'][0]['doseStatus'],'needs-calibration')
        self.assertEqual(job['board']['boundsMm'],[0.0,0.0,20.0,0.0])
        self.assertEqual(len(job['fiducials']),1)
        self.assertTrue(job['finePitchGroups'][0]['reviewRequired'])
        self.assertFalse(job['executionAuthorized'])
        self.assertEqual(job['board']['sha256'],P.plan_board(self.board())['board']['sha256'])

    def test_linear_calibration_interpolation_but_no_extrapolation(self):
        cal={'id':'synthetic','knots':[{'volumeMm3':0.01,'degrees':2},{'volumeMm3':0.03,'degrees':6}]}
        job=P.plan_board(self.board(),paste_thickness_mm=0.1,flow_calibration=cal)
        self.assertAlmostEqual(job['pads'][0]['doseBDegrees'],2)
        self.assertEqual(job['pads'][0]['doseStatus'],'calibrated')
        cal['knots'][0]['volumeMm3']=0.02
        job=P.plan_board(self.board(),paste_thickness_mm=0.1,flow_calibration=cal)
        self.assertIsNone(job['pads'][0]['doseBDegrees'])

    def test_backside_supported_but_calls_out_transform_review(self):
        data=self.board().replace(b'F.Cu',b'B.Cu').replace(b'F.Paste',b'B.Paste')
        job=P.plan_board(data,side='B.Cu')
        self.assertEqual(len(job['pads']),2)
        self.assertTrue(all(p['bottomSideTransformReviewRequired'] for p in job['pads']))

    def test_comments_semicolons_and_fp_text_reference(self):
        data=b'''(kicad_pcb (footprint "T:X" (layer "F.Cu") (at 5 8 90)
          (fp_text reference "U;2" (at 0 0) (layer "F.SilkS"))
          (fp_text value "semi;colon" (at 0 0) (layer "F.Fab"))
          (pad "1" smd rect (at 1 0 15) (size 1 2) (layers "F.Cu" "F.Paste")))) ; comment ( ignored\n'''
        job=P.plan_board(data)
        self.assertEqual(job['footprints'][0]['reference'],'U;2')
        self.assertEqual(job['pads'][0]['rotationDeg'],15) # pad angle in KiCad is absolute
        self.assertAlmostEqual(job['pads'][0]['centerMm'][0],5)
        self.assertAlmostEqual(job['pads'][0]['centerMm'][1],-7)

    def test_nonzero_paste_margin_does_not_claim_nominal_area(self):
        data=self.board().replace(b'(property "Value" "Fine")',b'(property "Value" "Fine") (solder_paste_margin 0.1)')
        job=P.plan_board(data,paste_thickness_mm=0.1)
        self.assertIsNone(job['pads'][0]['areaMm2'])
        self.assertIsNone(job['pads'][0]['pasteVolumeMm3'])
        self.assertEqual(job['pads'][0]['geometryStatus'],'paste-override-review-required')

    def test_invalid_thickness_scaling_and_nonmonotonic_calibration_rejected_as_unusable(self):
        with self.assertRaises(ValueError): P.plan_board(self.board(),paste_thickness_mm=0)
        with self.assertRaises(ValueError): P.plan_board(self.board(),aperture_scaling=-1)
        cal={'knots':[{'volumeMm3':0.01,'degrees':6},{'volumeMm3':0.03,'degrees':2}]}
        job=P.plan_board(self.board(),paste_thickness_mm=0.1,flow_calibration=cal)
        self.assertIsNone(job['pads'][0]['doseBDegrees'])

    def test_rejects_malformed_board(self):
        with self.assertRaises(ValueError): P.plan_board(b'(kicad_pcb')

    def test_arc_uses_extrema_and_exposes_exact_draw_geometry(self):
        data=b'''(kicad_pcb (gr_arc (start 10 0) (mid 7.0710678 -7.0710678) (end -10 0) (layer "Edge.Cuts")))'''
        board=P.plan_board(data)['board']
        self.assertAlmostEqual(board['boundsMm'][1],0,places=5)
        self.assertAlmostEqual(board['boundsMm'][3],10,places=5)
        arc=board['outline'][0]
        self.assertEqual(arc['geometryStatus'],'exact-circular-arc')
        self.assertAlmostEqual(arc['radiusMm'],10,places=5)
        self.assertAlmostEqual(abs(arc['sweepAngleDeg']),180,places=3)

    def test_degenerate_arc_suppresses_exact_bounds_claim(self):
        data=b'''(kicad_pcb (gr_arc (start 0 0) (mid 1 1) (end 2 2) (layer "Edge.Cuts")))'''
        board=P.plan_board(data)['board']
        self.assertEqual(board['boundsStatus'],'review-required-incomplete-outline-geometry')
        self.assertTrue(board['outline'][0]['geometryStatus'].startswith('review-required'))


if __name__=='__main__': unittest.main()
