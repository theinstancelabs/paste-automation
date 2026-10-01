#!/usr/bin/env python3
"""Capture one native fiducial detection at an already verified stationary camera pose."""
import argparse, hashlib, json, subprocess, time, uuid
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--barrier',type=Path,required=True)
    p.add_argument('--reference',choices=['FID1','FID2','FID3'],required=True)
    p.add_argument('--execute',action='store_true')
    a=p.parse_args();root=Path(__file__).resolve().parents[2]
    src=a.barrier.resolve(strict=True);b=json.loads(src.read_text());s=b['afterQuerySnapshot']
    if b.get('controllerPositionVerified') is not True or b.get('uncertainCompletion') is not False or b.get('error'):
        raise ValueError('Verified terminal position barrier required')
    q=dict(schema=1,scope='native-current-pose-fiducial-vision-request',id=str(uuid.uuid4()),createdMs=int(time.time()*1000),reference=a.reference,expectedCameraLocationMm=s['nativePoses']['top'],sourceBarrier=dict(path=str(src),sha256=hashlib.sha256(src.read_bytes()).hexdigest()))
    if not a.execute:
        print(json.dumps(q,indent=2));return
    out=root/'automation/evidence'/('native-fiducial-attempt-'+q['id']);out.mkdir()
    (out/'request.json').write_text(json.dumps(q,indent=2)+'\n')
    plan=root/'automation/plans/paste-fiducial-vision-request.json';plan.write_text(json.dumps(q,indent=2)+'\n')
    before=set((root/'automation/evidence').glob('native-fiducial-static-*'))
    start=time.time_ns();subprocess.run(['python3',str(root/'automation/scripts/run_reviewed_action.py'),'paste-fiducial-vision','--confirmed'],check=True,stdout=subprocess.DEVNULL)
    (out/'dispatched.json').write_text(json.dumps({'requestId':q['id'],'dispatchNs':start,'repeatDispatchAllowed':False})+'\n')
    end=time.monotonic()+30
    while time.monotonic()<end:
        error=root/'automation/plans/bridge-error.txt'
        if error.exists() and error.stat().st_mtime_ns>=start:
            raise RuntimeError(error.read_text())
        for folder in set((root/'automation/evidence').glob('native-fiducial-static-*'))-before:
            report=folder/'report.json'
            if not report.exists():continue
            try:r=json.loads(report.read_text())
            except json.JSONDecodeError:continue
            if r.get('status','').startswith('failed') or r.get('error'):raise RuntimeError(str(report)+': '+str(r.get('error',r['status'])))
            if r.get('status')=='completed-native-fiducial-detection-awaiting-review':
                print(json.dumps({'report':str(report),'detection':r['nativeFiducialDetection'],'configurationRestored':r['configurationRestored'],'modelPoseUnchanged':r['modelPoseUnchanged']}));return
        time.sleep(.1)
    raise TimeoutError('No terminal native vision result; inspect this attempt before retry: '+str(out))
if __name__=='__main__':main()
