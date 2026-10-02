#!/usr/bin/env python3
"""Project offline KiCad pad and line candidates through reviewed image calibration.

This adapter performs deterministic geometry only. It neither estimates registration
from images nor treats a projected proposal as a dispensing recipe.
"""
from __future__ import annotations

import hashlib
import json
import math
import re


def _matrix(projection):
    if not isinstance(projection,dict) or projection.get('schema')!=1 or projection.get('scope')!='reviewed-board-to-image-affine' or projection.get('validated') is not True:
        raise ValueError('A separately reviewed and validated board-to-image projection is required')
    evidence=projection.get('evidence')
    if not isinstance(evidence,dict) or not re.fullmatch(r'[a-f0-9]{64}',str(evidence.get('sha256',''))):
        raise ValueError('Projection evidence SHA-256 is required')
    values=projection.get('matrix')
    if not isinstance(values,list) or len(values)!=2 or any(not isinstance(row,list) or len(row)!=3 for row in values):
        raise ValueError('Projection matrix must be a 2x3 affine transform')
    m=[[float(v) for v in row] for row in values]
    if any(not math.isfinite(v) for row in m for v in row): raise ValueError('Projection matrix must be finite')
    det=m[0][0]*m[1][1]-m[0][1]*m[1][0]
    if abs(det)<1e-12: raise ValueError('Projection matrix must be invertible')
    return m


def _transform(m, point):
    x,y=map(float,point)
    return [m[0][0]*x+m[0][1]*y+m[0][2],m[1][0]*x+m[1][1]*y+m[1][2]]


def _pad_polygon(pad):
    x,y=map(float,pad['centerMm']);w,h=map(float,pad['sizeMm'])
    angle=math.radians(-float(pad.get('rotationDeg',0)))
    c,s=math.cos(angle),math.sin(angle)
    return [[x+dx*c-dy*s,y+dx*s+dy*c] for dx,dy in ((-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2))]


def _convex_hull(points):
    pts=sorted(set((float(x),float(y)) for x,y in points))
    if len(pts)<3: raise ValueError('At least three distinct projected points are required')
    def cross(o,a,b): return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lower=[]
    for p in pts:
        while len(lower)>=2 and cross(lower[-2],lower[-1],p)<=0: lower.pop()
        lower.append(p)
    upper=[]
    for p in reversed(pts):
        while len(upper)>=2 and cross(upper[-2],upper[-1],p)<=0: upper.pop()
        upper.append(p)
    return lower[:-1]+upper[:-1]


def _inside(point,polygon,tol=1e-7):
    x,y=point;sign=0
    for a,b in zip(polygon,polygon[1:]+polygon[:1]):
        cross=(b[0]-a[0])*(y-a[1])-(b[1]-a[1])*(x-a[0])
        if abs(cross)<=tol: continue
        current=1 if cross>0 else -1
        if sign and sign!=current: return False
        sign=current
    return True


def _candidate_corridor(polyline,width,hull):
    if not isinstance(polyline,list) or len(polyline)<2 or width<=0: return False
    for a,b in zip(polyline,polyline[1:]):
        dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
        if length<=0: return False
        nx,ny=-dy/length*width/2,dx/length*width/2
        count=max(1,math.ceil(length/.5))
        for i in range(count+1):
            t=i/count;x=a[0]+dx*t;y=a[1]+dy*t
            if not all(_inside((x+sign*nx,y+sign*ny),hull) for sign in (-1,0,1)): return False
    return True


def build_inspection_projection(job, projection):
    """Return pad polygons, CV row groups and CAD-line corridor checks.

    `projection.matrix` maps planner board millimeters to image pixels as two rows
    `[a,b,c]`, `[d,e,f]`. Its evidence must be independently reviewed.
    """
    m=_matrix(projection);pads=job.get('pads') or [];by_id={p['id']:p for p in pads}
    projected=[];polygons={}
    for pad in pads:
        poly=[_transform(m,p) for p in _pad_polygon(pad)]
        polygons[pad['id']]=poly
        projected.append({'id':pad['id'],'polygonPx':poly})
    groups=[];checks=[]
    for group in job.get('finePitchGroups') or []:
        if group.get('kind')!='fine-pitch-row' or not group.get('proposedLine'): continue
        ids=group['padIds']
        if any(pid not in polygons for pid in ids): raise ValueError('Fine-pitch group references unknown pads')
        hull=_convex_hull([point for pid in ids for point in polygons[pid]])
        line=group['proposedLine'];path=[_transform(m,p) for p in line['polylineMm']]
        nominal=float(line.get('nominalWidthMm') or 0)
        axis=(path[-1][0]-path[0][0],path[-1][1]-path[0][1]);length=math.hypot(*axis)
        if length<=0: raise ValueError('Projected line candidate has zero length')
        nx,ny=-axis[1]/length,axis[0]/length
        origin=line['polylineMm'][0];width_vector=[origin[0]+nx*nominal,origin[1]+ny*nominal]
        width_px=math.dist(_transform(m,origin),_transform(m,width_vector))
        inside=_candidate_corridor(path,width_px,hull)
        status='within-projected-row-envelope-review-required' if inside else 'outside-projected-row-envelope-rejected'
        groups.append({'id':group['id'],'padIds':ids,'cadProposalContainedInProjectedRowEnvelope':inside,
          'lineProposalValidationStatus':status})
        checks.append({'id':group['id'],'padIds':ids,'polylinePx':path,'widthPx':width_px,
          'cadProposalContainedInProjectedRowEnvelope':inside,'status':status,
          'validatedContinuousRecipeRequired':True,'executionAuthorized':False})
    digest=hashlib.sha256(json.dumps({'matrix':m,'pads':projected},sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'schema':1,'scope':'offline-projected-kicad-pad-polygons','projectionEvidenceSha256':projection['evidence']['sha256'],
      'polygonProjectionSha256':digest,'pads':projected,'rowGroups':groups,'lineProposalChecks':checks,
      'executionAuthorized':False,'status':'projected-geometry-requires-review'}
