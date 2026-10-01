#!/usr/bin/env python3
"""Author explicit cleanup evidence offline; delegate to the disabled existing preparer."""
import argparse,copy,hashlib,importlib.util,json,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('cleanup_preparer',HERE/'prepare-ftp-one-pad-cleanup.py')
C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
SOURCES=('template','barrier','stationaryImage','tipImage','registration','registrationRevalidation','targetBase','profileBase','surface','tipOffset','previousReport','ledger','defectReport','defectImage')
ATTESTATIONS=('padIdentityReviewed','defectReviewed','boardUnmovedSinceRegistration','bothHeadsClearanceReviewed','clearTransitCorridorReviewed','tipReviewedForCleanup','positiveOnlyTrialReviewed')

def fail(s):raise ValueError(s)

def derive(q,load,now):
 if q.get('schema')!=1 or q.get('scope')!='reviewed-one-pad-cleanup-authoring-inputs':fail('Explicit cleanup authoring scope required')
 stamp=q.get('reviewedMs')
 if type(stamp) is not int or not 0<=now-stamp<=300000:fail('Explicit fresh integer reviewedMs required')
 if not isinstance(q.get('reviewedBy'),str) or not q['reviewedBy'].strip():fail('Explicit reviewer required')
 for k in ('reviewBasis','profileBasis'):
  if not isinstance(q.get(k),str) or len(q[k].strip())<12:fail('Explicit '+k+' required')
 attest=q.get('attestations') or {}
 if any(attest.get(k) is not True for k in ATTESTATIONS):fail('Explicit physical review attestations required')
 src=q.get('sources') or {};docs={k:load(src.get(k),k not in ('stationaryImage','tipImage','defectImage')) for k in SOURCES}
 raw=(docs['barrier'].get('afterQuerySnapshot') or {}).get('raw')
 if not isinstance(q.get('startRaw'),dict) or set(q['startRaw'])!=set('XYZAB') or not all(C.finite(v) for v in q['startRaw'].values()) or q['startRaw']!=raw:fail('Explicit startRaw must equal barrier')
 clear=q.get('xyClearanceRawZ');surface=docs['surface'].get('surface') or {};work=surface.get('rawZ');offset=docs['tipOffset'].get('cameraMinusTipXYMm')
 if not C.finite(clear) or clear!=raw['Z'] or not C.finite(work) or clear>=work:fail('Barrier must already be at explicit cleanup clearance')
 if not isinstance(offset,list) or len(offset)!=2 or not all(C.finite(v) for v in offset):fail('Bound tip offset required')
 amount=q.get('retractDegrees');wait=q.get('dwellMilliseconds')
 if type(amount) is not int or amount not in (6,20) or type(wait) is not int or not 0<=wait<=2000:fail('Explicit positive6|20 and integer dwell0..2000 required')
 padid=q.get('padId');registered={p['padId']:p for p in docs['registration'].get('resistorPadMachineXYTargets',[])}
 if padid not in ('R1.1','R40.1','R16.2') or padid not in registered:fail('Eligible registered defect pad required')
 xy=registered[padid]['machineXYMm'];session={k:docs['template'][k] for k in ('sessionId','jvmStartMs','liveConfigurationSha256')}
 target=copy.deepcopy(docs['targetBase'])
 for k in ('compensatedSequence','inlineConditioning','pairReferences','padAvailabilityImage','padAvailabilityReport','boardCleaned','padsAvailable'):target.pop(k,None)
 target.update(schema=1,scope='ftp-one-pad-cleanup-targets',reviewedBy=q['reviewedBy'],reviewedMs=stamp,**session)
 target.update(boardUnmovedSinceRegistration=attest['boardUnmovedSinceRegistration'],registrationEvidence=copy.deepcopy(src['registration']),registrationRevalidationEvidence=copy.deepcopy(src['registrationRevalidation']),surfaceEvidence=copy.deepcopy(src['surface']),surface=copy.deepcopy(surface),tipOffsetEvidence=copy.deepcopy(src['tipOffset']),cameraMinusTipXYMm=copy.deepcopy(offset),provenance='commissioning-provisional',precisionCalibrated=False,flowCalibrated=False,quantizationMm=.01)
 target['cleanupSequence']={'schema':1,'protocol':'positive-B-aspiration-lift-one-pad','retractDegrees':amount,'dwellMilliseconds':wait}
 target['pads']=[{'padId':padid,'rawPose':{'X':C.q01(xy[0]-offset[0]),'Y':C.q01(xy[1]-offset[1]),'Z':work,'A':raw['A']},'padIdentityReviewed':attest['padIdentityReviewed'],'defectReviewed':attest['defectReviewed'],'defectReportEvidence':copy.deepcopy(src['defectReport']),'defectImageEvidence':copy.deepcopy(src['defectImage']),'defectCapturedMs':q.get('defectCapturedMs')}]
 C.validate_target(target,now,docs['template'])
 C.validate_defect_observation(target['pads'][0],docs['template'],now)
 profile=copy.deepcopy(docs['profileBase']);profile.update(boardId=target['boardId'],rawPose={k:raw[k] for k in 'XYZA'},estimatedGapMm=surface['estimatedGapMm']+(work-clear),gapUncertaintyMm=surface['gapUncertaintyMm'],basis=q['profileBasis'])
 review={'mode':'wet','reviewedBy':q['reviewedBy'],'reviewedMs':stamp,'imageEvidence':copy.deepcopy(src['stationaryImage']),'cleanTipImage':copy.deepcopy(src['tipImage']),'rawZRange':[clear,work],'basis':q['reviewBasis'],'attestations':copy.deepcopy(attest)}
 return review,profile,target

def build(inputs,output):
 ip=Path(inputs).resolve(strict=True);ib=ip.read_bytes();q=json.loads(ib);snapshots={ip:ib};now=int(time.time()*1000)
 def load(e,as_json=True):
  C.checked(e,'authoring source');p=Path(e['path']).resolve(strict=True);b=p.read_bytes()
  if hashlib.sha256(b).hexdigest()!=e['sha256']:fail('Source hash changed: '+str(p))
  snapshots[p]=b
  if not as_json:
   if not (b.startswith(b'\x89PNG\r\n\x1a\n') or b.startswith(b'\xff\xd8\xff')):fail('Image source must be PNG/JPEG')
   if e in [q.get('sources',{}).get(k) for k in ('stationaryImage','tipImage')]:
    captured=p.stat().st_mtime_ns//1000000
    if type(q.get('reviewedMs')) is not int or not 0<=now-captured<=300000 or captured>q['reviewedMs']:fail('Stationary/tip image must be fresh and precede explicit review')
  return json.loads(b) if as_json else b
 review,profile,target=derive(q,load,now)
 out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
 def write(name,v):
  p=out/name;p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n');return p
 review['authoringInputEvidence']=C.evidence(ip);rp=write('clearance-review.json',review);profile['measurementEvidence']=C.evidence(rp);pp=write('profile.json',profile);tp=write('targets.json',target)
 src=q['sources'];cmd=[sys.executable,str(HERE/'prepare-ftp-one-pad-cleanup.py')]
 for k,p in [('template',src['template']['path']),('barrier',src['barrier']['path']),('image',src['stationaryImage']['path']),('profile',pp),('clearance-review',rp),('target-record',tp),('previous-report',src['previousReport']['path']),('ledger',src['ledger']['path']),('output',out/'prepared'),('xy-clearance-raw-z',q['xyClearanceRawZ'])]:cmd.extend(['--'+k,str(p)])
 try:result=subprocess.run(cmd,check=True,text=True,capture_output=True)
 except subprocess.CalledProcessError as exc:fail('Cleanup disabled preparer rejected inputs: '+(exc.stderr or exc.stdout or str(exc)).strip())
 for p,b in snapshots.items():
  if p.read_bytes()!=b:fail('Source changed during preparation: '+str(p))
 print(json.dumps({'output':str(out),'previewRequest':str(out/'prepared/native/preview-request.json'),'enabled':False,'motionDispatched':False,'preparerResult':json.loads(result.stdout)},indent=2))

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inputs',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 try:build(a.inputs,a.output)
 except Exception as exc:p.error(str(exc))
if __name__=='__main__':main()
