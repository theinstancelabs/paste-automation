#!/usr/bin/env python3
"""Offline builder for a reviewed scrap prefix and one-to-eight selected FTP pads."""
import argparse, copy, datetime, hashlib, importlib.util, json, math, struct, subprocess, sys, time
from pathlib import Path

ROOT=Path('/home/lumen/lumenpnp'); HERE=Path(__file__).resolve().parent
GENERIC=ROOT/'automation/paste/prepare-contiguous-batch.py'
BASE=HERE/'prepare-conditioned-ftp-pair.py'
spec=importlib.util.spec_from_file_location('selected_pair_base',BASE); M=importlib.util.module_from_spec(spec); spec.loader.exec_module(M)
COMP,PREP=M.COMP,M.PREP
MIN_SPEC=importlib.util.spec_from_file_location('minimum_travel_policy',HERE/'minimum_travel_policy.py');MIN=importlib.util.module_from_spec(MIN_SPEC);MIN_SPEC.loader.exec_module(MIN)

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

def controller_steps(raw_b):
    f=lambda x:struct.unpack('f',struct.pack('f',float(x)))[0]
    return int(math.floor(f(f(raw_b)*f(4.44))+.5)) if raw_b>=0 else -int(math.floor(abs(f(f(raw_b)*f(4.44)))+.5))

def fractional_target(start_b,requested,count_target,direction):
    sign=1 if direction=='positive' else -1
    candidates=[]
    for cents in range(max(1,round((requested-.40)*100)),round((requested+.40)*100)+1):
        amount=cents/100;target=round((start_b+sign*amount)*100)/100
        actual=abs(target-start_b);count=abs(controller_steps(target)-controller_steps(start_b))
        if count==count_target:candidates.append((abs(actual-requested),actual))
    if not candidates:fail('No 0.01-degree raw B target reaches the reviewed nearest controller count')
    return sorted(candidates)[0][1],count_target

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
    wide=getattr(args,'up_to_40',False); comparison=getattr(args,'retraction_comparison',False); minimum_travel=getattr(args,'minimum_travel_eight_pad',False)
    if comparison:
        rc=target.get('retractionComparison') or {}
        if rc.get('schema')!=1 or rc.get('protocol')!='four-group-fractional-retraction-comparison' or rc.get('doseDegrees')!=6 or rc.get('stepsPerDegree')!=4.44 or c.get('protocol')!='restore-dose-retract-lift-retraction-comparison' or c.get('doseDegrees')!=6 or c.get('conditioningRetractDegrees')!=3 or c.get('retractDegrees')!=3: fail('Exact fractional comparison contract required')
    if minimum_travel:
        if target.get('pairReferences')!=['R17','R18','R19','R20']: fail('Minimum-travel scope requires exact ordered resistor references')
        policy=target.get('minimumTravelPolicy') or {}
        if (policy.get('schema')!=1 or policy.get('protocol')!='same-component-pair-no-interim-retract' or
                c.get('protocol')!='restore-dose-pair-carry-retract-lift-minimum-travel-eight-pad' or
                c.get('doseDegrees')!=6 or c.get('retractPercent')!=30 or c.get('requestedRetractionDegrees')!=1.8 or
                c.get('retractDegrees')!=3 or c.get('conditioningRetractDegrees')!=3 or c.get('dwellMilliseconds')!=2000 or
                c.get('retractDwellMilliseconds')!=500 or c.get('idleReliefDegrees')!=40): fail('Exact minimum-travel eight-pad recipe required')
    if not isinstance(pads,list) or not 1<=len(pads)<=(32 if comparison else 40 if wide else 8) or c.get('protocol') not in (('restore-dose-retract-lift-retraction-comparison',) if comparison else ('restore-dose-pair-carry-retract-lift-minimum-travel-eight-pad',) if minimum_travel else ('restore-dose-retract-lift-selected-pads',)): fail('Selected-pad count/protocol mismatch')
    ids=[p.get('padId') for p in pads]
    if len(set(ids))!=len(ids) or any(not isinstance(i,str) or not __import__('re').fullmatch(r'R(?:[1-9]|[1-3][0-9]|40)\.[12]',i) for i in ids): fail('Selected pads must be unique registered pad identities')
    if comparison and (len(pads)!=32 or [p['padId'] for p in pads]!=[f'R{r}.{side}' for r in range(1,17) for side in (1,2)]): fail('Comparison requires ordered R1-R16 pad pairs')
    if minimum_travel and (len(pads)!=8 or [p['padId'] for p in pads]!=[f'R{r}.{side}' for r in range(17,21) for side in (1,2)]): fail('Minimum-travel scope requires exactly the ordered R17-R20 adjacent pad pairs')
    if minimum_travel:
        for p in pads:
            reference,side=p['padId'].rsplit('.',1)
            if p.get('componentReference')!=reference or p.get('pairOrder')!=int(side) or p.get('retractPercent')!=30 or p.get('requestedRetractionDegrees')!=1.8: fail('Every minimum-travel pad must bind its exact component, pair order and fixed 30-percent request')
        travel=MIN.plan_minimum_travel_transitions([{'reference':p['padId'].rsplit('.',1)[0],'pad':p['padId'].rsplit('.',1)[1],'xy_mm':[p['rawPose']['X'],p['rawPose']['Y']]} for p in pads])
        if travel!=target['minimumTravelPolicy'].get('plan') or target['minimumTravelPolicy'].get('orderedPadIds')!=ids or len(travel['transitions'])!=7 or any((i%2==0 and (t['reason']!='same-component-short-move' or t['retractBeforeMove'] or t['restoreAfterMove'] or not t['skipRequiresNoPriorRetract'])) or (i%2==1 and (t['reason']!='component-boundary' or not t['retractBeforeMove'] or not t['restoreAfterMove'])) or not t['preserveClearanceLift'] for i,t in enumerate(travel['transitions'])): fail('Reviewed minimum-travel plan differs from current pad coordinates or pair boundaries')
    if comparison:
        groups=target['retractionComparison'].get('groups')
        if not isinstance(groups,list) or len(groups)!=4: fail('Four comparison groups required')
        for gi,g in enumerate(groups):
            expected=[p['padId'] for p in pads[gi*8:(gi+1)*8]]
            if g.get('group')!=gi+1 or g.get('retractPercent')!=[15,20,25,30][gi] or g.get('padIds')!=expected or not isinstance(g.get('scrapTargetsXY'),list) or len(g['scrapTargetsXY'])!=2 or not isinstance(g.get('primeRawXY'),list) or len(g['primeRawXY'])!=2: fail('Comparison group assignment/lane differs from R1-R16 ordered blocks')
            lane=(experiment.get('comparisonGroupTargetsXY') or [])
            if len(lane)!=4 or gi==0 and experiment.get('targetsXY')!=g['scrapTargetsXY'] or lane[gi].get('group')!=gi+1 or lane[gi].get('targetsXY')!=g['scrapTargetsXY'] or lane[gi].get('primeRawXY')!=g['primeRawXY']: fail('Reviewed experiment does not bind all four translated conditioning lanes')
            px,py=g['primeRawXY'];first,second=g['scrapTargetsXY']
            if abs(first.get('X')-(px+1.5))>.01 or abs(first.get('Y')-py)>.01 or abs(second.get('X')-(px+5.34))>.01 or abs(second.get('Y')-py)>.01: fail('Lane wipe/dummy targets must preserve reviewed +1.5/+5.34 mm X path')
            g.update(resetStartStageIndex=None,resetEndStageIndex=None,prefixStartStageIndex=0,groupStartStageIndex=0,groupEndStageIndex=0)
    if target.get('reviewedBy') is None or type(target.get('reviewedMs')) is not int or not captured<=target['reviewedMs']<=now: fail('Fresh complete-route pad review required')
    if not isinstance(review.get('reviewedBy'),str) or type(review.get('reviewedMs')) is not int or not captured<=review['reviewedMs']<=now or review.get('imageEvidence')!=ev(image): fail('Preparation review must bind fresh image and reviewer')
    if PREP.WIPE.checked_evidence(profile.get('measurementEvidence'),'profile review')!=ev(rp): fail('Preparation profile must bind exact review')
    if profile.get('sessionId')!=template.get('sessionId') or profile.get('jvmStartMs')!=template.get('jvmStartMs') or profile.get('liveConfigurationSha256')!=template.get('liveConfigurationSha256') or profile.get('provenance')!='commissioning-provisional' or profile.get('precisionCalibrated') is not False or profile.get('flowCalibrated') is not False: fail('Preparation profile identity/provisional mismatch')
    for k in 'XYZA':
        if abs(profile.get('rawPose',{}).get(k,float('inf'))-raw[k])>1e-4: fail('Profile does not match barrier '+k)
    ee,re=ev(ep),ev(rp)
    if PREP.WIPE.checked_evidence(review.get('experimentEvidence'),'review experiment')!=ee or experiment.get('mode')!='transfer-preparation' or experiment.get('startRaw')!=raw: fail('Preparation experiment/review must bind exact barrier')
    if comparison and (experiment.get('primeDegrees')!=60 or experiment.get('conditioningDoseDegrees')!=6 or experiment.get('conditioningRestoreDegrees',0)!=0 or experiment.get('retractDegrees')!=3 or experiment.get('retractDwellMilliseconds')!=500): fail('Each comparison lane requires the identical 60-degree prime and conditioner6/R3/500')
    if minimum_travel and (experiment.get('primeDegrees')!=60 or experiment.get('conditioningDoseDegrees')!=6 or experiment.get('conditioningRestoreDegrees',0)!=0 or experiment.get('retractDegrees')!=3 or experiment.get('retractDwellMilliseconds')!=500): fail('Minimum-travel route requires identical prime60/conditioner6/R3/500')
    if experiment.get('retractDegrees')!=c.get('retractDegrees') or experiment.get('conditioningDoseDegrees') not in (6,12,20) or experiment.get('conditioningRestoreDegrees',0) not in (0,3): fail('Conditioning amounts must match selected protocol')
    if experiment.get('conditioningDoseDegrees')==12 and (experiment.get('conditioningDwellMilliseconds',experiment.get('dwellMilliseconds',2000))!=2000 or experiment.get('retractDegrees')!=3 or experiment.get('retractDwellMilliseconds')!=500): fail('Conditioner12 requires 2000 ms and R3/500')
    if target.get('pads') and target['pads'][0].get('surface')!=target.get('surface'): fail('Top-level surface must mirror first selected pad surface')
    availability=[]
    for p in pads:
        if p.get('padIdentityReviewed') is not True or p.get('padAvailableReviewed') is not True: fail('Each selected pad needs explicit fresh review')
        read_availability(p,template,target['boardId'],target['reviewedMs'],now,snaps,900000 if wide or comparison or minimum_travel else 300000)
    gap=PREP.number(profile.get('estimatedGapMm'),'conditioning profile gap');unc=PREP.number(profile.get('gapUncertaintyMm'),'conditioning uncertainty')
    prefix,_,prep_accounting=PREP.stages_for(experiment,re,gap,unc)
    group_prefixes=[prefix]
    if comparison:
        for g in target['retractionComparison']['groups'][1:]:
            gx=copy.deepcopy(experiment);gx['startRaw']=dict(raw,X=g['primeRawXY'][0],Y=g['primeRawXY'][1]);gx['targetsXY']=copy.deepcopy(g['scrapTargetsXY']);gp,_,_=PREP.stages_for(gx,re,gap,unc);group_prefixes.append(gp)
    retract_i=len(prefix)-2-(1 if experiment.get('conditioningFinalWipeMm',0) else 0)
    if retract_i<0 or prefix[retract_i].get('axis')!='B' or prefix[-1].get('axis')!='Z': fail('Conditioner must finish with selected retract/wipe then clearance lift')
    at=copy.deepcopy(raw)
    for s in prefix: at[s['axis']]=s['target']
    clear=args.xy_clearance_raw_z
    if at['Z']!=experiment['clearanceRawZ'] or abs(clear-at['Z'])>.05+1e-9: fail('Selected route clearance must match reviewed conditioner lift')
    stages=list(prefix)
    if comparison: target['retractionComparison']['groups'][0].update(resetStartStageIndex=None,resetEndStageIndex=None,prefixStartStageIndex=0,prefixStageCount=len(prefix),groupStartStageIndex=len(prefix))
    if at['Z']!=clear: at=append(stages,at,'Z',clear)
    if clear>=min(p['surface']['rawZ'] for p in pads): fail('Common transit clearance must remain above all selected pad surfaces')
    for pi,p in enumerate(pads):
        if comparison and pi and pi%8==0:
            g=target['retractionComparison']['groups'][pi//8];g['resetStartStageIndex']=len(stages)
            lane=target['retractionComparison']['groups'][pi//8]['primeRawXY'];at=move(stages,at,'X',lane[0],clear);at=move(stages,at,'Y',lane[1],clear);at=move(stages,at,'Z',experiment['startRaw']['Z'],clear)
            g['resetEndStageIndex']=len(stages)-1;g['prefixStartStageIndex']=len(stages);base=experiment['startRaw']['B']
            gprefix=group_prefixes[pi//8];g['prefixStageCount']=len(gprefix);offset=at['B']-base
            for ps in gprefix:
                val=ps['target'] + (offset if ps['axis']=='B' else 0)
                at=append(stages,at,ps['axis'],val,**{k:v for k,v in ps.items() if k not in ('axis','target')})
            g['groupStartStageIndex']=len(stages)
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
        retract_degrees=(6*p['retractPercent']/100 if comparison else c['retractDegrees'])
        if comparison:
            p['group']=pi//8+1;p['retractPercent']=target['retractionComparison']['groups'][pi//8]['retractPercent'];p['requestedRetractionDegrees']=6*p['retractPercent']/100
            if pi%8==0:restore_amount=3.0;restore_steps=round(3*4.44)
            else:
                previous=pads[pi-1];restore_amount=previous['actualRetractRawDelta'];restore_steps=previous['actualRetractControllerSteps']
                if abs(controller_steps(at['B'])-controller_steps(at['B']-restore_amount)-restore_steps)>0: fail('Next pad restore cannot exactly reverse prior absolute controller count')
            after_restore=at['B']-restore_amount;after_dose=after_restore-6;desired_steps=math.floor(p['requestedRetractionDegrees']*4.44+.5)
            retract_amount,retract_steps=fractional_target(after_dose,p['requestedRetractionDegrees'],desired_steps,'positive');retract_degrees=retract_amount
            p['restoreRawDelta']=-restore_amount;p['actualRetractRawDelta']=retract_amount;p['actualRetractControllerSteps']=retract_steps;p['actualQuantizedRetractionDegrees']=round(retract_steps/4.44,6)
            p['restoreStageIndex']=bstep(-restore_amount,0)
        elif minimum_travel:
            p['componentReference']=ids[pi].rsplit('.',1)[0];p['pairOrder']=int(ids[pi].rsplit('.',1)[1]);p['retractPercent']=30;p['requestedRetractionDegrees']=1.8
            if p['pairOrder']==1:
                if pi==0: restore_target=at['B']-3.0;p['restoreSourceStageIndex']=retract_i
                else:
                    previous=pads[pi-1];restore_target=previous['retractRestoreTargetB'];p['restoreSourceStageIndex']=previous['retractStageIndex']
                expected_restore_steps=-round(3*4.44) if pi==0 else -previous['actualRetractControllerSteps']
                if controller_steps(restore_target)-controller_steps(at['B'])!=expected_restore_steps: fail('Pair-start restore must reverse the exact conditioner or preceding fractional retract count')
                p['restoreStageIndex']=len(stages);p['restoreTargetB']=restore_target;at=append(stages,at,'B',restore_target,gapEvidence=p['surfaceEvidence'],estimatedGapMm=surf['estimatedGapMm'],gapUncertaintyMm=surf['gapUncertaintyMm'],dwellMilliseconds=0)
            else:
                p['restoreStageIndex']=None;p['restoreSourceStageIndex']=None;p['restoreTargetB']=None
        else:p['restoreStageIndex']=bstep(-retract_degrees,0)
        if c['doseDegrees']==12:
            p['doseStageIndices']=[bstep(-6,0),bstep(-6,c['dwellMilliseconds'])]
        else: p['doseStageIndices']=[bstep(-c['doseDegrees'],c['dwellMilliseconds'])]
        if minimum_travel and p['pairOrder']==1:
            p['retractStageIndex']=None;p['actualRetractRawDelta']=None;p['actualRetractControllerSteps']=None;p['retractRestoreTargetB']=None
        elif minimum_travel:
            before_retract=at['B'];desired_steps=round(1.8*4.44);amount,steps=fractional_target(before_retract,1.8,desired_steps,'positive')
            p['retractRestoreTargetB']=before_retract;p['actualRetractRawDelta']=amount;p['actualRetractControllerSteps']=steps;p['actualQuantizedRetractionDegrees']=round(steps/4.44,6)
            p['retractStageIndex']=bstep(amount,c['retractDwellMilliseconds'])
        else:p['retractStageIndex']=bstep(retract_degrees,c['retractDwellMilliseconds'])
        p['liftStageIndex']=len(stages);at=append(stages,at,'Z',clear)
        if comparison and pi%8==7:
            gi=pi//8;g=target['retractionComparison']['groups'][gi];g['groupIdleReliefStageIndices']=[bstep(20,0),bstep(20,2000)];g['groupEndStageIndex']=g['groupIdleReliefStageIndices'][-1]
    idle=c['idleReliefDegrees']
    if comparison:
        if idle!=40:fail('Each comparison group requires identical 40-degree finishing relief')
    elif minimum_travel:
        if idle!=40:fail('Minimum-travel route requires final 40-degree relief')
        c['finalIdleStageIndices']=[bstep(20,0),bstep(20,2000)]
    elif idle==20:
        c['finalIdleStageIndex']=bstep(20,2000)
    elif idle==40:
        deltas=[20,20]
        c['finalIdleStageIndices']=[bstep(20,0),bstep(20,2000)]
    else: fail('Selected-pad idle relief must be20 or40')
    c.pop('finalIdleStageIndex',None) if idle==40 else None
    if len(stages)>(400 if wide or comparison else 96): fail('Selected-pad route exceeds its native stage cap')
    target['pads']=pads
    target['inlineConditioning']={'schema':1,'protocol':'scrap-condition-transit-retraction-comparison' if comparison else 'scrap-condition-transit-minimum-travel-eight-pad' if minimum_travel else 'scrap-condition-transit-selected-pads','experiment':copy.deepcopy(experiment),'experimentEvidence':ee,'maximumTransferMilliseconds':15000,'prefixStageCount':len(prefix),'retractionStageIndex':retract_i,'liftStageIndex':len(prefix)-1,'comparisonGroupPrefixes':[{'group':i+1,'prefixStageCount':len(x)} for i,x in enumerate(group_prefixes)] if comparison else None}
    route=[copy.deepcopy(raw)];cur=copy.deepcopy(raw)
    for s in stages:cur=copy.deepcopy(cur);cur[s['axis']]=s['target'];route.append(cur)
    bounds={a:{'min':min(x[a] for x in route),'max':max(x[a] for x in route)} for a in 'XYZB'};heads={}
    for name in ('N1','N2'):
        limits={}
        for axis in 'XYZ':
            sign=-1 if axis=='Z' and name=='N2' else 1;vals=[native[name][axis.lower()]+sign*(x[axis]-raw[axis]) for x in route];limits['min'+axis]=min(vals)-.001;limits['max'+axis]=max(vals)+.001
        heads[name]=limits
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=False);tpout=out/'targets.json';tpout.write_text(json.dumps(target,indent=2,allow_nan=False)+'\n')
    gross=sum(abs(b['B']-a['B']) for a,b in zip(route,route[1:]));
    if comparison and gross>813: fail('Fractional comparison exceeds the currently reviewed 813-degree remaining budget')
    if minimum_travel and (len(stages)>150 or gross>220): fail('Minimum-travel eight-pad route exceeds its 150-stage or 220-degree bound')
    recipe={'mode':'wet','stages':stages,'rawBounds':bounds,'headClearanceBounds':heads,'xyClearanceRawZ':clear,'clearanceReviewEvidence':re,'profileEvidence':ev(pp),'previousReportEvidence':ev(prevp),'previousLedgerPath':str(lp),'targetSurface':'ftp-selected-pads-retraction-comparison' if comparison else 'ftp-selected-pads-minimum-travel-eight-pad' if minimum_travel else 'ftp-selected-pads-up-to-40' if wide else 'ftp-selected-pads','ftpTargetEvidence':ev(tpout),'sourceTargetEvidence':ev(tp0),'bAccounting':{'initialB':raw['B'],'finalB':route[-1]['B'],'grossChargedDegrees':gross,'netDegrees':route[-1]['B']-raw['B'],'conditioningGrossDegrees':prep_accounting['grossCommandedDegrees'],'selectedPadCount':len(pads)}}
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
 p.add_argument('--retraction-comparison',action='store_true',help='Use the exact four-group fractional comparison native scope')
 p.add_argument('--up-to-40',action='store_true',help='Use distinct reviewed 1-40-pad scope and 400-stage ceiling')
 p.add_argument('--minimum-travel-eight-pad',action='store_true',help='Use the dedicated 8-pad R17-R20 pair-carry scope')
 p.add_argument('--application-restart-evidence',help='explicit continuity proof when resuming across an application restart')
 p.add_argument('--manual-home-ledger-anchor-evidence',help='narrow reviewed manual-home ledger continuity evidence')
 p.add_argument('--xy-clearance-raw-z',type=float,required=True);a=p.parse_args()
 try:build(a)
 except Exception as exc:p.error(str(exc))
if __name__=='__main__':main()
