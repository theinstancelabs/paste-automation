import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw

MODULE=Path(__file__).with_name('cv_pad_availability.py')
SPEC=importlib.util.spec_from_file_location('cv_pad_availability',MODULE)
CV=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(CV)


class CvAvailabilityTests(unittest.TestCase):
    def test_projects_camera_map_and_measures_both_bare_sibling_pads_review_only(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); img=Image.new('RGB',(100,80),(20,40,60)); d=ImageDraw.Draw(img)
            d.rectangle((47,37,52,42),fill=(230,235,235)); d.rectangle((47,39,52,44),fill=(230,235,235))
            ip=root/'camera.png'; img.save(ip)
            report={'status':'completed-camera-survey-awaiting-image-review',
              'afterQuerySnapshot':{'nativePoses':{'top':{'x':0.0,'y':0.0}}},
              'afterImages':{'top':{'path':'camera.png','width':100,'height':80}}}
            rp=root/'camera-report.json'; rp.write_text(json.dumps(report))
            registration={'scope':'offline-native-fresh-ftp-two-fiducial-transform-with-third-point-check',
              'acceptance':{'passed':True},'physicalRegistrationEstablished':False,'executionReady':False,
              'board':{'sha256':'a'*64},'transformFromFID1FID2':{'matrix':[[1,0],[0,1]],'translationMm':[0,0]}}
            job={'board':{'sha256':'a'*64},'pads':[
              {'id':'R1.1','reference':'R1','centerMm':[0,0],'sizeMm':[0.4,0.4],'rotationDeg':0},
              {'id':'R1.2','reference':'R1','centerMm':[0,0.2],'sizeMm':[0.4,0.4],'rotationDeg':0}]}
            output=root/'out'
            result=CV.scan(registration,{'R1.1':str(rp),'scrap5':str(rp)},output_dir=output,job=job,
                           scale_x_mm_per_px=0.1,scale_y_mm_per_px=0.1)
            self.assertEqual([r['padId'] for r in result['measurements']],['R1.1','R1.2'])
            self.assertEqual(result['measurements'][0]['expectedCenterPx'],[49.5,39.5])
            self.assertEqual(result['measurements'][1]['expectedCenterPx'],[49.5,41.5])
            self.assertGreater(result['measurements'][1]['brightFraction'],0.5)
            self.assertFalse(result['autoAuthorize'])
            self.assertTrue(all(Path(r['rawMaskPath']).is_file() for r in result['measurements']))
            diff=CV.compare_scans(result,result)
            self.assertEqual(len(diff['pads']),2)
            self.assertEqual(diff['pads'][1]['brightFractionDelta'],0)
            self.assertFalse(diff['autoAuthorize'])
            view_plan=CV.plan_camera_view_set(registration,{'R1.1':str(rp)},job=job,margin_px=5,
              scale_x_mm_per_px=0.1,scale_y_mm_per_px=0.1)
            self.assertEqual(view_plan['status'],'complete-review-only')
            self.assertEqual(view_plan['viewCount'],1)
            self.assertEqual(set(view_plan['views'][0]['coveredPadIds']),{'R1.1','R1.2'})
            self.assertFalse(view_plan['motionAuthorized'])

    def test_rejects_unreviewed_registration_and_binds_actual_capture_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); bad={'scope':'wrong','acceptance':{'passed':False}}
            with self.assertRaises(ValueError): CV.scan(bad,{},output_dir=root/'bad',job={'board':{'sha256':'x'},'pads':[]})


if __name__=='__main__': unittest.main()
