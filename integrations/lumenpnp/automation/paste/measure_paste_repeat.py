#!/usr/bin/env python3
"""Conventional before/after coverage measurements; no dose or volume inference.
Images must be upright captures of the same camera pose, exposure and board.
CLI reads explicit CAD-pad ROIs. Translation is estimated from unchanged top strip.
"""
import argparse, hashlib, json, math
from pathlib import Path
from PIL import Image

def measure(before_path, after_path, pads, mm_per_pixel):
    before=Image.open(before_path).convert('RGB');after=Image.open(after_path).convert('RGB')
    if before.size!=after.size:raise ValueError('Image dimensions differ')
    w,h=before.size; bp=before.load();ap=after.load()
    # Small translation only, using an explicitly unaffected top reference strip.
    candidates=[]
    for dy in range(-5,6):
        for dx in range(-5,6):
            errors=[abs(bp[x,y][1]-ap[x+dx,y+dy][1]) for y in range(20,min(200,h-10),8) for x in range(20,w-10,12)]
            candidates.append((sum(errors)/len(errors),dx,dy))
    error,dx,dy=min(candidates)
    if abs(dx)==5 or abs(dy)==5 or error>15:raise ValueError('Reference strip registration unresolved')
    result=[]
    for pad in pads:
        x0,y0,x1,y1=map(int,pad['roiPx'])
        if not(5<=x0<x1<w-5 and 5<=y0<y1<h-5):raise ValueError('ROI outside image')
        copper=[];covered=[];changed=[]
        for y in range(y0,y1):
            for x in range(x0,x1):
                b=bp[x,y];a=ap[x+dx,y+dy]
                if min(b)>210:
                    copper.append((x,y))
                    if b[1]-a[1]>70:covered.append((x,y))
                if b[1]-a[1]>35:changed.append((x,y))
        if not copper:raise ValueError('No bright bare pad reference in ROI')
        bbox=[min(x for x,y in changed),min(y for x,y in changed),max(x for x,y in changed)+1,max(y for x,y in changed)+1] if changed else None
        area=len(changed)*mm_per_pixel[0]*mm_per_pixel[1]
        result.append({'padId':pad['id'],'roiPx':pad['roiPx'],'brightBarePadPixels':len(copper),'coveredBrightPadPixels':len(covered),'brightPadCoverageFraction':len(covered)/len(copper),'changedAreaPx':len(changed),'approxChangedAreaMm2':area,'equivalentChangedDiameterMm':2*math.sqrt(area/math.pi),'changedBoundingBoxPx':bbox})
    areas=[p['approxChangedAreaMm2'] for p in result];mean=sum(areas)/len(areas)
    ev=lambda p:{'path':str(Path(p).resolve()),'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()}
    return {'schema':1,'scope':'conventional-before-after-paste-coverage','before':ev(before_path),'after':ev(after_path),'registration':{'translationPx':[dx,dy],'referenceStripGreenMeanAbsoluteError':error},'pads':result,'areaCoefficientOfVariation':math.sqrt(sum((a-mean)**2 for a in areas)/len(areas))/mean if mean else None,'physicalAcceptanceEstablished':False,'volumeMeasured':False,'limitations':['Thresholded 2D image change includes lighting/outline effects; not solder volume.','Bright-pad coverage measures visible bare pad replacement only.','Top reference strip must remain unchanged; no rotation or scale correction.','No bridge or reflow acceptance inferred.']}

def main():
    p=argparse.ArgumentParser();p.add_argument('before');p.add_argument('after');p.add_argument('rois');p.add_argument('output');a=p.parse_args();q=json.loads(Path(a.rois).read_text());r=measure(a.before,a.after,q['pads'],q['mmPerPixel']);Path(a.output).write_text(json.dumps(r,indent=2)+'\n')
if __name__=='__main__':main()
