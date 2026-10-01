#!/usr/bin/env python3
"""Prepare one registered FTP defect-pad aspiration/lift recipe offline; never dispatches."""
import argparse,copy,datetime,hashlib,importlib.util,json,math,subprocess,sys,time
from pathlib import Path
ROOT=Path('/home/lumen/lumenpnp');HERE=Path(__file__).resolve().parent;GENERIC=HERE/'prepare-contiguous-batch.py'
spec=importlib.util.spec_from_file_location('ftp_compensated_builder',HERE/'prepare-compensated-ftp-pair.py');COMP=importlib.util.module_from_spec(spec);spec.loader.exec_module(COMP)

def fail(s):raise ValueError(s)
def finite(v):return type(v) in (int,float) and math.isfinite(v)
def evidence(path):return COMP.evidence(path)
def checked(e,label):return COMP.require_evidence(e,label)
def read(path):return COMP.read(path)
def q01(v):return COMP.q01(v)

def validate_target(t,now,template):
 if t.get('schema')!=1 or t.get('scope')!='ftp-one-pad-cleanup-targets' or 'compensatedSequence' in t or 'inlineConditioning' in t:fail('Explicit one-pad cleanup target without compensated/conditioning scope required')
 if t.get('sessionId')!=template.get('sessionId') or t.get('jvmStartMs')!=template.get('jvmStartMs') or t.get('liveConfigurationSha256')!=template.get('liveConfigurationSha256'):fail('Target session/configuration mismatch')
 if not isinstance(t.get('boardId'),str) or not t['boardId'].strip() or t.get('quantizationMm')!=0.01:fail('Explicit board ID and 0.01-mm quantization required')
 if not isinstance(t.get('reviewedBy'),str) or not t['reviewedBy'].strip() or type(t.get('reviewedMs')) is not int or not 0<=now-t['reviewedMs']<=300000:fail('Fresh authored cleanup review required')
 if t.get('boardUnmovedSinceRegistration') is not True or t.get('provenance')!='commissioning-provisional' or t.get('precisionCalibrated') is not False or t.get('flowCalibrated') is not False:fail('Explicit unmoved and provisional board status required')
 c=t.get('cleanupSequence') or {}
 if c.get('schema')!=1 or c.get('protocol')!='positive-B-aspiration-lift-one-pad' or c.get('retractDegrees') not in (6,20) or type(c.get('dwellMilliseconds')) is not int or not 0<=c['dwellMilliseconds']<=2000:fail('Cleanup sequence must be positive B6|20 with authored integer dwell 0..2000')
 pads=t.get('pads');
 if not isinstance(pads,list) or len(pads)!=1:fail('Exactly one reviewed defect pad required')
 p=pads[0]
 if p.get('padId') not in ('R1.1','R40.1') or p.get('padIdentityReviewed') is not True or p.get('defectReviewed') is not True:fail('Only reviewed R1.1 or R40.1 identity/defect can be selected')
 for k in ('defectReportEvidence','defectImageEvidence'):checked(p.get(k),k)
 if type(p.get('defectCapturedMs')) is not int or not 0<=now-p['defectCapturedMs']<=300000 or p['defectCapturedMs']>t['reviewedMs']:fail('Fresh defect observation before target review required')
 for k in ('cadEvidence','registrationEvidence','registrationRevalidationEvidence','tipOffsetEvidence','surfaceEvidence'):checked(t.get(k),k)
 checks=t.get('padChecks')
 if not isinstance(checks,list) or len(checks)!=3 or sorted(c.get('reference') for c in checks)!=['R1','R16','R40']:fail('Preserve the three accepted distant-pad held-out checks')
 for check in checks:
  if check.get('reviewedAligned') is not True:fail('Each held-out pad check must remain explicitly reviewed')
  checked(check.get('reportEvidence'),'held-out pad report');checked(check.get('imageEvidence'),'held-out pad image')
 s=t.get('surface') or {};z=s.get('rawZ');gap=s.get('estimatedGapMm');unc=s.get('gapUncertaintyMm')
 if not all(finite(v) for v in (z,gap,unc)) or gap<=0 or unc<0 or gap-unc<0.1:fail('Reviewed board surface and positive gap lower bound required')
 offset=t.get('cameraMinusTipXYMm')
 if not isinstance(offset,list) or len(offset)!=2 or not all(finite(v) for v in offset):fail('Explicit selected camera-minus-tip offset required')
 return p,c,s,offset

def validate_defect_observation(p,template,now):
 ev=p['defectReportEvidence'];report,_,_=read(ev['path']);ms=round(datetime.datetime.fromisoformat(report['finishedAt'].replace('Z','+00:00')).timestamp()*1000)
 if ms!=p['defectCapturedMs'] or not 0<=now-ms<=300000:fail('Defect report finish time must match fresh authored capture time')
 if report.get('status') not in ('completed-camera-survey-awaiting-image-review','completed-contiguous-air-batch-awaiting-observation') or report.get('controllerPositionVerified') is not True or report.get('uncertainCompletion') is not False:fail('Verified camera survey/air report required for defect observation')
 req=report.get('request') or {}
 if req.get('jvmStartMs')!=template.get('jvmStartMs') or req.get('liveConfigurationSha256')!=template.get('liveConfigurationSha256'):fail('Defect report session/config mismatch')
 im=p['defectImageEvidence'];impath=Path(im['path']).resolve(strict=True);top=(report.get('afterImages') or {}).get('top')
 if not top or impath!=Path(ev['path']).resolve().parent.joinpath(top.get('path','')).resolve():fail('Defect image must be this report top-after image')
 if evidence(impath)!=im:fail('Defect image hash mismatch')
 return report

def build_route(raw,poses,t,clearance):
 p,c,s,offset=t['pads'][0],t['cleanupSequence'],t['surface'],t['cameraMinusTipXYMm']
 work=s['rawZ'];gap=s['estimatedGapMm'];unc=s['gapUncertaintyMm']
 if not finite(clearance) or raw['Z']!=clearance or clearance>=work:fail('Fresh barrier must already be at reviewed XY clearance below work Z')
 if work-clearance>5.0:fail('Reviewed immediate work-to-clearance lift exceeds 5 mm')
 reg,_,_=read(t['registrationEvidence']['path']);entry={v['padId']:v for v in reg.get('resistorPadMachineXYTargets',[])}.get(p['padId'])
 if not entry:fail('Selected target absent from accepted registration')
 pose=p.get('rawPose') or {};expected=[q01(entry['machineXYMm'][i]-offset[i]) for i in range(2)]
 if [pose.get('X'),pose.get('Y')]!=expected or pose.get('Z')!=work or pose.get('A')!=raw['A']:fail('Cleanup pose must equal registered-minus-tip coordinates, surface Z and barrier A')
 stages=[];at=dict(raw);states=[dict(at)]
 def append(axis,value,**meta):
  nonlocal at
  if not finite(value):fail('Non-finite route endpoint')
  if at[axis]==value:return None
  nxt=dict(at);nxt[axis]=value;stages.append({'axis':axis,'target':value,**meta});at=nxt;states.append(dict(at));return len(stages)-1
 def move(axis,value,limit):
  if abs(value-q01(value))>1e-9:fail('Movement endpoint must be on the 0.01-mm grid')
  start=at[axis];n=max(1,math.ceil(abs(value-start)/limit))
  while True:
   vals=[q01(start+(value-start)*i/n) for i in range(1,n)]+[value]
   if all(abs(b-a)<=limit+1e-9 for a,b in zip([start]+vals[:-1],vals)):break
   n+=1
  for v in vals:
   if axis in ('X','Y') and at['Z']!=clearance:fail('XY must remain at reviewed clearance')
   append(axis,v)
 move('X',pose['X'],9.9);move('Y',pose['Y'],9.9);move('Z',work,5.0)
 if at['Z']!=work:fail('Route failed to approach exact reviewed work plane')
 asp=append('B',at['B']+c['retractDegrees'],gapEvidence=t['surfaceEvidence'],estimatedGapMm=gap,gapUncertaintyMm=unc,dwellMilliseconds=c['dwellMilliseconds'])
 lift=append('Z',clearance)
 if asp is None or lift!=asp+1 or len(stages)!=lift+1:fail('Exactly one positive-B stage immediately followed by final lift required')
 if len(stages)>40:fail('One-pad cleanup route exceeds native 40-stage limit')
 out=copy.deepcopy(t);out['pads'][0]['aspirationStageIndex']=asp;out['pads'][0]['liftStageIndex']=lift
 bounds={a:{'min':min(v[a] for v in states),'max':max(v[a] for v in states)} for a in ('X','Y','Z','B')};heads={}
 for name in ('N1','N2'):
  lim={}
  for a in 'XYZ':
   sign=-1 if name=='N2' and a=='Z' else 1;vals=[poses[name][a.lower()]+sign*(v[a]-raw[a]) for v in states];lim['min'+a]=min(vals)-.001;lim['max'+a]=max(vals)+.001
  heads[name]=lim
 gross=sum(abs(b['target']-a['B']) if b['axis']=='B' else 0 for a,b in zip(states,stages))
 return out,stages,bounds,heads,{'initialB':raw['B'],'finalB':at['B'],'grossChargedDegrees':gross,'netDegrees':at['B']-raw['B']}

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('template','barrier','image','profile','clearance-review','target-record','previous-report','ledger','output'):p.add_argument('--'+name,required=True)
 p.add_argument('--xy-clearance-raw-z',required=True,type=float);a=p.parse_args();now=int(time.time()*1000)
 template,tp,tb=read(a.template);barrier,bp,bb=read(a.barrier);target,sp,sb=read(a.target_record);profile,pp,pb=read(a.profile);review,rp,rb=read(a.clearance_review);prev,prp,prb=read(a.previous_report);ledger,lp,lb=read(a.ledger);image=Path(a.image).resolve(strict=True);ib=image.read_bytes();im_ev=evidence(image);captured=image.stat().st_mtime_ns//1000000
 if not (ib.startswith(b'\x89PNG\r\n\x1a\n') or ib.startswith(b'\xff\xd8\xff')) or not 0<=now-captured<=300000:fail('Fresh reviewed image required')
 if barrier.get('status')!='completed-read-only-position-barrier' or barrier.get('controllerPositionVerified') is not True or barrier.get('noMotionCommandSubmitted') is not True or barrier.get('uncertainCompletion') is not False:fail('Successful read-only barrier required')
 barrier_ms=round(datetime.datetime.fromisoformat(barrier['finishedAt'].replace('Z','+00:00')).timestamp()*1000)
 if not 0<=now-barrier_ms<=300000:fail('Fresh barrier required')
 req=barrier.get('request') or {};snap=barrier.get('afterQuerySnapshot') or {};raw=snap.get('raw');driver=snap.get('driver');poses=snap.get('nativePoses')
 if req.get('jvmStartMs')!=template.get('jvmStartMs') or barrier.get('liveConfigurationSha256')!=template.get('liveConfigurationSha256') or not isinstance(raw,dict) or set(raw)!=set('XYZAB') or not isinstance(driver,dict) or set(driver)!=set(raw) or not isinstance(poses,dict) or set(poses)!={'N1','N2','top','bottom'}:fail('Barrier/template session mismatch or incomplete snapshot')
 ptarget,c,s,offset=validate_target(target,now,template);validate_defect_observation(ptarget,template,now)
 bound_sources=[]
 def bind_snapshot(item):
  path=Path(item['path']).resolve(strict=True);data=path.read_bytes()
  if hashlib.sha256(data).hexdigest()!=item['sha256']:fail('Target evidence hash changed before preparation: '+str(path))
  bound_sources.append((path,data,item['sha256']))
 for item in [target[k] for k in ('cadEvidence','registrationEvidence','registrationRevalidationEvidence','tipOffsetEvidence','surfaceEvidence')]+[ptarget[k] for k in ('defectReportEvidence','defectImageEvidence')]:bind_snapshot(item)
 for check in target['padChecks']:
  for item in (check['reportEvidence'],check['imageEvidence']):bind_snapshot(item)
 if target.get('boardId')!=profile.get('boardId') or profile.get('sessionId')!=template.get('sessionId') or profile.get('jvmStartMs')!=template.get('jvmStartMs') or profile.get('liveConfigurationSha256')!=template.get('liveConfigurationSha256') or profile.get('provenance')!='commissioning-provisional' or profile.get('precisionCalibrated') is not False or profile.get('flowCalibrated') is not False:fail('Provisional profile identity mismatch')
 for axy in 'XYZA':
  if not finite(profile.get('rawPose',{}).get(axy)) or abs(profile['rawPose'][axy]-raw[axy])>1e-4:fail('Profile must match barrier '+axy)
 if review.get('mode')!='wet' or not isinstance(review.get('reviewedBy'),str) or not review['reviewedBy'].strip() or review.get('imageEvidence')!=im_ev:fail('Complete wet clearance review must bind exact image')
 if type(review.get('reviewedMs')) is not int or not captured<=review['reviewedMs']<=now or now-review['reviewedMs']>300000 or review.get('rawZRange')!=[min(a.xy_clearance_raw_z,s['rawZ']),max(a.xy_clearance_raw_z,s['rawZ'])]:fail('Clearance review time/Z range must match route')
 if type(target.get('reviewedMs')) is not int or not ptarget['defectCapturedMs']<=target['reviewedMs']<=now:fail('Target review must follow defect observation')
 out,stages,bounds,heads,acct=build_route(raw,poses,target,a.xy_clearance_raw_z)
 # Verify original registration, revalidation and all explicit target evidence before emitting a copy.
 for k in ('cadEvidence','registrationEvidence','registrationRevalidationEvidence','tipOffsetEvidence','surfaceEvidence'):checked(target.get(k),k)
 for path,data,label in ((tp,tb,'template'),(bp,bb,'barrier'),(sp,sb,'target'),(pp,pb,'profile'),(rp,rb,'review'),(prp,prb,'previous report'),(lp,lb,'ledger'),(image,ib,'image')):
  if path.read_bytes()!=data:fail(label+' changed while preparing')
 for path,data,digest in bound_sources:
  if hashlib.sha256(data).hexdigest()!=digest or path.read_bytes()!=data:fail('Bound target evidence changed while preparing: '+str(path))
 outdir=Path(a.output).resolve();outdir.mkdir(parents=True,exist_ok=False);targetcopy=outdir/'targets.json';targetcopy.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
 recipe={'mode':'wet','stages':stages,'rawBounds':bounds,'headClearanceBounds':heads,'xyClearanceRawZ':a.xy_clearance_raw_z,'clearanceReviewEvidence':evidence(rp),'profileEvidence':evidence(pp),'previousReportEvidence':evidence(prp),'previousLedgerPath':str(lp),'targetSurface':'ftp-one-pad-cleanup','ftpTargetEvidence':evidence(targetcopy),'computedAspirationLiftIndices':{out['pads'][0]['padId']:[out['pads'][0]['aspirationStageIndex'],out['pads'][0]['liftStageIndex']]},'bAccounting':acct,'sourceTargetEvidence':evidence(sp)}
 recipep=outdir/'recipe.json';recipep.write_text(json.dumps(recipe,indent=2,allow_nan=False)+'\n');nativeout=outdir/'native';cmd=[sys.executable,str(GENERIC),'prepare','--template',str(tp),'--barrier',str(bp),'--image',str(image),'--recipe',str(recipep),'--output',str(nativeout)]
 try:result=subprocess.run(cmd,check=True,text=True,capture_output=True)
 except subprocess.CalledProcessError as e:fail('Generic disabled validator rejected cleanup: '+(e.stderr or e.stdout).strip())
 for path,data,label in ((tp,tb,'template'),(bp,bb,'barrier'),(sp,sb,'target'),(pp,pb,'profile'),(rp,rb,'review'),(prp,prb,'previous report'),(lp,lb,'ledger'),(image,ib,'image')):
  if path.read_bytes()!=data:fail(label+' changed during generic validation')
 for path,data,digest in bound_sources:
  if hashlib.sha256(data).hexdigest()!=digest or path.read_bytes()!=data:fail('Bound target evidence changed during generic validation: '+str(path))
 print(json.dumps({'target':str(targetcopy),'recipe':str(recipep),'previewRequest':str(nativeout/'preview-request.json'),'stages':len(stages),'aspirationIndex':out['pads'][0]['aspirationStageIndex'],'liftIndex':out['pads'][0]['liftStageIndex'],'bAccounting':acct,'genericValidator':result.stdout.strip(),'enabled':False,'motionDispatched':False},indent=2))
if __name__=='__main__':
 try:main()
 except Exception as e:argparse.ArgumentParser().error(str(e))
