#!/usr/bin/env python3
"""Offline conventional-CV availability scan of bare-copper pad regions.

Inputs are a separately reviewed CAD-to-machine registration and a map from pad
IDs to completed camera reports. Images are measured only; this tool never
connects to OpenPnP, changes registration, or authorizes placement/dispensing.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw

PX_PER_MM_X = 1.0 / 0.01068376
PX_PER_MM_Y = 1.0 / 0.01072961


def _load_job(registration):
    board = registration.get('board', {})
    path = Path(board.get('path', '')).resolve(strict=True)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != board.get('sha256'):
        raise ValueError('board file hash differs from reviewed registration')
    module_path = Path(__file__).with_name('job_planner.py')
    spec = importlib.util.spec_from_file_location('paste_job_planner', module_path)
    planner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(planner)
    job = planner.plan_board(path)
    if job.get('board', {}).get('sha256') != digest:
        raise ValueError('planner board hash mismatch')
    return job


def _machine_xy(design_xy, transform):
    matrix = transform['matrix']; tx, ty = transform['translationMm']
    x, y = design_xy
    return [matrix[0][0]*x + matrix[0][1]*y + tx,
            matrix[1][0]*x + matrix[1][1]*y + ty]


def _pixel_xy(machine_xy, camera_xy, width, height, sx, sy):
    # These saved, upright images were checked against the known R2.1/R2.2
    # diagonal pad pair: machine +X maps to pixel -X and machine +Y to pixel +Y.
    # The optical center is pixel-centered and each axis uses its calibrated scale.
    return [(width-1)/2 - (machine_xy[0]-camera_xy[0])/sx,
            (height-1)/2 + (machine_xy[1]-camera_xy[1])/sy]


def _pad_polygon(pad, transform, camera_xy, width, height, sx, sy):
    cx, cy = pad['centerMm']; w, h = pad['sizeMm']; theta=math.radians(float(pad.get('rotationDeg',0)))
    c,s=math.cos(theta),math.sin(theta)
    corners=[]
    for dx,dy in [(-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2)]:
        design=[cx+c*dx-s*dy,cy+s*dx+c*dy]
        corners.append(_pixel_xy(_machine_xy(design,transform),camera_xy,width,height,sx,sy))
    center=_pixel_xy(_machine_xy([cx,cy],transform),camera_xy,width,height,sx,sy)
    return corners,center


def _selected_pad_ids(camera_report_map,pads):
    targets=set(); ignored=[]
    for pad_id in camera_report_map:
        if pad_id not in pads:
            ignored.append(pad_id); continue
        reference=pads[pad_id]['reference']
        ids=[pid for pid,pad in pads.items() if pad.get('reference')==reference]
        if reference=='R30': ids=[pid for pid in ids if pid=='R30.2']
        targets.update(ids)
    return sorted(targets),sorted(ignored)


def plan_camera_view_set(registration, camera_report_map, *, job=None, margin_px=40,
                         scale_x_mm_per_px=0.01068376, scale_y_mm_per_px=0.01072961):
    """Greedy deterministic set cover over already recorded camera centers only."""
    if margin_px<0: raise ValueError('margin_px must be nonnegative')
    if registration.get('scope')!='offline-native-fresh-ftp-two-fiducial-transform-with-third-point-check' or registration.get('acceptance',{}).get('passed') is not True:
        raise ValueError('accepted fresh registration required')
    job=job or _load_job(registration)
    if job.get('board',{}).get('sha256')!=registration.get('board',{}).get('sha256'): raise ValueError('job and registration board hashes differ')
    pads={p['id']:p for p in job.get('pads',[])}; selected,ignored=_selected_pad_ids(camera_report_map,pads)
    transform=registration['transformFromFID1FID2']; candidates=[]; seen=set()
    for map_id,value in sorted(camera_report_map.items()):
        report_path=Path(value['path'] if isinstance(value,dict) else value).resolve(strict=True)
        report=json.loads(report_path.read_text(encoding='utf-8'))
        pose=report.get('afterQuerySnapshot',{}).get('nativePoses',{}).get('top'); image=report.get('afterImages',{}).get('top')
        if report.get('status') not in ('completed-camera-survey-awaiting-image-review','completed-contiguous-air-batch-awaiting-observation','completed-contiguous-batch-awaiting-observation') or not isinstance(pose,dict) or not isinstance(image,dict):
            continue
        key=(round(float(pose['x']),5),round(float(pose['y']),5))
        if key in seen: continue
        seen.add(key); width=int(image['width']); height=int(image['height']); cam=[float(pose['x']),float(pose['y'])]
        covered=[]; centers={}
        for pid in selected:
            polygon,center=_pad_polygon(pads[pid],transform,cam,width,height,scale_x_mm_per_px,scale_y_mm_per_px)
            if all(margin_px<=x<width-margin_px and margin_px<=y<height-margin_px for x,y in polygon):
                covered.append(pid); centers[pid]=center
        candidates.append({'id':map_id,'reportEvidencePath':str(report_path),'reportSha256':hashlib.sha256(report_path.read_bytes()).hexdigest(),
          'nativeTopCameraXYMm':cam,'imageSizePx':[width,height],'coveredPadIds':covered,'projectedPadCentersPx':centers})
    uncovered=set(selected); chosen=[]
    while uncovered:
        ranked=sorted(candidates,key=lambda c:(-len(uncovered.intersection(c['coveredPadIds'])),c['id']))
        best=ranked[0] if ranked else None
        gain=uncovered.intersection(best['coveredPadIds']) if best else set()
        if not gain: break
        chosen.append({'order':len(chosen),'candidateId':best['id'],'reportEvidencePath':best['reportEvidencePath'],
          'reportSha256':best['reportSha256'],'nativeTopCameraXYMm':best['nativeTopCameraXYMm'],
          'imageSizePx':best['imageSizePx'],'coveredPadIds':sorted(gain),'projectedPadCentersPx':{k:best['projectedPadCentersPx'][k] for k in sorted(gain)}})
        uncovered-=gain
    return {'schema':1,'scope':'offline-registered-camera-view-set-cover','boardSha256':job['board']['sha256'],
      'registrationSha256':hashlib.sha256(json.dumps(registration,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
      'scaleMmPerPx':{'x':scale_x_mm_per_px,'y':scale_y_mm_per_px},'marginPx':margin_px,
      'candidateCount':len(candidates),'candidateCentersAreExistingReportsOnly':True,
      'selectedPadIds':selected,'ignoredMapEntries':ignored,'viewCount':len(chosen),'views':chosen,
      'uncoveredPadIds':sorted(uncovered),'status':'complete-review-only' if not uncovered else 'incomplete-review-only',
      'motionAuthorized':False}


def _inside(x,y,poly):
    inside=False; j=len(poly)-1
    for i,(xi,yi) in enumerate(poly):
        xj,yj=poly[j]
        if ((yi>y)!=(yj>y)) and x < (xj-xi)*(y-yi)/(yj-yi)+xi: inside=not inside
        j=i
    return inside


def _bright(rgb, minimum, max_spread):
    r,g,b=rgb
    return min(r,g,b)>=minimum and max(r,g,b)-min(r,g,b)<=max_spread


def scan(registration, camera_report_map, *, output_dir, job=None,
         scale_x_mm_per_px=0.01068376, scale_y_mm_per_px=0.01072961,
         bright_min=165, max_rgb_spread=70):
    if not (math.isfinite(scale_x_mm_per_px) and scale_x_mm_per_px>0 and math.isfinite(scale_y_mm_per_px) and scale_y_mm_per_px>0):
        raise ValueError('camera scales must be positive finite mm/px values')
    if not 0<=bright_min<=255 or not 0<=max_rgb_spread<=255:
        raise ValueError('RGB thresholds must be byte values')
    if registration.get('scope')!='offline-native-fresh-ftp-two-fiducial-transform-with-third-point-check' or registration.get('acceptance',{}).get('passed') is not True:
        raise ValueError('accepted, reviewed fresh registration required')
    if registration.get('physicalRegistrationEstablished') is not False or registration.get('executionReady') is not False:
        raise ValueError('registration must remain analysis-only')
    job=job or _load_job(registration)
    if job.get('board',{}).get('sha256')!=registration.get('board',{}).get('sha256'):
        raise ValueError('job and registration must bind the same board hash')
    pads={p['id']:p for p in job.get('pads',[])}
    transform=registration['transformFromFID1FID2']
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=False)
    results=[]; targets={}
    # A center-position report commonly frames the selected pad and its mate.
    # Reuse that same real capture for both pads on the same resistor footprint,
    # while deliberately excluding R30.1: the supplied map's R30.2 target is
    # the unpasted pad and R30.1 is outside this bare-pad review set.
    selected,ignored_ids=_selected_pad_ids(camera_report_map,pads)
    ignored=[{'id':pid,'reason':'camera-map entry is not a CAD pad reference'} for pid in ignored_ids]
    for target_id in selected:
        owner=next((key for key in camera_report_map if key in pads and pads[key]['reference']==pads[target_id]['reference']),None)
        if owner is not None: targets[target_id]=camera_report_map[owner]
    for pad_id, report_value in sorted(targets.items()):
        report_path=Path(report_value['path'] if isinstance(report_value,dict) else report_value).resolve(strict=True)
        report=json.loads(report_path.read_text(encoding='utf-8'))
        if report.get('status') not in ('completed-camera-survey-awaiting-image-review','completed-contiguous-air-batch-awaiting-observation','completed-contiguous-batch-awaiting-observation'):
            raise ValueError(f'{pad_id} report is not a completed camera capture')
        pose=report.get('afterQuerySnapshot',{}).get('nativePoses',{}).get('top')
        image_ref=report.get('afterImages',{}).get('top')
        if not isinstance(pose,dict) or not isinstance(image_ref,dict) or not image_ref.get('path'):
            raise ValueError(f'{pad_id} report lacks actual post-capture top-camera pose/image')
        image_path=(report_path.parent/image_ref['path']).resolve(strict=True)
        im=Image.open(image_path).convert('RGB'); width,height=im.size
        if image_ref.get('width')!=width or image_ref.get('height')!=height:
            raise ValueError(f'{pad_id} image dimensions disagree with camera report')
        camera_xy=[float(pose['x']),float(pose['y'])]
        polygon,center=_pad_polygon(pads[pad_id],transform,camera_xy,width,height,
                                    scale_x_mm_per_px,scale_y_mm_per_px)
        if any(not (0<=x<width and 0<=y<height) for x,y in polygon):
            raise ValueError(f'{pad_id} expected CAD polygon leaves captured image')
        x0=max(0,math.floor(min(p[0] for p in polygon))); x1=min(width,math.ceil(max(p[0] for p in polygon)))
        y0=max(0,math.floor(min(p[1] for p in polygon))); y1=min(height,math.ceil(max(p[1] for p in polygon)))
        pixels=im.load(); selected=[]; bright=[]
        for y in range(y0,y1):
            for x in range(x0,x1):
                if _inside(x+.5,y+.5,polygon):
                    selected.append((x,y))
                    if _bright(pixels[x,y],bright_min,max_rgb_spread): bright.append((x,y))
        mask=Image.new('L',(width,height),0); md=ImageDraw.Draw(mask)
        for x,y in bright: md.point((x,y),fill=255)
        mask_path=out/(pad_id.replace('/','_')+'-mask.png'); mask.save(mask_path)
        centroid=[sum(p[0]+.5 for p in bright)/len(bright),sum(p[1]+.5 for p in bright)/len(bright)] if bright else None
        offset_px=[centroid[0]-center[0],centroid[1]-center[1]] if centroid else None
        offset_mm=[offset_px[0]*scale_x_mm_per_px,offset_px[1]*scale_y_mm_per_px] if offset_px else None
        bright_area_mm2=len(bright)*scale_x_mm_per_px*scale_y_mm_per_px
        results.append({'padId':pad_id,'cameraReportPath':str(report_path),
          'cameraReportSha256':hashlib.sha256(report_path.read_bytes()).hexdigest(),
          'imagePath':str(image_path),'imageSha256':hashlib.sha256(image_path.read_bytes()).hexdigest(),
          'cameraTopNativeXYMm':camera_xy,'expectedCenterPx':center,'expectedPolygonPx':polygon,
          'cadSizeMm':pads[pad_id]['sizeMm'],'brightThreshold':{'minRgb':bright_min,'maxSpread':max_rgb_spread},
          'rawMaskPath':str(mask_path.resolve()),'polygonPixels':len(selected),'brightPixels':len(bright),
          'brightFraction':len(bright)/len(selected) if selected else 0.0,
          'brightAreaMm2':bright_area_mm2,'equivalentCircleDiameterMm':math.sqrt(4*bright_area_mm2/math.pi),
          'brightCentroidPx':centroid,'centroidErrorPx':offset_px,'centroidErrorMm':offset_mm,
          'quality':'low-confidence-manual-review','status':'measurement-only','autoAuthorize':False})
    registration_sha=hashlib.sha256(json.dumps(registration,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    projection_model={'boardSha256':job['board']['sha256'],'matrix':transform['matrix'],
      'translationMm':transform['translationMm'],'cameraScaleMmPerPx':{'x':scale_x_mm_per_px,'y':scale_y_mm_per_px},
      'orientation':'upright-180','machineToPixelSigns':{'x':'negative','y':'positive'}}
    projection_model_sha=hashlib.sha256(json.dumps(projection_model,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    camera_map_sha=hashlib.sha256(json.dumps(camera_report_map,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    report={'schema':1,'scope':'offline-registered-bare-copper-availability-scan',
      'boardSha256':job['board']['sha256'],'registrationSha256':registration_sha,'projectionModelSha256':projection_model_sha,'cameraReportMapSha256':camera_map_sha,
      'cameraScaleMmPerPx':{'x':scale_x_mm_per_px,'y':scale_y_mm_per_px},
      'orientation':'upright-180','machineToPixelSigns':{'x':'negative','y':'positive','verificationPadPair':['R2.1','R2.2']},
      'threshold':'bright low-chroma pixels clipped to transformed CAD pad polygon',
      'measurements':results,'ignoredMapEntries':ignored,'status':'low-confidence-review-only','autoAuthorize':False,
      'limitations':['Uses supplied registration and camera scale; neither is re-estimated here.',
        'Brightness is only a bare-copper availability cue and can be confounded by glare, finish, residue, or exposure.',
        'Pixel masks and centroid errors do not establish pickup success, paste quality, or placement authorization.']}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


def compare_scans(before, after):
    if before.get('scope')!='offline-registered-bare-copper-availability-scan' or after.get('scope')!=before.get('scope'):
        raise ValueError('expected two registered pad-availability scans')
    for key in ('boardSha256','projectionModelSha256','cameraScaleMmPerPx','orientation','machineToPixelSigns','threshold'):
        if before.get(key)!=after.get(key): raise ValueError(f'before/after scans differ in {key}')
    b={m['padId']:m for m in before.get('measurements',[])}; a={m['padId']:m for m in after.get('measurements',[])}
    if not b or b.keys()!=a.keys(): raise ValueError('before/after scans must contain the same nonempty pad set')
    rows=[]
    for pid in sorted(b):
        x,y=b[pid],a[pid]
        rows.append({'padId':pid,'beforeBrightFraction':x['brightFraction'],'afterBrightFraction':y['brightFraction'],
          'brightFractionDelta':y['brightFraction']-x['brightFraction'],
          'beforeBrightAreaMm2':x['brightAreaMm2'],'afterBrightAreaMm2':y['brightAreaMm2'],
          'brightAreaDeltaMm2':y['brightAreaMm2']-x['brightAreaMm2'],
          'beforeEquivalentCircleDiameterMm':x['equivalentCircleDiameterMm'],
          'afterEquivalentCircleDiameterMm':y['equivalentCircleDiameterMm'],
          'equivalentCircleDiameterDeltaMm':y['equivalentCircleDiameterMm']-x['equivalentCircleDiameterMm'],
          'beforeCentroidErrorMm':x['centroidErrorMm'],'afterCentroidErrorMm':y['centroidErrorMm'],
          'pasteCentroidDisplacementFromBareCopperMm':([y['centroidErrorMm'][0]-x['centroidErrorMm'][0],y['centroidErrorMm'][1]-x['centroidErrorMm'][1]] if x.get('centroidErrorMm') and y.get('centroidErrorMm') else None),
          'beforeImagePath':x['imagePath'],'afterImagePath':y['imagePath']})
    return {'schema':1,'scope':'offline-before-after-pad-availability-comparison','boardSha256':before['boardSha256'],
      'projectionModelSha256':before['projectionModelSha256'],'pads':rows,'status':'low-confidence-review-only','autoAuthorize':False}


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--registration',required=True); p.add_argument('--camera-map',required=True); p.add_argument('--output-dir',required=True); p.add_argument('--compare-before')
    p.add_argument('--scale-x',type=float,default=0.01068376); p.add_argument('--scale-y',type=float,default=0.01072961)
    p.add_argument('--bright-min',type=int,default=165); p.add_argument('--max-rgb-spread',type=int,default=70)
    a=p.parse_args(); reg=json.loads(Path(a.registration).read_text()); mapping=json.loads(Path(a.camera_map).read_text())
    report=scan(reg,mapping,output_dir=a.output_dir,scale_x_mm_per_px=a.scale_x,scale_y_mm_per_px=a.scale_y,bright_min=a.bright_min,max_rgb_spread=a.max_rgb_spread)
    if a.compare_before:
        before=json.loads(Path(a.compare_before).read_text())
        diff=compare_scans(before,report)
        Path(a.output_dir,'comparison.json').write_text(json.dumps(diff,indent=2)+'\n',encoding='utf-8')
    view_plan=plan_camera_view_set(reg,mapping,scale_x_mm_per_px=a.scale_x,scale_y_mm_per_px=a.scale_y)
    Path(a.output_dir,'camera-view-set-plan.json').write_text(json.dumps(view_plan,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(Path(a.output_dir).resolve()),'count':len(report['measurements']),'status':report['status']}))

if __name__=='__main__': main()
