#!/usr/bin/env python3
"""Offline builder for a single contiguous scrap-conditioning + two-pad FTP recipe.
No controller access or dispatch; native preview stays disabled.
"""
import argparse
import copy
import datetime
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path('/home/lumen/lumenpnp')
GENERIC = ROOT / 'automation/paste/prepare-contiguous-batch.py'
COMP_SCRIPT = Path(__file__).with_name('prepare-compensated-ftp-pair.py')
PREP_SCRIPT = Path(__file__).with_name('prepare-retraction-coupon.py')

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

COMP = load_module('ftp_pair_builder', COMP_SCRIPT)
PREP = load_module('scrap_coupon_builder', PREP_SCRIPT)


def fail(msg):
    raise ValueError(msg)


def path_evidence(path):
    path = Path(path).resolve(strict=True)
    data = path.read_bytes()
    if not data:
        fail(f'Empty evidence: {path}')
    return {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest()}


def build(args):
    now = int(time.time() * 1000)
    template, tp, template_bytes = COMP.read(args.template)
    barrier, bp, barrier_bytes = COMP.read(args.barrier)
    target, source_target_path, source_target_bytes = COMP.read(args.target_record)
    experiment, ep, experiment_bytes = COMP.read(args.experiment)
    profile, pp, profile_bytes = COMP.read(args.profile)
    review, rp, review_bytes = COMP.read(args.clearance_review)
    previous_report, previous_report_path, previous_report_bytes = COMP.read(args.previous_report)
    ledger, ledger_path, ledger_bytes = COMP.read(args.ledger)
    image = Path(args.image).resolve(strict=True)
    image_bytes = image.read_bytes()
    captured = image.stat().st_mtime_ns // 1_000_000
    if not (image_bytes.startswith(b'\x89PNG\r\n\x1a\n') or image_bytes.startswith(b'\xff\xd8\xff')) or not 0 <= now-captured <= 300000:
        fail('Fresh PNG/JPEG evidence (no older than five minutes) required')
    if barrier.get('status') != 'completed-read-only-position-barrier' or barrier.get('controllerPositionVerified') is not True or barrier.get('noMotionCommandSubmitted') is not True or barrier.get('uncertainCompletion') is not False:
        fail('Successful fresh read-only barrier required')
    barrier_ms = int(datetime.datetime.fromisoformat(barrier['finishedAt'].replace('Z', '+00:00')).timestamp()*1000)
    if not 0 <= now-barrier_ms <= 300000:
        fail('Barrier must be no more than five minutes old')
    req = barrier.get('request') or {}
    snap = barrier.get('afterQuerySnapshot') or {}
    start = snap.get('raw'); native = snap.get('nativePoses')
    if not isinstance(start, dict) or set(start) != set('XYZAB') or not isinstance(native, dict) or set(native) != {'N1','N2','top','bottom'}:
        fail('Barrier needs complete raw/native pose snapshot')
    if req.get('jvmStartMs') != template.get('jvmStartMs') or barrier.get('liveConfigurationSha256') != template.get('liveConfigurationSha256'):
        fail('Barrier/template session or live configuration mismatch')
    if profile.get('sessionId') != template.get('sessionId') or profile.get('jvmStartMs') != template.get('jvmStartMs') or profile.get('liveConfigurationSha256') != template.get('liveConfigurationSha256') or profile.get('provenance') != 'commissioning-provisional' or profile.get('precisionCalibrated') is not False or profile.get('flowCalibrated') is not False:
        fail('Preparation profile identity/provisional status mismatch')
    if (target.get('schema') != 1 or target.get('scope') != 'ftp-two-pad-commissioning-targets' or
            target.get('sessionId') != template.get('sessionId') or target.get('jvmStartMs') != template.get('jvmStartMs') or
            target.get('liveConfigurationSha256') != barrier.get('liveConfigurationSha256') or
            target.get('quantizationMm') != 0.01 or target.get('boardUnmovedSinceRegistration') is not True or
            target.get('precisionCalibrated') is not False or target.get('flowCalibrated') is not False):
        fail('FTP target identity/provisional/unmoved review mismatch')
    for axis in 'XYZA':
        if not COMP.finite(profile.get('rawPose', {}).get(axis)) or abs(profile['rawPose'][axis]-start[axis]) > 0.0001:
            fail(f'Preparation profile must match current barrier {axis}')
    ee = path_evidence(ep)
    re = path_evidence(rp)
    if PREP.WIPE.checked_evidence(review.get('experimentEvidence'), 'review experiment') != ee:
        fail('Preparation review must bind exact experiment')
    if PREP.WIPE.checked_evidence(review.get('imageEvidence'), 'review image') != path_evidence(image):
        fail('Preparation review must bind current image')
    if PREP.WIPE.checked_evidence(profile.get('measurementEvidence'), 'profile review') != re:
        fail('Preparation profile must bind exact review')
    if not PREP.BATCH.same(experiment.get('startRaw'), start):
        fail('Preparation experiment startRaw differs from fresh barrier')
    if experiment.get('retractDegrees') != (target.get('compensatedSequence') or {}).get('retractDegrees'):
        fail('Conditioner retraction must match FTP restore/retract selection')
    if experiment.get('mode') != 'transfer-preparation':
        fail('Inline conditioning must use explicit transfer-preparation experiment')
    if review.get('reviewedBy') is None or type(review.get('reviewedMs')) is not int or not captured <= review['reviewedMs'] <= now:
        fail('Authored fresh preparation review required')
    gap = PREP.number(profile.get('estimatedGapMm'), 'profile estimatedGapMm')
    uncertainty = PREP.number(profile.get('gapUncertaintyMm'), 'profile gapUncertaintyMm')
    prefix, prefix_poses, prep_accounting = PREP.stages_for(experiment, re, gap, uncertainty)
    if len(prefix) < 2 or prefix[-2].get('axis') != 'B' or prefix[-1].get('axis') != 'Z':
        fail('Preparation must end in selected +R retraction then lift')
    max_transfer = 15000

    # Derive transfer raw state from the authored prefix; do not invent any
    # observation or attest that this route will be accepted physically.
    at = dict(start)
    for stage in prefix:
        at[stage['axis']] = stage['target']
    if at['Z'] != experiment['clearanceRawZ']:
        fail('Preparation lift did not end at its reviewed clearance')
    transfer_clearance = args.xy_clearance_raw_z
    if (not COMP.finite(transfer_clearance) or
            abs(transfer_clearance-experiment['clearanceRawZ']) > 0.05+1e-9 or
            transfer_clearance >= target.get('surface', {}).get('rawZ', float('nan'))):
        fail('FTP clearance must match the reviewed preparation lift plane within 0.05 mm and remain below work Z')
    extra_prefix = []
    if at['Z'] != transfer_clearance:
        extra_prefix.append({'axis':'Z','target':transfer_clearance})
        at['Z'] = transfer_clearance
    shifted_native = copy.deepcopy(native)
    for name in ('N1','N2','top','bottom'):
        for axis in ('x','y','z'):
            raw_axis = axis.upper()
            sign = -1 if raw_axis == 'Z' and name == 'N2' else 1
            shifted_native[name][axis] += sign*(at[raw_axis]-start[raw_axis])

    target_copy = copy.deepcopy(target)
    inline = {'schema':1,'protocol':'scrap-condition-transit-two-pad','experiment':copy.deepcopy(experiment),
              'experimentEvidence':ee,'maximumTransferMilliseconds':max_transfer,
              'prefixStageCount':len(prefix),'retractionStageIndex':len(prefix)-2,'liftStageIndex':len(prefix)-1}
    target_copy['inlineConditioning'] = inline
    target_copy['compensatedSequence'] = copy.deepcopy(target.get('compensatedSequence',{}))
    for key in ('conditioningReportEvidence','conditioningLedgerEvidence','preparationExperimentEvidence',
                'tipObservationEvidence','conditioningFinishedMs','maximumElapsedMilliseconds'):
        target_copy['compensatedSequence'].pop(key,None)
    suffix_target, suffix, _, _, accounting = COMP.build_route(at, shifted_native, target_copy, transfer_clearance)
    for pad in suffix_target['pads']:
        for key in ('restoreStageIndex','retractStageIndex','liftStageIndex'):
            pad[key] += len(prefix)+len(extra_prefix)
        pad['doseStageIndices'] = [i+len(prefix)+len(extra_prefix) for i in pad['doseStageIndices']]
    seq = suffix_target['compensatedSequence']
    for key in ('finalIdleStageIndex',):
        if key in seq: seq[key] += len(prefix)+len(extra_prefix)
    if 'finalIdleStageIndices' in seq: seq['finalIdleStageIndices'] = [i+len(prefix)+len(extra_prefix) for i in seq['finalIdleStageIndices']]
    stages = prefix + extra_prefix + suffix
    if len(stages) > 40:
        fail('Combined preparation and FTP route exceeds the native 40-stage limit')
    if source_target_path.read_bytes() != source_target_bytes or ep.read_bytes() != experiment_bytes:
        fail('Authored target or conditioning experiment changed during preparation')

    # Compute complete-route bounds and head bounds from the original barrier.
    route = [dict(start)]
    cur = dict(start)
    for stage in stages:
        cur = dict(cur); cur[stage['axis']] = stage['target']; route.append(cur)
    bounds = {axis:{'min':min(p[axis] for p in route),'max':max(p[axis] for p in route)} for axis in 'XYZB'}
    heads = {}
    for name in ('N1','N2'):
        limits={}
        for axis in 'XYZ':
            sign=-1 if axis=='Z' and name=='N2' else 1
            vals=[native[name][axis.lower()]+sign*(p[axis]-start[axis]) for p in route]
            limits['min'+axis]=min(vals)-0.001; limits['max'+axis]=max(vals)+0.001
        heads[name]=limits
    out = Path(args.output).resolve(); out.mkdir(parents=True,exist_ok=False)
    out_target_path=out/'targets.json'; out_target_path.write_text(json.dumps(suffix_target,indent=2,allow_nan=False)+'\n')
    route_gross=sum(abs(right['B']-left['B']) for left,right in zip(route,route[1:]))
    recipe={'mode':'wet','stages':stages,'rawBounds':bounds,'headClearanceBounds':heads,
            'xyClearanceRawZ':transfer_clearance,'clearanceReviewEvidence':re,
            'profileEvidence':path_evidence(pp),'previousReportEvidence':path_evidence(args.previous_report),
            'previousLedgerPath':str(ledger_path),'targetSurface':'scrap-conditioned-ftp-demo',
            'ftpTargetEvidence':path_evidence(out_target_path),'sourceTargetEvidence':path_evidence(source_target_path),
            'computedDoseStageIndices':{p['padId']:p['doseStageIndices'] for p in suffix_target['pads']},
            'computedRestoreRetractLiftIndices':{p['padId']:[p['restoreStageIndex'],p['retractStageIndex'],p['liftStageIndex']] for p in suffix_target['pads']},
            'bAccounting':{'initialB':start['B'],'finalB':route[-1]['B'],
                'grossChargedDegrees':route_gross,'netDegrees':route[-1]['B']-start['B'],
                'conditioningGrossDegrees':prep_accounting['grossCommandedDegrees'],
                'ftpPairGrossDegrees':accounting['grossChargedDegrees'],
                'ftpPairFinalB':accounting['finalB']},
            'conditioningAccounting':prep_accounting,
            'inlineConditioningEvidence':ee}
    recipe_path=out/'recipe.json'; recipe_path.write_text(json.dumps(recipe,indent=2,allow_nan=False)+'\n')
    # Normal offline preparation path. This only writes disabled preview artifacts.
    native_out=out/'native'
    cmd=[sys.executable,str(GENERIC),'prepare','--template',str(tp),'--barrier',str(bp),'--image',str(image),'--recipe',str(recipe_path),'--output',str(native_out)]
    try: completed=subprocess.run(cmd,check=True,text=True,capture_output=True)
    except subprocess.CalledProcessError as exc: fail('Generic offline native validator rejected route: '+(exc.stderr or exc.stdout).strip())
    frozen = ((ep,experiment_bytes,'experiment'),(source_target_path,source_target_bytes,'target'),
              (tp,template_bytes,'template'),(bp,barrier_bytes,'barrier'),(pp,profile_bytes,'profile'),
              (rp,review_bytes,'review'),(previous_report_path,previous_report_bytes,'previous report'),
              (ledger_path,ledger_bytes,'ledger'),(image,image_bytes,'image'))
    for path,original,label in frozen:
        if path.read_bytes() != original:
            fail(f'{label} changed during preparation')
    print(json.dumps({'targets':str(out_target_path),'recipe':str(recipe_path),'previewRequest':str(native_out/'preview-request.json'),
          'prefixStageCount':len(prefix),'transferStageCount':len(suffix),'BAccounting':recipe['bAccounting'],
          'nativeValidator':completed.stdout.strip(),'enabled':False,'motionDispatched':False},indent=2))


def main_cli():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('experiment','template','barrier','profile','clearance-review','image','target-record','previous-report','ledger','output'):
        p.add_argument('--'+name,required=True)
    p.add_argument('--xy-clearance-raw-z',type=float,required=True)
    a=p.parse_args()
    try: build(a)
    except Exception as exc: p.error(str(exc))

if __name__=='__main__': main_cli()
