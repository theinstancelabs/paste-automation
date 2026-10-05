#!/usr/bin/env python3
"""Preview a reviewed station-to-station XY route from a private station recipe."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import time
import uuid

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).parent
_spec=importlib.util.spec_from_file_location('survey_route',HERE/'run-survey-route.py')
route=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(route)
DEFAULT_RECIPE=ROOT/'.local-machine-backups/tip-cleaning-station.json'


def load_recipe(path):
    q=json.loads(Path(path).read_bytes())
    if (not isinstance(q,dict) or type(q.get('schema')) is not int or q.get('schema')!=1 or q.get('scope')!='local-registered-tip-cleaning-station'
            or type(q.get('fixedX')) not in (int,float) or not math.isfinite(q['fixedX'])
            or type(q.get('transitZ')) not in (int,float) or not math.isfinite(q['transitZ'])
            or not isinstance(q.get('stations'),dict) or set(q['stations'])!={'cup','cloth'}):
        raise ValueError('Local station recipe has invalid schema or registrations')
    for name,station in q['stations'].items():
        if not isinstance(station,dict) or type(station.get('y')) not in (int,float) or not math.isfinite(station['y']):
            raise ValueError(f'Local station {name} needs one finite registered Y')
    return q


def preview(source_path,image_path,recipe_path,destination,review,now_ms=None):
    now_ms=time.time_ns()//1_000_000 if now_ms is None else now_ms
    if destination not in ('cup','cloth','cloth-wiggle'):
        raise ValueError('Destination must be cup, cloth, or cloth-wiggle')
    if not isinstance(review,str) or not review.strip():
        raise ValueError('Explicit full-corridor review text required')
    recipe=load_recipe(recipe_path)
    source_path=Path(source_path).resolve(strict=True); source_bytes=source_path.read_bytes(); source=json.loads(source_bytes)
    _kind,_jvm,config,raw,_driver,_poses=route.prepare.source_snapshot(source)
    if source.get('uncertainCompletion') is not False or source.get('controllerPositionVerified') is not True:
        raise ValueError('Certain, verified terminal source required')
    if abs(raw['X']-recipe['fixedX'])>.02:
        raise ValueError('Source X is outside registered station tolerance; this route will not move X')
    if destination!='cloth-wiggle' and abs(raw['Z']-recipe['transitZ'])>.02:
        raise ValueError('Source Z must equal the recipe transit height before XY motion')
    wiggle=destination=='cloth-wiggle'
    station='cloth' if wiggle else destination
    target_y=recipe['stations'][station]['y']
    if wiggle:
        z=recipe.get('clothWiggleZ'); halfspan=recipe.get('clothWiggleHalfspanMm'); cycles=recipe.get('clothWiggleCycles')
        if type(z) not in (int,float) or not math.isfinite(z) or type(halfspan) not in (int,float) or not math.isfinite(halfspan) or not 0 < halfspan <= 1:
            raise ValueError('Recipe cloth wiggle needs finite Z and halfspan in (0, 1] mm')
        if type(cycles) is not int or not 1 <= cycles <= 5:
            raise ValueError('Recipe cloth wiggle cycles must be an integer from 1 to 5')
        if abs(raw['Y']-target_y)>.02 or abs(raw['Z']-z)>.02:
            raise ValueError('Source must already be at registered cloth Y and wiggle Z')
    elif abs(raw['Y']-target_y)<=.02:
        return {'schema':1,'status':'already-at-station','destination':destination,
                'sourceReport':str(source_path),'sourceSha256':hashlib.sha256(source_bytes).hexdigest(),
                'dispatchPerformed':False,'physicalAcceptanceEstablished':False}
    image_path=Path(image_path).resolve(strict=True); image_data=image_path.read_bytes(); stat=image_path.stat()
    if not (image_data.startswith(b'\x89PNG\r\n\x1a\n') or image_data.startswith(b'\xff\xd8\xff')):
        raise ValueError('Full-corridor image must be PNG or JPEG')
    captured=stat.st_mtime_ns//1_000_000
    if captured>now_ms or now_ms-captured>300_000:
        raise ValueError('Fresh full-corridor image required')
    evidence={'path':str(image_path),'sha256':hashlib.sha256(image_data).hexdigest(),'capturedMs':captured}
    envelope_builder=getattr(route.prepare,'commissioning_envelope',None)
    envelope=envelope_builder(config) if callable(envelope_builder) else None
    spec={'schema':1,'scope':'reviewed-constant-Z-XY-survey-route','id':str(uuid.uuid4()),
          'sourceReport':str(source_path),'sourceSha256':hashlib.sha256(source_bytes).hexdigest(),
          'operator':review.strip(),'reviewedEntireCorridor':True,'corridorEvidence':evidence,
          'waypoints':([{'axis':'X','targetMm':recipe['fixedX']+(halfspan if i%2==0 else -halfspan)} for i in range(cycles*2)]+[{'axis':'X','targetMm':recipe['fixedX']}]
                       if wiggle else [{'axis':'Y','targetMm':target_y}])}
    if envelope is not None: spec['commissioningEnvelope']=envelope
    planned=route.plan(spec,now_ms)
    return {'schema':1,'status':'preview','destination':destination,'recipe':str(Path(recipe_path).resolve()),
            'sourceReport':str(source_path),'sourceSha256':spec['sourceSha256'],'startRaw':raw,
            'target':({'X':recipe['fixedX'],'Y':target_y,'Z':raw['Z']} if not wiggle else {'X':recipe['fixedX'],'Y':target_y,'Z':z}),
            'fixedAxes':(['Y','Z','A','B'] if wiggle else ['X','Z','A','B']),
            'wiggle':({'halfspanMm':halfspan,'cycles':cycles,'returnsToCenter':True} if wiggle else None),
            'verticalProfile':recipe.get(station+'Cycle'),
            'routeSpec':spec,'route':planned,'dispatchPerformed':False,'physicalAcceptanceEstablished':False,
            'nextStage':('Review fresh imagery before any further operation; no automatic physical acceptance.' if wiggle else 'Use a fresh reviewed USB image and the existing vertical-cycle helper for the explicit target/clearance/dwell.'
                         if destination=='cloth' else 'Use a fresh reviewed USB image and the existing vertical-cycle helper for the explicit dip target/clearance/dwell.')}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source_report',type=Path);p.add_argument('image',type=Path)
    p.add_argument('destination',choices=('cup','cloth','cloth-wiggle'));p.add_argument('--recipe',type=Path,default=DEFAULT_RECIPE)
    p.add_argument('--review',required=True);p.add_argument('--write-spec',type=Path)
    a=p.parse_args();result=preview(a.source_report,a.image,a.recipe,a.destination,a.review)
    if a.write_spec:
        if 'routeSpec' not in result: p.error('Already at the requested station; there is no route spec to write')
        private=(ROOT/'.local-machine-backups').resolve()
        out=a.write_spec.resolve()
        if private not in out.parents: p.error('--write-spec must be inside .local-machine-backups')
        with out.open('x') as stream: stream.write(json.dumps(result['routeSpec'],indent=2)+'\n')
        result['writtenRouteSpec']=str(out)
    print(json.dumps(result,indent=2,allow_nan=False))

if __name__=='__main__':main()
