import importlib.util
from pathlib import Path
import tempfile
import unittest
from PIL import Image

BASE=Path(__file__).resolve().parent
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
P=load('row_planner_for_projection',BASE/'job_planner.py')
G=load('reviewed_projected_polygons',BASE/'projected_polygons.py')
I=load('row_projection_cv_inspector',BASE/'pad_inspection.py')


class ProjectedPolygonTests(unittest.TestCase):
    def qfp(self):
        pads=' '.join(f'(pad "{i+1}" smd rect (at {(i-1.5)*.5} 0 -33) (size .2 .6) (layers "F.Cu" "F.Paste"))' for i in range(4))
        return P.plan_board(f'(kicad_pcb (footprint "QFP" (layer "F.Cu") (at 4 7 33) (property "Reference" "U9") {pads}))'.encode())

    def projection(self):
        return {'schema':1,'scope':'reviewed-board-to-image-affine','validated':True,
          'matrix':[[50,0,400],[0,50,600]],'evidence':{'sha256':'a'*64}}

    def test_reviewed_affine_projects_full_rotated_row_and_cv_row_ids(self):
        job=self.qfp();projection=G.build_inspection_projection(job,self.projection())
        group=next(g for g in projection['lineProposalChecks'] if len(g['padIds'])==4)
        self.assertTrue(group['cadProposalContainedInProjectedRowEnvelope'])
        self.assertTrue(group['status'].startswith('within-projected'))
        self.assertEqual(projection['rowGroups'][0]['id'],job['finePitchGroups'][0]['id'])
        self.assertEqual(len(projection['pads']),4)
        self.assertFalse(projection['executionAuthorized'])

    def test_unvalidated_or_noninvertible_projection_rejected(self):
        for patch in ({'validated':False},{'matrix':[[1,0,0],[2,0,1]]},{'evidence':{'sha256':'bad'}}):
            with self.assertRaises(ValueError):G.build_inspection_projection(self.qfp(),{**self.projection(),**patch})

    def test_geometry_outside_row_envelope_cannot_become_cv_line_candidate(self):
        job=self.qfp();g=next(g for g in job['finePitchGroups'] if g['kind']=='fine-pitch-row')
        g['proposedLine']['nominalWidthMm']=3
        projected=G.build_inspection_projection(job,self.projection())
        check=projected['lineProposalChecks'][0]
        self.assertFalse(check['cadProposalContainedInProjectedRowEnvelope'])
        with tempfile.TemporaryDirectory() as tmp:
            image=Path(tmp)/'board.png';Image.new('RGB',(1000,1000),(255,255,255)).save(image)
            report=I.inspect_image(image,projected['pads'],paste_rgb=(0,0,0),row_groups=projected['rowGroups'])
        self.assertFalse(report['finePitchRows'][0]['continuousLineProposalEligible'])
        self.assertFalse(report['finePitchRows'][0]['cadProposalContainedInProjectedRowEnvelope'])

    def test_unrelated_pair_and_irregular_three_pad_shape_do_not_become_line_rows(self):
        data=b'''(kicad_pcb
          (footprint "0603" (layer "F.Cu") (at 4 7) (property "Reference" "R1")
            (pad "1" smd roundrect (at -.25 0) (size .3 .6) (layers "F.Cu" "F.Paste"))
            (pad "2" smd roundrect (at .25 0) (size .3 .6) (layers "F.Cu" "F.Paste")))
          (footprint "Odd" (layer "F.Cu") (at 20 5) (property "Reference" "U2")
            (pad "1" smd rect (at 0 0) (size .2 .4) (layers "F.Cu" "F.Paste"))
            (pad "2" smd rect (at .5 0) (size .2 .4) (layers "F.Cu" "F.Paste"))
            (pad "3" smd rect (at 1.15 .15) (size .2 .4) (layers "F.Cu" "F.Paste"))))'''
        job=P.plan_board(data);self.assertFalse(any(g['kind']=='fine-pitch-row' for g in job['finePitchGroups']))


if __name__=='__main__':unittest.main()
