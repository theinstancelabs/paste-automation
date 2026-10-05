import importlib.util,json,pathlib,tempfile,unittest
from unittest.mock import patch
s=importlib.util.spec_from_file_location('experiment',pathlib.Path(__file__).with_name('prepare-operator-experiment.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class TestPrepare(unittest.TestCase):
 def test_tip_xy_correction_preview_evidence_is_hash_bound(self):
  with tempfile.TemporaryDirectory() as d:
   evidence=pathlib.Path(d)/'centroids.json';evidence.write_text('{"scope":"repeated-deposit-centroid-offset"}')
   digest=__import__('hashlib').sha256(evidence.read_bytes()).hexdigest()
   m.verify_tip_xy_evidence({'tipXYCorrection':{'evidence':{'path':str(evidence),'sha256':digest}}})
   with self.assertRaisesRegex(ValueError,'evidence changed'):
    m.verify_tip_xy_evidence({'tipXYCorrection':{'evidence':{'path':str(evidence),'sha256':'0'*64}}})
   evidence.unlink()
   with self.assertRaisesRegex(ValueError,'evidence changed'):
    m.verify_tip_xy_evidence({'tipXYCorrection':{'evidence':{'path':str(evidence),'sha256':digest}}})
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
 def test_same_cycle_conditioning_copies_main_recipe_and_omits_hop(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'automation/plans').mkdir(parents=True)
   with patch.object(m,'validate',return_value={'plannedGrossDegrees':231,'endingPendingRetractDegrees':7}), patch('builtins.print') as printed:
    q=m.main(['dispense-and-survey','--refs','R39','R40','--condition-refs','D36','--condition-same-cycle',
      '--dose','35','--push-deg-s','16','--retract-percent','20','--retract-deg-s','100',
      '--dwell-ms','2000','--retract-dwell-ms','500','--gap-mm','.2','--paired-pad-hop-mm','.5','--root',str(root)])
   preview=json.loads(printed.call_args[0][0])['preview']
   self.assertEqual(preview['endingPendingRetractDegrees'],7)
   self.assertEqual(preview['plannedGrossDegrees'],231)
   expected=dict(q['recipe']);expected.pop('pairedPadHopMm')
   self.assertEqual(q['conditioning']['recipe'],expected)
   self.assertEqual(q['recipe']['pairedPadHopMm'],.5)
   self.assertEqual(q['references'],['R39','R40']);self.assertEqual(q['conditioning']['references'],['D36'])
  with self.assertRaises(SystemExit):m.main(['dispense-and-survey','--refs','R39','--condition-same-cycle'])
 def test_independent_pad_modes(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'automation/plans').mkdir(parents=True)
   with patch.object(m,'validate',return_value={'plannedGrossDegrees':1}):
    q=m.main(['dispense-and-survey','--refs','R27','--condition-refs','D25','--pad-mode','2','--condition-pad-mode','1','--dose','30','--push-deg-s','50','--retract-percent','5','--retract-deg-s','100','--dwell-ms','0','--retract-dwell-ms','0','--gap-mm','.1','--root',str(root)])
   self.assertEqual(q['recipe']['padMode'],'2');self.assertEqual(q['conditioning']['recipe']['padMode'],'1')
if __name__=='__main__':unittest.main()
