#!/usr/bin/env python3
"""Offline builder for a reviewed scrap prefix and one-to-eight selected FTP pads."""
import argparse, copy, datetime, hashlib, importlib.util, json, math, subprocess, sys, time
from pathlib import Path

ROOT=Path('/home/lumen/lumenpnp'); HERE=Path(__file__).resolve().parent
GENERIC=ROOT/'automation/paste/prepare-contiguous-batch.py'
BASE=HERE/'prepare-conditioned-ftp-pair.py'
spec=importlib.util.spec_from_file_location('selected_pair_base',BASE); M=importlib.util.module_from_spec(spec); spec.loader.exec_module(M)
COMP,PREP=M.COMP,M.PREP

def fail(s): raise ValueError(s)
def ev(path): return M.path_evidence(path)

def read_availability(pad,template,board_id,reviewed_ms,now,snapshots,max_age_ms=300000):
    for k in ('availabilityReportEvidence','availabilityImageEvidence','surfaceEvidence'):
        e=pad.get(k); PREP.WIPE.checked_evidence(e,'selected '+k); path=Path(e['path']).resolve(strict=True); data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=e['sha256']: fail('Selected '+k+' hash mismatch')
        snapshots[path]=data
        if k=='availabilityReportEvidence':
            report=json.loads(data); stamp=round(datetime.datetime.fromisoformat(report['finishedAt'].replace('Z','+00:00')).timestamp()*1000)
            if stamp!=pad.get('availabilityCapturedMs') or not 0<=now-stamp<=max_age_ms or stamp>reviewed_ms: fail('Selected-pad camera observation is stale or time-mismatched')
            if report.get('status') not in ('completed-camera-survey-awaiting-image-review','completed-contiguous-air-batch-awaiting-observation') or report.get('controllerPositionVerified') is not True or report.get('uncertainCompletion') is not False: fail('Selected-pad availability needs verified camera report')
            req=report.get('request') or {}
            if req.get('jvmStartMs')!=template.get('jvmStartMs') or req.get('liveConfigurationSha256')!=template.get('liveConfigurationSha256'): fail('Selected-pad camera report session/configuration differs')
            top=(report.get('afterImages') or {}).get('top')
            image=pad['availabilityImageEvidence']
            if not top or Path(image['path']).resolve()!=path.parent.joinpath(top.get('path','')).resolve(): fail('Selected availability image must be the report top image')
        elif k=='availabilityImageEvidence':
            if not (data.startswith(b'\x89PNG\r\n\x1a\n') or data.startswith(b'\xff\xd8\xff')): fail('Selected availability image must be PNG/JPEG')
        else:
            doc=json.loads(data);surface=doc.get('surface')
            if surface!=pad.get('surface') or doc.get('boardId')!=board_id or doc.get('provenance')!='commissioning-provisional' or doc.get('precisionCalibrated') is not False or doc.get('flowCalibrated') is not False or doc.get('jvmStartMs')!=template.get('jvmStartMs') or doc.get('liveConfigurationSha256')!=template.get('liveConfigurationSha256') or not isinstance(doc.get('reviewedBy'),str) or not doc['reviewedBy'].strip(): fail('Per-pad surface differs from same-session reviewed evidence')
            PREP.WIPE.checked_evidence(doc.get('basisEvidence'),'per-pad surface basis')
    return snapshots

def append(stages,at,axis,value,**meta):
    if not isinstance(value,(int,float)) or not math.isfinite(value): fail('Non-finite selected route endpoint')
    if abs(value-M.COMP.q01(value))>1e-9: fail('Selected route endpoint must use 0.01 mm grid')
    if at[axis]==value: return at
    nxt=copy.deepcopy(at);nxt[axis]=value;stages.append({'axis':axis,'target':value,**meta});return nxt

def move(stages,at,axis,value,clearance):
    limit=9.9 if axis in ('X','Y') else 5.0
    if axis in ('X','Y') and at['Z']!=clearance: fail('Selected-pad XY travel must remain at common reviewed clearance')
    start=at[axis];count=max(1,math.ceil(abs(value-start)/limit))
    while True:
        vals=[M.COMP.q01(start+(value-start)*i/count) for i in range(1,count)]+[value]
        if all(abs(b-a)<=limit+1e-9 for a,b in zip([start]+vals[:-1],vals)): break
        count+=1
    for v in vals:
        if axis in ('X','Y') and at['Z']!=clearance: fail('Selected-pad XY travel must remain at common reviewed clearance')
        if abs(v-at[axis])>limit+1e-9: fail('Selected movement exceeds native per-stage bound')
        at=append(stages,at,axis,v)
    return at

def build(args):
    now=int(time.time()*1000); snaps={}
    template,tp,tbytes=COMP.read(args.template);barrier,bp,bbytes=COMP.read(args.barrier);target,tp0,tbytes0=COMP.read(args.target_record);experiment,ep,ebytes=COMP.read(args.experiment);profile,pp,pbytes=COMP.read(args.profile);review,rp,rbytes=COMP.read(args.clearance_review);prev,prevp,prevbytes=COMP.read(args.previous_report);ledger,lp,lbytes=COMP.read(args.ledger)
    for path,data in ((tp,tbytes),(bp,bbytes),(tp0,tbytes0),(ep,ebytes),(pp,pbytes),(rp,rbytes),(prevp,prevbytes),(lp,lbytes)):
        snaps[path]=data
    image=Path(args.image).resolve(strict=True);ib=image.read_bytes();captured=image.stat().st_mtime_ns//1_000_000
    snaps[image]=ib
    if not (ib.startswith(b'\x89PNG\r\n\x1a\n') or ib.startswith(b'\xff\xd8\xff')) or not 0<=now-captured<=300000: fail('Fresh preparation image required')
    if barrier.get('status')!='completed-read-only-position-barrier' or barrier.get('controllerPositionVerified') is not True or barrier.get('noMotionCommandSubmitted') is not True or barrier.get('uncertainCompletion') is not False: fail('Fresh successful read-only barrier required')
    raw=barrier.get('afterQuerySnapshot',{}).get('raw');native=barrier.get('afterQuerySnapshot',{}).get('nativePoses')
    if not isinstance(raw,dict) or set(raw)!=set('XYZAB') or not isinstance(native,dict) or set(native)!={'N1','N2','top','bottom'}: fail('Complete barrier snapshot required')
    if barrier.get('request',{}).get('jvmStartMs')!=template.get('jvmStartMs') or barrier.get('liveConfigurationSha256')!=template.get('liveConfigurationSha256'): fail('Barrier/template session mismatch')
    if target.get('schema')!=1 or target.get('scope')!='ftp-selected-pads-targets' or target.get('sessionId')!=template.get('sessionId') or target.get('jvmStartMs')!=template.get('jvmStartMs') or target.get('liveConfigurationSha256')!=barrier.get('liveConfigurationSha256') or target.get('quantizationMm')!=.01 or target.get('boardUnmovedSinceRegistration') is not True: fail('Selected target identity/review mismatch')
    pads=target.get('pads');c=target.get('compensatedSequence') or {}
    wide=getattr(args,'up_to_40',False)
    if not isinstance(pads,list) or not 1<=len(pads)<=(40 if wide else 8) or c.get('protocol')!='restore-dose-retract-lift-selected-pads': fail('Select one to forty unique pads under selected-pad protocol' if wide else 'Select one to eight unique pads under selected-pad protocol')
    ids=[p.get('padId') for p in pads]
    if len(set(ids))!=len(ids) or any(not isinstance(i,str) or not __import__('re').fullmatch(r'R(?:[1-9]|[1-3][0-9]|40)\.[12]',i) for i in ids): fail('Selected pads must be unique registered pad identities')
    if target.get('reviewedBy') is None or type(target.get('reviewedMs')) is not int or not captured<=target['reviewedMs']<=now: fail('Fresh complete-route pad review required')
    if not isinstance(review.get('reviewedBy'),str) or type(review.get('reviewedMs')) is not int or not captured<=review['reviewedMs']<=now or review.get('imageEvidence')!=ev(image): fail('Preparation review must bind fresh image and reviewer')
    if PREP.WIPE.checked_evidence(profile.get('measurementEvidence'),'profile review')!=ev(rp): fail('Preparation profile must bind exact review')
    if profile.get('sessionId')!=template.get('sessionId') or profile.get('jvmStartMs')!=template.get('jvmStartMs') or profile.get('liveConfigurationSha256')!=template.get('liveConfigurationSha256') or profile.get('provenance')!='commissioning-provisional' or profile.get('precisionCalibrated') is not False or profile.get('flowCalibrated') is not False: fail('Preparation profile identity/provisional mismatch')
    for k in 'XYZA':
        if abs(profile.get('rawPose',{}).get(k,float('inf'))-raw[k])>1e-4: fail('Profile does not match barrier '+k)
    ee,re=ev(ep),ev(rp)
    if PREP.WIPE.checked_evidence(review.get('experimentEvidence'),'review experiment')!=ee or experiment.get('mode')!='transfer-preparation' or experiment.get('startRaw')!=raw: fail('Preparation experiment/review must bind exact barrier')
    if experiment.get('retractDegrees')!=c.get('retractDegrees') or experiment.get('conditioningDoseDegrees') not in (6,12,20) or experiment.get('conditioningRestoreDegrees',0) not in (0,3): fail('Conditioning amounts must match selected protocol')
    if experiment.get('conditioningDoseDegrees')==12 and (experiment.get('conditioningDwellMilliseconds',experiment.get('dwellMilliseconds',2000))!=2000 or experiment.get('retractDegrees')!=3 or experiment.get('retractDwellMilliseconds')!=500): fail('Conditioner12 requires 2000 ms and R3/500')
    if target.get('pads') and target['pads'][0].get('surface')!=target.get('surface'): fail('Top-level surface must mirror first selected pad surface')
    availability=[]
    for p in pads:
        if p.get('padIdentityReviewed') is not True or p.get('padAvailableReviewed') is not True: fail('Each selected pad needs explicit fresh review')
        read_availability(p,template,target['boardId'],target['reviewedMs'],now,snaps,900000 if wide else 300000)
    gap=PREP.number(profile.get('estimatedGapMm'),'conditioning profile gap');unc=PREP.number(profile.get('gapUncertaintyMm'),'conditioning uncertainty')
    prefix,_,prep_accounting=PREP.stages_for(experiment,re,gap,unc)
    retract_i=len(prefix)-2-(1 if experiment.get('conditioningFinalWipeMm',0) else 0)
    if retract_i<0 or prefix[retract_i].get('axis')!='B' or prefix[-1].get('axis')!='Z': fail('Conditioner must finish with selected retract/wipe then clearance lift')
    at=copy.deepcopy(raw)
    for s in prefix: at[s['axis']]=s['target']
    clear=args.xy_clearance_raw_z
    if at['Z']!=experiment['clearanceRawZ'] or abs(clear-at['Z'])>.05+1e-9: fail('Selected route clearance must match reviewed conditioner lift')
    stages=list(prefix)
    if at['Z']!=clear: at=append(stages,at,'Z',clear)
    if clear>=min(p['surface']['rawZ'] for p in pads): fail('Common transit clearance must remain above all selected pad surfaces')
    for p in pads:
        surf=p['surface'];pose=p['rawPose']
        if surf['rawZ']-clear>5.0+1e-9: fail('Selected pad immediate lift exceeds native 5 mm limit')
        if pose['Z']!=surf['rawZ'] or pose['A']!=raw['A']: fail('Pad raw pose must bind individual surface and barrier A')
        for axis in ('X','Y'): at=move(stages,at,axis,pose[axis],clear)
        at=move(stages,at,'Z',surf['rawZ'],clear)
        def bstep(delta,dwell):
            nonlocal at
            gap=surf['estimatedGapMm']+(surf['rawZ']-at['Z'])
            at=append(stages,at,'B',at['B']+delta,gapEvidence=p['surfaceEvidence'],estimatedGapMm=gap,gapUncertaintyMm=surf['gapUncertaintyMm'],dwellMilliseconds=dwell)
            return len(stages)-1
        p['restoreStageIndex']=bstep(-c['retractDegrees'],0)
        if c['doseDegrees']==12:
            p['doseStageIndices']=[bstep(-6,0),bstep(-6,c['dwellMilliseconds'])]
        else: p['doseStageIndices']=[bstep(-c['doseDegrees'],c['dwellMilliseconds'])]
        p['retractStageIndex']=bstep(c['retractDegrees'],c['retractDwellMilliseconds'])
        p['liftStageIndex']=len(stages);at=append(stages,at,'Z',clear)
    idle=c['idleReliefDegrees']
    if idle==20:
        c['finalIdleStageIndex']=bstep(20,2000)
    elif idle==40:
        deltas=[20,20]
        c['finalIdleStageIndices']=[bstep(20,0),bstep(20,2000)]
    else: fail('Selected-pad idle relief must be20 or40')
    c.pop('finalIdleStageIndex',None) if idle==40 else None
    if len(stages)>(400 if wide else 96): fail('Selected-pad route exceeds its native stage cap')
    target['pads']=pads
    target['inlineConditioning']={'schema':1,'protocol':'scrap-condition-transit-selected-pads','experiment':copy.deepcopy(experiment),'experimentEvidence':ee,'maximumTransferMilliseconds':15000,'prefixStageCount':len(prefix),'retractionStageIndex':retract_i,'liftStageIndex':len(prefix)-1}
    route=[copy.deepcopy(raw)];cur=copy.deepcopy(raw)
    for s in stages:cur=copy.deepcopy(cur);cur[s['axis']]=s['target'];route.append(cur)
    bounds={a:{'min':min(x[a] for x in route),'max':max(x[a] for x in route)} for a in 'XYZB'};heads={}
    for name in ('N1','N2'):
        limits={}
        for axis in 'XYZ':
            sign=-1 if axis=='Z' and name=='N2' else 1;vals=[native[name][axis.lower()]+sign*(x[axis]-raw[axis]) for x in route];limits['min'+axis]=min(vals)-.001;limits['max'+axis]=max(vals)+.001
        heads[name]=limits
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=False);tpout=out/'targets.json';tpout.write_text(json.dumps(target,indent=2,allow_nan=False)+'\n')
    gross=sum(abs(b['B']-a['B']) for a,b in zip(route,route[1:]));recipe={'mode':'wet','stages':stages,'rawBounds':bounds,'headClearanceBounds':heads,'xyClearanceRawZ':clear,'clearanceReviewEvidence':re,'profileEvidence':ev(pp),'previousReportEvidence':ev(prevp),'previousLedgerPath':str(lp),'targetSurface':'ftp-selected-pads-up-to-40' if wide else 'ftp-selected-pads','ftpTargetEvidence':ev(tpout),'sourceTargetEvidence':ev(tp0),'bAccounting':{'initialB':raw['B'],'finalB':route[-1]['B'],'grossChargedDegrees':gross,'netDegrees':route[-1]['B']-raw['B'],'conditioningGrossDegrees':prep_accounting['grossCommandedDegrees'],'selectedPadCount':len(pads)}}
    rpout=out/'recipe.json';rpout.write_text(json.dumps(recipe,indent=2,allow_nan=False)+'\n');nativeout=out/'native';cmd=[sys.executable,str(GENERIC),'prepare','--template',str(tp),'--barrier',str(bp),'--image',str(image),'--recipe',str(rpout),'--output',str(nativeout)]
    if getattr(args,'application_restart_evidence',None):cmd.extend(['--application-restart-evidence',str(Path(args.application_restart_evidence).resolve(strict=True))])
    if getattr(args,'manual_home_ledger_anchor_evidence',None):cmd.extend(['--manual-home-ledger-anchor-evidence',str(Path(args.manual_home_ledger_anchor_evidence).resolve(strict=True))])
    try:result=subprocess.run(cmd,check=True,text=True,capture_output=True)
    except subprocess.CalledProcessError as exc:fail('Generic offline native validator rejected selected route: '+(exc.stderr or exc.stdout).strip())
    for path,b in snaps.items():
        if path.read_bytes()!=b:fail('Selected evidence changed during preparation: '+str(path))
    if tp0.read_bytes()!=tbytes0 or ep.read_bytes()!=ebytes or tp.read_bytes()!=tbytes or bp.read_bytes()!=bbytes or lp.read_bytes()!=lbytes or prevp.read_bytes()!=prevbytes: fail('Core input changed during preparation')
    print(json.dumps({'output':str(out),'previewRequest':str(nativeout/'preview-request.json'),'stages':len(stages),'selectedPads':ids,'bAccounting':recipe['bAccounting'],'enabled':False,'motionDispatched':False,'nativeValidator':result.stdout.strip()},indent=2))

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('template','barrier','target-record','experiment','profile','clearance-review','image','previous-report','ledger','output'):p.add_argument('--'+name,required=True)
 p.add_argument('--up-to-40',action='store_true',help='Use distinct reviewed 1-40-pad scope and 400-stage ceiling')
 p.add_argument('--application-restart-evidence',help='explicit continuity proof when resuming across an application restart')
 p.add_argument('--manual-home-ledger-anchor-evidence',help='narrow reviewed manual-home ledger continuity evidence')
 p.add_argument('--xy-clearance-raw-z',type=float,required=True);a=p.parse_args()
 try:build(a)
 except Exception as exc:p.error(str(exc))
if __name__=='__main__':main()
