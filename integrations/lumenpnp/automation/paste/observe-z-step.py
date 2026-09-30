#!/usr/bin/env python3
"""Prepare/execute one explicitly reviewed Z step via existing native owner."""
import argparse, datetime, hashlib, json, re, subprocess, time, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def read(p): return json.loads(Path(p).read_text())
def evidence(p):
 p=Path(p).resolve(); return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def save(p,q): p.write_text(json.dumps(q,indent=2)+'\n')
def measured_firmware_step(path,jvm,config):
 r=read(path);q=r.get('request',{})
 if r.get('status')!='completed-Z-observation-awaiting-image-review' or r.get('uncertainCompletion') is not False or r.get('motionSubmitted') is not True or r.get('nativeMotionCompletionReported') is not True or r.get('controllerPositionVerified') is not True or r.get('independentFirmwareStepVerified') is not True or q.get('schema')!=2 or q.get('scope')!='bounded-signed-raw-Z-observation' or q.get('axis')!='Z' or q.get('jvmStartMs')!=jvm or q.get('liveConfigurationSha256')!=config or q.get('deltaMm') not in [-5,-1,-.5,-.25,-.1,.1,.25,.5,1,5] or r.get('commandedControllerAxes')!=['Z']:
  raise ValueError('Hash-bound completed same-JVM/config one-axis Z observation required')
 try: finished=datetime.datetime.fromisoformat(r['finishedAt'].replace('Z','+00:00')).timestamp()
 except (KeyError,ValueError,TypeError): raise ValueError('Completed Z evidence timestamp required')
 if finished>time.time() or time.time()-finished>86400: raise ValueError('Completed Z count evidence is stale')
 def count(responses):
  found=[]
  for line in responses:
   m=re.fullmatch(r'.*X:-?\d+\.\d+\s*Y:-?\d+\.\d+\s*Z:-?\d+\.\d+\s*A:-?\d+\.\d+\s*B:-?\d+\.\d+\s+Count X:(-?\d+) Y:(-?\d+) Z:(-?\d+) A:(-?\d+) B:(-?\d+)\s*',str(line))
   if m: found.append(dict(zip(('X','Y','Z','A','B'),map(int,m.groups()))))
  if len(found)!=1: raise ValueError('Exactly one full five-axis M114 count required')
  return found[0]
 before=count(r.get('before',{}).get('responses',[]));after=count(r.get('after',{}).get('responses',[]));delta=q['deltaMm']*40
 if abs(delta-round(delta))>1e-9 or after['Z']-before['Z']!=round(delta) or any(after[a]!=before[a] for a in ('X','Y','A','B')):
  raise ValueError('Firmware counts do not prove exact Z-only 40-steps/mm displacement')
 start=r.get('before',{}).get('reported',{});end=r.get('after',{}).get('reported',{});snap=r.get('afterQuerySnapshot',{}).get('raw',{})
 if not start or not end or any(abs(end[a]-(start[a]+(q['deltaMm'] if a=='Z' else 0)))>0.02 for a in ('X','Y','Z','A','B')) or any(abs(snap[a]-end[a])>0.02 for a in ('X','Y','Z','A','B')):
  raise ValueError('Reported before/after pose disagrees with firmware count evidence')
 return r
def dispatch(action,report):
 subprocess.run(['python3',str(ROOT/'automation/scripts/run_reviewed_action.py'),action,'--confirmed'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
 end=time.monotonic()+60
 while time.monotonic()<end:
  if report.exists():
   try: d=read(report)
   except json.JSONDecodeError:
    time.sleep(.1);continue
   if d.get('error') or d.get('status','').startswith('failed'): raise RuntimeError(str(report)+' '+str(d.get('error')))
   if d.get('status','').startswith('completed-'): return d
  time.sleep(.1)
 raise TimeoutError('No verified terminal; do not replay: '+str(report))
def main():
 a=argparse.ArgumentParser(description=__doc__);a.add_argument('source',type=Path);a.add_argument('image',type=Path);a.add_argument('--delta',type=float,choices=[-5,-1,-.5,-.25,-.1,.1,.25,.5,1,5],required=True);a.add_argument('--firmware-evidence',type=Path,help='Hash-bound completed same-JVM Z observation with verified M114 counts; required for |delta| < 1 mm');a.add_argument('--review',required=True);a.add_argument('--execute',action='store_true');x=a.parse_args()
 fine=abs(x.delta)<1
 if fine and x.firmware_evidence is None: raise ValueError('--firmware-evidence is required for fine Z steps')
 if not fine and x.firmware_evidence is not None: raise ValueError('--firmware-evidence is only used for fine Z steps')
 s=read(x.source)
 if s.get('error') or s.get('uncertainCompletion') is not False or not s.get('controllerPositionVerified') or not s.get('status','').startswith('completed-'): raise ValueError('Verified terminal source required')
 if time.time()-x.image.stat().st_mtime>300: raise ValueError('Fresh reviewed image required')
 snap=s['afterQuerySnapshot'];q=read(ROOT/'automation/plans/paste-position-barrier-request.json');q.update(id=str(uuid.uuid4()),createdMs=int(time.time()*1000),expectedRaw=snap['raw'],expectedDriver=snap['driver'],expectedNativePoses=snap['nativePoses'],operator=x.review)
 config=s.get('liveConfigurationSha256',s['request']['liveConfigurationSha256'])
 if config!=q['liveConfigurationSha256'] or s['request']['jvmStartMs']!=q['jvmStartMs']: raise ValueError('Source differs from current reviewed barrier session')
 if fine: measured_firmware_step(x.firmware_evidence,q['jvmStartMs'],config)
 z=read(ROOT/'automation/paste/z-observation.pending.json');z.update(schema=2,id=str(uuid.uuid4()),createdMs=int(time.time()*1000),jvmStartMs=q['jvmStartMs'],operator=x.review,liveConfigurationSha256=config,speedFraction=1.0,speedOverPrecision=True,motionAreaClear=True,noHeldPartsObserved=True,expectedRaw=snap['raw'],expectedDriver=snap['driver'],expectedNativePoses=snap['nativePoses'],axis='Z',deltaMm=x.delta,jointInterval={'minRawZ':min(snap['raw']['Z'],snap['raw']['Z']+x.delta),'maxRawZ':max(snap['raw']['Z'],snap['raw']['Z']+x.delta),'reviewedForCurrentPose':True,'reviewRecord':x.review},operatorVerifiedJointZStep=True,bothHeadsClearAlongStep=True,corridorEvidence={**evidence(x.image),'capturedMs':int(x.image.stat().st_mtime*1000)},nativeZConfiguration=read(ROOT/'automation/plans/paste-z-observation-request.json')['nativeZConfiguration'])
 if fine: z.update(reviewedFineZStep=True,reviewedFirmwareZStepsPerMm=40,firmwareStepEvidence=evidence(x.firmware_evidence))
 if not x.execute: print(json.dumps({'barrier':q,'zStep':z,'dispatchPerformed':False},indent=2));return
 save(ROOT/'automation/plans/paste-position-barrier-request.json',q);bp=ROOT/f"automation/evidence/paste-position-barrier-{q['id']}/report.json";b=dispatch('paste-position-barrier',bp)
 z.update(createdMs=int(time.time()*1000),expectedRaw=b['afterQuerySnapshot']['raw'],expectedDriver=b['afterQuerySnapshot']['driver'],expectedNativePoses=b['afterQuerySnapshot']['nativePoses'],barrierEvidence=evidence(bp));save(ROOT/'automation/plans/paste-z-observation-request.json',z);zp=ROOT/f"automation/evidence/paste-z-observation-{z['id']}/report.json";dispatch('paste-z-observe',zp);print(json.dumps({'report':str(zp)}))
if __name__=='__main__': main()
