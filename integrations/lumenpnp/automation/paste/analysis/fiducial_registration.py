#!/usr/bin/env python3
"""Offline three-fiducial rigid/similarity fit; never changes machine registration."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
from needle_centroid import sweep

PARSER = Path(__file__).resolve().parents[1]/'pads/extract_ftp_pads.py'
spec = importlib.util.spec_from_file_location('ftp_geometry', PARSER)
cad = importlib.util.module_from_spec(spec); spec.loader.exec_module(cad)
source_spec = importlib.util.spec_from_file_location('survey_source', PARSER.parent.parent/'prepare-survey-request.py')
source = importlib.util.module_from_spec(source_spec); source_spec.loader.exec_module(source)


def bound(path):
    p = Path(path).resolve(strict=True); data = p.read_bytes()
    return data, {'path': str(p), 'sha256': hashlib.sha256(data).hexdigest()}


def fiducials(data):
    result = {}
    for footprint in cad.children(cad.sexpr(data.decode()), 'footprint'):
        refs = [p[2] for p in cad.children(footprint, 'property') if p[1] == 'Reference']
        if len(refs) != 1 or refs[0] not in ('FID1', 'FID2', 'FID3'): continue
        ref = refs[0]
        if ref in result: raise ValueError('Duplicate fiducial')
        if cad.one(footprint, 'layer')[1] != 'F.Cu': raise ValueError('Only front-side fiducials supported')
        pads = cad.children(footprint, 'pad')
        if len(pads) != 1 or pads[0][3] != 'circle': raise ValueError('Expected one circular fiducial pad')
        pad_at = cad.one(pads[0], 'at')
        if any(cad.number(v) != 0 for v in pad_at[1:3]): raise ValueError('Offset fiducial pad requires explicit transform support')
        at = cad.one(footprint, 'at'); result[ref] = [cad.number(v) for v in at[1:3]]
    if set(result) != {'FID1', 'FID2', 'FID3'}: raise ValueError('All three CAD fiducials required')
    return result


def fit(points, observations, rigid=False):
    if len(points) != 3 or len(observations) != 3: raise ValueError('Exactly three correspondences required')
    if any(len(p) != 2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in p) for p in points+observations):
        raise ValueError('Finite 2D correspondences required')
    cross = ((points[1][0]-points[0][0])*(points[2][1]-points[0][1])-
             (points[1][1]-points[0][1])*(points[2][0]-points[0][0]))
    if abs(cross) < 1e-6: raise ValueError('Noncollinear fiducials required')
    pmean=[sum(p[i] for p in points)/3 for i in range(2)]
    qmean=[sum(p[i] for p in observations)/3 for i in range(2)]
    ps=[[p[i]-pmean[i] for i in range(2)] for p in points]
    qs=[[p[i]-qmean[i] for i in range(2)] for p in observations]
    den=sum(x*x+y*y for x,y in ps)
    a=sum(p[0]*q[0]+p[1]*q[1] for p,q in zip(ps,qs))/den
    b=sum(p[0]*q[1]-p[1]*q[0] for p,q in zip(ps,qs))/den
    scale=math.hypot(a,b)
    if scale < 1e-12: raise ValueError('Degenerate correspondence')
    if rigid: a,b=a/scale,b/scale
    fitted_scale=1.0 if rigid else scale
    t=[qmean[0]-a*pmean[0]+b*pmean[1],qmean[1]-b*pmean[0]-a*pmean[1]]
    predicted=[[a*x-b*y+t[0],b*x+a*y+t[1]] for x,y in points]
    errors=[math.dist(p,q) for p,q in zip(predicted,observations)]
    return {'model':'rigid' if rigid else 'similarity','scale':fitted_scale,'rotationDegrees':math.degrees(math.atan2(b,a)),
            'matrix':[[a,-b],[b,a]],'translationMm':t,'predictedMm':predicted,'residualsMm':errors,
            'maxResidualMm':max(errors),'rmsResidualMm':math.sqrt(sum(e*e for e in errors)/3),
            'passesOfflineGeometryGate':.99 <= fitted_scale <= 1.01 and max(errors)<=.08}


def analyze(request):
    board, board_ref=bound(request['board'])
    kicad=fiducials(board);nominal={k:[p[0],-p[1]] for k,p in kicad.items()}; refs=['FID1','FID2','FID3']
    if set(request['reports']) != set(refs): raise ValueError('Exact three report identities required')
    j=request.get('localImageJacobianPixelsPerMm')
    if j is not None:
        if len(j)!=2 or any(len(row)!=2 for row in j) or any(type(v) not in (float,int) or not math.isfinite(v) for row in j for v in row): raise ValueError('Finite 2x2 local Jacobian required')
        determinant=j[0][0]*j[1][1]-j[0][1]*j[1][0]
        if abs(determinant)<1e-9: raise ValueError('Singular image Jacobian')
    samples=[]; session=None; fixed=None
    for ref in refs:
        data, report_ref=bound(request['reports'][ref]);r=json.loads(data)
        if r.get('status')!='completed-camera-survey-awaiting-image-review' or any(r.get(k) is not True for k in ['controllerPositionVerified','independentFirmwareStepVerified']) or r.get('uncertainCompletion') is not False or r.get('error'): raise ValueError('Completed verified survey required')
        _,jvm,config,raw,driver,poses=source.source_snapshot(r);same=(jvm,config);held=tuple(raw[k] for k in ('Z','A','B'))
        if session is not None and (session!=same or fixed!=held): raise ValueError('Session/configuration/ZAB changed')
        session,fixed=same,held
        root=Path(report_ref['path']).parent; image_path=(root/r['afterImages']['top']['path']).resolve()
        if image_path.parent != root: raise ValueError('Image outside report folder')
        image, image_ref=bound(image_path);metric=sweep(image,request['roi'],request['thresholds'],'R')
        selected=[v['selected'] for v in metric['thresholds']]
        if any(s is None or s['touchesRoiEdge'] or s['equalAreaAmbiguity'] for s in selected): raise ValueError('Ambiguous/clipped fiducial component')
        center=[metric['centroidSummary'][k]['median'] for k in ('x','y')]
        target=[metric['geometricImageCenterPixelIndex'][k] for k in ('x','y')];error=[target[i]-center[i] for i in range(2)]
        if math.hypot(*error)>2: raise ValueError('Fiducial more than2 pixels from image center')
        pose=poses['top'];camera=[pose['x'],pose['y']]
        correction=[0.,0.] if j is None else [(j[1][1]*error[0]-j[0][1]*error[1])/determinant,(-j[1][0]*error[0]+j[0][0]*error[1])/determinant]
        samples.append({'reference':ref,'kicadSourceMm':kicad[ref],'nominalMm':nominal[ref],'report':report_ref,'image':image_ref,'cameraMm':camera,'centroidPixelIndex':center,'centerErrorPx':error,'thresholdAnalysis':metric,'localCorrectionMm':correction,'correctedCameraMm':[camera[i]+correction[i] for i in range(2)]})
    points=[s['nominalMm'] for s in samples]
    models={label:{kind:fit(points,[s[key] for s in samples],rigid=kind=='rigid') for kind in ('rigid','similarity')} for label,key in [('uncorrected','cameraMm'),('locallyCorrected','correctedCameraMm')]}
    return {'schema':1,'scope':'offline-three-fiducial-registration-review','board':board_ref,'nominalFrame':{'name':'front-board Cartesian','fromKiCadMatrix':[[1,0],[0,-1]],'meaning':'Explicit Y reflection, consistent positive-Y Gerber/board coordinates'},'parser':bound(PARSER)[1],'samples':samples,'models':models,
            'localImageJacobianPixelsPerMm':j,'session':{'jvmStartMs':session[0],'liveConfigurationSha256':session[1],'fixedZAB':fixed},
            'acceptancePolicy':{'scaleRange':[.99,1.01],'maximumResidualMm':.08,'maximumCenterErrorPx':2},
            'physicalUncertaintyAllowanceMm':.05,'uncertaintyInterpretation':'Review allowance, not a calibrated statistical confidence bound; local image Jacobian and approach repeatability remain provisional.',
            'requiresIndependentPadChecks':True,'machineConfigurationChanged':False,'physicalRegistrationEstablished':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('request',type=Path);p.add_argument('output',type=Path);q=p.parse_args()
    data,provenance=bound(q.request);r=analyze(json.loads(data));r['request']=provenance
    with q.output.open('x') as f:json.dump(r,f,indent=2,allow_nan=False);f.write('\n')
if __name__=='__main__':main()
