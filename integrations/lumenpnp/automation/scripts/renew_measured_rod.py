#!/usr/bin/env python3
"""Preview a fresh operator rod measurement; --apply preserves all ledger charges."""
import argparse, hashlib, json, os, pathlib, shutil, subprocess, time
R=pathlib.Path(__file__).resolve().parents[2]
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--exposure-mm',type=float,required=True)
ap.add_argument('--measurement-evidence',type=pathlib.Path,required=True)
ap.add_argument('--apply',action='store_true')
a=ap.parse_args()
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
# A fixed modest renewal, limited further by the physical measurement. Never refund history.
used=l['usedAdditionalGrossDegrees'];cap=used+3000;mm=19/32*.5/360
assert 0<a.exposure_mm<=70 and (a.exposure_mm-11.3262217-10)/mm>=3000

def bound(f):return {'path':str(f.resolve()),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
e={'schema':1,'scope':'operator-measured-rod-renewal','operatorConfirmed':True,'sessionId':p['sessionId'],'reportedExposureMm':a.exposure_mm,'nearBottomExposureMm':11.3262217,'engineeringAllowanceMm':10,'mmPerMotorDegreeNominal':mm,'grossUsedAtMeasurement':used,'verifiedBAtMeasurement':l['lastVerifiedRaw']['B'],'additionalAllowanceDegrees':1000,'recordedAtUnixMs':evidence['recordedUnixMs'],'operatorReport':bound(a.measurement_evidence)}
x={'schema':1,'scope':'measured-rod-cumulative-extension','sessionId':p['sessionId'],'grossUsedAtMeasurement':used,'cumulativeAllowanceDegrees':3000,'newPhysicalMeasurement':False,'engineeringAllowanceUnchangedMm':10}
nextp=json.loads(json.dumps(p));nextp['rodBudget']['maximumAdditionalGrossDegrees']=cap
code="const P=require(process.argv[1]),q=JSON.parse(require('fs').readFileSync(0));P.validateProfile(q.p);P.validateMeasuredRenewal(q.p.rodBudget,q.e,q.l,q.l,q.p.sessionId,q.x);if(q.c.alignmentApplied)P.fitAlignment(q.c.alignmentSamples,q.p);"
subprocess.run(['node','-e',code,str(R/'automation/paste/operator-console-policy.cjs')],input=json.dumps({'p':nextp,'e':e,'l':l,'c':c,'x':x}),text=True,check=True)
print(json.dumps({'exposureMm':a.exposure_mm,'remainingPhysicalMmAfterReserve':a.exposure_mm-11.3262217-10,'grossPreserved':used,'additionalAllowance':3000,'newCap':cap,'pendingPreserved':l['pendingRetractDegrees'],'apply':a.apply}))
if not a.apply:raise SystemExit
b=R/'.local-machine-backups'/('operator-measured-rod-renewal-'+str(time.time_ns()));b.mkdir()
for f,n in [(pp,'profile.json'),(lp,'ledger.json'),(cp,'calibration.json')]:
 assert f.read_bytes()==original[f], 'Concurrent state change before backup'
 (b/n).write_bytes(original[f])
e['ledgerSnapshot']=bound(b/'ledger.json');ef=b/'measurement.json';ef.write_text(json.dumps(e,indent=2)+'\n');x['originalMeasurement']=bound(ef);xf=b/'extension.json';xf.write_text(json.dumps(x,indent=2)+'\n')
p['rodMeasuredRenewal']=bound(ef);p['rodMeasuredExtension']=bound(xf);p['rodBudget']['maximumAdditionalGrossDegrees']=l['maximumAdditionalGrossDegrees']=cap;p['rawBounds']['B']={'min':l['baselineB']-cap,'max':l['baselineB']+cap}
for n in ['profile.json','ledger.json','calibration.json','measurement.json','extension.json']:p['sourceEvidence'].append(bound(b/n))
p['id']=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest();l['profileId']=c['profileId']=p['id']
for f,n in [(pp,'profile.json'),(lp,'ledger.json'),(cp,'calibration.json')]:assert f.read_bytes()==(b/n).read_bytes(),'Concurrent state change'
# Profile last: intermediate state cannot arm the old profile against a new ledger.
for dest,q in [(d/('calibration-'+p['id']+'.json'),c),(lp,l),(pp,p)]:
 tmp=dest.with_suffix('.tmp');tmp.write_text(json.dumps(q,indent=2,allow_nan=False)+'\n');os.replace(tmp,dest)
print('APPLIED '+p['id'])
