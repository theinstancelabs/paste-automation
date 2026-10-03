import importlib.util
from pathlib import Path
import unittest
import json
import time
import datetime
import tempfile
from types import SimpleNamespace
from unittest import mock


SCRIPT = Path(__file__).with_name('run-operator-vacuum-reference.py')
SPEC = importlib.util.spec_from_file_location('run_operator_vacuum_reference', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WaitReportTests(unittest.TestCase):
    def test_controlled_stop_cleanup_error_is_transient_until_pump_off_terminal(self):
        reports = iter((
            {'status': 'controlled-policy-vacuum-off-acknowledged',
             'error': 'controlled policy stop; cleanup still verifying pose'},
            {'status': 'stopped-policy-vacuum-off-position-verified',
             'error': None, 'normalVacuumOffAcknowledged': True,
             'controllerPositionVerified': True},
        ))
        with (mock.patch.object(Path, 'is_file', return_value=True),
              mock.patch.object(MODULE, 'load', side_effect=lambda _path: next(reports)),
              mock.patch.object(MODULE.time, 'monotonic', side_effect=(0, 0, 0)),
              mock.patch.object(MODULE.time, 'sleep')):
            report = MODULE.wait_report('/tmp/synthetic-probe-report.json',
                                        'completed-seal-candidate-held-at-z-awaiting-physical-review')
        self.assertEqual(report['status'], 'stopped-policy-vacuum-off-position-verified')
        self.assertTrue(report['normalVacuumOffAcknowledged'])


class PrepareBoundaryTests(unittest.TestCase):
    def test_native_z_roundoff_accepts_exact_40_steps_and_review_interval(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);source=base/'barrier.json';image=base/'overview.png';review=base/'review.json'
            source.write_text(json.dumps({'status':'completed-read-only-position-barrier',
                'controllerPositionVerified':True,'noMotionCommandSubmitted':True,
                'uncertainCompletion':False,'finishedAt':(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(seconds=2)).isoformat(),
                'afterQuerySnapshot':{'raw':{'Z':6.250000000000007}}}))
            image.write_bytes(b'not-read-by-this-validation-test')
            data={'operator':'test','reviewedMs':time.time_ns()//1_000_000,'reviewRecord':'reviewed exact two-mm envelope',
                  'jointInterval':{'reviewedForCurrentPose':True,'minRawZ':4.25,'maxRawZ':6.25,'reviewRecord':'same envelope'}}
            for key in ('operatorVerifiedEmptyFreeAirBaseline','operatorVerifiedProbeTarget',
                        'operatorVerifiedJointEnvelope','bothHeadsClearAlongEnvelope','motionAreaClear',
                        'noHeldPartsObserved','n2Quarantined','nativeZConfigurationReviewed'):
                data[key]=True
            review.write_text(json.dumps(data))
            args=SimpleNamespace(source=source,image=image,review=review,floor=4.25,
                                 execute=False,target='synthetic fiducial',output=base/'output')
            # Stop immediately after validation, before builders or dispatch.
            with mock.patch.object(Path,'mkdir',side_effect=RuntimeError('validation reached output creation')):
                with self.assertRaisesRegex(RuntimeError,'validation reached output creation'):
                    MODULE.prepare(args)
            args.floor=4.20
            with self.assertRaisesRegex(ValueError,'at most 2.00'):
                MODULE.prepare(args)
            args.floor=4.25;data['jointInterval']['maxRawZ']=6.249
            review.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'jointInterval'):
                MODULE.prepare(args)


if __name__ == '__main__':
    unittest.main()
