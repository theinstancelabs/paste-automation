import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image, ImageDraw
from tip_height_interval import analyze, endpoint, interpolate_interval


def image_bytes(row, salt=0):
    im=Image.new('RGB',(1280,720),'white');d=ImageDraw.Draw(im)
    d.rectangle((595,80,605,row),fill='black');d.point((salt%1280,700),fill=(salt%250,1,2))
    out=io.BytesIO();im.save(out,format='PNG');return out.getvalue()


class HeightTests(unittest.TestCase):
    def fixture(self, root):
        def bound(name,data):
            p=root/name;p.write_bytes(data);return {'path':str(p),'sha256':hashlib.sha256(data).hexdigest()}
        q={'schema':1,'scope':'same-world-XY-side-endpoint-height-interval','operator':'test',
           'cameraSetupId':'test fixed camera','sameWorldXYReview':'synthetic same target','n1DatumReview':'synthetic datum',
           'localLinearityReview':'synthetic linear projection', 'fixedCameraAndLightingReviewed':True,'sameWorldXYReviewed':True,
           'stationaryCapturesReviewed':True,'endpointIdentityReviewed':True,'n1DatumUncertaintyMm':.1,
           'sameWorldXYRowUncertaintyPx':.5,'localLinearityUncertaintyMm':.01,'rawZUncertaintyMm':.02,
           'referenceN1HeightMm':31.5,'coupledZSumMm':63,'reviewedN1RawZIntervalMm':[31.5,32.5],'reviewedRightRawZIntervalMm':[30.5,32.5],'poses':{},
           'bottomAlignmentEvidence':{'N1':bound('align-left.png',image_bytes(300,41)), 'N2':bound('align-right.png',image_bytes(300,42))}}
        for i,(name,z,y) in enumerate([('n1Reference',31.5,300),('n1Dither',32.5,280),('n1Return',31.5,300),('rightLow',30.5,280),('rightHigh',32.5,320)]):
            r={'status':'completed-Z-observation-awaiting-image-review','controllerPositionVerified':True,'uncertainCompletion':False,'reported':{'X':1 if name.startswith('n1') else 2,'Y':1,'Z':z,'A':720,'B':720},'request':{'jvmStartMs':42,'liveConfigurationSha256':'a'*64}}
            frames=[{'image':bound(name+str(j)+'.png',image_bytes(y,i*2+j+1)),'roi':[580,70,620,350],'seed':[600,100],'thresholds':[40,80],'polarity':'dark','annotationUncertaintyPx':.5} for j in range(2)]
            q['poses'][name]={'positionEvidence':bound(name+'.json',json.dumps(r).encode()),'frames':frames}
        for head,name in [('N1','n1Reference'),('N2','rightLow')]:
            image=q['bottomAlignmentEvidence'][head];ref=q['poses'][name]['positionEvidence'];r=json.loads(Path(ref['path']).read_bytes());r['afterImages']={'bottom':{'path':Path(image['path']).name}};ref=bound(head+'-alignment.json',json.dumps(r).encode());q['bottomAlignmentEvidence'][head]={'image':image,'positionEvidence':ref}
        return q

    def test_endpoint_seed_threshold_and_clipping(self):
        data=image_bytes(300)
        result=endpoint(data,[580,70,620,350],[600,100],[40,80],'dark',.5)
        self.assertEqual(result['endpointRowIntervalPx'],[299.5,300.5])
        for roi,seed in [([580,70,620,301],[600,100]),([595,70,620,350],[600,100]),([580,70,620,350],[610,100])]:
            with self.assertRaises(ValueError):endpoint(data,roi,seed,[40,80],'dark',.5)

    def test_interpolation_corner_hull_no_extrapolation(self):
        out=interpolate_interval(30,[279,281],32,[319,321],[299,301])
        self.assertAlmostEqual(out[0],30.9);self.assertAlmostEqual(out[1],31.1)
        for low,high,target in [([280,302],[300,320],[299,301]),([279,281],[319,321],[280,300])]:
            with self.assertRaises(ValueError):interpolate_interval(30,low,32,high,target)

    def test_complete_synthetic_interval_contains_zero_and_explicit_uncertainty(self):
        with tempfile.TemporaryDirectory() as d:
            out=analyze(self.fixture(Path(d)))
            self.assertLess(out['rightTipOffsetIntervalMm'][0],-.1)
            self.assertGreater(out['rightTipOffsetIntervalMm'][1],.1)
            self.assertFalse(out['physicalCalibrationEstablished'])
            self.assertFalse(out['motionAuthorized'])

    def test_repeated_frames_hash_change_missing_attestation_fail(self):
        with tempfile.TemporaryDirectory() as d:
            q=self.fixture(Path(d))
            for change in ('repeat','hash','review'):
                b=copy.deepcopy(q)
                if change=='repeat':b['poses']['n1Reference']['frames'][1]=b['poses']['n1Reference']['frames'][0]
                elif change=='hash':b['poses']['rightLow']['positionEvidence']['sha256']='0'*64
                else:b['sameWorldXYReviewed']=False
                with self.assertRaises(ValueError):analyze(b)

    def test_session_xy_rotation_and_z_return_changes_fail(self):
        with tempfile.TemporaryDirectory() as d:
            q=self.fixture(Path(d))
            for name,key,value in [('n1Return','Z',31.6),('n1Dither','X',2),('rightLow','B',719),('rightHigh','jvmStartMs',43)]:
                b=copy.deepcopy(q);ref=b['poses'][name]['positionEvidence'];p=Path(ref['path']);original=p.read_bytes();r=json.loads(original)
                if key=='jvmStartMs':r['request'][key]=value
                else:r['reported'][key]=value
                data=json.dumps(r).encode();p.write_bytes(data);ref['sha256']=hashlib.sha256(data).hexdigest()
                with self.assertRaises(ValueError):analyze(b)
                p.write_bytes(original)

    def test_explicit_wider_bracket_supports_minus_one_offset(self):
        with tempfile.TemporaryDirectory() as d:
            q=self.fixture(Path(d));q['reviewedRightRawZIntervalMm']=[29.5,31.5]
            for name,z in [('rightLow',29.5),('rightHigh',31.5)]:
                ref=q['poses'][name]['positionEvidence'];p=Path(ref['path']);r=json.loads(p.read_bytes());r['reported']['Z']=z
                data=json.dumps(r).encode();p.write_bytes(data);ref['sha256']=hashlib.sha256(data).hexdigest()
            out=analyze(q)['rightTipOffsetIntervalMm']
            self.assertLess(out[0],-1);self.assertGreater(out[1],-1)
            q['reviewedRightRawZIntervalMm']=[30.5,31.5]
            with self.assertRaisesRegex(ValueError,'outside reviewed bracket'):analyze(q)

    def test_nonterminal_source_and_unlinked_alignment_fail(self):
        with tempfile.TemporaryDirectory() as d:
            q=self.fixture(Path(d));ref=q['poses']['n1Reference']['positionEvidence'];p=Path(ref['path']);r=json.loads(p.read_bytes());r['status']='query-started'
            data=json.dumps(r).encode();p.write_bytes(data);ref['sha256']=hashlib.sha256(data).hexdigest()
            with self.assertRaisesRegex(ValueError,'terminal'):analyze(q)
            q=self.fixture(Path(d));q['bottomAlignmentEvidence']['N1']['image']=q['bottomAlignmentEvidence']['N2']['image']
            with self.assertRaisesRegex(ValueError,'report capture'):analyze(q)

    def test_explicit_five_mm_dither_and_exact_review_interval(self):
        with tempfile.TemporaryDirectory() as d:
            q=self.fixture(Path(d));q['reviewedN1RawZIntervalMm']=[31.5,36.5]
            ref=q['poses']['n1Dither']['positionEvidence'];p=Path(ref['path']);r=json.loads(p.read_bytes());r['reported']['Z']=36.5
            data=json.dumps(r).encode();p.write_bytes(data);ref['sha256']=hashlib.sha256(data).hexdigest()
            for i,f in enumerate(q['poses']['n1Dither']['frames']):
                data=image_bytes(200,80+i);Path(f['image']['path']).write_bytes(data);f['image']['sha256']=hashlib.sha256(data).hexdigest()
            self.assertLess(analyze(q)['rightTipOffsetIntervalMm'][0],0)
            q['reviewedN1RawZIntervalMm']=[31.5,37]
            with self.assertRaisesRegex(ValueError,'must equal'):analyze(q)
            q['reviewedN1RawZIntervalMm']=[31.5,37.5];r['reported']['Z']=37.5
            data=json.dumps(r).encode();p.write_bytes(data);ref['sha256']=hashlib.sha256(data).hexdigest()
            with self.assertRaisesRegex(ValueError,'at most 5'):analyze(q)

    def test_wrong_polarity_and_unbracketed_row_fail(self):
        with tempfile.TemporaryDirectory() as d:
            q=self.fixture(Path(d))
            for frame in q['poses']['n1Dither']['frames']:
                data=image_bytes(320,100+frame['seed'][0]+len(frame['image']['path']))
                Path(frame['image']['path']).write_bytes(data);frame['image']['sha256']=hashlib.sha256(data).hexdigest()
            with self.assertRaisesRegex(ValueError,'decreasing image row'):
                # Keep the two independent frames distinct without changing their endpoints.
                f=q['poses']['n1Dither']['frames'][1];data=image_bytes(320,200);Path(f['image']['path']).write_bytes(data);f['image']['sha256']=hashlib.sha256(data).hexdigest()
                analyze(q)


if __name__=='__main__':unittest.main()
