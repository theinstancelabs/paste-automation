import importlib.util, tempfile, unittest
from pathlib import Path
from PIL import Image,ImageDraw
s=importlib.util.spec_from_file_location('m',Path(__file__).with_name('measure_paste_repeat.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class CoverageTests(unittest.TestCase):
 def test_translation_and_known_coverage(self):
  with tempfile.TemporaryDirectory() as d:
   a=Image.new('RGB',(300,400),(0,100,160));p=a.load()
   for y in range(200):
    for x in range(300):p[x,y]=(0,(x*13+y*19)%180,160)
   ImageDraw.Draw(a).rectangle((100,250,139,289),fill='white');b=Image.new('RGB',a.size,(0,100,160));b.paste(a,(2,1));ImageDraw.Draw(b).rectangle((102,251,121,290),fill=(0,30,80));a.save(Path(d)/'a.png');b.save(Path(d)/'b.png')
   r=m.measure(Path(d)/'a.png',Path(d)/'b.png',[{'id':'R1.1','roiPx':[90,240,150,300]}],[.01,.01]);self.assertEqual(r['registration']['translationPx'],[2,1]);self.assertEqual(r['pads'][0]['brightPadCoverageFraction'],.5);self.assertFalse(r['volumeMeasured'])
 def test_unchanged_pad_has_zero_coverage(self):
  with tempfile.TemporaryDirectory() as d:
   im=Image.new('RGB',(300,400),(0,100,160));ImageDraw.Draw(im).rectangle((100,250,139,289),fill='white');im.save(Path(d)/'a.png')
   # textured fixed strip removes translation ambiguity
   p=im.load()
   for y in range(200):
    for x in range(300):p[x,y]=(0,(x*13+y*19)%180,160)
   im.save(Path(d)/'a.png');r=m.measure(Path(d)/'a.png',Path(d)/'a.png',[{'id':'R1.1','roiPx':[90,240,150,300]}],[.01,.01]);self.assertEqual(r['pads'][0]['brightPadCoverageFraction'],0)
if __name__=='__main__':unittest.main()
