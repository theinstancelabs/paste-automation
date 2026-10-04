import importlib.util,pathlib,unittest
from unittest.mock import patch
s=importlib.util.spec_from_file_location('preset',pathlib.Path(__file__).with_name('conditioned-30deg.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class PresetTests(unittest.TestCase):
    def test_preview_fixed_recipe(self):
        with patch.object(m.subprocess,'run') as run:
            m.main(['--refs','R2,R3','--condition-refs','R1'])
            cmd=run.call_args.args[0]
            self.assertNotIn('--execute',cmd)
            for key,value in {'--dose':'30','--push-deg-s':'50','--retract-percent':'10','--retract-deg-s':'100','--dwell-ms':'1000','--retract-dwell-ms':'0','--gap-mm':'0.1','--condition-dose':'0.25'}.items():self.assertEqual(cmd[cmd.index(key)+1],value)
            self.assertIn('--retract-each-pad',cmd)
            self.assertTrue(run.call_args.kwargs['check'])
    def test_execute_forwarded_once(self):
        with patch.object(m.subprocess,'run') as run:
            m.main(['--refs','D2','--condition-refs','D1','--execute','--root','/tmp/example'])
            self.assertEqual(run.call_count,1);self.assertEqual(run.call_args.args[0].count('--execute'),1)
    def test_conditioning_required_distinct(self):
        with patch.object(m.subprocess,'run') as run:
            with self.assertRaises(SystemExit):m.main(['--refs','R1'])
            with self.assertRaises(SystemExit):m.main(['--refs','R1','--condition-refs','R1'])
            run.assert_not_called()
if __name__=='__main__':unittest.main()
