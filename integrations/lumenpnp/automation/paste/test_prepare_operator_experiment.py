import importlib.util,json,pathlib,tempfile,unittest
from unittest.mock import patch
s=importlib.util.spec_from_file_location('experiment',pathlib.Path(__file__).with_name('prepare-operator-experiment.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class TestPrepare(unittest.TestCase):
 def test_active_and_preview_preserved(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);plans=root/'automation/plans';plans.mkdir(parents=True);active=plans/'operator-batch-request.json';active.write_text(json.dumps({'id':'active'}));original=active.read_bytes()
   with self.assertRaisesRegex(ValueError,'pending/active'):m.active_guard(root)
   with patch.object(m,'validate',return_value={'plannedGrossDegrees':0}):q=m.main(['survey','--refs','R1,R2','--root',str(root)])
   self.assertEqual(active.read_bytes(),original);self.assertEqual(q['references'],['R1','R2']);self.assertTrue((plans/('operator-'+q['id']+'.json')).exists())
 def test_dispense_requires_explicit_settings(self):
  with self.assertRaises(SystemExit):m.main(['dispense-and-survey','--refs','R1'])
 def test_terminal_request_allows_new_dispatch(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'automation/plans').mkdir(parents=True);(root/'automation/plans/operator-batch-request.json').write_text(json.dumps({'id':'old'}));out=root/'automation/evidence/operator-batches/old';out.mkdir(parents=True);(out/'report.json').write_text(json.dumps({'status':'completed-awaiting-image-review'}));m.active_guard(root)
 def test_independent_pad_modes(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'automation/plans').mkdir(parents=True)
   with patch.object(m,'validate',return_value={'plannedGrossDegrees':1}):
    q=m.main(['dispense-and-survey','--refs','R27','--condition-refs','D25','--pad-mode','2','--condition-pad-mode','1','--dose','30','--push-deg-s','50','--retract-percent','5','--retract-deg-s','100','--dwell-ms','0','--retract-dwell-ms','0','--gap-mm','.1','--root',str(root)])
   self.assertEqual(q['recipe']['padMode'],'2');self.assertEqual(q['conditioning']['recipe']['padMode'],'1')
if __name__=='__main__':unittest.main()
