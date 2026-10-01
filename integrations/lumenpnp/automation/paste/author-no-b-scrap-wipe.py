#!/usr/bin/env python3
"""Author a reviewed no-B wipe on scrap and prepare a disabled native air request.

This local helper never connects to OpenPnP, writes a motion plan, or dispatches.
"""
import argparse, copy, datetime, hashlib, json, math, subprocess, sys, time
from pathlib import Path
ROOT=Path('/home/lumen/lumenpnp'); HERE=Path(__file__).resolve().parent
PREP=HERE/'prepare-contiguous-batch.py'
REQUIRED_ATTEST=('scrapOnly','bareScrapReviewed','bothHeadsClearanceReviewed','tipAndWipeReviewed','noBNoVacuumOrHoming','noFtpTargets')
SOURCE_KEYS=('template','barrier','image','profileBase','previousReport','ledger')
def fail(s): raise ValueError(s)
def finite(x): return type(x) in (int,float) and math.isfinite(x)
def ev(path):
 p=Path(path).resolve(strict=True);b=p.read_bytes()
 if not b: fail('Empty evidence: '+str(p))
 return {'path':str(p),'sha256':hashlib.sha256(b).hexdigest()}
def load(e,label,json_value=True,snap=None):
 if not isinstance(e,dict) or not isinstance(e.get('path'),str) or not isinstance(e.get('sha256'),str): fail(label+' requires path and SHA-256')
 p=Path(e['path']).resolve(strict=True);b=p.read_bytes()
 if hashlib.sha256(b).hexdigest()!=e['sha256']: fail(label+' SHA-256 mismatch')
 if snap is not None: snap[p]=b
 return (json.loads(b) if json_value else b),p,b
def utc_ms(s,label):
 try:
  v=datetime.datetime.fromisoformat(s.replace('Z','+00:00'))
  if v.tzinfo is None: raise ValueError()
  return round(v.timestamp()*1000)
 except (ValueError,TypeError): fail(label+' must be timezone-aware ISO time')
def chunks(start,end,limit):
 if not finite(start) or not finite(end) or not finite(limit) or limit<=0: fail('Finite route endpoints required')
 d=end-start
 if d==0: return []
 n=math.ceil(abs(d)/limit);return [round(start+d*i/n,2) for i in range(1,n)]+[end]
def build(inputs,output,now=None):
 now=int(time.time()*1000) if now is None else now
 inp=Path(inputs).resolve(strict=True);ib=inp.read_bytes();q=json.loads(ib);snap={inp:ib}
 if q.get('schema')!=1 or q.get('scope')!='reviewed-no-b-scrap-wipe-inputs': fail('Explicit no-B scrap-wipe authoring scope required')
 if any(k in q for k in ('ftpTarget','ftpTargets','targetSurface')): fail('No FTP target or dispensing scope permitted')
 reviewed=q.get('reviewedMs')
 if type(reviewed)is not int or not 0<=now-reviewed<=300000 or not isinstance(q.get('reviewedBy'),str) or not q['reviewedBy'].strip(): fail('Fresh explicit reviewer and integer timestamp required')
 for k in ('reviewBasis','profileBasis'):
  if not isinstance(q.get(k),str) or len(q[k].strip())<12: fail('Explicit '+k+' required')
 attest=q.get('attestations') or {}
 if any(attest.get(k)is not True for k in REQUIRED_ATTEST): fail('Every no-B scrap/wipe safety review must be explicit true')
 src=q.get('sources') or {}
 if set(src)!=set(SOURCE_KEYS): fail('Provide exactly template, barrier, image, profileBase, previousReport and ledger evidence')
 docs={};paths={}
 for k in SOURCE_KEYS:
  docs[k],paths[k],_=load(src[k],k, k!='image',snap)
 image=paths['image'];image_bytes=snap[image];captured=image.stat().st_mtime_ns//1_000_000
 if not (image_bytes.startswith(b'\x89PNG\r\n\x1a\n') or image_bytes.startswith(b'\xff\xd8\xff')) or not 0<=now-captured<=300000 or captured>reviewed: fail('Fresh reviewed top-camera PNG/JPEG must precede review')
 template,barrier=docs['template'],docs['barrier'];raw=(barrier.get('afterQuerySnapshot') or {}).get('raw');poses=(barrier.get('afterQuerySnapshot') or {}).get('nativePoses')
 if barrier.get('status')!='completed-read-only-position-barrier' or barrier.get('controllerPositionVerified') is not True or barrier.get('noMotionCommandSubmitted') is not True or barrier.get('uncertainCompletion') is not False: fail('Successful no-motion position barrier required')
 if utc_ms(barrier.get('finishedAt'), 'Barrier finishedAt')>now or now-utc_ms(barrier.get('finishedAt'),'Barrier finishedAt')>300000: fail('Barrier must be fresh')
 if not isinstance(raw,dict) or set(raw)!=set('XYZAB') or any(not finite(raw[k]) for k in 'XYZAB') or not isinstance(poses,dict) or set(poses)!={'N1','N2','top','bottom'}: fail('Barrier must bind finite five-axis raw position and all four native poses')
 for name in ('N1','N2'):
  if not isinstance(poses[name],dict) or any(not finite(poses[name].get(k)) for k in ('x','y','z')): fail('Barrier must bind finite N1/N2 native poses')
 if barrier.get('request',{}).get('jvmStartMs')!=template.get('jvmStartMs') or barrier.get('liveConfigurationSha256')!=template.get('liveConfigurationSha256'): fail('Barrier/template session and configuration differ')
 if q.get('startRaw')!=raw: fail('Explicit reviewed startRaw must exactly equal the fresh barrier')
 if any(abs(raw[k]*100-round(raw[k]*100))>1e-7 for k in ('X','Y','Z')): fail('Fresh start X/Y/Z must lie on the 0.01 mm reporting grid')
 wipe=q.get('wipe')
 if not isinstance(wipe,dict) or set(wipe)!=set(('axis','deltaMm','workRawZ','clearanceRawZ','estimatedGapMm','gapUncertaintyMm')): fail('Wipe must specify only axis, delta, heights and positive-gap interval')
 axis=wipe['axis'];delta=wipe['deltaMm'];work=wipe['workRawZ'];clear=wipe['clearanceRawZ'];gap=wipe['estimatedGapMm'];unc=wipe['gapUncertaintyMm']
 if axis not in ('X','Y') or not finite(delta) or delta==0 or abs(delta)>2 or abs(delta*100-round(delta*100))>1e-7: fail('Wipe must be one nonzero X/Y move of at most 2 mm on the 0.01 mm grid')
 if not all(finite(v) for v in (work,clear)) or raw['Z']!=clear or not 0<work-clear<=5 or abs(work*100-round(work*100))>1e-7 or abs(clear*100-round(clear*100))>1e-7: fail('Work Z must be above the fresh start/clearance and within one 5 mm Z move')
 if not finite(gap) or not finite(unc) or gap<=0 or unc<0 or gap-unc<.1: fail('Reviewed no-B wipe gap lower bound must be at least 0.1 mm')
 prof=docs['profileBase']
 session={k:template[k] for k in ('sessionId','jvmStartMs','liveConfigurationSha256')}
 if any(prof.get(k)!=v for k,v in session.items()) or prof.get('provenance')!='commissioning-provisional' or prof.get('precisionCalibrated') is not False or prof.get('flowCalibrated') is not False: fail('Profile base must be same-session, provisional and uncalibrated')
 profile=copy.deepcopy(prof);profile.update(session,rawPose={k:raw[k] for k in 'XYZA'},estimatedGapMm=gap+(work-clear),gapUncertaintyMm=unc,basis=q['profileBasis'])
 out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
 def write(name,v): p=out/name;p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n');return p
 review={'mode':'air','reviewedBy':q['reviewedBy'],'reviewedMs':reviewed,'imageEvidence':ev(image),'rawZRange':[min(clear,work),max(clear,work)],'basis':q['reviewBasis'],'attestations':copy.deepcopy(attest)}
 rp=write('clearance-review.json',review);profile['measurementEvidence']=ev(rp);pp=write('profile.json',profile)
 route=[dict(raw)];steps=[];at=dict(raw)
 for z in chunks(clear,work,5):
  steps.append({'axis':'Z','target':z});at=dict(at,Z=z);route.append(at)
 xy=round(at[axis]+delta,2)
 if abs(xy-at[axis])>10: fail('Wipe move exceeds existing native XY stage bound')
 to=dict(at);to[axis]=xy;steps.append({'axis':axis,'target':xy,'wipeReview':True,'estimatedGapMm':gap,'gapUncertaintyMm':unc,'wipeReviewEvidence':ev(rp)});at=to;route.append(at)
 for z in chunks(work,clear,5):
  steps.append({'axis':'Z','target':z});at=dict(at,Z=z);route.append(at)
 if any(s['axis']=='B' for s in steps) or steps[-1]['axis']!='Z' or steps[-2]['axis']!=axis: fail('Route must be one no-B reviewed wipe followed immediately by clearance lift')
 bounds={k:{'min':min(p[k] for p in route),'max':max(p[k] for p in route)} for k in ('X','Y','Z','B')};heads={}
 for name in ('N1','N2'):
  limits={}
  for a in 'XYZ':
   sign=-1 if a=='Z' and name=='N2' else 1;v=[poses[name][a.lower()]+sign*(p[a]-raw[a]) for p in route];limits['min'+a]=min(v)-.001;limits['max'+a]=max(v)+.001
  heads[name]=limits
 recipe={'mode':'air','stages':steps,'rawBounds':bounds,'headClearanceBounds':heads,'xyClearanceRawZ':clear,'clearanceReviewEvidence':ev(rp),'profileEvidence':ev(pp),'previousReportEvidence':ev(paths['previousReport']),'previousLedgerPath':str(paths['ledger'])}
 rec=write('recipe.json',recipe);prepared=out/'prepared'
 cmd=[sys.executable,str(PREP),'prepare','--template',str(paths['template']),'--barrier',str(paths['barrier']),'--image',str(image),'--recipe',str(rec),'--output',str(prepared)]
 try:result=subprocess.run(cmd,cwd=ROOT,check=True,text=True,capture_output=True)
 except subprocess.CalledProcessError as exc: fail('Existing disabled native air preparer rejected wipe: '+(exc.stderr or exc.stdout or str(exc)).strip())
 for p,b in snap.items():
  if p.read_bytes()!=b: fail('Input source changed during no-B preparation: '+str(p))
 print(json.dumps({'output':str(out),'previewRequest':str(prepared/'preview-request.json'),'mode':'air','stages':steps,'BUnchanged':raw['B']==at['B'],'enabled':False,'motionDispatched':False,'preparerResult':result.stdout.strip()},indent=2))
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inputs',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 try:build(a.inputs,a.output)
 except Exception as exc:p.error(str(exc))
if __name__=='__main__':main()
