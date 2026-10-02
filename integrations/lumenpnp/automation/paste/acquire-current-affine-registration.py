#!/usr/bin/env python3
"""Acquire current-session camera samples for an offline affine registration.

This is an execution wrapper for the reviewed camera-only and native-CV tools.
It does not infer acceptance: all images and reports remain available for
independent review. Run only by the designated machine operator.
"""
from __future__ import annotations
import argparse, hashlib, json, math, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'automation/evidence'
REG = ROOT / 'automation/evidence/manual-home-r33-resume/reduced-registration-rest/registration.json'
JOB = ROOT / 'automation/jobs/ftp-inspection-registered-1790924641873.job.xml'
PREP = ROOT / 'automation/paste/prepare-fast-camera-inspection.py'
RUN = ROOT / 'automation/scripts/run_reviewed_action.py'
FID = ROOT / 'automation/paste/run-native-fiducial-vision.py'
HELDOUT_PAD3 = 'R40.1'
POSITION = ROOT / 'automation/paste/capture-manual-home-position.py'
sys.path.insert(0, str(ROOT / 'automation/paste/analysis'))
from needle_centroid import sweep
from fresh_ftp_registration import fast_camera_source

REVIEW = ('Root reviewed the clear camera-only corridor and bounded fiducial/pad targets; '
          'placements disabled, fixed joint clearance Z/A/B, no hands in the work area. '
          'This acquisition is for image registration only.')

def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def run(args):
    return subprocess.run([str(x) for x in args], cwd=ROOT, check=True,
                          text=True, capture_output=True).stdout.strip()

def wait_report(p: Path, timeout=75):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        err=ROOT/'automation/plans/bridge-error.txt'
        if err.exists():
            try:
                if err.stat().st_mtime_ns >= start_ns:
                    raise RuntimeError(err.read_text())
            except FileNotFoundError: pass
        if p.exists():
            try:r=json.loads(p.read_text())
            except (json.JSONDecodeError,OSError):time.sleep(.15);continue
            if r.get('error') or r.get('status','').startswith('failed'):
                raise RuntimeError(f'{p}: {r.get("error",r.get("status"))}')
            if r.get('status')=='completed-camera-survey-awaiting-image-review':
                if r.get('controllerPositionVerified') is not True or r.get('uncertainCompletion') is not False:
                    raise RuntimeError('Camera survey did not end with certain position verification')
                return r
        time.sleep(.15)
    raise TimeoutError(f'No terminal report; inspect before any retry: {p}')

def dispatch_survey(source: Path, outdir: Path, label: str, ref: str, *,
                    sample=None, center_report=None, target_mode=None, registration=REG):
    plan=outdir/f'{label}-request.json'
    cmd=['python3',PREP,'--source-report',source,'--registration',registration,'--inspection-job',JOB,
         '--references',ref,'--review',REVIEW,'--output',plan]
    if sample: cmd += ['--fiducial-sample',sample]
    if center_report: cmd += ['--fiducial-centering-report',center_report]
    if target_mode: cmd += ['--target-mode',target_mode]
    run(cmd); q=json.loads(plan.read_text())
    (ROOT/'automation/plans/fast-camera-inspection-request.json').write_bytes(plan.read_bytes())
    global start_ns
    start_ns=time.time_ns()
    run(['python3',RUN,'paste-fast-camera-inspection','--confirmed'])
    report=EVIDENCE/f"camera-inspection-{q['id']}/report.json"
    r=wait_report(report)
    return report,r

def current_barrier():
    global start_ns
    start_ns=time.time_ns()
    result=run(['python3',POSITION,'--operator-home-confirmed'])
    p=Path(result.splitlines()[-1]).resolve(strict=True)
    b=json.loads(p.read_text())
    if b.get('controllerPositionVerified') is not True or b.get('uncertainCompletion') is not False:
        raise RuntimeError('Fresh read-only stationary position barrier required')
    return p

def native_center(ref):
    barrier=current_barrier()
    obj=json.loads(run(['python3',FID,'--barrier',barrier,'--reference',ref,'--execute']))
    p=Path(obj['report']).resolve(strict=True)
    r=json.loads(p.read_text())
    if (r.get('status')!='completed-native-fiducial-detection-awaiting-review'
        or r.get('noMotion') is not True or r.get('noActuation') is not True
        or r.get('modelPoseUnchanged') is not True or r.get('configurationRestored') is not True):
        raise RuntimeError(f'Unacceptable native CV result for {ref}: {p}')
    return p,r

def centroid(report_path):
    r=json.loads(report_path.read_text()); im=r['afterImages']['top']; ip=(report_path.parent/im['path']).resolve(strict=True)
    if ip.parent!=report_path.parent:raise RuntimeError('External camera image path')
    image_sha=sha(ip)
    if im.get('sha256') is not None and image_sha!=im['sha256']:
        raise RuntimeError('Camera image hash disagrees with report')
    m=sweep(ip.read_bytes(),[800,400,1100,700],[100,120,140],'R')
    c=m['centroidSummary']
    if not c:raise RuntimeError(f'FID image has no measurable feature: {report_path}')
    xy=[c['x']['median'],c['y']['median']]
    d=math.dist(xy,[959.5,539.5])
    return {'imagePath':str(ip),'imageSha256':image_sha,'reportImageSha256':im.get('sha256'),
            'centroidPixel':xy,'geometricCenterPixel':[959.5,539.5],
            'offsetPixels':d,'measurement':m}

def save_checkpoint(out, session, records, centers, current, reg_sha, job_sha, heldout_registration=None):
    manifest={'schema':1,'kind':'current-session-affine-registration-acquisition','acceptanceEstablished':False,
        'limitations':['Human review and offline center measurement are required; this manifest is not an accepted registration.',
                       'Historical registration is used only by the request builder for approximate navigation.',
                       'Camera image hashes are computed from saved files; source reports may omit an image hash.',
                       'No paste, calibration, placement, or production action is included.'],
        'session':session,'historicalApproximationRegistration':{'path':str(REG),'sha256':reg_sha},
        'heldOutPadRegistration':heldout_registration,'heldOutPadIds':['R1.2','R16.1',HELDOUT_PAD3],
        'inspectionJob':{'path':str(JOB),'sha256':job_sha},'nativeFiducialCenters':centers,
        'records':records,'terminalSource':{'path':str(current),'sha256':sha(current) if Path(current).is_file() else None}}
    (out/'measurements-manifest.json.tmp').write_text(json.dumps(manifest,indent=2)+'\n')
    (out/'measurements-manifest.json.tmp').replace(out/'measurements-manifest.json')
    byname={r['name']:r for r in records}
    bases=[r for r in records if r.get('name')=='FID2-base' or r.get('name','').startswith('FID2-recenter-')]
    heldout_ids=['R1.2','R16.1',HELDOUT_PAD3]
    if bases and all(k in byname for k in ['FID2-xplus','FID2-yplus',*heldout_ids]):
        jacobian_base=bases[-1]
        inp={'jacobianSamples':[{'name':n,'report':(jacobian_base if n=='base' else byname['FID2-'+n])['report'],
             'roi':[850,350,1150,650],'thresholds':[100,120,140],'channel':'R'}
             for n in ('base','xplus','yplus')],
             'heldOutPads':[{'padId':n,'report':byname[n]['report'],'roi':[900,480,1020,600],
             'thresholds':[100,120,140],'channel':'R'} for n in heldout_ids]}
        tmp=out/'measurements-input.json.tmp';tmp.write_text(json.dumps(inp,indent=2)+'\n');tmp.replace(out/'measurements-input.json')

def validate_heldout_registration(path, jvm, config):
    path=Path(path).resolve(strict=True); value=json.loads(path.read_text())
    if (value.get('scope')!='offline-fresh-ftp-three-fiducial-affine-with-held-out-pad-checks'
        or value.get('acceptance',{}).get('passed') is not True
        or value.get('machineConfigurationChanged') is not False
        or value.get('jobChanged') is not False
        or value.get('session',{}).get('jvmStartMs')!=jvm
        or value.get('session',{}).get('liveConfigurationSha256')!=config
        or value.get('board',{}).get('sha256')!=sha(ROOT/'pnp/pcb/ftp/ftp.kicad_pcb')):
        raise ValueError('--heldout-registration must be an accepted same-session affine registration for the canonical board')
    targets=value.get('resistorPadMachineXYTargets')
    ids={p.get('padId') for p in targets or [] if isinstance(p,dict)}
    if len(targets or [])!=80 or not {'R1.2','R16.1','R40.1','R24.1'}<=ids:
        raise ValueError('--heldout-registration must contain all 80 resistor pad targets and the three independent held-out pads')
    return {'path':str(path),'sha256':sha(path),'scope':value['scope'],'acceptancePassed':True}

def main():
    global HELDOUT_PAD3
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,required=True,help='Fresh completed current-JVM AIR survey report at FID2')
    ap.add_argument('--heldout-registration',type=Path,help='Accepted affine registration used only for held-out pad targets; FID requests retain historical native registration')
    ap.add_argument('--heldout-pads',default='R1.2,R16.1,R40.1',help='Exactly R1.2,R16.1,R40.1 (default) or R1.2,R16.1,R24.1 when R40.1 is unsuitable')
    ap.add_argument('--output',type=Path,required=True,help='New empty directory for acquisition manifest')
    a=ap.parse_args(); source=a.source.resolve(strict=True); out=a.output.resolve(); heldout_ids=[v.strip() for v in a.heldout_pads.split(',')]
    if heldout_ids not in (['R1.2','R16.1','R40.1'],['R1.2','R16.1','R24.1']):
        raise ValueError('--heldout-pads must be exactly R1.2,R16.1,R40.1 or R1.2,R16.1,R24.1 in that order')
    HELDOUT_PAD3=heldout_ids[2]
    if out.exists():raise ValueError('Output directory must not already exist')
    out.mkdir(parents=True)
    src=json.loads(source.read_text()); snap=src.get('afterQuerySnapshot',{}); raw=snap.get('raw',{}); req=src.get('request',{})
    allowed_source_status={'completed-camera-survey-awaiting-image-review','completed-contiguous-air-batch-awaiting-observation'}
    if req.get('scope')=='camera-only-registered-fast-inspection':
        # Fast-camera reports prove each bounded step through route-step-verified
        # transitions and bind the terminal raw/driver/M114/image state. They do
        # not emit the independentFirmwareStepVerified field used by AIR surveys.
        fast_camera_source(src,'FID2',source,now=int(time.time()*1000))
    elif (src.get('status') not in allowed_source_status or src.get('id')!=req.get('id') or src.get('controllerPositionVerified') is not True
        or src.get('uncertainCompletion') is not False or src.get('motionSubmitted') is not True
        or src.get('transportUncertain') is True or src.get('independentFirmwareStepVerified') is not True):
        raise ValueError('--source must be a certain completed same-session camera survey')
    if type(req.get('jvmStartMs')) is not int or not isinstance(req.get('liveConfigurationSha256'),str):
        raise ValueError('--source must bind a same-session JVM and configuration')
    if snap.get('raw')!=snap.get('driver'):
        raise ValueError('Source raw and driver axes must match exactly')
    if raw.get('Z')!=32.25 or raw.get('A')!=200.0 or (snap.get('nativePoses',{}).get('top',{}).get('z')!=0.0):
        raise ValueError('Expected current AIR source at camera Z=0 with raw Z/A 32.25/200')
    if not (REG.is_file() and JOB.is_file()):raise FileNotFoundError('Historical approximation registration or fixed inspection job missing')
    session={'jvmStartMs':req['jvmStartMs'],'liveConfigurationSha256':req['liveConfigurationSha256'],
             'source':{'path':str(source),'sha256':sha(source),'id':src['id']},'cameraZ':0.0,'rawZAB':[raw['Z'],raw['A'],raw['B']]}
    heldout_registration=validate_heldout_registration(a.heldout_registration,req['jvmStartMs'],req['liveConfigurationSha256']) if a.heldout_registration else None
    heldout_reg_path=Path(heldout_registration['path']) if heldout_registration else REG
    records=[]; current=source;fidcenters={}
    reg_sha=sha(REG);job_sha=sha(JOB)
    save_checkpoint(out,session,records,fidcenters,current,reg_sha,job_sha,heldout_registration)

    # Fresh native detector center at FID2, then establish its local 2-D pixel response.
    native2, nr=native_center('FID2')
    fid2_center=str(native2)
    fidcenters['FID2']=fid2_center
    save_checkpoint(out,session,records,fidcenters,current,reg_sha,job_sha,heldout_registration)
    for attempt in range(1,4):
        base,br=dispatch_survey(current,out,'FID2-base' if attempt==1 else f'FID2-recenter-{attempt}',
                                'FID2',sample='base',center_report=fid2_center);current=base
        bc=centroid(base)
        records.append({'name':'FID2-base' if attempt==1 else f'FID2-recenter-{attempt}',
                        'report':str(base),'reportSha256':sha(base),'center':bc})
        save_checkpoint(out,session,records,fidcenters,current,reg_sha,job_sha,heldout_registration)
        if bc['offsetPixels']<=2.0:break
        if attempt<3:
            native2,_=native_center('FID2');fid2_center=str(native2)
    else:raise RuntimeError('FID2 remains outside 2 px after three fresh native-CV corrections')
    # Use the same fresh native FID2 center for both orthogonal one-millimeter samples.
    for sm in ('xplus','yplus'):
        p,r=dispatch_survey(current,out,'FID2-'+sm,'FID2',sample=sm,center_report=fid2_center);current=p
        records.append({'name':'FID2-'+sm,'report':str(p),'reportSha256':sha(p),'center':centroid(p)})
        save_checkpoint(out,session,records,fidcenters,current,reg_sha,job_sha,heldout_registration)

    # Fresh native centering evidence and a checked camera-center frame for each remaining FID.
    for ref in ('FID1','FID3'):
        # Navigate approximately using the historical registration, then acquire a
        # fresh native detector center at that pose and correct to it.
        p,_=dispatch_survey(current,out,ref+'-arrival',ref);current=p
        records.append({'name':ref+'-arrival','report':str(p),'reportSha256':sha(p),
                        'image':p.parent.joinpath(json.loads(p.read_text())['afterImages']['top']['path']).as_posix()})
        save_checkpoint(out,session,records,fidcenters,current,reg_sha,job_sha,heldout_registration)
        for attempt in range(1,4):
            cp,_=native_center(ref); fidcenters[ref]=str(cp)
            p,r=dispatch_survey(current,out,f'{ref}-center-{attempt}',ref,center_report=str(cp));current=p
            c=centroid(p)
            records.append({'name':f'{ref}-center-{attempt}','report':str(p),'reportSha256':sha(p),'center':c})
            save_checkpoint(out,session,records,fidcenters,current,reg_sha,job_sha,heldout_registration)
            if c['offsetPixels']<=2.0:break
        else:raise RuntimeError(f'{ref} remains outside 2 px after three fresh native-CV corrections')
    # Held-out CAD checks, each at the intended pad center.
    for name,ref,mode in (('R1.2','R1','pad2'),('R16.1','R16','pad1'),(HELDOUT_PAD3,HELDOUT_PAD3.split('.')[0],'pad1')):
        p,r=dispatch_survey(current,out,name,ref,target_mode=mode,registration=heldout_reg_path);current=p
        im=r['afterImages']['top']; ip=(p.parent/im['path']).resolve(strict=True)
        if ip.parent!=p.parent:raise RuntimeError('External held-out image path')
        image_sha=sha(ip)
        if im.get('sha256') is not None and image_sha!=im['sha256']:raise RuntimeError('Held-out image hash disagrees with report')
        records.append({'name':name,'report':str(p),'reportSha256':sha(p),'image':im,
                        'imagePath':str(ip),'imageSha256':image_sha})
        save_checkpoint(out,session,records,fidcenters,current,reg_sha,job_sha,heldout_registration)
    manifest={'schema':1,'kind':'current-session-affine-registration-acquisition','acceptanceEstablished':False,
        'limitations':['Human review and offline center measurement are required; this manifest is not an accepted registration.',
                       'Historical registration is used only by the request builder for approximate navigation.',
                       'No paste, calibration, placement, or production action is included.'],
        'session':session,'historicalApproximationRegistration':{'path':str(REG),'sha256':sha(REG)},
        'heldOutPadRegistration':heldout_registration,'heldOutPadIds':['R1.2','R16.1',HELDOUT_PAD3],
        'inspectionJob':{'path':str(JOB),'sha256':sha(JOB)},'nativeFiducialCenters':fidcenters,
        'records':records,'terminalSource':{'path':str(current),'sha256':sha(current)}}
    dest=out/'measurements-manifest.json'
    dest.write_text(json.dumps(manifest,indent=2)+'\n')
    inp=out/'measurements-input.json'
    print(json.dumps({'manifest':str(dest),'measurementsInput':str(inp),'records':len(records),
                      'acceptanceEstablished':False},indent=2))

if __name__=='__main__':main()
