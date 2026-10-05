#!/usr/bin/env python3
"""One reviewed stationary prime segment with USB-camera preflight and concurrent evidence. Never retries."""
import argparse
import datetime as dt
import json
import pathlib
import subprocess
import sys
import time
import uuid

R=pathlib.Path(__file__).resolve().parents[2]
CAPTURE=R/'automation/scripts/capture_viewer_usb_series.py'

def verified_initial_capture(output, run=subprocess.run):
    result=run([sys.executable,str(CAPTURE),'--output',str(output),'--sample-times','0'],capture_output=True,text=True,timeout=15)
    if result.returncode!=0:raise RuntimeError('USB camera preflight failed; no prime dispatch')
    manifest=json.loads((output/'manifest.json').read_text())
    if manifest.get('status')!='complete' or manifest.get('errors') or len(manifest.get('captures',[]))!=1:raise RuntimeError('USB camera preflight did not produce exactly one valid sample; no prime dispatch')
    capture=manifest['captures'][0];image=(output/capture['file']).resolve(strict=True)
    if image.parent!=output.resolve() or image.stat().st_size<4 or not image.read_bytes().startswith(b'\xff\xd8\xff'):raise RuntimeError('USB camera preflight image is missing or malformed; no prime dispatch')
    captured=dt.datetime.fromisoformat(capture['captured_at_utc'].replace('Z','+00:00'))
    if captured>dt.datetime.now(dt.timezone.utc):raise RuntimeError('USB camera preflight timestamp is future-dated; no prime dispatch')
    return manifest

def state():
    profile=json.loads((R/'automation/plans/paste-operator-profile.json').read_text())
    ledger_path=R/'automation/evidence/operator-paste-runs'/profile['sessionId']/'budget-ledger.json'
    ledger=json.loads(ledger_path.read_text())
    if ledger['status']!='verified' or not ledger.get('entries') or ledger['entries'][-1]['status']!='verified':raise RuntimeError('Unverified prior operation; no motion')
    return profile,ledger_path,ledger

def main(argv=None,dispatch=subprocess.run,capture_runner=subprocess.run):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--degrees',type=int,default=10);parser.add_argument('--speed',type=float,default=1.5);parser.add_argument('--execute',action='store_true');a=parser.parse_args(argv)
    if not 1<=a.degrees<=10 or not 1<=a.speed<=2:parser.error('Initial observed priming: 1..10 degrees, 1..2 degrees/s')
    profile,lp,before=state()
    q={'schema':1,'scope':'operator-prime-segment','profileId':profile['id'],'nonce':str(uuid.uuid4()),'currentB':before['lastVerifiedRaw']['B'],'createdAt':int(time.time()*1000),'degrees':a.degrees,'speedDegreesPerSecond':a.speed}
    print(json.dumps({'request':q,'execute':a.execute}),flush=True)
    if not a.execute:return 0
    out=R/'automation/evidence/new-syringe-20261004'/('segment-'+q['nonce']);out.mkdir()
    try:
        verified_initial_capture(out/'camera-preflight',capture_runner)
        latest_profile,latest_lp,latest=json.loads((R/'automation/plans/paste-operator-profile.json').read_text()),lp,json.loads(lp.read_text())
        if latest_profile['id']!=profile['id'] or latest_lp!=lp or latest['profileId']!=before['profileId'] or latest['entries']!=before['entries'] or latest['usedAdditionalGrossDegrees']!=before['usedAdditionalGrossDegrees'] or latest['pendingRetractDegrees']!=before['pendingRetractDegrees'] or latest['lastVerifiedRaw']!=before['lastVerifiedRaw']:
            raise RuntimeError('Profile or verified ledger changed during camera preflight; no prime dispatch')
        q['currentB']=latest['lastVerifiedRaw']['B'];q['createdAt']=int(time.time()*1000)
        (out/'request.json').write_text(json.dumps(q,indent=2))
        req=R/'automation/plans/operator-prime-segment-request.json'
        with req.open('x') as f:json.dump(q,f)
        cap=subprocess.Popen([sys.executable,str(CAPTURE),'--output',str(out/'camera-series'),'--seconds','18'])
        r=dispatch([sys.executable,str(R/'automation/scripts/run_reviewed_action.py'),'operator-prime-segment','--confirmed'],capture_output=True,text=True,cwd=R);(out/'dispatch.txt').write_text(r.stdout+r.stderr)
        result={'dispatchReturnCode':r.returncode,'status':'unverified-no-replay','motionReviewRequired':True}
        try:
            if r.returncode:raise RuntimeError('Dispatch failed: inspect dispatch.txt, never replay')
            deadline=time.monotonic()+35
            while time.monotonic()<deadline:
                after=json.loads(lp.read_text())
                if len(after['entries'])==len(before['entries'])+1 and after['entries'][-1]['status']=='verified':
                    raw=after['lastVerifiedRaw'];assert after['profileId']==profile['id'];assert abs(raw['B']-(q['currentB']-a.degrees))<.005
                    assert all(abs(raw[k]-before['lastVerifiedRaw'][k])<.005 for k in ['X','Y','Z','A'])
                    result.update(status='motion-verified-awaiting-image-review',recordId=after['entries'][-1]['id'],raw=raw);break
                time.sleep(.25)
            else:raise RuntimeError('No verified terminal before timeout; no replay')
        except Exception as e:result['error']=str(e)
        finally:
            cap.wait();result['cameraExitCode']=cap.returncode;(out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps({'output':str(out),**result}),flush=True)
        return 1 if 'error' in result else 0
    except Exception as e:
        (out/'preflight-failure.json').write_text(json.dumps({'status':'no-prime-dispatch','error':str(e)},indent=2));raise

if __name__=='__main__':raise SystemExit(main())
