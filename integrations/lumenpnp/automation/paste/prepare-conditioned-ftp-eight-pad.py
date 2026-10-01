#!/usr/bin/env python3
"""Offline builder for one scrap-conditioning prefix followed by four FTP pad pairs.
The route is prepared and validated offline; no machine interface or dispatch exists.
"""
import argparse, copy, datetime, hashlib, importlib.util, json, math, subprocess, sys, time
from pathlib import Path

ROOT=Path('/home/lumen/lumenpnp')
GENERIC=ROOT/'automation/paste/prepare-contiguous-batch.py'
PAIR=Path(__file__).with_name('prepare-conditioned-ftp-pair.py')

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
BASE=module('conditioned_pair_helper',PAIR)
COMP,PREP=BASE.COMP,BASE.PREP

def fail(s): raise ValueError(s)
def ev(path):return BASE.path_evidence(path)

def validate_eight(t):
    if t.get('schema')!=1 or t.get('scope')!='ftp-eight-pad-commissioning-targets':fail('Explicit eight-pad FTP target record required')
    refs=t.get('pairReferences');pads=t.get('pads')
    if not isinstance(refs,list) or len(refs)!=4 or len(set(refs))!=4 or not isinstance(pads,list) or len(pads)!=8:fail('Exactly four unique references and eight pads required')
    if len(refs)!=4 or not all(isinstance(r,str) and r.startswith('R') and r[1:].isdigit() and 1<=int(r[1:])<=40 for r in refs):fail('Resistor references must be R1..R40')
    for i,ref in enumerate(refs):
        pair=pads[2*i:2*i+2]
        if {p.get('padId') for p in pair}!={ref+'.1',ref+'.2'}:fail('Pads must be four adjacent complete resistor pairs in pairReferences order')
        for p in pair:
            if p.get('padAvailableReviewed') is not True:fail('Each pad needs explicit availability review')
            PREP.WIPE.checked_evidence(p.get('availabilityImageEvidence'),'availability image')
            if p.get('padIdentityReviewed') is not True:fail('Each pad needs explicit identity review')
            PREP.WIPE.checked_evidence(p.get('availabilityReportEvidence'),'availability report')
            if type(p.get('availabilityCapturedMs')) is not int:fail('Each pad needs camera-report capture time')
    c=t.get('compensatedSequence') or {}
    if c.get('schema')!=1 or c.get('protocol')!='restore-dose-retract-lift-eight-pad' or c.get('doseDegrees') not in (4,6,12,20) or c.get('retractDegrees')!=2 or type(c.get('dwellMilliseconds')) is not int or c.get('dwellMilliseconds') not in (200,1000,2000) or c.get('retractDwellMilliseconds')!=500 or c.get('idleReliefDegrees')!=40:fail('Eight-pad sequence is fixed at dose4|6|12|20/R2/forward200|1000|2000ms/retract500ms/final40')
    return refs,pads

def validate_availability_reports(pads, template, now):
    sources={}
    for p in pads:
        report_path=Path(p['availabilityReportEvidence']['path']).resolve(strict=True)
        report_bytes=report_path.read_bytes()
        sources[report_path]=report_bytes
        if hashlib.sha256(report_bytes).hexdigest()!=p['availabilityReportEvidence']['sha256']:
            fail('Availability camera report hash mismatch')
        report=json.loads(report_bytes)
        finished=report.get('finishedAt')
        if not isinstance(finished,str):fail('Availability report needs finishedAt')
        finished_ms=round(datetime.datetime.fromisoformat(finished.replace('Z','+00:00')).timestamp()*1000)
        if p['availabilityCapturedMs']!=finished_ms or not 0<=now-finished_ms<=300000:fail('Pad availability observation must be fresh and match camera report time')
        if report.get('status') not in ('completed-camera-survey-awaiting-image-review','completed-contiguous-air-batch-awaiting-observation') or report.get('controllerPositionVerified') is not True or report.get('uncertainCompletion') is not False:fail('Availability must use a verified camera survey or air report')
        req=report.get('request') or {}
        if req.get('jvmStartMs')!=template.get('jvmStartMs') or req.get('liveConfigurationSha256')!=template.get('liveConfigurationSha256'):fail('Availability report runtime/configuration mismatch')
        image_ev=p['availabilityImageEvidence']; image_path=Path(image_ev['path']).resolve(strict=True)
        if image_path!=report_path.parent.joinpath((report.get('afterImages') or {}).get('top',{}).get('path','')).resolve():fail('Availability image must be the report top-after image')
        if ev(image_path)!=image_ev:fail('Availability image hash mismatch')
        sources[image_path]=image_path.read_bytes()
    return sources

def build(args):
    now=int(time.time()*1000)
    template,tp,tbytes=COMP.read(args.template);barrier,bp,bbytes=COMP.read(args.barrier)
    target,target_path,target_bytes=COMP.read(args.target_record);experiment,ep,ebytes=COMP.read(args.experiment)
    profile,pp,pbytes=COMP.read(args.profile);review,rp,rbytes=COMP.read(args.clearance_review)
    previous,prevp,prevbytes=COMP.read(args.previous_report);ledger,lp,lbytes=COMP.read(args.ledger)
    image=Path(args.image).resolve(strict=True);ib=image.read_bytes();captured=image.stat().st_mtime_ns//1_000_000
    if not (ib.startswith(b'\x89PNG\r\n\x1a\n') or ib.startswith(b'\xff\xd8\xff')) or not 0<=now-captured<=300000:fail('Fresh PNG/JPEG required')
    if barrier.get('status')!='completed-read-only-position-barrier' or barrier.get('controllerPositionVerified') is not True or barrier.get('noMotionCommandSubmitted') is not True or barrier.get('uncertainCompletion') is not False:fail('Successful read-only barrier required')
    barrier_ms=int(datetime.datetime.fromisoformat(barrier['finishedAt'].replace('Z','+00:00')).timestamp()*1000)
    if not 0<=now-barrier_ms<=300000:fail('Barrier must be no more than five minutes old')
    req=barrier.get('request') or {};snap=barrier.get('afterQuerySnapshot') or {};start=snap.get('raw');native=snap.get('nativePoses')
    if not isinstance(start,dict) or set(start)!=set('XYZAB') or not isinstance(native,dict) or set(native)!={'N1','N2','top','bottom'}:fail('Complete raw/native position snapshot required')
    if req.get('jvmStartMs')!=template.get('jvmStartMs') or barrier.get('liveConfigurationSha256')!=template.get('liveConfigurationSha256'):fail('Barrier/template identity mismatch')
    refs,pads=validate_eight(target)
    availability_sources=validate_availability_reports(pads,template,now)
    if target.get('sessionId')!=template.get('sessionId') or target.get('jvmStartMs')!=template.get('jvmStartMs') or target.get('liveConfigurationSha256')!=barrier.get('liveConfigurationSha256') or target.get('quantizationMm')!=0.01 or target.get('boardUnmovedSinceRegistration') is not True or target.get('precisionCalibrated') is not False or target.get('flowCalibrated') is not False:fail('Target identity/provisional/unmoved evidence mismatch')
    if profile.get('sessionId')!=template.get('sessionId') or profile.get('jvmStartMs')!=template.get('jvmStartMs') or profile.get('liveConfigurationSha256')!=template.get('liveConfigurationSha256') or profile.get('provenance')!='commissioning-provisional' or profile.get('precisionCalibrated') is not False or profile.get('flowCalibrated') is not False:fail('Preparation profile identity mismatch')
    for a in 'XYZA':
        if not COMP.finite(profile.get('rawPose',{}).get(a)) or abs(profile['rawPose'][a]-start[a])>0.0001:fail('Preparation profile does not match barrier '+a)
    ee,re=ev(ep),ev(rp)
    if PREP.WIPE.checked_evidence(review.get('experimentEvidence'),'review experiment')!=ee or PREP.WIPE.checked_evidence(review.get('imageEvidence'),'review image')!=ev(image) or PREP.WIPE.checked_evidence(profile.get('measurementEvidence'),'profile review')!=re:fail('Preparation experiment/review/profile evidence does not bind')
    if review.get('reviewedBy') is None or type(review.get('reviewedMs')) is not int or not captured<=review['reviewedMs']<=now:fail('Fresh authored complete-route review required')
    if not PREP.BATCH.same(experiment.get('startRaw'),start) or experiment.get('mode')!='transfer-preparation':fail('Transfer preparation must start at exact fresh barrier')
    if experiment.get('doseDegrees')!=target['compensatedSequence'].get('doseDegrees') or experiment.get('conditioningDoseDegrees')!=20:fail('Preparation experiment dose must match the selected FTP dose and retain conditioning dose20')
    gap=PREP.number(profile.get('estimatedGapMm'),'profile gap');unc=PREP.number(profile.get('gapUncertaintyMm'),'profile uncertainty')
    prefix,_,prep_accounting=PREP.stages_for(experiment,re,gap,unc)
    if len(prefix)<2 or prefix[-2].get('axis')!='B' or prefix[-1].get('axis')!='Z':fail('Preparation must end with +R then lift')
    at=dict(start)
    for s in prefix:at[s['axis']]=s['target']
    clearance=args.xy_clearance_raw_z
    if at['Z']!=experiment['clearanceRawZ'] or abs(clearance-at['Z'])>0.05+1e-9 or clearance>=target['surface']['rawZ']:fail('FTP clearance must match reviewed preparation lift plane within 0.05mm and stay above work surface')
    pre_extra=[]
    if at['Z']!=clearance:pre_extra.append({'axis':'Z','target':clearance});at['Z']=clearance
    base_stages=prefix+pre_extra;all_stages=list(base_stages);out=copy.deepcopy(target)
    out['inlineConditioning']={'schema':1,'protocol':'scrap-condition-transit-eight-pad','experiment':copy.deepcopy(experiment),'experimentEvidence':ee,'maximumTransferMilliseconds':15000,'prefixStageCount':len(prefix),'retractionStageIndex':len(prefix)-2,'liftStageIndex':len(prefix)-1}
    c=out['compensatedSequence']
    for k in ('conditioningReportEvidence','conditioningLedgerEvidence','preparationExperimentEvidence','tipObservationEvidence','conditioningFinishedMs','maximumElapsedMilliseconds'):c.pop(k,None)
    out['pads']=copy.deepcopy(pads)
    registration,_,_=COMP.read(target['registrationEvidence']['path'])
    registered={p['padId']:p for p in registration.get('resistorPadMachineXYTargets',[])}
    offset=target.get('cameraMinusTipXYMm')
    if not isinstance(offset,list) or len(offset)!=2 or not all(COMP.finite(x) for x in offset):fail('Explicit camera-minus-tip offset required')
    for p in out['pads']:
        pose=p.get('rawPose') or {};r=registered.get(p['padId'])
        if not r or any(not COMP.finite(pose.get(k)) for k in 'XYZA') or pose['Z']!=target['surface']['rawZ'] or pose['A']!=start['A']:fail('Pad pose or affine registration missing')
        if [pose['X'],pose['Y']]!=[COMP.q01(r['machineXYMm'][i]-offset[i]) for i in range(2)]:fail('Pad pose differs from registered-minus-tip coordinates')
    pairgross=0;pair_stage_count=0
    for group,ref in enumerate(refs):
        subset=copy.deepcopy(out);subset['pads']=copy.deepcopy(out['pads'][group*2:group*2+2])
        shifted=copy.deepcopy(native)
        for name in ('N1','N2','top','bottom'):
            for axis in ('x','y','z'):
                ra=axis.upper();sign=-1 if ra=='Z' and name=='N2' else 1
                shifted[name][axis]+=sign*(at[ra]-start[ra])
        pair_out,route,_,_,acct=COMP.build_route(at,shifted,subset,clearance)
        offset_index=len(all_stages)
        active=route if group==3 else route[:-2]
        if group<3 and (len(route)<2 or route[-2].get('axis')!='B' or route[-1].get('axis')!='B'):fail('Only final resistor pair may receive idle relief')
        dst_by_id={p['padId']:p for p in out['pads'][group*2:group*2+2]}
        for po in pair_out['pads']:
            dst=dst_by_id[po['padId']]
            dst['restoreStageIndex']=po['restoreStageIndex']+offset_index
            dst['doseStageIndices']=[i+offset_index for i in po['doseStageIndices']]
            dst['retractStageIndex']=po['retractStageIndex']+offset_index
            dst['liftStageIndex']=po['liftStageIndex']+offset_index
        if group==3:
            out['compensatedSequence']['finalIdleStageIndices']=[i+offset_index for i in pair_out['compensatedSequence']['finalIdleStageIndices']]
        else:
            pairgross+=acct['grossChargedDegrees']-40
        if group==3:pairgross+=acct['grossChargedDegrees']
        all_stages.extend(active);pair_stage_count+=len(active)
        for s in active:at[s['axis']]=s['target']
    if len(all_stages)>96:fail('Eight-pad combined route exceeds explicit 96-stage group limit')
    if target_path.read_bytes()!=target_bytes or ep.read_bytes()!=ebytes:fail('Authored target/experiment changed while preparing')
    route_states=[dict(start)];cur=dict(start)
    for s in all_stages:cur=dict(cur);cur[s['axis']]=s['target'];route_states.append(cur)
    bounds={a:{'min':min(p[a] for p in route_states),'max':max(p[a] for p in route_states)} for a in 'XYZB'}
    heads={}
    for name in ('N1','N2'):
        limits={}
        for a in 'XYZ':
            sign=-1 if a=='Z' and name=='N2' else 1;vals=[native[name][a.lower()]+sign*(p[a]-start[a]) for p in route_states]
            limits['min'+a]=min(vals)-.001;limits['max'+a]=max(vals)+.001
        heads[name]=limits
    outdir=Path(args.output).resolve();outdir.mkdir(parents=True,exist_ok=False)
    targetcopy=outdir/'targets.json';targetcopy.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
    gross=sum(abs(r['B']-l['B']) for l,r in zip(route_states,route_states[1:]))
    recipe={'mode':'wet','stages':all_stages,'rawBounds':bounds,'headClearanceBounds':heads,'xyClearanceRawZ':clearance,
        'clearanceReviewEvidence':re,'profileEvidence':ev(pp),'previousReportEvidence':ev(prevp),'previousLedgerPath':str(lp),
        'targetSurface':'scrap-conditioned-ftp-eight-pad','ftpTargetEvidence':ev(targetcopy),
        'computedDoseStageIndices':{p['padId']:p['doseStageIndices'] for p in out['pads']},
        'computedRestoreRetractLiftIndices':{p['padId']:[p['restoreStageIndex'],p['retractStageIndex'],p['liftStageIndex']] for p in out['pads']},
        'bAccounting':{'initialB':start['B'],'finalB':at['B'],'grossChargedDegrees':gross,'netDegrees':at['B']-start['B'],
                       'conditioningGrossDegrees':prep_accounting['grossCommandedDegrees'],'ftpGroupGrossDegrees':pairgross},
        'sourceTargetEvidence':ev(target_path),'inlineConditioningEvidence':ee}
    recipep=outdir/'recipe.json';recipep.write_text(json.dumps(recipe,indent=2,allow_nan=False)+'\n')
    nativeout=outdir/'native';cmd=[sys.executable,str(GENERIC),'prepare','--template',str(tp),'--barrier',str(bp),'--image',str(image),'--recipe',str(recipep),'--output',str(nativeout)]
    try: result=subprocess.run(cmd,check=True,text=True,capture_output=True)
    except subprocess.CalledProcessError as e:fail('Generic native offline validator rejected route: '+(e.stderr or e.stdout).strip())
    for p,b,n in ((tp,tbytes,'template'),(bp,bbytes,'barrier'),(target_path,target_bytes,'target'),(ep,ebytes,'experiment'),(pp,pbytes,'profile'),(rp,rbytes,'review'),(prevp,prevbytes,'previous report'),(lp,lbytes,'ledger'),(image,ib,'image')):
        if p.read_bytes()!=b:fail(n+' changed during preparation')
    for p,b in availability_sources.items():
        if p.read_bytes()!=b:fail('Availability evidence changed during preparation')
    print(json.dumps({'targets':str(targetcopy),'recipe':str(recipep),'previewRequest':str(nativeout/'preview-request.json'),
        'conditioningPrefixStages':len(prefix),'ftpPairStages':pair_stage_count,'totalStages':len(all_stages),
        'pairReferences':refs,'bAccounting':recipe['bAccounting'],'nativeValidator':result.stdout.strip(),
        'enabled':False,'motionDispatched':False},indent=2))

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('experiment','template','barrier','profile','clearance-review','image','target-record','previous-report','ledger','output'):p.add_argument('--'+n,required=True)
 p.add_argument('--xy-clearance-raw-z',type=float,required=True);a=p.parse_args()
 try:build(a)
 except Exception as e:p.error(str(e))
if __name__=='__main__':main()
