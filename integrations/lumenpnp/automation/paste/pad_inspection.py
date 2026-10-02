#!/usr/bin/env python3
"""Deterministic offline paste-image measurements against calibrated CAD pixel polygons.

No registration is inferred here: polygonPx must come from a separately reviewed
camera calibration/registration. Threshold color is explicit and image-specific.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path
from PIL import Image


def _mask_components(mask,w,h):
    seen=bytearray(w*h); comps=[]
    for idx,on in enumerate(mask):
        if not on or seen[idx]: continue
        seen[idx]=1; todo=[idx]; pixels=[]
        while todo:
            n=todo.pop(); pixels.append(n); x=n%w; y=n//w
            for dy in (-1,0,1):
                for dx in (-1,0,1):
                    nx,ny=x+dx,y+dy
                    if (dx or dy) and 0<=nx<w and 0<=ny<h:
                        q=ny*w+nx
                        if mask[q] and not seen[q]: seen[q]=1; todo.append(q)
        comps.append(pixels)
    return comps


def _inside(x,y,poly):
    inside=False; j=len(poly)-1
    for i,(xi,yi) in enumerate(poly):
        xj,yj=poly[j]
        if ((yi>y)!=(yj>y)) and x < (xj-xi)*(y-yi)/(yj-yi)+xi: inside=not inside
        j=i
    return inside


def _recipe_matches(recipe, group_id):
    if not isinstance(recipe,dict) or recipe.get('schema')!=1 or recipe.get('scope')!='reviewed-continuous-line-process-recipe':
        return False
    if recipe.get('validated') is not True or recipe.get('padGroupId')!=group_id or not str(recipe.get('reviewedBy','')).strip():
        return False
    supplied=recipe.get('recipeSha256')
    body={k:v for k,v in recipe.items() if k!='recipeSha256'}
    expected=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return isinstance(supplied,str) and supplied==expected


def inspect_image(image_path, pads, *, paste_rgb, tolerance=35, min_component_pixels=2,
                  row_groups=None, process_recipe=None, roi_margin_px=4):
    """Measure thresholded paste-like pixels in CAD polygons.

    `pads`: list of {id, polygonPx:[[x,y],...]}; coordinates must use image pixels.
    Output is evidence for review, never an authorization or a dose calculation.
    """
    if len(paste_rgb)!=3 or any(not 0<=int(v)<=255 for v in paste_rgb): raise ValueError('paste_rgb must be RGB bytes')
    if tolerance<0 or min_component_pixels<1 or roi_margin_px<0: raise ValueError('invalid threshold, ROI margin, or component size')
    started=time.perf_counter()
    im=Image.open(image_path).convert('RGB'); w,h=im.size
    if not pads: raise ValueError('at least one projected pad is required')
    normalized=[]; seen_ids=set()
    for p in pads:
        poly=p.get('polygonPx')
        if not p.get('id') or not isinstance(poly,list) or len(poly)<3: raise ValueError('each pad needs id and polygonPx')
        points=[(float(x),float(y)) for x,y in poly]
        if any(not math.isfinite(v) for pair in points for v in pair): raise ValueError('non-finite polygon coordinate')
        pid=str(p['id'])
        if pid in seen_ids: raise ValueError(f'duplicate pad ID: {pid}')
        seen_ids.add(pid)
        if any(x<0 or y<0 or x>=w or y>=h for x,y in points): raise ValueError(f'pad polygon outside image: {pid}')
        if abs(sum(points[i][0]*points[(i+1)%len(points)][1]-points[(i+1)%len(points)][0]*points[i][1] for i in range(len(points))))<1e-6:
            raise ValueError(f'degenerate polygon: {pid}')
        normalized.append((pid,points))
    target=tuple(int(v) for v in paste_rgb); sq=tolerance*tolerance
    rx0=max(0,math.floor(min(x for _,p in normalized for x,y in p))-roi_margin_px)
    ry0=max(0,math.floor(min(y for _,p in normalized for x,y in p))-roi_margin_px)
    rx1=min(w,math.ceil(max(x for _,p in normalized for x,y in p))+roi_margin_px)
    ry1=min(h,math.ceil(max(y for _,p in normalized for x,y in p))+roi_margin_px)
    rw,rh=rx1-rx0,ry1-ry0
    crop=im.crop((rx0,ry0,rx1,ry1)); crop_pixels=crop.getdata()
    mask=bytearray(rw*rh)
    for i,(r,g,b) in enumerate(crop_pixels): mask[i]=int((r-target[0])**2+(g-target[1])**2+(b-target[2])**2<=sq)
    raw_comps=[c for c in _mask_components(mask,rw,rh) if len(c)>=min_component_pixels]
    # Discard sub-threshold specks from every reported measurement, not just component labels.
    mask=bytearray(rw*rh)
    for c in raw_comps:
        for i in c: mask[i]=1
    comps=[]
    for c in raw_comps:
        xs=[n%rw+rx0 for n in c]; ys=[n//rw+ry0 for n in c]
        comps.append({'pixels':c,'bboxPx':[min(xs),min(ys),max(xs)+1,max(ys)+1],
                      'aspectRatio':max(max(xs)-min(xs)+1,max(ys)-min(ys)+1)/max(1,min(max(xs)-min(xs)+1,max(ys)-min(ys)+1))})
    pad_masks=[]; results=[]
    for pid,poly in normalized:
        x0=max(rx0,math.floor(min(x for x,y in poly))); x1=min(rx1,math.ceil(max(x for x,y in poly)))
        y0=max(ry0,math.floor(min(y for x,y in poly))); y1=min(ry1,math.ceil(max(y for x,y in poly)))
        inside=[]
        for y in range(y0,y1):
            for x in range(x0,x1):
                if _inside(x+.5,y+.5,poly): inside.append((y-ry0)*rw+(x-rx0))
        area=len(inside); pad_masks.append(set(inside))
        hits=[i for i in inside if mask[i]]; coverage=len(hits)/area if area else 0
        if hits: cx=sum(i%rw+rx0+.5 for i in hits)/len(hits); cy=sum(i//rw+ry0+.5 for i in hits)/len(hits)
        else: cx=cy=None
        bb=[min(x for x,y in poly),min(y for x,y in poly),max(x for x,y in poly),max(y for x,y in poly)]
        diagonal=max(1.0,math.hypot(bb[2]-bb[0],bb[3]-bb[1]))
        alignment=math.exp(-math.hypot(cx-(bb[0]+bb[2])/2,cy-(bb[1]+bb[3])/2)/diagonal) if hits else 0.0
        results.append({'padId':pid,'cadPolygonAreaPx':area,'pasteLikePixels':len(hits),'coverage':coverage,
          'pasteCentroidPx':[cx,cy] if hits else None,'cadCentroidPx':[(bb[0]+bb[2])/2,(bb[1]+bb[3])/2],
          'centroidOffsetPx':[cx-(bb[0]+bb[2])/2,cy-(bb[1]+bb[3])/2] if hits else None,
          'alignmentScore':alignment,
          'status':'detected' if hits else 'not-detected'})
    bridges=[]; component_pad_ids=[]
    for comp in comps:
        ids=[]; component=set(comp['pixels'])
        for (pid,_),pm in zip(normalized,pad_masks):
            if component & pm: ids.append(pid)
        component_pad_ids.append(ids)
        if len(ids)>1:
            bridges.append({'padIds':ids,'componentPixels':len(comp['pixels']),'status':'possible-bridge-review'})
    by_id={r['padId']:r for r in results}
    rows=[]
    for group in row_groups or []:
        ids=list(group.get('padIds',[]))
        if len(ids)<2 or any(pid not in by_id for pid in ids): raise ValueError('row_groups must reference at least two known pad IDs')
        crossing=[c for c,cids in zip(comps,component_pad_ids) if len(set(cids)&set(ids))>1]
        all_detected=all(by_id[pid]['status']=='detected' for pid in ids)
        thin=any(c['aspectRatio']>=3 for c in crossing)
        if thin:
            kind='connected-thin-row-possible-bridge'
        elif all_detected:
            kind='separate-pad-blobs'
        else:
            kind='incomplete-or-unresolved-row'
        recipe_ok=_recipe_matches(process_recipe,group.get('id'))
        rows.append({'id':group.get('id'),'padIds':ids,'classification':kind,
          'cadGroupReviewRequired':True,'continuousLineRecipeValidated':recipe_ok,
          'continuousLineProposalEligible':bool(thin and recipe_ok),
          'reason':'Image shape alone cannot establish paste volume or process validity.'})
    total=sum(r['pasteLikePixels'] for r in results)
    projection={'imageSizePx':[w,h],'pads':[{'id':pid,'polygonPx':[[x,y] for x,y in poly]} for pid,poly in normalized]}
    projection_hash=hashlib.sha256(json.dumps(projection,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'schema':1,'scope':'offline-calibrated-pad-paste-inspection','image':{'path':str(image_path),'widthPx':w,'heightPx':h},
      'projectionSha256':projection_hash,'processingRoiPx':[rx0,ry0,rw,rh],
      'threshold':{'pasteRgb':list(target),'euclideanTolerance':tolerance,'minComponentPixels':min_component_pixels},
      'pads':results,'possibleBridges':bridges,'finePitchRows':rows,'pasteLikeAreaPx':total,
      'processingMs':round((time.perf_counter()-started)*1000,2),
      'status':'measurements-require-operator-review','executionAuthorized':False,
      'limitations':['Requires externally reviewed calibrated image-to-CAD projection.','Color threshold is explicit and must be validated for the image.','Pixel area is not paste volume and does not infer dispense dose.']}


def compare_inspections(before,after):
    """Report pixel-area and bridge changes for paired images with same CAD pad IDs."""
    if before.get('scope')!='offline-calibrated-pad-paste-inspection' or after.get('scope')!=before.get('scope'):
        raise ValueError('expected two pad inspection reports')
    if before.get('threshold')!=after.get('threshold'):
        raise ValueError('before/after thresholds differ')
    if before.get('projectionSha256')!=after.get('projectionSha256'):
        raise ValueError('before/after CAD projection differs')
    if (before.get('image',{}).get('widthPx'),before.get('image',{}).get('heightPx')) != (after.get('image',{}).get('widthPx'),after.get('image',{}).get('heightPx')):
        raise ValueError('before/after image dimensions differ')
    b={p['padId']:p for p in before['pads']}; a={p['padId']:p for p in after['pads']}
    if b.keys()!=a.keys(): raise ValueError('before/after pad identities differ')
    rows=[]
    for pid in sorted(b):
        x,y=b[pid]['pasteLikePixels'],a[pid]['pasteLikePixels']
        rows.append({'padId':pid,'beforePixels':x,'afterPixels':y,'deltaPixels':y-x,
                     'areaRatio':y/x if x else None})
    return {'schema':1,'scope':'offline-before-after-paste-inspection-comparison','pads':rows,
      'beforePossibleBridges':before['possibleBridges'],'afterPossibleBridges':after['possibleBridges'],
      'status':'measurements-require-operator-review','executionAuthorized':False}


def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('image'); ap.add_argument('projected_pads_json')
    ap.add_argument('--paste-rgb',required=True,help='e.g. 180,180,180'); ap.add_argument('--tolerance',type=int,default=35); ap.add_argument('-o','--output',required=True)
    a=ap.parse_args(); pads=json.loads(Path(a.projected_pads_json).read_text()); rgb=tuple(map(int,a.paste_rgb.split(',')))
    Path(a.output).write_text(json.dumps(inspect_image(a.image,pads,paste_rgb=rgb,tolerance=a.tolerance),indent=2)+'\n')


if __name__=='__main__': main()
