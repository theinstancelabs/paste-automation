#!/usr/bin/env python3
"""Preview or execute a short, reviewed X-axis paper-towel wipe and Z lift."""
import argparse
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
_spec = importlib.util.spec_from_file_location('survey_route', HERE/'run-survey-route.py')
route = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(route)
_zspec = importlib.util.spec_from_file_location('observe_z_step', HERE/'observe-z-step.py')
observe_z = importlib.util.module_from_spec(_zspec)
_zspec.loader.exec_module(observe_z)
Z_STEPS = (5, 1, .5, .25, .1)


def lift_steps(start_z, clearance_z):
    if not (math.isfinite(start_z) and math.isfinite(clearance_z)) or clearance_z >= start_z:
        raise ValueError('Clearance Z must be numerically smaller than the reviewed starting raw Z')
    remaining = round(start_z-clearance_z, 4)
    result = []
    for step in Z_STEPS:
        while remaining + 1e-8 >= step:
            result.append(-step)
            remaining = round(remaining-step, 4)
    if remaining > 1e-8:
        raise ValueError('Requested lift cannot be represented by allowed Z steps')
    return result


def build(source_path, image_path, review, halfspan=.5, cycles=3, clearance_z=None, now_ms=None):
    now_ms = time.time_ns()//1_000_000 if now_ms is None else now_ms
    if not math.isfinite(halfspan) or not 0 < halfspan <= 1:
        raise ValueError('Halfspan must be greater than 0 and at most 1 mm')
    if type(cycles) is not int or not 1 <= cycles <= 5:
        raise ValueError('Cycles must be an integer from 1 through 5')
    if not isinstance(review, str) or not review.strip():
        raise ValueError('Required review text must identify the reviewed towel corridor and starting pose')
    source_path, image_path = Path(source_path).resolve(strict=True), Path(image_path).resolve(strict=True)
    source_bytes = source_path.read_bytes()
    source = json.loads(source_bytes)
    kind, jvm, config, raw, _, _ = route.prepare.source_snapshot(source)
    if kind == 'successful-stop-audit':
        raise ValueError('A stop audit cannot start a wipe route')
    if clearance_z is None:
        raise ValueError('--clearance-z is required')
    z_steps = lift_steps(raw['Z'], float(clearance_z))
    image_bytes = image_path.read_bytes()
    captured_ms = image_path.stat().st_mtime_ns//1_000_000
    image = {'path': str(image_path), 'sha256': hashlib.sha256(image_bytes).hexdigest(), 'capturedMs': captured_ms}
    waypoints = []
    for _ in range(cycles):
        waypoints.extend(({'axis':'X','targetMm':raw['X']+halfspan}, {'axis':'X','targetMm':raw['X']-halfspan}))
    waypoints.append({'axis':'X','targetMm':raw['X']})
    spec = {'schema':1,'scope':'reviewed-constant-Z-XY-survey-route','id':str(uuid.uuid4()),
            'reviewedEntireCorridor':True,'operator':review.strip(),'sourceReport':str(source_path),
            'sourceSha256':hashlib.sha256(source_bytes).hexdigest(),'corridorEvidence':image,'waypoints':waypoints}
    planned = route.plan(spec, now_ms)
    return {'schema':1,'id':str(uuid.uuid4()),'status':'preview','source':str(source_path),
            'sourceSha256':spec['sourceSha256'],'review':review.strip(),'routeSpec':spec,'route':planned,
            'halfspanMm':halfspan,'cycles':cycles,'clearanceZ':float(clearance_z),'zLiftSteps':z_steps,
            'fixedAxes':{k:raw[k] for k in ('Y','Z','A','B')},'dispatchPerformed':False,
            'physicalAcceptanceEstablished':False}


def execute(preview, root=ROOT, run_route=route.execute, z_runner=None, firmware_evidence=None):
    root=Path(root)
    run_id=preview['id']; out=root/'automation/evidence'/('paper-towel-wipe-'+run_id)
    out.mkdir()  # exclusive UUID claim
    record={**preview,'status':'claimed','routeRecord':None,'zReports':[],'physicalAcceptanceEstablished':False}
    route.save(out/'report.json',record)
    if any(abs(delta)<1 for delta in preview['zLiftSteps']):
        if firmware_evidence is None: raise ValueError('--firmware-evidence is required for fine Z steps')
        _, jvm, config, _, _, _=route.prepare.source_snapshot(json.loads(Path(preview['source']).read_bytes()))
        observe_z.measured_firmware_step(firmware_evidence,jvm,config)
    record.update(status='running',dispatchPerformed=True)
    route.save(out/'report.json',record)
    try:
        route_record=run_route(preview['routeSpec'], root=root)
    except Exception as exc:
        record.update(status='failed-no-lift-no-recovery',error=str(exc),completionUncertain=True)
        route.save(out/'report.json',record)
        raise
    record['routeRecord']=route_record
    if route_record.get('status')!='completed-route-awaiting-image-review':
        record.update(status='failed-no-lift',completionUncertain=True)
        route.save(out/'report.json',record)
        return record
    if z_runner is None:
        def z_runner(source, delta):
            args=[sys.executable,str(HERE/'observe-z-step.py'),str(source),preview['routeSpec']['corridorEvidence']['path'],
                  '--delta',str(delta),'--review',preview['review'],'--execute']
            if abs(delta)<1:
                if firmware_evidence is None: raise ValueError('--firmware-evidence is required for fine Z steps')
                args.extend(['--firmware-evidence',str(firmware_evidence)])
            completed=subprocess.run(args,cwd=root,check=True,capture_output=True,text=True)
            return json.loads(completed.stdout)['report']
    source=Path(route_record['steps'][-1]['report']) if route_record.get('steps') else Path(preview['source'])
    try:
        for delta in preview['zLiftSteps']:
            result=z_runner(source,delta)
            result=Path(result)
            report=json.loads(result.read_bytes())
            record['zReports'].append({'path':str(result),'sha256':hashlib.sha256(result.read_bytes()).hexdigest(),'deltaMm':delta})
            if report.get('status')!='completed-Z-observation-awaiting-image-review' or report.get('uncertainCompletion') is not False:
                raise RuntimeError('Z lift lacks a verified completed Z observation')
            source=result
            route.save(out/'report.json',record)
    except Exception as exc:
        record.update(status='failed-no-retry-no-recovery',error=str(exc),completionUncertain=True)
        route.save(out/'report.json',record)
        raise
    record['status']='completed-awaiting-image-review'
    route.save(out/'report.json',record)
    return record


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('image',type=Path);p.add_argument('--review',required=True)
    p.add_argument('--halfspan',type=float,default=.5);p.add_argument('--cycles',type=int,default=3)
    p.add_argument('--clearance-z',type=float,required=True);p.add_argument('--execute',action='store_true')
    p.add_argument('--firmware-evidence',type=Path,help='Required verified evidence if a fine Z step is needed')
    a=p.parse_args()
    result=build(a.source,a.image,a.review,a.halfspan,a.cycles,a.clearance_z)
    if a.execute: result=execute(result,firmware_evidence=a.firmware_evidence)
    print(json.dumps(result,indent=2,allow_nan=False))

if __name__=='__main__': main()
