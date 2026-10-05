import contextlib
import datetime as dt
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from automation.scripts import run_observed_prime_segment as runner


class ObservedPrimeTests(unittest.TestCase):
    def test_initial_capture_requires_one_complete_real_jpeg(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'frames';out.mkdir();(out/'0000.jpg').write_bytes(b'\xff\xd8\xffimage')
            captured=dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
            (out/'manifest.json').write_text(json.dumps({'status':'complete','errors':[],'captures':[{'file':'0000.jpg','captured_at_utc':captured}]}))
            result=runner.verified_initial_capture(out,Mock(return_value=subprocess.CompletedProcess([],0,'' ,'')))
            self.assertEqual(result['status'],'complete')
            (out/'0000.jpg').write_bytes(b'not-a-jpeg')
            with self.assertRaisesRegex(RuntimeError,'malformed'):
                runner.verified_initial_capture(out,Mock(return_value=subprocess.CompletedProcess([],0,'' ,'')))

    def test_requested_rate_contract_defaults_to_five_and_accepts_5_to_20(self):
        profile={'id':'a'*64,'sessionId':'s'}
        ledger_path=Path('/tmp/operator-prime-test-ledger.json')
        ledger={'lastVerifiedRaw':{'B':-100},'profileId':profile['id'],'entries':[{'id':'old','status':'verified'}], 'status':'verified'}
        for speed in ('default','5','10','20'):
            args=[] if speed=='default' else ['--speed',speed]
            if speed=='default':args+=['--degrees','30','--observe-seconds','8']
            output=io.StringIO()
            with patch.object(runner,'state',return_value=(profile,ledger_path,ledger)), contextlib.redirect_stdout(output):
                self.assertEqual(runner.main(args),0)
            request=json.loads(output.getvalue())['request']
            self.assertEqual(request['speedDegreesPerSecond'],5 if speed=='default' else float(speed))
            self.assertEqual(json.loads(output.getvalue())['observeSeconds'],8 if speed=='default' else 18)
        for speed in ('1.5','4.99','20.01'):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                runner.main(['--speed',speed])
        for args in (['--degrees','31'],['--degrees','30','--observe-seconds','7'],['--observe-seconds','61'],['--degrees','30','--speed','5','--observe-seconds','7']):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                runner.main(args)

    def test_failed_camera_preflight_never_creates_or_dispatches_prime_request(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'automation/plans').mkdir(parents=True);(root/'automation/evidence/operator-paste-runs/s').mkdir(parents=True)
            (root/'automation/evidence/new-syringe-20261004').mkdir()
            profile={'id':'a'*64,'sessionId':'s'};(root/'automation/plans/paste-operator-profile.json').write_text(json.dumps(profile))
            ledger={'status':'verified','profileId':profile['id'],'entries':[{'id':'old','status':'verified'}],'usedAdditionalGrossDegrees':60,'pendingRetractDegrees':0,'lastVerifiedRaw':{'X':1,'Y':2,'Z':32.25,'A':200,'B':-100}}
            (root/'automation/evidence/operator-paste-runs/s/budget-ledger.json').write_text(json.dumps(ledger))
            dispatch=Mock()
            with patch.object(runner,'R',root),contextlib.redirect_stdout(io.StringIO()),self.assertRaisesRegex(RuntimeError,'preflight failed'):
                runner.main(['--execute'],dispatch=dispatch,capture_runner=Mock(return_value=subprocess.CompletedProcess([],1,'','offline')))
            dispatch.assert_not_called()
            self.assertFalse((root/'automation/plans/operator-prime-segment-request.json').exists())


if __name__=='__main__':unittest.main()
