#!/usr/bin/env python3
"""Prepare a read-only preview/request for a bounded registered top-camera route.

Offline only: reads terminal position, registration, and disabled inspection-job
files. It never calls OpenPnP, a camera, a controller, or a motion API.
"""
from __future__ import annotations
import argparse, hashlib, json, math, time, uuid
import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
REG=ROOT/'automation/evidence/manual-home-r33-resume/order-registration2/registration.json'
SOURCE=ROOT/'automation/evidence/paste-contiguous-batch-a4a854ad-7e90-47dd-8736-20e11b1e3423/report.json'
JOB=ROOT/'automation/jobs/ftp-inspection-registered-1790920936515.job.xml'
MAX_SEGMENT=10.0
MAX_TOTAL=120.0
MAX_STEPS=32
def report_grid(value:float)->float:return math.floor(float(value)*100.0+0.5)/100.0
TERMINAL_SOURCE_STATUSES={'completed-contiguous-air-batch-awaiting-observation','completed-contiguous-batch-awaiting-observation','completed-camera-survey-awaiting-image-review'}

def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def fail(msg):raise ValueError(msg)
def axes_map(v,label):
    if not isinstance(v,dict) or set(v)!={'X','Y','Z','A','B'}:fail(f'{label} must bind exactly raw X/Y/Z/A/B')
    if any(type(x) not in (int,float) or not math.isfinite(x) for x in v.values()):fail(f'{label} contains non-finite coordinates')
    return {k:float(v[k]) for k in ('X','Y','Z','A','B')}
def file_hash(path):
    path=Path(path).resolve(strict=True)
    return {'path':str(path),'sha256':sha(path)}
def build(source_path=SOURCE,registration_path=REG,job_path=JOB,references=None,
          operator='Root',review='',camera_target=None,target_mode='midpoint',now_ms=None,fiducial_sample='base',fiducial_centering_report=None):
    now_ms=time.time_ns()//1_000_000 if now_ms is None else now_ms
    source_path=Path(source_path).resolve(strict=True);registration_path=Path(registration_path).resolve(strict=True);job_path=Path(job_path).resolve(strict=True)
    source=json.loads(source_path.read_text());request=source.get('request',{});snap=source.get('afterQuerySnapshot',{})
    raw=axes_map(snap.get('raw'),'Source raw');driver=axes_map(snap.get('driver'),'Source driver')
    if (source.get('status') not in TERMINAL_SOURCE_STATUSES or source.get('motionSubmitted') is not True
            or source.get('controllerPositionVerified') is not True or source.get('uncertainCompletion') is not False
            or source.get('transportUncertain') is True or source.get('id')!=request.get('id')):
        fail('Source must be a completed, certain same-session terminal camera report')
    if raw!=driver:fail('Source raw and driver axes differ')
    if (raw['Z'],raw['A'])!=(32.25,200.0):fail('Source must bind current Z/A to 32.25 / 200; B remains source-bound and unchanged')
    jvm=request.get('jvmStartMs');config=request.get('liveConfigurationSha256')
    if type(jvm) is not int or not isinstance(config,str) or len(config)!=64:fail('Source JVM/configuration binding missing')
    top=((snap.get('nativePoses') or {}).get('top'))
    poses=snap.get('nativePoses')
    if not isinstance(top,dict) or set(poses or {})!={'N1','N2','top','bottom'}:fail('Source native camera/nozzle poses incomplete')
    for name,pose in poses.items():
        if not isinstance(pose,dict) or any(type(pose.get(k)) not in (int,float) or not math.isfinite(pose[k]) for k in ('x','y','z','rotation')):fail(f'Invalid {name} native pose')
    reg=json.loads(registration_path.read_text())
    allowed_registration_scopes={'offline-native-fresh-ftp-two-fiducial-transform-with-third-point-check','offline-fresh-ftp-three-fiducial-affine-with-held-out-pad-checks'}
    if reg.get('scope') not in allowed_registration_scopes or reg.get('acceptance',{}).get('passed') is not True or reg.get('machineConfigurationChanged') is not False or reg.get('jobChanged') is not False:fail('Current accepted offline similarity or held-out affine registration required')
    if reg.get('board',{}).get('sha256')!=sha(ROOT/'pnp/pcb/ftp/ftp.kicad_pcb'):fail('Registered board hash no longer matches canonical CAD')
    targets={p.get('padId'):p.get('machineXYMm') for p in reg.get('resistorPadMachineXYTargets',[]) if isinstance(p,dict)}
    target_list=[];centering_evidence=None
    if target_mode not in ('midpoint','pad1','pad2'):fail('Target mode must be midpoint, pad1 or pad2')
    fiducial_offsets={'base':(0.0,0.0),'xplus':(1.0,0.0),'yplus':(0.0,1.0)}
    if fiducial_sample not in fiducial_offsets:fail('FID sample must be base, xplus or yplus')
    if camera_target is not None:
        if camera_target!=(310.0,232.27) or not review.strip():fail('Only the explicitly reviewed scrap camera point [310,232.27] is permitted')
        mode='reviewed-scrap-camera';target_mode='fixed-scrap-camera';refs=[];target_list=[{'reference':'scrap','x':310.0,'y':232.27,'pads':[]}]
    elif references and all(r in ('FID1','FID2','FID3') for r in references):
        if reg.get('scope')!='offline-native-fresh-ftp-two-fiducial-transform-with-third-point-check':fail('Fiducial sampling requires the accepted native two-fiducial registration source')
        if not 1<=len(references)<=3 or len(set(references))!=len(references):fail('Choose one to three unique registered fiducials')
        if fiducial_sample!='base' and len(references)!=1:fail('An offset sample must select exactly one registered fiducial')
        if fiducial_centering_report is not None and len(references)!=1:fail('A centering report applies to exactly one registered fiducial')
        mode='registered-fiducials';refs=references
        measurements=reg.get('measurements',{})
        center_report=None
        if fiducial_centering_report is not None:
            cp=Path(fiducial_centering_report).resolve(strict=True);center_report=json.loads(cp.read_text());det=center_report.get('nativeFiducialDetection',{});ref=refs[0]
            if (center_report.get('schema')!=1 or center_report.get('scope')!='native-current-pose-fiducial-vision'
                    or center_report.get('status')!='completed-native-fiducial-detection-awaiting-review'
                    or center_report.get('error') or center_report.get('physicalRegistrationEstablished') is not False
                    or center_report.get('noMotion') is not True or center_report.get('noActuation') is not True
                    or center_report.get('noVacuum') is not True or center_report.get('jobSaved') is not False
                    or center_report.get('configurationSaved') is not False or center_report.get('modelPoseUnchanged') is not True
                    or center_report.get('configurationRestored') is not True or center_report.get('jvmStartMs')!=jvm
                    or center_report.get('liveConfigurationBeforeSha256')!=config or center_report.get('liveConfigurationAfterSha256')!=config
                    or center_report.get('reference')!=ref or det.get('reference')!=ref):fail('Fresh same-session completed native FID centering report required')
            try: finished=datetime.datetime.fromisoformat(center_report['finishedAt'].replace('Z','+00:00')).timestamp()*1000
            except Exception: fail('FID centering report completion time required')
            if finished>now_ms or now_ms-finished>30*60*1000:fail('FID centering report must be no more than 30 minutes old')
            raw_pose=center_report.get('nativePose',{}).get('rawAxes',{})
            try:
                center_raw={a:raw_pose[a]['model'] for a in ('X','Y','Z','A','B')}
                center_driver={a:raw_pose[a]['driver'] for a in ('X','Y','Z','A','B')}
            except Exception: fail('FID centering report native raw pose incomplete')
            if any(type(v) not in (int,float) or not math.isfinite(v) for v in list(center_raw.values())+list(center_driver.values())) or center_raw!=center_driver or any(center_raw[k]!=raw[k] for k in ('Z','A','B')):fail('FID centering report drivers must match raw axes and Z/A/B must remain exact')
            cam=center_report.get('camera',{}).get('locationMm',{})
            if cam.get('x')!=center_raw['X'] or cam.get('y')!=center_raw['Y']:fail('FID centering camera XY must match its native raw pose')
            base=det.get('detectedMachineXYMm')
            if not isinstance(base,list) or len(base)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in base):fail('Native FID detector machine center required')
            regbase=measurements.get(ref,{}).get('measuredTopCameraXYMm')
            if not isinstance(regbase,list) or math.dist(base,regbase)>.2:fail('Detected FID center must remain within 0.2 mm of accepted registration')
            raw_image=center_report.get('images',{}).get('raw',{});ip=Path(cp.parent/raw_image.get('path','')).resolve(strict=True)
            if ip.parent!=cp.parent or sha(ip)!=raw_image.get('sha256'):fail('Hash-bound raw image must belong to centering report')
            centering_evidence={**file_hash(cp),'id':center_report.get('requestId'),'reference':ref,'detectedMachineXYMm':base,'finishedAt':center_report.get('finishedAt'),'jvmStartMs':jvm,'liveConfigurationSha256':config,'fixedRawZAB':[center_raw[k] for k in ('Z','A','B')],'image':file_hash(ip)}
        for ref in refs:
            xy=(center_report.get('nativeFiducialDetection',{}).get('detectedMachineXYMm') if center_report is not None else measurements.get(ref,{}).get('measuredTopCameraXYMm'))
            if not isinstance(xy,list) or len(xy)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in xy):fail(f'Registration missing native measured top-camera center for {ref}')
            offset=fiducial_offsets[fiducial_sample]
            target_list.append({'reference':ref,'x':float(xy[0])+offset[0],'y':float(xy[1])+offset[1],'sample':fiducial_sample,'offsetXYMm':list(offset),'pads':[]})
    else:
        mode='registered-references';refs=references or []
        if not 1<=len(refs)<=8 or len(set(refs))!=len(refs) or any(not isinstance(r,str) or not __import__('re').fullmatch(r'R(?:[1-9]|[1-3][0-9]|40)',r) for r in refs):fail('Choose 1–8 unique R1–R40 references')
        for ref in refs:
            p1,p2=targets.get(ref+'.1'),targets.get(ref+'.2')
            if not isinstance(p1,list) or not isinstance(p2,list) or len(p1)!=2 or len(p2)!=2:fail(f'Registration missing both centers for {ref}')
            xy=[float(p1[0]),float(p1[1])] if target_mode=='pad1' else [float(p2[0]),float(p2[1])] if target_mode=='pad2' else [(float(p1[0])+float(p2[0]))/2,(float(p1[1])+float(p2[1]))/2]
            target_list.append({'reference':ref,'x':xy[0],'y':xy[1], 'pads':[{'padId':ref+'.1','x':float(p1[0]),'y':float(p1[1])},{'padId':ref+'.2','x':float(p2[0]),'y':float(p2[1])}]})
    cursor=(raw['X'],raw['Y']);total=0.;steps=[]
    for target in target_list:
        end=(report_grid(target['x']),report_grid(target['y']));distance=math.sqrt((end[0]-cursor[0])**2+(end[1]-cursor[1])**2)
        if distance < .0001:
            if mode=='reviewed-scrap-camera':continue
            fail('Registered target rounds to the current camera position; use reviewed in-place scrap capture')
        count=math.ceil(distance/MAX_SEGMENT)
        for i in range(1,count+1):
            f=i/count;x=report_grid(cursor[0]+(end[0]-cursor[0])*f);y=report_grid(cursor[1]+(end[1]-cursor[1])*f)
            prior=(steps[-1]['x'],steps[-1]['y']) if steps else cursor
            d=math.sqrt((x-prior[0])**2+(y-prior[1])**2)
            if d < .0001:continue
            if d>MAX_SEGMENT+1e-9:fail('Report-grid quantization exceeds segment travel ceiling')
            step={'index':len(steps),'x':x,'y':y,'z':raw['Z'],'a':raw['A'],'b':raw['B'],'captureReferences':[target['reference']] if i==count else []}
            steps.append(step);total+=d
        cursor=end
    if total>MAX_TOTAL or len(steps)>MAX_STEPS:fail('Registered route exceeds 120 mm / 32 bounded segments')
    # Runtime loader verifies every placement is disabled; offline generation binds exact source hashes.
    job_xml=ET.parse(job_path).getroot();boards=job_xml.findall(".//object[@class='org.openpnp.model.BoardLocation']")
    if len(boards)!=1:fail('Inspection job must contain exactly one registered board')
    board_path=Path(boards[0].get('file-name','')).resolve(strict=True)
    job_placements=ET.parse(board_path).getroot().findall('./placements/placement')
    if not job_placements or any(p.get('enabled')!='false' for p in job_placements):fail('Inspection board must keep every placement disabled')
    if not all(r.get('rotation')==0 for r in [top]):fail('Top camera must have the reviewed zero rotation')
    plan={'schema':1,'scope':'camera-only-registered-fast-inspection','enabled':True,'id':str(uuid.uuid4()),'createdMs':now_ms,'jvmStartMs':jvm,
      'liveConfigurationSha256':config,'mode':mode,'targetMode':target_mode,'operatorReviewed':True,'reviewedBy':operator,'review':review or 'Registered-reference camera-only inspection; all component placements remain disabled.',
      'speedFraction':1.0,'speedOverPrecision':True,'maxSegmentMm':MAX_SEGMENT,'maxTotalTravelMm':MAX_TOTAL,'plannedDistanceMm':round(total,6),
      'sourceReport':{**file_hash(source_path),'id':source['id'],'finishedAt':source.get('finishedAt'),'status':source['status']},
      'registration':{**file_hash(registration_path),'scope':reg['scope'],'targets':[{'padId':k,'machineXYMm':v} for k,v in sorted(targets.items()) if any(k.startswith(r+'.') for r in refs)],'fiducials':[{'reference':r,'measuredTopCameraXYMm':reg['measurements'][r]['measuredTopCameraXYMm']} for r in refs if r in reg.get('measurements',{})]},
      'inspectionJob':{'jobPath':str(job_path),'jobSha256':sha(job_path),'boardPath':str(board_path),'boardSha256':sha(board_path)},
      'expectedRaw':raw,'expectedDriver':driver,'expectedNativePoses':poses,'references':refs,'targets':target_list,'routeSteps':steps,
      'fiducialCenteringReport':centering_evidence,
      'fiducialSample':fiducial_sample if mode=='registered-fiducials' else None,
      'completionScope':'Camera frames and XY position reports only; no paste, calibration, or placement acceptance.'}
    return plan

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-report',type=Path,default=SOURCE);p.add_argument('--registration',type=Path,default=REG);p.add_argument('--inspection-job',type=Path,default=JOB);p.add_argument('--references',help='Comma-separated registered references (R1–R40), or native measured FID1,FID2,FID3 targets');p.add_argument('--camera-target',help='Only exact reviewed scratch coordinate 310,232.27');p.add_argument('--target-mode',choices=('midpoint','pad1','pad2'),default='midpoint',help='Registered resistor target: midpoint (default), pad1 or pad2 center');p.add_argument('--fiducial-sample',choices=('base','xplus','yplus'),default='base',help='For one registered FID only: base, +1 mm X, or +1 mm Y camera sample');p.add_argument('--fiducial-centering-report',type=Path,help='Completed native FID detector report to use as the measured center (within 0.2 mm of registration)');p.add_argument('--operator',default='Root');p.add_argument('--review',default='');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 refs=[x.strip() for x in a.references.split(',') if x.strip()] if a.references else None
 target=tuple(map(float,a.camera_target.split(','))) if a.camera_target else None
 result=build(a.source_report,a.registration,a.inspection_job,refs,a.operator,a.review,target,a.target_mode,fiducial_sample=a.fiducial_sample,fiducial_centering_report=a.fiducial_centering_report)
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'output':str(a.output),'id':result['id'],'mode':result['mode'],'references':result['references'],'waypoints':len(result['routeSteps']),'distanceMm':result['plannedDistanceMm']},indent=2))
if __name__=='__main__':main()
