import unittest,math
from pathlib import Path
from fiducial_registration import fit,fiducials
class FiducialFitTests(unittest.TestCase):
    def test_known_rotation_translation_scale(self):
        points=[[62.5,5],[12.5,70],[62.5,70]];angle=.1;scale=1.003
        observed=[[scale*(math.cos(angle)*x-math.sin(angle)*y)+200,scale*(math.sin(angle)*x+math.cos(angle)*y)+100] for x,y in points]
        result=fit(points,observed);self.assertAlmostEqual(result['scale'],scale);self.assertAlmostEqual(result['rotationDegrees'],math.degrees(angle));self.assertLess(result['maxResidualMm'],1e-10);self.assertTrue(result['passesOfflineGeometryGate'])
    def test_bad_third_point_cannot_hide_in_free_affine(self):
        points=[[0,0],[50,0],[0,65]];observed=[[100,100],[150,100],[101,165]]
        self.assertFalse(fit(points,observed)['passesOfflineGeometryGate'])
        self.assertFalse(fit(points,observed,True)['passesOfflineGeometryGate'])
    def test_scale_reflection_degeneracy(self):
        points=[[0,0],[50,0],[0,65]]
        self.assertFalse(fit(points,[[0,0],[55,0],[0,71.5]])['passesOfflineGeometryGate'])
        self.assertFalse(fit(points,[[0,0],[-50,0],[0,65]])['passesOfflineGeometryGate'])
        with self.assertRaises(ValueError):fit([[0,0],[1,1],[2,2]],points)
    def test_canonical_source_fid1_is_not_old_modified_xml(self):
        p=Path(__file__).resolve().parents[3]/'pnp/pcb/ftp/ftp.kicad_pcb'
        if not p.is_file(): self.skipTest('canonical board not in source export')
        self.assertEqual(fiducials(p.read_bytes()),{'FID1':[62.5,-5.0],'FID2':[12.5,-70.0],'FID3':[62.5,-70.0]})

class FiducialEvidenceTests(unittest.TestCase):
    def test_same_bytes_provenance_and_changed_session_rejection(self):
        import tempfile,json,hashlib
        from PIL import Image,ImageDraw
        from fiducial_registration import analyze
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);board=root/'board.kicad_pcb'
            nominal={'FID1':(62.5,5),'FID2':(12.5,70),'FID3':(62.5,70)}
            board.write_text('(kicad_pcb '+''.join(f'(footprint "test" (layer "F.Cu") (property "Reference" "{k}") (at {x} {-y}) (pad "1" smd circle (at 0 0)))' for k,(x,y) in nominal.items())+')')
            reports={}
            for i,(ref,(x,y)) in enumerate(nominal.items()):
                folder=root/ref;folder.mkdir();image=Image.new('RGB',(64,64));draw=ImageDraw.Draw(image);draw.ellipse((27,27,37,37),fill=(220,0,0));image.save(folder/'top.png')
                raw={'X':x+100,'Y':y+100,'Z':26.5,'A':200,'B':720};pose={'x':raw['X'],'y':raw['Y'],'z':15,'rotation':0}
                identity=f'12345678-1234-1234-1234-{i:012d}'
                q={'id':identity,'scope':'camera-survey-single-raw-XY-axis','jvmStartMs':1,'liveConfigurationSha256':'a'*64}
                r={'schema':1,'id':identity,'status':'completed-camera-survey-awaiting-image-review','request':q,'motionSubmitted':True,'nativeMotionCompletionReported':True,'controllerPositionVerified':True,'independentFirmwareStepVerified':True,'uncertainCompletion':False,'after':{'reported':raw},'afterQuerySnapshot':{'raw':raw,'driver':raw,'nativePoses':{k:pose for k in ['N1','N2','top','bottom']}},'afterImages':{'top':{'path':'top.png'}}}
                path=folder/'report.json';path.write_text(json.dumps(r));reports[ref]=str(path)
            request={'board':str(board),'reports':reports,'roi':[20,20,45,45],'thresholds':[60,80,100,120]}
            result=analyze(request);self.assertTrue(result['models']['uncorrected']['rigid']['passesOfflineGeometryGate'])
            self.assertEqual(result['board']['sha256'],hashlib.sha256(board.read_bytes()).hexdigest())
            for sample in result['samples']:
                for key in ['report','image']:
                    provenance=sample[key];self.assertEqual(provenance['sha256'],hashlib.sha256(Path(provenance['path']).read_bytes()).hexdigest())
            path=Path(reports['FID3']);changed=json.loads(path.read_bytes());changed['request']['jvmStartMs']=2;path.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):analyze(request)
