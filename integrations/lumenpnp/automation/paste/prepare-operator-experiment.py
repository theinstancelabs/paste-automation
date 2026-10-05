#!/usr/bin/env python3
"""Preview an explicit operator experiment; --execute stages and dispatches once."""
import argparse,fcntl,hashlib,json,os,pathlib,subprocess,sys,uuid
ROOT=pathlib.Path(__file__).resolve().parents[2]
def read(p): return json.loads(p.read_text())
def active_guard(root):
    request=root/'automation/plans/operator-batch-request.json'
    if request.exists():
        q=read(request); report=root/'automation/evidence/operator-batches'/q['id']/'report.json'
        if not report.exists() or read(report).get('status') not in ('completed-awaiting-image-review','failed-no-retry'):
            raise ValueError('Existing request is pending/active; preserve it and wait for its terminal report')
def verify_tip_xy_evidence(c):
    correction=c.get('tipXYCorrection')
    if correction is None:return
    evidence=correction.get('evidence') if isinstance(correction,dict) else None
    if not isinstance(evidence,dict) or not isinstance(evidence.get('path'),str):raise ValueError('Tip XY correction evidence path missing')
    path=pathlib.Path(evidence['path'])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=evidence.get('sha256'):raise ValueError('Tip XY correction evidence changed')
def validate(root,q):
    p=read(root/'automation/plans/paste-operator-profile.json'); folder=root/'automation/evidence/operator-paste-runs'/p['sessionId']; c=read(folder/('calibration-'+p['id']+'.json')); l=read(folder/'budget-ledger.json')
    if any(x['profileId']!=p['id'] or x['sessionId']!=p['sessionId'] for x in (c,l)) or l['status']!='verified': raise ValueError('Calibration/ledger identity mismatch')
    verify_tip_xy_evidence(c)
    if abs(sum(e['plannedGrossDegrees'] for e in l['entries'])-l['usedAdditionalGrossDegrees'])>.0001: raise ValueError('Gross ledger total mismatch')
    touch = c.get('boardTouchReference') or c.get('coplanarTouchReference') or {}
    for evidence in [touch.get('evidence')]:
        if evidence and hashlib.sha256(pathlib.Path(evidence['path']).read_bytes()).hexdigest()!=evidence['sha256']: raise ValueError('Touch evidence changed')
    q['profileId']=p['id']
    code="""const fs=require('fs'),P=require(process.argv[1]),{p:base,c,l,q}=JSON.parse(fs.readFileSync(0,'utf8'));let p=P.validateProfile(base);if(q.mode==='dispense-and-survey'){if(!c.alignmentApplied||!c.zApplied)throw Error('Fresh XY/height calibration required');p=P.withCalibration(base,c);P.validateProfile(p);const r=q.recipe;r.workZ=p.workZ;let initial=l.lastVerifiedRaw,used=l.usedAdditionalGrossDegrees,pending=l.pendingRetractDegrees,conditioning=null;if(q.conditioning){const refs=q.conditioning.references;if(!refs.length||refs.some(x=>q.references.includes(x)))throw Error('Conditioning must use separate references');q.conditioning.recipe.workZ=p.workZ;conditioning=P.plan(refs,q.conditioning.recipe,p,initial,used,pending);initial=conditioning.finalRaw;used+=conditioning.grossDegrees;pending=conditioning.pendingRetractDegrees;}const plan=P.plan(q.references,r,p,initial,used,pending);process.stdout.write(JSON.stringify({plannedGrossDegrees:plan.grossDegrees+(conditioning?conditioning.grossDegrees:0),remainingAfter:l.maximumAdditionalGrossDegrees-used-plan.grossDegrees,stageCount:plan.stages.length+(conditioning?conditioning.stages.length:0),endingPendingRetractDegrees:plan.pendingRetractDegrees,recipe:r,conditioning:q.conditioning||null}));}else{if(c.alignmentApplied)p=P.withCalibration(base,c);P.select(q.references,'both',p);process.stdout.write(JSON.stringify({plannedGrossDegrees:0,remainingAfter:l.maximumAdditionalGrossDegrees-l.usedAdditionalGrossDegrees}));}"""
    result=subprocess.run(['node','-e',code,str(root/'automation/paste/operator-console-policy.cjs')],input=json.dumps({'p':p,'c':c,'l':l,'q':q}),capture_output=True,text=True,check=True)
    preview=json.loads(result.stdout)
    if 'recipe' in preview:q['recipe']=preview['recipe']
    if preview.get('conditioning'):q['conditioning']=preview['conditioning']
    return preview

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['survey','dispense-and-survey']);ap.add_argument('--refs',nargs='+',required=True);ap.add_argument('--root',type=pathlib.Path,default=ROOT);ap.add_argument('--execute',action='store_true');ap.add_argument('--retract-each-pad',action='store_true');ap.add_argument('--condition-refs',nargs='+');ap.add_argument('--condition-dose',type=float,default=.25);ap.add_argument('--condition-same-cycle',action='store_true',help='Copy the main recipe exactly for conditioning, except omit paired-pad hop');ap.add_argument('--pad-mode',choices=['both','1','2'],default='both');ap.add_argument('--condition-pad-mode',choices=['both','1','2'],default='both')
    for name in ['dose','push-deg-s','retract-percent','retract-deg-s','dwell-ms','retract-dwell-ms','gap-mm']:ap.add_argument('--'+name,type=float)
    ap.add_argument('--retract-degrees',type=float,help='Optional absolute retract per pad/resistor; overrides --retract-percent');ap.add_argument('--paired-pad-hop-mm',type=float,help='Optional 0.50..2.00 mm hop between measured paired pads (both mode only)')
    a=ap.parse_args(argv); q={'schema':1,'enabled':True,'id':'experiment-'+str(uuid.uuid4()),'mode':a.mode,'references':[r for token in a.refs for r in token.split(',')]}
    if a.mode=='dispense-and-survey':
        names=['dose','push_deg_s','retract_percent','retract_deg_s','dwell_ms','retract_dwell_ms','gap_mm']
        if any(getattr(a,k) is None for k in names):ap.error('Dispense requires every dose/speed/retraction/wait/gap option explicitly')
        q['recipe']={'doseDegrees':a.dose,'bSpeedFraction':a.push_deg_s/100,'retractPercent':a.retract_percent,'retractSpeedFraction':a.retract_deg_s/100,'dwellMs':a.dwell_ms,'retractDwellMs':a.retract_dwell_ms,'heightMode':'gap','gapMm':a.gap_mm,'padMode':a.pad_mode,'retractEachPad':a.retract_each_pad}
        if a.retract_degrees is not None:q['recipe']['retractDegrees']=a.retract_degrees
        if a.paired_pad_hop_mm is not None:q['recipe']['pairedPadHopMm']=a.paired_pad_hop_mm
    if a.condition_same_cycle and not a.condition_refs:ap.error('--condition-same-cycle requires --condition-refs')
    if a.condition_refs:
        if a.mode!='dispense-and-survey':ap.error('Conditioning requires dispense-and-survey')
        refs=[r for token in a.condition_refs for r in token.split(',')]
        if set(refs)&set(q['references']):ap.error('Conditioning references must not overlap main group')
        if a.condition_same_cycle:
            condition_recipe=dict(q['recipe']);condition_recipe.pop('pairedPadHopMm',None)
        else:
            condition_recipe={**q['recipe'],'doseDegrees':a.condition_dose,'padMode':a.condition_pad_mode,'retractPercent':0,'retractDegrees':0,'dwellMs':0,'retractDwellMs':0}
            condition_recipe.pop('pairedPadHopMm',None)
        q['conditioning']={'references':refs,'recipe':condition_recipe}
    preview=validate(a.root,q); path=a.root/'automation/plans'/('operator-'+q['id']+'.json');path.write_text(json.dumps(q,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'request':str(path),'id':q['id'],'preview':preview,'executed':a.execute}))
    if a.execute:
        with (a.root/'automation/plans/operator-experiment.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);active_guard(a.root);validate(a.root,q)
            target=a.root/'automation/plans/operator-batch-request.json';tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(q,indent=2,allow_nan=False)+'\n');os.replace(tmp,target)
            subprocess.run([sys.executable,str(a.root/'automation/scripts/run_reviewed_action.py'),'operator-batch','--confirmed'],cwd=a.root,check=True)
    return q
if __name__=='__main__':main()
