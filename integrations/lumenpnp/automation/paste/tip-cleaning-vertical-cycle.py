#!/usr/bin/env python3
"""Preview or run one reviewed, vertical-only tip cleaning dip or blot cycle."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
_rspec=importlib.util.spec_from_file_location('survey_route',HERE/'run-survey-route.py')
route=importlib.util.module_from_spec(_rspec);_rspec.loader.exec_module(route)
_zspec = importlib.util.spec_from_file_location('observe_z_step', HERE/'observe-z-step.py')
observe_z = importlib.util.module_from_spec(_zspec)
_zspec.loader.exec_module(observe_z)
STEPS = (5, 1, .5, .25, .1)
MAX_DWELL_MS = 10_000
MAX_SEQUENCE_STEPS = 2
STEP_DISPATCH_TIMEOUT_MS = 60_000
EXECUTION_MARGIN_MS = 15_000


def native_z_config(root):
    path=Path(root)/'automation/plans/paste-z-observation-request.json'
    doc=json.loads(path.read_bytes()); config=doc.get('nativeZConfiguration')
    keys={'softLowEnabled','softLowMm','softHighEnabled','softHighMm','safeLowEnabled','safeLowMm','safeHighEnabled','safeHighMm'}
    if not isinstance(config,dict) or set(config)!=keys:
        raise ValueError('Exact current native Z limit snapshot required')
    for key,value in config.items():
        if key.endswith('Enabled'):
            if type(value) is not bool: raise ValueError('Native Z limit flags must be boolean')
        elif type(value) not in (int,float) or not math.isfinite(value):
            raise ValueError('Native Z limit values must be finite')
    return config


def validate_range(config, z_values):
    low=min(z_values);high=max(z_values)
    if config['softLowEnabled'] and low < config['softLowMm']:
        raise ValueError('Whole vertical plan falls below the enabled native Z soft-low bound')
    if config['softHighEnabled'] and high > config['softHighMm']:
        raise ValueError('Whole vertical plan exceeds the enabled native Z soft-high bound')


def execution_budget_ms(step_count,dwell_ms):
    # Each Z step performs one barrier and one Z observation, each polled for at
    # most 60 seconds by the existing owner wrapper.
    return step_count*2*STEP_DISPATCH_TIMEOUT_MS+dwell_ms+EXECUTION_MARGIN_MS


def deltas(start, target):
    if not (math.isfinite(start) and math.isfinite(target)) or start == target:
        raise ValueError('Each vertical leg needs distinct finite raw Z endpoints')
    remaining = round(abs(target-start), 4)
    sign = 1 if target > start else -1
    result = []
    for step in STEPS:
        while remaining + 1e-8 >= step:
            result.append(sign*step)
            remaining = round(remaining-step, 4)
    if remaining > 1e-8:
        raise ValueError('Vertical leg cannot be represented by allowed reviewed Z steps')
    return result


def image_evidence(path, now_ms):
    path = Path(path).resolve(strict=True)
    before = path.stat()
    data = path.read_bytes()
    after = path.stat()
    if (before.st_mtime_ns,before.st_size,before.st_ino)!=(after.st_mtime_ns,after.st_size,after.st_ino):
        raise ValueError('Camera evidence changed while reading')
    if not (data.startswith(b'\x89PNG\r\n\x1a\n') or data.startswith(b'\xff\xd8\xff')):
        raise ValueError('Camera evidence must be PNG or JPEG')
    captured = after.st_mtime_ns//1_000_000
    if captured > now_ms or now_ms-captured > 300_000:
        raise ValueError('Fresh camera evidence (five minutes or newer) required')
    return {'path':str(path),'sha256':hashlib.sha256(data).hexdigest(),'capturedMs':captured}


def build(source_path, image_path, mode, target_z, clearance_z, dwell_ms, review, now_ms=None, root=ROOT):
    now_ms = time.time_ns()//1_000_000 if now_ms is None else now_ms
    if mode not in ('dip','blot'):
        raise ValueError('Mode must be dip or blot')
    if not isinstance(review,str) or not review.strip():
        raise ValueError('Explicit review text for the centered vertical corridor is required')
    if type(dwell_ms) is not int or not 0 <= dwell_ms <= MAX_DWELL_MS:
        raise ValueError(f'Dwell must be an integer from 0 through {MAX_DWELL_MS} ms')
    source_path=Path(source_path).resolve(strict=True)
    source_bytes=source_path.read_bytes(); source=json.loads(source_bytes)
    route.prepare.source_snapshot(source)
    if source.get('error') or source.get('uncertainCompletion') is not False or source.get('controllerPositionVerified') is not True:
        raise ValueError('Certain, verified source position report required')
    snap=source.get('afterQuerySnapshot')
    if not isinstance(snap,dict) or not isinstance(snap.get('raw'),dict):
        raise ValueError('Source report lacks verified raw terminal coordinates')
    start_z=snap['raw'].get('Z')
    target_z=float(target_z); clearance_z=float(clearance_z)
    if not all(math.isfinite(v) for v in (start_z,target_z,clearance_z)):
        raise ValueError('Start, target and clearance raw Z must be finite')
    if clearance_z > start_z or start_z >= target_z:
        raise ValueError('Require clearance Z <= already-centered start Z < reviewed dip/blot target Z')
    down=deltas(start_z,target_z); up=deltas(target_z,clearance_z)
    step_count=len(down)+len(up)
    if step_count > MAX_SEQUENCE_STEPS:
        raise ValueError(f'Plan exceeds {MAX_SEQUENCE_STEPS} Z steps and cannot fit the native evidence lifetime')
    config=native_z_config(root)
    validate_range(config,(start_z,target_z,clearance_z))
    image=image_evidence(image_path,now_ms)
    budget=execution_budget_ms(step_count,dwell_ms)
    if now_ms-image['capturedMs']+budget > 300_000:
        raise ValueError('Camera evidence does not have enough remaining lifetime for this bounded sequence')
    return {'schema':1,'id':str(uuid.uuid4()),'status':'preview','mode':mode,
            'source':str(source_path),'sourceSha256':hashlib.sha256(source_bytes).hexdigest(),
            'image':image,'review':review.strip(),'startZ':start_z,'targetZ':target_z,
            'clearanceZ':clearance_z,'dwellMs':dwell_ms,'descentSteps':down,'liftSteps':up,
            'nativeZConfiguration':config,'maximumExecutionMs':budget,
            'fixedAxes':{a:snap['raw'][a] for a in ('X','Y','A','B')},
            'commandedAxes':['Z'],'dispatchPerformed':False,'physicalAcceptanceEstablished':False}


def execute(preview, root=ROOT, step_runner=None, firmware_evidence=None, sleep=time.sleep):
    root=Path(root); out=root/'automation/evidence'/('tip-cleaning-'+preview['id'])
    out.mkdir()
    record={**preview,'status':'claimed','steps':[],'physicalAcceptanceEstablished':False}
    def save():
        tmp=out/'report.tmp';tmp.write_text(json.dumps(record,indent=2,allow_nan=False)+'\n');tmp.replace(out/'report.json')
    save()
    source=Path(preview['source'])
    if hashlib.sha256(source.read_bytes()).hexdigest()!=preview['sourceSha256']:
        record.update(status='failed-before-dispatch',error='Source report changed after preview');save();raise ValueError(record['error'])
    if image_evidence(preview['image']['path'],time.time_ns()//1_000_000)!=preview['image']:
        record.update(status='failed-before-dispatch',error='Camera evidence changed or expired after preview');save();raise ValueError(record['error'])
    current_config=native_z_config(root)
    validate_range(current_config,(preview['startZ'],preview['targetZ'],preview['clearanceZ']))
    if current_config!=preview['nativeZConfiguration']:
        record.update(status='failed-before-dispatch',error='Native Z limit snapshot changed after preview');save();raise ValueError(record['error'])
    movements=preview['descentSteps']+preview['liftSteps']
    if len(movements)>MAX_SEQUENCE_STEPS:
        record.update(status='failed-before-dispatch',error='Sequence exceeds the bounded evidence lifetime');save();raise ValueError(record['error'])
    budget=execution_budget_ms(len(movements),preview['dwellMs'])
    if time.time_ns()//1_000_000-preview['image']['capturedMs']+budget>300_000:
        record.update(status='failed-before-dispatch',error='Camera evidence has insufficient remaining lifetime');save();raise ValueError(record['error'])
    has_fine=any(abs(d)<1 for d in movements)
    if has_fine:
        if firmware_evidence is None:
            record.update(status='failed-before-dispatch',error='--firmware-evidence is required for fine Z steps');save();raise ValueError(record['error'])
        src=json.loads(source.read_bytes());request=src.get('request',{})
        observe_z.measured_firmware_step(firmware_evidence,request.get('jvmStartMs'),request.get('liveConfigurationSha256'))
    elif firmware_evidence is not None:
        raise ValueError('--firmware-evidence is only used when the sequence needs a sub-1 mm step')
    if step_runner is None:
        def step_runner(src,delta):
            args=[sys.executable,str(HERE/'observe-z-step.py'),str(src),preview['image']['path'],
                  '--delta',str(delta),'--review',preview['review'],'--execute']
            if abs(delta)<1: args.extend(['--firmware-evidence',str(firmware_evidence)])
            completed=subprocess.run(args,cwd=root,check=True,capture_output=True,text=True)
            return json.loads(completed.stdout)['report']
    private=root/'.local-machine-backups'
    if not private.is_dir(): raise ValueError('Private lock directory missing')
    source_report=source
    expected_raw=json.loads(source.read_bytes())['afterQuerySnapshot']['raw']
    step_inflight=False
    try:
        with (private/'tip-cleaning-vertical-cycle.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            record.update(status='running',dispatchPerformed=True);save()
            for phase,steps in (('descend',preview['descentSteps']),('lift',preview['liftSteps'])):
                for delta in steps:
                    if image_evidence(preview['image']['path'],time.time_ns()//1_000_000)!=preview['image']:
                        raise RuntimeError('Camera evidence expired during cycle; stop without further motion')
                    expected={**expected_raw,'Z':expected_raw['Z']+delta}
                    step_inflight=True
                    report_path=Path(step_runner(source_report,delta))
                    data=report_path.read_bytes();report=json.loads(data)
                    req=report.get('request',{});raw=report.get('afterQuerySnapshot',{}).get('raw',{})
                    if (report.get('status')!='completed-Z-observation-awaiting-image-review' or report.get('uncertainCompletion') is not False
                            or report.get('controllerPositionVerified') is not True or report.get('motionSubmitted') is not True
                            or report.get('nativeMotionCompletionReported') is not True or req.get('axis')!='Z'
                            or req.get('deltaMm')!=delta or report.get('commandedControllerAxes')!=['Z']):
                        raise RuntimeError('Z step lacks exact verified single-axis completion')
                    for axis in ('X','Y','Z','A','B'):
                        tolerance=.3 if axis in ('A','B') else .02
                        if abs(raw[axis]-expected[axis])>tolerance:
                            raise RuntimeError(f'Unexpected {axis} position; stop without retry or recovery')
                    record['steps'].append({'phase':phase,'deltaMm':delta,'report':str(report_path),'sha256':hashlib.sha256(data).hexdigest(),'raw':raw})
                    source_report=report_path;expected_raw=raw;step_inflight=False;save()
                if phase=='descend':
                    record['dwellStartedAt']=time.time_ns()//1_000_000;save()
                    sleep(preview['dwellMs']/1000)
                    record['dwellCompletedAt']=time.time_ns()//1_000_000;save()
    except Exception as exc:
        record.update(status='failed-no-retry-no-recovery',error=str(exc),completionUncertain=step_inflight);save();raise
    record['status']='completed-awaiting-image-review';record['completionUncertain']=False;save()
    return record


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('image',type=Path)
    p.add_argument('--mode',choices=('dip','blot'),required=True);p.add_argument('--target-z',type=float,required=True)
    p.add_argument('--clearance-z',type=float,required=True);p.add_argument('--dwell-ms',type=int,required=True)
    p.add_argument('--review',required=True);p.add_argument('--firmware-evidence',type=Path)
    p.add_argument('--execute',action='store_true')
    a=p.parse_args()
    preview=build(a.source,a.image,a.mode,a.target_z,a.clearance_z,a.dwell_ms,a.review)
    result=execute(preview,firmware_evidence=a.firmware_evidence) if a.execute else preview
    print(json.dumps(result,indent=2,allow_nan=False))

if __name__=='__main__': main()
