#!/usr/bin/env python3
"""Author hash-bound eight-pad inputs offline, then run the disabled recipe preparer."""
import argparse, copy, datetime, hashlib, importlib.util, json, math, subprocess, sys, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('eight_preparer',HERE/'prepare-conditioned-ftp-eight-pad.py')
EIGHT=importlib.util.module_from_spec(spec);spec.loader.exec_module(EIGHT)
SOURCE_KEYS=('template','barrier','stationaryImage','tipImage','registration','registrationRevalidation','targetBase','scrapExperiment','scrapProfile','surface','tipOffset','previousReport','ledger')
ATTESTATIONS=('boardCleaned','padsAvailable','boardUnmovedSinceRegistration','bothHeadsClearanceReviewed','clearTransitCorridorReviewed','scrapPrimeAndWipeReviewed','tipReviewedNoLongStrand')

def fail(s):raise ValueError(s)
def finite(x):return type(x) in (int,float) and math.isfinite(x)
def text(x,label):
 if not isinstance(x,str) or len(x.strip())<12:fail(label+' must contain explicit review text')
 return x

def derive(q,load,now):
 """Pure authoring. load verifies evidence bytes; no observations are synthesized."""
 if q.get('schema')!=1 or q.get('scope')!='reviewed-eight-pad-authoring-inputs':fail('Explicit reviewed authoring scope required')
 stamp=q.get('reviewedMs')
 if type(stamp) is not int or not 0<=now-stamp<=300000:fail('Authored reviewedMs must be within five minutes')
 if not isinstance(q.get('reviewedBy'),str) or not q['reviewedBy'].strip():fail('Explicit reviewedBy required')
 text(q.get('reviewBasis'),'reviewBasis');text(q.get('profileBasis'),'profileBasis')
 attest=q.get('attestations') or {}
 if any(attest.get(k) is not True for k in ATTESTATIONS):fail('Every physical attestation must be explicitly true')
 src=q.get('sources') or {};docs={k:load(src.get(k),k not in ('stationaryImage','tipImage')) for k in SOURCE_KEYS}
 template,barrier=docs['template'],docs['barrier'];raw=(barrier.get('afterQuerySnapshot') or {}).get('raw')
 if not isinstance(q.get('startRaw'),dict) or set(q['startRaw'])!=set('XYZAB') or not all(finite(v) for v in q['startRaw'].values()) or q['startRaw']!=raw:fail('Explicit startRaw must equal supplied barrier')
 session={k:template[k] for k in ('sessionId','jvmStartMs','liveConfigurationSha256')}
 if q.get('doseDegrees') not in (4,6,12,20) or type(q['doseDegrees']) is not int:fail('Dose must be integer4,6,12 or20')
 dwell=q.get('dwellMilliseconds',200)
 if type(dwell) is not int or dwell not in (200,1000,2000):fail('Forward dwell must be integer200,1000 or2000 ms')
 conditioning=q.get('conditioningDoseDegrees',20)
 if type(conditioning) is not int or conditioning not in (6,12,20):fail('Conditioning dose must be integer6,12 or20 degrees')
 retract=q.get('retractDegrees',2)
 if type(retract) is not int or retract not in (2,3):fail('Retraction must be integer2 or3 degrees')
 final_wipe=q.get('conditioningFinalWipeMm',0)
 if type(final_wipe) not in (int,float) or final_wipe not in (0,1.5):fail('Final conditioning wipe must be0 or+X1.5 mm')
 if final_wipe and (conditioning!=6 or retract!=3 or attest.get('conditioningFinalWipeReviewed') is not True):fail('Final wipe requires conditioner6/R3 and explicit complete-path review')
 restore=q.get('conditioningRestoreDegrees',0)
 if type(restore) is not int or restore not in (0,3) or restore and (conditioning!=12 or retract!=3 or final_wipe):fail('Conditioning restore3 requires conditioner12/R3 and no final wipe')
 clear=q.get('xyClearanceRawZ');work=q.get('surfaceRawZ')
 if not finite(clear) or not finite(work) or clear>=work:fail('Explicit work/clearance Z required')
 surface=docs['surface'].get('surface');offset=docs['tipOffset'].get('cameraMinusTipXYMm')
 if not surface or surface.get('rawZ')!=work:fail('Selected surface Z must equal immutable surface evidence')
 if not isinstance(offset,list) or len(offset)!=2 or not all(finite(v) for v in offset):fail('Immutable selected tip offset required')
 exp=copy.deepcopy(docs['scrapExperiment']);exp.update(startRaw=copy.deepcopy(raw),doseDegrees=q['doseDegrees'],retractDegrees=retract,conditioningDoseDegrees=conditioning,conditioningRestoreDegrees=restore,conditioningFinalWipeMm=final_wipe,targetsXY=copy.deepcopy(q.get('scrapTargetsXY')))
 if exp.get('mode')!='transfer-preparation' or exp.get('workRawZ')!=raw['Z'] or not isinstance(exp['targetsXY'],list) or len(exp['targetsXY'])!=2:fail('Explicit transfer-preparation experiment and two scrap XY targets required')
 if final_wipe:exp['conditioningFinalWipeReviewed']=attest['conditioningFinalWipeReviewed']
 else:exp.pop('conditioningFinalWipeReviewed',None)
 # Full emitted prefix is checked by the existing preparer; retain its authored amounts and waits.
 target=copy.deepcopy(docs['targetBase']);target.update(schema=1,scope='ftp-eight-pad-commissioning-targets',reviewedBy=q['reviewedBy'],reviewedMs=stamp,**session)
 for k in ('boardCleaned','padsAvailable','boardUnmovedSinceRegistration'):target[k]=attest[k]
 target.update(registrationEvidence=copy.deepcopy(src['registration']),registrationRevalidationEvidence=copy.deepcopy(src['registrationRevalidation']),surfaceEvidence=copy.deepcopy(src['surface']),surface=copy.deepcopy(surface),tipOffsetEvidence=copy.deepcopy(src['tipOffset']),cameraMinusTipXYMm=copy.deepcopy(offset),provenance='commissioning-provisional',precisionCalibrated=False,flowCalibrated=False,quantizationMm=.01)
 target['compensatedSequence']={'schema':1,'protocol':'restore-dose-retract-lift-eight-pad','doseDegrees':q['doseDegrees'],'retractDegrees':retract,'dwellMilliseconds':dwell,'retractDwellMilliseconds':500,'idleReliefDegrees':40}
 pairs=q.get('pairReviews');registered={p['padId']:p for p in docs['registration'].get('resistorPadMachineXYTargets',[])}
 if not isinstance(pairs,list) or len(pairs)!=4:fail('Four explicit pair reviews required')
 target['pairReferences']=[];target['pads']=[]
 for pair in pairs:
  ref=pair.get('reference');ids=pair.get('padIds')
  if not isinstance(ref,str) or ref not in {f'R{i}' for i in range(1,41)} or not isinstance(ids,list) or sorted(ids)!=[ref+'.1',ref+'.2'] or ref in target['pairReferences']:fail('Four unique complete ordered resistor pairs required')
  if pair.get('padIdentityReviewed') is not True or pair.get('padsAvailableReviewed') is not True:fail('Explicit per-pair identity and availability review required')
  report=load(pair.get('reportEvidence'),True);load(pair.get('imageEvidence'),False)
  capture=pair.get('capturedMs')
  if type(capture) is not int or not 0<=now-capture<=300000 or capture>stamp:fail('Pair capture must precede review and remain fresh')
  try:actual=round(datetime.datetime.fromisoformat(report['finishedAt'].replace('Z','+00:00')).timestamp()*1000)
  except (KeyError,ValueError,TypeError):fail('Pair report has no valid finish time')
  if capture!=actual:fail('Pair capturedMs must equal immutable camera report finish time')
  target['pairReferences'].append(ref)
  for padid in ids:
   if padid not in registered:fail('Pad absent from supplied registration')
   xy=registered[padid]['machineXYMm']
   target['pads'].append({'padId':padid,'rawPose':{'X':EIGHT.COMP.q01(xy[0]-offset[0]),'Y':EIGHT.COMP.q01(xy[1]-offset[1]),'Z':work,'A':raw['A']},'padIdentityReviewed':pair['padIdentityReviewed'],'padAvailableReviewed':pair['padsAvailableReviewed'],'availabilityImageEvidence':copy.deepcopy(pair['imageEvidence']),'availabilityReportEvidence':copy.deepcopy(pair['reportEvidence']),'availabilityCapturedMs':capture})
 target['padAvailabilityImage']=copy.deepcopy(pairs[0]['imageEvidence']);target['padAvailabilityReport']=copy.deepcopy(pairs[0]['reportEvidence']);target['authoringReviewBasis']=q['reviewBasis']
 EIGHT.validate_eight(target)
 profile=copy.deepcopy(docs['scrapProfile']);profile.update(rawPose={k:raw[k] for k in 'XYZA'},basis=q['profileBasis'])
 review={'mode':'wet','reviewedBy':q['reviewedBy'],'reviewedMs':stamp,'imageEvidence':copy.deepcopy(src['stationaryImage']),'cleanTipImage':copy.deepcopy(src['tipImage']),'rawZRange':[min(clear,exp['clearanceRawZ']),max(work,exp['workRawZ'])],'basis':q['reviewBasis'],'attestations':copy.deepcopy(attest)}
 return exp,review,profile,target

def build(inputs,output):
 ip=Path(inputs).resolve(strict=True);ib=ip.read_bytes();q=json.loads(ib);snapshots={ip:ib};now=int(time.time()*1000)
 def load(e,json_value=True):
  EIGHT.PREP.WIPE.checked_evidence(e,'authoring source')
  p=Path(e['path']).resolve(strict=True);b=p.read_bytes()
  if hashlib.sha256(b).hexdigest()!=e['sha256']:fail('Source hash changed: '+str(p))
  snapshots[p]=b
  if not json_value and e in [q.get('sources',{}).get(k) for k in ('stationaryImage','tipImage')]:
   if not (b.startswith(b'\x89PNG\r\n\x1a\n') or b.startswith(b'\xff\xd8\xff')):fail('Stationary/tip evidence must be PNG or JPEG')
   capture=p.stat().st_mtime_ns//1000000
   if not 0<=now-capture<=300000 or capture>q['reviewedMs']:fail('Stationary/tip image must be fresh and precede explicit review')
  return json.loads(b) if json_value else b
 exp,review,profile,target=derive(q,load,now)
 out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
 def write(name,v):
  p=out/name;p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n');return p
 ep=write('experiment.json',exp);review['experimentEvidence']=EIGHT.ev(ep);review['authoringInputEvidence']=EIGHT.ev(ip);rp=write('clearance-review.json',review)
 profile['measurementEvidence']=EIGHT.ev(rp);pp=write('profile.json',profile);tp=write('targets.json',target)
 src=q['sources'];cmd=[sys.executable,str(HERE/'prepare-conditioned-ftp-eight-pad.py')]
 for k,p in [('experiment',ep),('template',src['template']['path']),('barrier',src['barrier']['path']),('profile',pp),('clearance-review',rp),('image',src['stationaryImage']['path']),('target-record',tp),('previous-report',src['previousReport']['path']),('ledger',src['ledger']['path']),('output',out/'prepared'),('xy-clearance-raw-z',q['xyClearanceRawZ'])]:cmd.extend(['--'+k,str(p)])
 try:result=subprocess.run(cmd,check=True,text=True,capture_output=True)
 except subprocess.CalledProcessError as exc:fail('Eight-pad offline preparer rejected inputs: '+(exc.stderr or exc.stdout or str(exc)).strip())
 for p,b in snapshots.items():
  if p.read_bytes()!=b:fail('Input evidence changed during preparation: '+str(p))
 print(json.dumps({'output':str(out),'previewRequest':str(out/'prepared/native/preview-request.json'),'enabled':False,'motionDispatched':False,'preparerResult':json.loads(result.stdout)},indent=2))

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inputs',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 try:build(a.inputs,a.output)
 except Exception as exc:p.error(str(exc))
if __name__=='__main__':main()
