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
        self.assertEqual(job['pads'][0]['doseStatus'],'candidate-unverified-flow-model')
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

    def test_rotated_three_plus_qfp_row_is_stable_and_never_automatically_continuous(self):
        rows=[]
        for i in range(4):
            x=(i-1.5)*.5
            rows.append(f'(pad "{i+1}" smd rect (at {x} 0 0) (size .2 .6) (layers "F.Cu" "F.Paste"))')
        board=('(kicad_pcb (footprint "Package:QFP" (layer "F.Cu") (at 4 7 33) '
          '(property "Reference" "U9") '+' '.join(rows)+') '
          '(footprint "Device:R" (layer "F.Cu") (at 20 5) (property "Reference" "R1") '
          '(pad "1" smd roundrect (at -.25 0) (size .3 .6) (layers "F.Cu" "F.Paste")) '
          '(pad "2" smd roundrect (at .25 0) (size .3 .6) (layers "F.Cu" "F.Paste"))))').encode()
        job=P.plan_board(board,paste_thickness_mm=.1)
        group=next(g for g in job['finePitchGroups'] if g['reference']=='U9')
        self.assertEqual(group['kind'],'fine-pitch-row')
        self.assertEqual(len(group['padIds']),4)
        self.assertEqual(group['padIds'],['U9.1','U9.2','U9.3','U9.4'])
        repeated=next(g for g in P.plan_board(board,paste_thickness_mm=.1)['finePitchGroups'] if g['reference']=='U9')
        self.assertEqual(group['id'],repeated['id'])
        self.assertEqual(group['depositStrategy'],'individual-pad-deposits-unless-line-recipe-reviewed')
        self.assertIsNone(group['proposedLine']['theoreticalVolumeBasedWidthMm'])
        self.assertEqual(group['proposedLine']['volumeModelStatus'],'CAD-aperture-theory-only')
        self.assertTrue(group['continuousLineProcessRecipeRequired'])
        self.assertTrue(all(p['depositProposal']['kind']=='short-line' for p in job['pads'] if p['reference']=='U9'))
        pair=next(g for g in job['finePitchGroups'] if g['reference']=='R1')
        self.assertEqual(pair['kind'],'close-pad-pair')
        self.assertIsNone(pair['proposedLine'])
        self.assertTrue(all(p['depositProposal']['kind']=='dot' for p in job['pads'] if p['reference']=='R1'))

    def test_calibrated_flow_evidence_only_enables_theoretical_row_width(self):
        row=' '.join(f'(pad "{i+1}" smd rect (at {(i-1.5)*.5} 0 0) (size .2 .6) (layers "F.Cu" "F.Paste"))' for i in range(4))
        board=f'(kicad_pcb (footprint "QFP" (layer "F.Cu") (at 0 0) (property "Reference" "U1") {row}))'.encode()
        cal={'id':'reviewed-flow-1','verified':True,'evidence':{'sha256':'a'*64},
          'knots':[{'volumeMm3':.001,'degrees':1},{'volumeMm3':.1,'degrees':100}]}
        verified_job=P.plan_board(board,paste_thickness_mm=.1,flow_calibration=cal)
        self.assertTrue(all(p['doseStatus']=='calibrated' for p in verified_job['pads']))
        group=verified_job['finePitchGroups'][0]
        self.assertEqual(group['proposedLine']['volumeModelStatus'],'theoretical-only-verified-input-calibration')
        self.assertGreater(group['proposedLine']['theoreticalVolumeBasedWidthMm'],0)
        unverified={**cal,'verified':False}
        result=P.plan_board(board,paste_thickness_mm=.1,flow_calibration=unverified)
        self.assertIsNone(result['finePitchGroups'][0]['proposedLine']['theoreticalVolumeBasedWidthMm'])
        self.assertEqual(result['pasteModel']['calibrationStatus'],'supplied-model-unverified')

    def test_irregular_noncollinear_three_pad_shape_is_not_a_row(self):
        data=b'''(kicad_pcb (footprint "Test:Odd" (layer "F.Cu") (at 0 0) (property "Reference" "U3")
          (pad "1" smd rect (at 0 0) (size .2 .4) (layers "F.Cu" "F.Paste"))
          (pad "2" smd rect (at .5 0) (size .2 .4) (layers "F.Cu" "F.Paste"))
          (pad "3" smd rect (at 1.15 .15) (size .2 .4) (layers "F.Cu" "F.Paste"))))'''
        self.assertFalse(any(g['kind']=='fine-pitch-row' for g in P.plan_board(data)['finePitchGroups']))

    def test_same_library_unreferenced_instances_are_never_joined_as_one_row(self):
        data=b'''(kicad_pcb
          (footprint "Package:QFP" (layer "F.Cu") (at 0 0)
            (pad "1" smd rect (at -.25 0) (size .2 .5) (layers "F.Cu" "F.Paste"))
            (pad "2" smd rect (at .25 0) (size .2 .5) (layers "F.Cu" "F.Paste")))
          (footprint "Package:QFP" (layer "F.Cu") (at 1.5 0)
            (pad "1" smd rect (at -.25 0) (size .2 .5) (layers "F.Cu" "F.Paste"))
            (pad "2" smd rect (at .25 0) (size .2 .5) (layers "F.Cu" "F.Paste"))))'''
        job=P.plan_board(data)
        self.assertEqual(len({p['footprintInstanceId'] for p in job['pads']}),2)
        self.assertFalse(any(g['kind']=='fine-pitch-row' for g in job['finePitchGroups']))
        self.assertEqual(len(job['finePitchGroups']),2)


if __name__=='__main__': unittest.main()
