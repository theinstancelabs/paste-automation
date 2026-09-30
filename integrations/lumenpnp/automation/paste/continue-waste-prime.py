#!/usr/bin/env python3
"""One observed continuation via existing controller. No loop or automatic image judgment."""
import argparse,json,pathlib,hashlib,time,uuid,subprocess,shutil
ROOT=pathlib.Path(__file__).resolve().parents[2]
def read(p):return json.loads(pathlib.Path(p).read_text())
def save(p,o):pathlib.Path(p).write_text(json.dumps(o,indent=2)+'\n')
def bound(p):
 p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def dispatch(action):subprocess.run(['python3',str(ROOT/'automation/scripts/run_reviewed_action.py'),action,'--confirmed'],cwd=ROOT,check=True,capture_output=True,text=True)
def wait(p,success):
 end=time.monotonic()+30
 while time.monotonic()<end:
  if p.exists():
   try:r=read(p)
   except json.JSONDecodeError:
    time.sleep(.1);continue
   if r.get('error'):raise RuntimeError(r['error'])
   if r.get('status')==success:return r
  time.sleep(.25)
 raise RuntimeError('No verified completion; do not replay. Inspect '+str(p))
p=argparse.ArgumentParser(description=__doc__);p.add_argument('previous_report',type=pathlib.Path);p.add_argument('reviewed_image',type=pathlib.Path);p.add_argument('--result',required=True,choices=['no-visible-paste','emerging-not-consistent']);p.add_argument('--budget-amendment',type=pathlib.Path);p.add_argument('--execute',action='store_true');a=p.parse_args()
r=read(a.previous_report);assert r['status']=='completed-waste-prime-awaiting-observation' and r['controllerPositionVerified'] and r['countsVerified'] and not r['uncertainCompletion'];q=r['request'];now=int(time.time()*1000);im=bound(a.reviewed_image);im['capturedMs']=a.reviewed_image.stat().st_mtime_ns//1000000
assert 0<=now-im['capturedMs']<300000
if not a.execute:print(json.dumps({'nextB':q['expectedRaw']['B']-40,'singleIncrement':20,'result':a.result,'dispatch':False}));raise SystemExit
out=ROOT/'automation/evidence'/('paste-prime-continuation-'+str(uuid.uuid4()));out.mkdir();s=r['afterQuerySnapshot'];b=read(ROOT/'automation/plans/paste-position-barrier-request.json');b.update(id=str(uuid.uuid4()),createdMs=now,liveConfigurationSha256=q['liveConfigurationSha256'],expectedRaw=s['raw'],expectedDriver=s['driver'],expectedNativePoses=s['nativePoses']);b.pop('sourceEvidence',None);save(ROOT/'automation/plans/paste-position-barrier-request.json',b);dispatch('paste-position-barrier');bp=ROOT/('automation/evidence/paste-position-barrier-'+b['id']+'/report.json');wait(bp,'completed-read-only-position-barrier')
inputq=read(ROOT/'automation/evidence/paste-first-waste-prime-preparation/input.json');inputq.update(barrierPath=str(bp),budgetAmendmentPath=str(a.budget_amendment.resolve()) if a.budget_amendment else None);save(out/'input.json',inputq)
subprocess.run(['node',str(ROOT/'automation/scripts/build_waste_prime_request.cjs'),'--preview-only',str(out/'input.json'),str(out/'preview-request.json')],check=True,capture_output=True)
v=read(out/'preview-request.json');shutil.copyfile(out/'preview-request.json',ROOT/'automation/plans/paste-waste-prime-preview-request.json');dispatch('paste-waste-prime-preview');vp=ROOT/('automation/evidence/paste-waste-prime-preview-'+v['id']+'/report.json');wait(vp,'completed-model-only-native-preview')
o={'schema':1,'scope':'reviewed-waste-prime-outlet-and-receiver','previousRequestId':r['id'],'sessionId':q['sessionId'],'profileSha256':q['profileEvidence']['sha256'],'liveConfigurationSha256':q['liveConfigurationSha256'],'jvmStartMs':q['jvmStartMs'],'outletAndReceiverReviewed':True,'result':a.result,'operator':'codex-parent','reviewedMs':now,'previousReportEvidence':bound(a.previous_report),'images':[im]};save(out/'observation.json',o)
inputq.update(reviewedMs=int(time.time()*1000),nativePreviewPath=str(vp),corridor=im,previousLedgerPath=str(ROOT/'automation/evidence/paste-waste-prime-session/ledger.json'),observationPath=str(out/'observation.json'));save(out/'input.json',inputq)
subprocess.run(['node',str(ROOT/'automation/scripts/build_waste_prime_request.cjs'),str(out/'input.json'),str(out/'request.json')],check=True,capture_output=True)
w=read(out/'request.json');shutil.copyfile(out/'request.json',ROOT/'automation/plans/paste-waste-prime-request.json');dispatch('paste-waste-prime');wp=ROOT/('automation/evidence/paste-waste-prime-'+w['id']+'/report.json');done=wait(wp,'completed-waste-prime-awaiting-observation');print(json.dumps({'report':str(wp),'status':done['status'],'B':done['after']['reported']['B'],'reservedDegrees':done['reservedCumulativeDegrees'],'freshImageReviewRequired':True}))
