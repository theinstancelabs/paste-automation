import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw

MODULE=Path(__file__).with_name('pad_inspection.py')
SPEC=importlib.util.spec_from_file_location('pad_inspection',MODULE)
V=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(V)


class PadInspectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.dir=Path(self.tmp.name)
        self.pads=[{'id':'U1.1','polygonPx':[[10,10],[30,10],[30,25],[10,25]]},
                    {'id':'U1.2','polygonPx':[[40,10],[60,10],[60,25],[40,25]]}]
        self.rows=[{'id':'fine-row-U1','padIds':['U1.1','U1.2']}]

    def tearDown(self): self.tmp.cleanup()

    def image(self,name,draw):
        im=Image.new('RGB',(80,45),(20,20,20)); d=ImageDraw.Draw(im); draw(d)
        path=self.dir/name; im.save(path); return path

    def inspect(self,path,rows=None):
        return V.inspect_image(path,self.pads,paste_rgb=(220,220,220),tolerance=10,row_groups=self.rows if rows is None else rows)

    def recipe(self):
        r={'schema':1,'scope':'reviewed-continuous-line-process-recipe','validated':True,
           'reviewedBy':'synthetic reviewer','padGroupId':'fine-row-U1','parameters':{'targetVolumeMm3':0.02}}
        r['recipeSha256']=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        return r

    def test_centered_blobs_and_shift_have_numerical_alignment(self):
        centered=self.image('center.png',lambda d:(d.rectangle((15,13,25,22),fill=(220,220,220)),d.rectangle((45,13,55,22),fill=(220,220,220))))
        shifted=self.image('shift.png',lambda d:(d.rectangle((25,13,35,22),fill=(220,220,220)),d.rectangle((55,13,65,22),fill=(220,220,220))))
        a=self.inspect(centered); b=self.inspect(shifted)
        self.assertGreater(a['pads'][0]['alignmentScore'],b['pads'][0]['alignmentScore'])
        self.assertEqual(a['finePitchRows'][0]['classification'],'separate-pad-blobs')
        self.assertFalse(a['finePitchRows'][0]['continuousLineProposalEligible'])

    def test_connected_thin_line_is_bridge_review_not_dose_authority(self):
        path=self.image('line.png',lambda d:d.rectangle((18,17,52,19),fill=(220,220,220)))
        result=self.inspect(path,self.rows)
        self.assertEqual(result['finePitchRows'][0]['classification'],'connected-thin-row-possible-bridge')
        self.assertEqual(len(result['possibleBridges']),1)
        self.assertFalse(result['finePitchRows'][0]['continuousLineProposalEligible'])
        self.assertFalse(result['executionAuthorized'])

    def test_line_candidate_requires_matching_validated_recipe(self):
        path=self.image('line-recipe.png',lambda d:d.rectangle((18,17,52,19),fill=(220,220,220)))
        recipe=self.recipe()
        result=V.inspect_image(path,self.pads,paste_rgb=(220,220,220),tolerance=10,row_groups=self.rows,process_recipe=recipe)
        self.assertTrue(result['finePitchRows'][0]['continuousLineProposalEligible'])
        self.assertFalse(result['executionAuthorized'])
        recipe['parameters']['targetVolumeMm3']=0.5 # tampering without revalidation breaks hash binding
        result=V.inspect_image(path,self.pads,paste_rgb=(220,220,220),tolerance=10,row_groups=self.rows,process_recipe=recipe)
        self.assertFalse(result['finePitchRows'][0]['continuousLineProposalEligible'])

    def test_validated_recipe_gate_is_explicit_and_area_delta_reported(self):
        before=self.image('before.png',lambda d:(d.rectangle((15,13,25,22),fill=(220,220,220)),d.rectangle((45,13,55,22),fill=(220,220,220))))
        after=self.image('after.png',lambda d:(d.rectangle((13,11,27,24),fill=(220,220,220)),d.rectangle((43,11,57,24),fill=(220,220,220))))
        recipe=self.recipe()
        a=V.inspect_image(after,self.pads,paste_rgb=(220,220,220),tolerance=10,row_groups=self.rows,process_recipe=recipe)
        self.assertFalse(a['finePitchRows'][0]['continuousLineProposalEligible']) # shapes remain separate
        diff=V.compare_inspections(self.inspect(before),self.inspect(after))
        self.assertGreater(diff['pads'][0]['deltaPixels'],0)
        self.assertFalse(diff['executionAuthorized'])

    def test_random_nonpaste_pixels_do_not_become_components(self):
        path=self.image('noise.png',lambda d:(d.point((15,15),fill=(220,220,220)),d.point((5,5),fill=(255,0,0))))
        report=self.inspect(path)
        self.assertEqual(report['pasteLikeAreaPx'],0)
        self.assertEqual([p['status'] for p in report['pads']],['not-detected','not-detected'])

    def test_comparison_binds_exact_projection_and_validation_rejects_bad_pads(self):
        img=self.image('zeros.png',lambda d:None); a=self.inspect(img)
        changed=[dict(p) for p in self.pads]; changed[0]={'id':'U1.1','polygonPx':[[11,10],[30,10],[30,25],[11,25]]}
        b=V.inspect_image(img,changed,paste_rgb=(220,220,220),tolerance=10,row_groups=self.rows)
        with self.assertRaises(ValueError): V.compare_inspections(a,b)
        with self.assertRaises(ValueError): V.inspect_image(img,self.pads+[self.pads[0]],paste_rgb=(1,2,3))
        out=[{'id':'bad','polygonPx':[[-1,0],[2,0],[2,2],[0,2]]}]
        with self.assertRaises(ValueError): V.inspect_image(img,out,paste_rgb=(1,2,3))


if __name__=='__main__': unittest.main()
