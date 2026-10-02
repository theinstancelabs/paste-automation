"""Offline CAD-bound preparation gate for generic paste jobs. Never dispatches motion."""
import hashlib
import json
import math
import re

SHA256 = re.compile(r'^[a-f0-9]{64}$')


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _sha(value):
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def _job_id(job):
    data = json.dumps(job, indent=2, sort_keys=True, allow_nan=False).encode() + b'\n'
    return hashlib.sha256(data).hexdigest()


def prepare_generic_job(job, job_id, review):
    """Validate a human-reviewed offline input and return an honest readiness/target preview.

    Review records bind to the deterministic saved job hash and carry evidence digests;
    this verifies shape and binding only. No machine state is read and no evidence or
    physical readiness is inferred from a supplied digest.
    """
    if not isinstance(job, dict) or job.get('scope') != 'offline-kicad-paste-job':
        raise ValueError('Expected an offline KiCad paste plan.')
    if not isinstance(job_id, str) or not SHA256.fullmatch(job_id) or _job_id(job) != job_id:
        raise ValueError('CAD job identity does not match its deterministic saved hash.')
    if not isinstance(review, dict):
        review = {}
    pads = job.get('pads') if isinstance(job.get('pads'), list) else []
    pad_ids = [p.get('id') for p in pads if isinstance(p, dict) and isinstance(p.get('id'), str)]
    if len(pad_ids) != len(pads) or len(set(pad_ids)) != len(pad_ids):
        raise ValueError('Planner pad identities must be unique before preparation.')
    missing = []
    errors = []
    if review.get('scope') != 'generic-paste-human-review' or review.get('cadJobSha256') != job_id:
        missing.append('review.cadJobSha256 bound to this saved CAD job')
    if not isinstance(review.get('reviewedBy'), str) or not review['reviewedBy'].strip():
        missing.append('review.reviewedBy')
    transform = review.get('transform') if isinstance(review.get('transform'), dict) else {}
    if transform.get('reviewed') is not True or not _sha(transform.get('evidenceSha256')):
        missing.append('reviewed fiducial transform evidence SHA-256')
    fiducials = transform.get('fiducials') if isinstance(transform.get('fiducials'), list) else []
    fid_ids = {f.get('reference') for f in fiducials if isinstance(f, dict) and isinstance(f.get('reference'), str)}
    cad_fids={f.get('reference') for f in job.get('fiducials') or [] if isinstance(f,dict) and f.get('reference')}
    if len(fid_ids) < 3 or not fid_ids.issubset(cad_fids) or not _finite(transform.get('rmsResidualMm')) or transform.get('rmsResidualMm') > 0.08:
        missing.append('at least three reviewed fiducials and RMS residual ≤ 0.08 mm')
    affine = transform.get('cadToMachineAffine')
    if not isinstance(affine, list) or len(affine) != 2 or any(not isinstance(row, list) or len(row) != 3 or not all(_finite(v) for v in row) for row in affine):
        missing.append('finite 2×3 CAD-to-machine affine transform')
    else:
        a, b = affine[0][:2], affine[1][:2]
        if abs(a[0] * b[1] - a[1] * b[0]) < 1e-9:
            errors.append('CAD-to-machine transform is singular.')
    pad_review = review.get('pads') if isinstance(review.get('pads'), list) else []
    by_id = {p.get('padId'): p for p in pad_review if isinstance(p, dict) and isinstance(p.get('padId'), str)}
    if len(by_id) != len(pad_review) or set(by_id) != set(pad_ids):
        missing.append('one unique reviewed availability and surface record for every CAD pad')
    for pad_id in pad_ids:
        item = by_id.get(pad_id)
        if not item:
            continue
        xy = item.get('machineXYMm')
        if item.get('identityReviewed') is not True or item.get('availabilityReviewed') is not True or not _sha(item.get('evidenceSha256')):
            missing.append(f'{pad_id}: reviewed pad identity/availability evidence')
        if item.get('surfaceReviewed') is not True or not _sha(item.get('surfaceEvidenceSha256')) or not _finite(item.get('rawZMm')) or not _finite(item.get('estimatedGapMm')) or not _finite(item.get('gapUncertaintyMm')) or item.get('estimatedGapMm', 0) - item.get('gapUncertaintyMm', 0) < 0.1:
            missing.append(f'{pad_id}: reviewed per-pad surface, evidence, and positive gap lower bound')
        if not isinstance(xy, list) or len(xy) != 2 or not all(_finite(v) for v in xy):
            missing.append(f'{pad_id}: finite registered machine XY')
        elif isinstance(affine,list) and len(affine)==2 and all(isinstance(row,list) and len(row)==3 and all(_finite(v) for v in row) for row in affine):
            source=next(p for p in pads if p.get('id')==pad_id).get('centerMm')
            if not isinstance(source,list) or len(source)!=2 or not all(_finite(v) for v in source):
                missing.append(f'{pad_id}: finite CAD pad center for transform validation')
            else:
                projected=[affine[0][0]*source[0]+affine[0][1]*source[1]+affine[0][2],affine[1][0]*source[0]+affine[1][1]*source[1]+affine[1][2]]
                if math.hypot(projected[0]-xy[0],projected[1]-xy[1])>0.08:
                    errors.append(f'{pad_id}: reviewed machine target disagrees with the CAD affine by more than 0.08 mm.')
    recipe = review.get('recipe') if isinstance(review.get('recipe'), dict) else {}
    doses = recipe.get('padDoseDegrees') if isinstance(recipe.get('padDoseDegrees'), dict) else {}
    model=job.get('pasteModel') if isinstance(job.get('pasteModel'),dict) else {}
    if not _finite(model.get('thicknessMm')) or model.get('thicknessMm')<=0 or not _finite(model.get('apertureScaling')) or model.get('apertureScaling')<=0:
        missing.append('positive reviewed paste thickness and aperture scaling in the CAD plan')
    if model.get('calibrationVerified') is not True or model.get('calibrationStatus')!='verified' or recipe.get('measuredCalibration') is not True or not _sha(recipe.get('calibrationEvidenceSha256')):
        missing.append('measured flow calibration evidence SHA-256')
    if set(doses) != set(pad_ids) or any(not _finite(v) or v <= 0 for v in doses.values()):
        missing.append('positive calibrated dose for every CAD pad')
    clearance = review.get('bothHeadClearance') if isinstance(review.get('bothHeadClearance'), dict) else {}
    bounds = clearance.get('headBoundsMm') if isinstance(clearance.get('headBoundsMm'), dict) else {}
    if clearance.get('reviewed') is not True or not _sha(clearance.get('evidenceSha256')):
        missing.append('reviewed both-head clearance evidence SHA-256')
    for head in ('N1', 'N2'):
        box = bounds.get(head)
        if not isinstance(box, dict) or any(not _finite(box.get(k)) for k in ('minX', 'maxX', 'minY', 'maxY')) or box.get('minX', 0) >= box.get('maxX', 0) or box.get('minY', 0) >= box.get('maxY', 0):
            missing.append(f'reviewed {head} travel bounds')
        elif any(isinstance(p,dict) and isinstance(p.get('machineXYMm'),list) and len(p['machineXYMm'])==2 and all(_finite(v) for v in p['machineXYMm']) and not (box['minX']<=p['machineXYMm'][0]<=box['maxX'] and box['minY']<=p['machineXYMm'][1]<=box['maxY']) for p in pad_review):
            errors.append(f'One or more registered pad targets exceed the reviewed {head} travel bounds.')
    fine_pitch = job.get('finePitchGroups') if isinstance(job.get('finePitchGroups'), list) else []
    row_gates = []
    for group in fine_pitch:
        if not isinstance(group, dict):
            continue
        recipe_note = group.get('validatedLineRecipe')
        allowed = isinstance(recipe_note, dict) and recipe_note.get('reviewed') is True and _sha(recipe_note.get('evidenceSha256'))
        row_gates.append({'groupId': group.get('id'), 'padIds': group.get('padIds'),
                          'lineDispatchSupported': False, 'status': 'blocked-no-validated-line-recipe' if not allowed else 'preview-only-physical-dispatch-not-implemented'})
    targets = []
    if not errors and not missing:
        for pad_id in pad_ids:
            item = by_id.get(pad_id)
            if item and isinstance(item.get('machineXYMm'), list) and len(item['machineXYMm']) == 2 and all(_finite(v) for v in item['machineXYMm']):
                targets.append({'padId': pad_id, 'machineXYMm': item['machineXYMm'], 'rawZMm': item.get('rawZMm'),
                                'doseDegrees': doses.get(pad_id), 'depositKind': 'individual-dot-only'})
    ready = not missing and not errors
    return {'schema': 1, 'scope': 'generic-paste-offline-preparation-preview', 'jobId': job_id,
            'reviewStatus': 'complete-shape-and-binding-only' if ready else 'incomplete',
            'missingRequirements': sorted(set(missing)), 'validationErrors': errors,
            'reviewEvidenceDigestsAreNotPhysicalVerification': True,
            'headClearanceStatus': 'human-reviewed-input-unverified-by-adapter' if ready else 'required',
            'finePitchGroups': row_gates, 'individualDotTargets': targets if ready else [],
            'previewAuthorized': ready, 'executionAuthorized': False,
            'dispatcherStatus': 'disabled-no-generic-native-dispatch-adapter'}
