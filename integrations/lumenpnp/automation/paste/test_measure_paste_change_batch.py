import importlib.util
import unittest
from pathlib import Path
from PIL import Image, ImageDraw

MODULE=Path(__file__).with_name('measure_paste_change_batch.py')
SPEC=importlib.util.spec_from_file_location('paste_change_batch',MODULE)
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)

class PasteChangePixelTests(unittest.TestCase):
 def test_changed_patch_centroid_is_measured_from_bare_copper_centroid(self):
  before=Image.new('RGB',(100,80),(20,40,70));draw=ImageDraw.Draw(before);draw.rectangle((30,30,39,39),fill=(230,235,235))
  after=before.copy();ImageDraw.Draw(after).rectangle((33,34,36,37),fill=(120,120,120))
  r=M._photometric_delta(before,after,[20,20,50,50],(0,0),(0.1,0.1))
  self.assertEqual(r['bareCopperPixels'].__len__(),100)
  self.assertEqual(r['changedPixels'].__len__(),16)
  self.assertEqual(r['centroidShiftPx'],[0.0,1.0])
  self.assertEqual(r['centroidShiftMm'],[0.0,0.1])
  self.assertAlmostEqual(r['equivalentDiameterMm'],2*(0.16/3.141592653589793)**0.5)

 def test_no_photometric_change_has_no_fabricated_centroid(self):
  before=Image.new('RGB',(100,80),(20,40,70));ImageDraw.Draw(before).rectangle((30,30,39,39),fill=(230,235,235))
  result=M._photometric_delta(before,before.copy(),[20,20,50,50],(0,0),(0.1,0.1))
  self.assertEqual(result['changedPixels'],[])
  self.assertIsNone(result['changedCentroidPx'])
  self.assertEqual(result['changedAreaMm2'],0)

if __name__=='__main__':unittest.main()
