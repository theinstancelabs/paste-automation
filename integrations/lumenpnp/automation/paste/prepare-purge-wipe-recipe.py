#!/usr/bin/env python3
"""Build a hash-bound, offline B-prime/wipe recipe. Does not access or control OpenPnP."""
import argparse, hashlib, json, math, re, time
from pathlib import Path


def fail(message): raise ValueError(message)
def load(path):
    p=Path(path).resolve(strict=True); b=p.read_bytes(); return json.loads(b),p,b
def evidence(path):
    p=Path(path).resolve(strict=True); b=p.read_bytes()
    if not b: fail(f'Empty evidence: {p}')
    return {'path':str(p),'sha256':hashlib.sha256(b).hexdigest()}
def validate_review_time(value, now_ms):
    if type(value) is not int or value < 0 or value > now_ms or now_ms-value > 300000:
        fail('Review timestamp must be a current finite integer millisecond value')

def write_exclusive(path, result):
    with Path(path).open('x',encoding='utf-8') as f: json.dump(result,f,indent=2,allow_nan=False);f.write('\n')

def checked_evidence(item,label):
    if not isinstance(item,dict) or not isinstance(item.get('path'),str): fail(f'{label} requires path and SHA-256')
    actual=evidence(item['path'])
    if actual['sha256']!=item.get('sha256'): fail(f'{label} hash mismatch')
    return actual
def chunks(total,step=20): return [min(step,total-i) for i in range(0,total,step)]
def recipe_stages(raw, review_ev, axis, wipe_delta, clearance, gap, uncertainty, prime, before, after):
    if axis not in ('X','Y'): fail('Wipe axis must be X or Y')
    if type(wipe_delta) not in (int,float) or not math.isfinite(wipe_delta) or wipe_delta==0 or abs(wipe_delta)>2: fail('Wipe delta must be nonzero and at most 2 mm')
    if (any(type(x) not in (int,float) or not math.isfinite(x) for x in (gap,uncertainty))
            or gap<=0 or uncertainty<0 or gap-uncertainty<0.1): fail('Reviewed gap lower bound must be at least 0.1 mm')
    if prime not in (20,40,60) or before not in (0,2,3,4,6,20) or after not in (0,2,4,6,20,40): fail('B stroke outside reviewed choices')
    start_z=raw['Z']
    if not isinstance(clearance,(int,float)) or not math.isfinite(clearance) or not start_z-5<=clearance<start_z: fail('Right-tip clearance must satisfy startZ-5 <= clearance < startZ')
    current=dict(raw); stages=[]
    def add(a,target,**extra):
        nonlocal current
        nxt=dict(current);nxt[a]=target
        stages.append({'axis':a,'target':target,**extra});current=nxt
    def stroke(delta,dwell):
        gap_at_height=gap+(start_z-current['Z'])
        add('B',current['B']+delta,gapEvidence=review_ev,estimatedGapMm=gap_at_height,gapUncertaintyMm=uncertainty,dwellMilliseconds=dwell)
    ps=chunks(prime)
    for i,n in enumerate(ps): stroke(-n,2000 if i==len(ps)-1 else 0)
    if before: stroke(before,1000)
    add(axis,current[axis]+wipe_delta,wipeReview=True,wipeReviewEvidence=review_ev,estimatedGapMm=gap,gapUncertaintyMm=uncertainty)
    add('Z',clearance)
    ars=chunks(after)
    for i,n in enumerate(ars): stroke(n,2000 if i==len(ars)-1 else 0)
    return stages

def build(barrier_path,profile_path,review_path,report_path,ledger_path,axis,wipe_delta,clearance,gap,uncertainty,prime,before,after):
    barrier,bp,_=load(barrier_path); profile,pp,_=load(profile_path); review,rp,_=load(review_path); report,rp2,_=load(report_path); ledger,lp,lb=load(ledger_path)
    if barrier.get('status')!='completed-read-only-position-barrier' or barrier.get('controllerPositionVerified') is not True or barrier.get('noMotionCommandSubmitted') is not True or barrier.get('uncertainCompletion') is not False: fail('Successful no-motion source barrier required')
    req=barrier.get('request') or {}; snap=barrier.get('afterQuerySnapshot') or {}; raw=snap.get('raw');driver=snap.get('driver');poses=snap.get('nativePoses')
    if not isinstance(raw,dict) or set(raw)!={'X','Y','Z','A','B'} or not isinstance(driver,dict) or set(driver)!=set(raw) or not isinstance(poses,dict) or set(poses)!={'N1','N2','top','bottom'}: fail('Barrier must contain complete same-pose raw, driver and four native poses')
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in list(raw.values())+list(driver.values())): fail('Barrier axes must be finite numeric values')
    for n in ('N1','N2'):
        if any(type(poses[n].get(k)) not in (int,float) or not math.isfinite(poses[n][k]) for k in ('x','y','z')): fail(f'{n} native pose must contain finite XYZ')
    jvm=req.get('jvmStartMs'); config=barrier.get('liveConfigurationSha256')
    if type(jvm) is not int or not isinstance(config,str) or not re.fullmatch(r'[a-f0-9]{64}',config): fail('Barrier JVM/configuration identity missing')
    if profile.get('provenance')!='commissioning-provisional' or profile.get('flowCalibrated') is not False or profile.get('precisionCalibrated') is not False: fail('Profile must remain provisional and uncalibrated')
    if profile.get('sessionId')!=ledger.get('sessionId') or profile.get('sessionId')!=report.get('request',{}).get('sessionId') or profile.get('jvmStartMs')!=jvm or profile.get('liveConfigurationSha256')!=config: fail('Profile/report/ledger session identity differs from source barrier')
    pr=profile.get('rawPose') or {}
    for k in ('X','Y','Z','A'):
        if not isinstance(pr.get(k),(int,float)) or not math.isclose(pr[k],raw[k],abs_tol=1e-4): fail(f'Profile does not match current barrier {k}')
    if review.get('mode')!='wet' or not isinstance(review.get('reviewedBy'),str) or not review['reviewedBy'].strip(): fail('A named review of the wet wipe route is required')
    validate_review_time(review.get('reviewedMs'),int(time.time()*1000))
    for k in ('imageEvidence','cleanTipImage','priorTopImage'): checked_evidence(review.get(k),f'review {k}')
    rev_ev=evidence(rp)
    if ledger.get('status')!='verified' or ledger.get('lastVerifiedB')!=raw['B'] or ledger.get('sessionId')!=profile.get('sessionId') or ledger.get('syringeId')!=profile.get('syringeId') or report.get('id')!=report.get('request',{}).get('id') or report.get('uncertainCompletion') is not False or report.get('completedLedgerSha256')!=hashlib.sha256(lb).hexdigest(): fail('Verified latest report/current ledger must match the source pose and hash')
    if (report.get('status') not in ('completed-commissioning-stroke-awaiting-observation','completed-dose-cycle-awaiting-observation','completed-contiguous-batch-awaiting-observation')
            or report.get('request',{}).get('jvmStartMs')!=jvm or report.get('request',{}).get('liveConfigurationSha256')!=config): fail('Previous report must be successful in the current session/configuration')
    if not ledger.get('entries') or ledger['entries'][-1].get('status')!='verified' or report['id'] not in (ledger['entries'][-1].get('requestId'),ledger['entries'][-1].get('cycleId'),ledger['entries'][-1].get('batchId')): fail('Previous report must be the verified ledger tail')
    stages=recipe_stages(raw,rev_ev,axis,wipe_delta,clearance,gap,uncertainty,prime,before,after)
    path=[raw];at=dict(raw)
    for stage in stages:
        at=dict(at);at[stage['axis']]=stage['target'];path.append(at)
    bounds={a:{'min':min(p[a] for p in path),'max':max(p[a] for p in path)} for a in ('X','Y','Z','B')}
    heads={}
    for name in ('N1','N2'):
        pose=poses[name]; hb={}
        for a in ('X','Y','Z'):
            sign=-1 if a=='Z' and name=='N2' else 1
            values=[pose[a.lower()]+sign*(p[a]-raw[a]) for p in path]
            hb['min'+a]=min(values)-0.001;hb['max'+a]=max(values)+0.001
        heads[name]=hb
    review_range=review.get('rawZRange')
    if review_range != [bounds['Z']['min'],bounds['Z']['max']]: fail('Review rawZRange must exactly bind the full route Z envelope')
    return {'mode':'wet','stages':stages,'rawBounds':bounds,'headClearanceBounds':heads,'xyClearanceRawZ':clearance,
            'clearanceReviewEvidence':rev_ev,'profileEvidence':evidence(pp),'previousReportEvidence':evidence(rp2),
            'previousLedgerPath':str(lp),'previousLedgerEvidence':evidence(lp),'barrierEvidence':evidence(bp),
            'gapEstimate':{'gapMm':gap,'uncertaintyMm':uncertainty,'lowerBoundMm':gap-uncertainty},
            'bAccounting':{'primeDegrees':prime,'reliefBeforeDegrees':before,'reliefAfterDegrees':after,
                           'grossCommandedDegrees':prime+before+after,'netDegrees':-prime+before+after},
            'limitations':['Preparation only; later batch policy and detached native preview must validate the complete route.',
                           'A successful first purge/wipe trial does not qualify physical tip cleaning; inspect and review the tip independently.',
                           'Gap is an explicit engineering estimate, not contact metrology or precision calibration.']}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--barrier',required=True);p.add_argument('--profile',required=True);p.add_argument('--review',required=True)
    p.add_argument('--previous-report',required=True);p.add_argument('--ledger',required=True);p.add_argument('--axis',choices=('X','Y'),required=True)
    p.add_argument('--wipe-delta-mm',type=float,required=True);p.add_argument('--clearance-raw-z',type=float,required=True)
    p.add_argument('--gap-mm',type=float,required=True);p.add_argument('--gap-uncertainty-mm',type=float,required=True)
    p.add_argument('--prime-degrees',type=int,choices=(20,40,60),required=True)
    p.add_argument('--relief-before-degrees',type=int,choices=(0,2,4,6,20),required=True)
    p.add_argument('--relief-after-degrees',type=int,choices=(0,2,4,6,20,40),required=True)
    p.add_argument('--output',required=True)
    a=p.parse_args()
    try:
        result=build(a.barrier,a.profile,a.review,a.previous_report,a.ledger,a.axis,a.wipe_delta_mm,a.clearance_raw_z,a.gap_mm,a.gap_uncertainty_mm,a.prime_degrees,a.relief_before_degrees,a.relief_after_degrees)
        write_exclusive(a.output,result)
    except (OSError,ValueError,TypeError,KeyError) as e: p.error(str(e))
    print(json.dumps({'output':str(Path(a.output).resolve()),'stageCount':len(result['stages']),'bAccounting':result['bAccounting']}))
if __name__=='__main__':main()
