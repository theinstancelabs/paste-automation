import hashlib
import json
import unittest

from generic_paste_adapter import prepare_generic_job


def bind(job):
    return hashlib.sha256(json.dumps(job, indent=2, sort_keys=True, allow_nan=False).encode()+b'\n').hexdigest()


class GenericPasteAdapterTests(unittest.TestCase):
    def setUp(self):
        self.job={'scope':'offline-kicad-paste-job','board':{'sha256':'f'*64},
          'pads':[{'id':'R1.1','centerMm':[1.0,2.0]}],
          'fiducials':[{'reference':x} for x in ('FID1','FID2','FID3')],
          'finePitchGroups':[],
          'pasteModel':{'calibrationVerified':True,'calibrationStatus':'verified','thicknessMm':0.1,'apertureScaling':1.0}}
        self.job_id=bind(self.job)
        self.review={'scope':'generic-paste-human-review','cadJobSha256':self.job_id,'reviewedBy':'reviewer',
          'transform':{'reviewed':True,'evidenceSha256':'a'*64,'rmsResidualMm':0.03,
            'fiducials':[{'reference':x} for x in ('FID1','FID2','FID3')],
            'cadToMachineAffine':[[1,0,10],[0,1,20]]},
          'pads':[{'padId':'R1.1','identityReviewed':True,'availabilityReviewed':True,'evidenceSha256':'b'*64,
            'surfaceReviewed':True,'surfaceEvidenceSha256':'c'*64,'rawZMm':58.4,'estimatedGapMm':0.4,
            'gapUncertaintyMm':0.1,'machineXYMm':[11,22]}],
          'recipe':{'measuredCalibration':True,'calibrationEvidenceSha256':'d'*64,'padDoseDegrees':{'R1.1':8}},
          'bothHeadClearance':{'reviewed':True,'evidenceSha256':'e'*64,
            'headBoundsMm':{h:{'minX':0,'maxX':100,'minY':0,'maxY':100} for h in ('N1','N2')}}}

    def test_valid_review_generates_offline_dot_preview_only(self):
        result=prepare_generic_job(self.job,self.job_id,self.review)
        self.assertTrue(result['previewAuthorized'])
        self.assertFalse(result['executionAuthorized'])
        self.assertEqual(result['individualDotTargets'][0]['machineXYMm'],[11,22])
        self.assertEqual(result['individualDotTargets'][0]['depositKind'],'individual-dot-only')
        self.assertIn('human-reviewed-input-unverified-by-adapter',result['headClearanceStatus'])

    def test_incomplete_review_reports_exact_missing_requirements(self):
        result=prepare_generic_job(self.job,self.job_id,{})
        self.assertFalse(result['previewAuthorized'])
        self.assertFalse(result['individualDotTargets'])
        self.assertTrue(any('measured flow calibration' in x for x in result['missingRequirements']))
        self.assertFalse(result['executionAuthorized'])

    def test_job_hash_mismatch_and_transform_disagreement_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'does not match'):
            prepare_generic_job(self.job,'0'*64,self.review)
        self.review['pads'][0]['machineXYMm']=[11.2,22]
        result=prepare_generic_job(self.job,self.job_id,self.review)
        self.assertFalse(result['previewAuthorized'])
        self.assertTrue(any('affine' in x for x in result['validationErrors']))

    def test_fine_pitch_never_becomes_a_line_dispatch(self):
        self.job['finePitchGroups']=[{'id':'row-u1','padIds':['R1.1','R1.2'],
            'validatedLineRecipe':{'reviewed':True,'evidenceSha256':'f'*64}}]
        self.job['pads'].append({'id':'R1.2','centerMm':[2.0,2.0]})
        self.review['pads'].append({'padId':'R1.2','identityReviewed':True,'availabilityReviewed':True,'evidenceSha256':'b'*64,
            'surfaceReviewed':True,'surfaceEvidenceSha256':'c'*64,'rawZMm':58.4,'estimatedGapMm':0.4,
            'gapUncertaintyMm':0.1,'machineXYMm':[12,22]})
        self.review['recipe']['padDoseDegrees']['R1.2']=8
        self.job_id=bind(self.job);self.review['cadJobSha256']=self.job_id
        result=prepare_generic_job(self.job,self.job_id,self.review)
        self.assertFalse(result['executionAuthorized'])
        self.assertFalse(result['finePitchGroups'][0]['lineDispatchSupported'])
        self.assertIn(result['finePitchGroups'][0]['status'],('blocked-no-validated-line-recipe','preview-only-physical-dispatch-not-implemented'))


if __name__=='__main__':
    unittest.main()
