#!/usr/bin/env python3
"""Preview a fresh operator rod measurement; --apply preserves all ledger charges."""
import argparse, hashlib, json, os, pathlib, shutil, subprocess, time
R=pathlib.Path(__file__).resolve().parents[2]
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--exposure-mm',type=float,required=True)
ap.add_argument('--measurement-evidence',type=pathlib.Path,required=True)
ap.add_argument('--allowance-degrees',type=int,default=60,help='Measured renewal allowance (1..3000; default 60)')
ap.add_argument('--replacement-evidence',type=pathlib.Path,help='Explicit operator-confirmed no-motion syringe replacement record')
ap.add_argument('--apply',action='store_true')
a=ap.parse_args()
if not 1<=a.allowance_degrees<=3000: ap.error('--allowance-degrees must be 1..3000')
pp=R/'automation/plans/paste-operator-profile.json';p=json.loads(pp.read_text())
d=R/'automation/evidence/operator-paste-runs'/p['sessionId'];lp=d/'budget-ledger.json';cp=d/('calibration-'+p['id']+'.json')
original={f:f.read_bytes() for f in (pp,lp,cp)}
assert json.loads(original[pp])==p
l=json.loads(original[lp]);c=json.loads(original[cp]);evidence=json.loads(a.measurement_evidence.read_text())
assert p['id']==l['profileId']==c['profileId']
assert l['status']=='verified' and l['entries'][-1]['status']=='verified'
assert abs(l['lastVerifiedRaw']['Z']-p['safeZ'])<.001
assert evidence['reportedExposureMm']==a.exposure_mm and evidence['currentB']==l['lastVerifiedRaw']['B']
age_ms=time.time()*1000-evidence['recordedUnixMs']
assert 0<=age_ms<3600000, 'Measurement evidence must be from the past hour'
# A configurable bounded renewal, limited by fresh physical measurement. Never refund history.
used=l['usedAdditionalGrossDegrees'];cap=used+a.allowance_degrees;mm=19/32*.5/360
assert 0<a.exposure_mm<=70 and (a.exposure_mm-11.3262217-10)/mm>=a.allowance_degrees
replacement=json.loads(a.replacement_evidence.read_text()) if a.replacement_evidence else None

def bound(f):return {'path':str(f.resolve()),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
e={'schema':1,'scope':'operator-measured-rod-renewal','operatorConfirmed':True,'sessionId':p['sessionId'],'reportedExposureMm':a.exposure_mm,'nearBottomExposureMm':11.3262217,'engineeringAllowanceMm':10,'mmPerMotorDegreeNominal':mm,'grossUsedAtMeasurement':used,'verifiedBAtMeasurement':l['lastVerifiedRaw']['B'],'additionalAllowanceDegrees':a.allowance_degrees,'recordedAtUnixMs':evidence['recordedUnixMs'],'operatorReport':bound(a.measurement_evidence)}
nextp=json.loads(json.dumps(p));nextp['rodBudget']['maximumAdditionalGrossDegrees']=cap
if replacement:
 code="const P=require(process.argv[1]),q=JSON.parse(require('fs').readFileSync(0));P.validateSyringeReplacement(q.e,q.p,q.l,q.c);"
 subprocess.run(['node','-e',code,str(R/'automation/paste/operator-console-policy.cjs')],input=json.dumps({'e':replacement,'p':p,'l':l,'c':c}),text=True,check=True)
 nextp['syringeId']=replacement['newSyringeId']
code="const P=require(process.argv[1]),q=JSON.parse(require('fs').readFileSync(0));P.validateProfile(q.p);P.validateMeasuredRenewal(q.p.rodBudget,q.e,q.l,q.l,q.p.sessionId);if(q.c.alignmentApplied)P.fitAlignment(q.c.alignmentSamples,q.p);"
subprocess.run(['node','-e',code,str(R/'automation/paste/operator-console-policy.cjs')],input=json.dumps({'p':nextp,'e':e,'l':l,'c':c}),text=True,check=True)
print(json.dumps({'exposureMm':a.exposure_mm,'remainingPhysicalMmAfterReserve':a.exposure_mm-11.3262217-10,'grossPreserved':used,'additionalAllowance':a.allowance_degrees,'newCap':cap,'pendingRetractDegrees':0 if replacement else l['pendingRetractDegrees'],'replacementEvidence':bool(replacement),'apply':a.apply}))
if not a.apply:raise SystemExit
b=R/'.local-machine-backups'/('operator-measured-rod-renewal-'+str(time.time_ns()));b.mkdir()
for f,n in [(pp,'profile.json'),(lp,'ledger.json'),(cp,'calibration.json')]:
 assert f.read_bytes()==original[f], 'Concurrent state change before backup'
 (b/n).write_bytes(original[f])
e['ledgerSnapshot']=bound(b/'ledger.json');ef=b/'measurement.json';ef.write_text(json.dumps(e,indent=2)+'\n')
p['rodMeasuredRenewal']=bound(ef);p.pop('rodMeasuredExtension',None);p['rodBudget']['maximumAdditionalGrossDegrees']=l['maximumAdditionalGrossDegrees']=cap;p['rawBounds']['B']={'min':l['baselineB']-cap,'max':l['baselineB']+cap}
for n in ['profile.json','ledger.json','calibration.json','measurement.json']:p['sourceEvidence'].append(bound(b/n))
if replacement:
 replacement=dict(replacement);replacement['ledgerSnapshot']=bound(b/'ledger.json');rf=b/'syringe-replacement.json';rf.write_text(json.dumps(replacement,indent=2)+'\n');p['syringeReplacement']=bound(rf)
 p['syringeId']=replacement['newSyringeId']
 l.setdefault('reliefDecisions',[]).append({'recordId':'syringe-replacement-'+str(time.time_ns()),'at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'discardedPendingDegrees':l['pendingRetractDegrees'],'reason':'operator-confirmed-physical-syringe-replacement','grossBudgetUnchanged':l['usedAdditionalGrossDegrees'],'replacementEvidence':bound(rf)});l['pendingRetractDegrees']=0;p['sourceEvidence'].append(bound(rf))
p['id']=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest();l['profileId']=c['profileId']=p['id']
for f,n in [(pp,'profile.json'),(lp,'ledger.json'),(cp,'calibration.json')]:assert f.read_bytes()==(b/n).read_bytes(),'Concurrent state change'
# Profile last: intermediate state cannot arm the old profile against a new ledger.
for dest,q in [(d/('calibration-'+p['id']+'.json'),c),(lp,l),(pp,p)]:
 tmp=dest.with_suffix('.tmp');tmp.write_text(json.dumps(q,indent=2,allow_nan=False)+'\n');os.replace(tmp,dest)
print('APPLIED '+p['id'])
