#!/usr/bin/env python3
"""Deterministic, offline KiCad-to-paste-job planner. No machine I/O."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path


def _tokens(text):
    # KiCad comments begin with semicolon only outside a quoted string.
    out=[]; i=0
    while i<len(text):
        c=text[i]
        if c==';':
            while i<len(text) and text[i] not in '\r\n': i+=1
        elif c.isspace(): i+=1
        elif c in '()': out.append(c); i+=1
        elif c=='"':
            start=i; i+=1; escaped=False
            while i<len(text):
                if escaped: escaped=False
                elif text[i]=='\\': escaped=True
                elif text[i]=='"': i+=1; break
                i+=1
            else: raise ValueError('Unterminated quoted KiCad string')
            out.append(text[start:i])
        else:
            start=i
            while i<len(text) and not text[i].isspace() and text[i] not in '();': i+=1
            out.append(text[start:i])
    return out


def sexpr(text):
    stack, roots = [], []
    for token in _tokens(text):
        if token == '(':
            node = []
            (stack[-1] if stack else roots).append(node)
            stack.append(node)
        elif token == ')':
            if not stack: raise ValueError('Unbalanced KiCad expression')
            stack.pop()
        else:
            if not stack: raise ValueError('Atom outside KiCad expression')
            stack[-1].append(json.loads(token) if token.startswith('"') else token)
    if stack or len(roots) != 1 or not roots[0] or roots[0][0] != 'kicad_pcb':
        raise ValueError('Expected one complete kicad_pcb expression')
    return roots[0]


def _children(node, tag):
    return [x for x in node if isinstance(x, list) and x and x[0] == tag]


def _one(node, tag, default=None):
    vals = _children(node, tag)
    if len(vals) > 1: raise ValueError(f'Duplicate {tag} field')
    return vals[0] if vals else default


def _num(v):
    n = float(v)
    if not math.isfinite(n): raise ValueError('Non-finite board coordinate')
    return n


def _xy(node, tag='at'):
    v = _one(node, tag)
    if v is None or len(v) < 3: raise ValueError(f'Missing {tag} coordinate')
    return _num(v[1]), _num(v[2]), _num(v[3]) if len(v) > 3 else 0.0


def _rotate(x, y, deg):
    r = math.radians(deg); return x*math.cos(r)-y*math.sin(r), x*math.sin(r)+y*math.cos(r)


def _shape_area(kind, w, h, ratio=None):
    if kind == 'circle': return math.pi*(min(w,h)/2)**2
    if kind == 'rect': return w*h
    if kind == 'oval':
        a,b=max(w,h),min(w,h); return math.pi*(b/2)**2+(a-b)*b
    if kind == 'roundrect' and ratio is not None:
        r=min(w,h)*ratio
        return w*h-(4-math.pi)*r*r
    return None


def _paste_override(node):
    """True when explicit nonzero pad/footprint paste margins need rendered geometry."""
    for tag in ('solder_paste_margin','solder_paste_margin_ratio',
                'pad_to_paste_clearance','pad_to_paste_clearance_ratio'):
        field=_one(node,tag)
        if field is not None:
            if len(field)<2 or _num(field[1]) != 0: return True
    return False


def _arc_geometry(start, mid, end):
    """Exact circular arc through KiCad's start/mid/end points in design XY."""
    (ax,ay),(bx,by),(cx,cy)=start,mid,end
    d=2*(ax*(by-cy)+bx*(cy-ay)+cx*(ay-by))
    if abs(d)<1e-10: return None
    aa=ax*ax+ay*ay; bb=bx*bx+by*by; cc=cx*cx+cy*cy
    ox=(aa*(by-cy)+bb*(cy-ay)+cc*(ay-by))/d
    oy=(aa*(cx-bx)+bb*(ax-cx)+cc*(bx-ax))/d
    r=math.hypot(ax-ox,ay-oy)
    a0=math.degrees(math.atan2(ay-oy,ax-ox))%360
    am=math.degrees(math.atan2(by-oy,bx-ox))%360
    a1=math.degrees(math.atan2(cy-oy,cx-ox))%360
    ccw=lambda u,v:(v-u)%360
    sweep=ccw(a0,a1)
    if ccw(a0,am)>sweep+1e-7: sweep-=360
    def on_sweep(a):
        return ccw(a0,a)<=sweep+1e-7 if sweep>=0 else ccw(a,a0)<=-sweep+1e-7
    extrema=[[ox+r*math.cos(math.radians(a)),oy+r*math.sin(math.radians(a))]
             for a in (0,90,180,270) if on_sweep(a)]
    return {'centerMm':[ox,oy],'radiusMm':r,'startAngleDeg':a0,'sweepAngleDeg':sweep,'boundsExtremaMm':extrema}


def _calibrate(volume, calibration):
    if volume is None or not isinstance(calibration, dict): return None
    knots=calibration.get('knots')
    if not isinstance(knots,list) or len(knots)<2: return None
    pts=[]
    for p in knots:
        try: pts.append((_num(p['volumeMm3']),_num(p['degrees'])))
        except (KeyError,TypeError,ValueError): return None
    pts.sort()
    if any(pts[i][0]<=0 or pts[i][1]<0 or pts[i][0]>=pts[i+1][0] or pts[i][1]>=pts[i+1][1] for i in range(len(pts)-1)): return None
    if pts[-1][0]<=0 or pts[-1][1]<0: return None
    for (x0,y0),(x1,y1) in zip(pts,pts[1:]):
        if x0<=volume<=x1: return y0+(volume-x0)*(y1-y0)/(x1-x0)
    return None


def plan_board(path_or_bytes, *, filename=None, side='F.Cu', paste_thickness_mm=None,
               aperture_scaling=1.0, flow_calibration=None):
    """Parse a KiCad board and return a JSON-ready job. CAD XY is X,-Y like KiCad exports."""
    if side not in ('F.Cu','B.Cu'): raise ValueError("side must be 'F.Cu' or 'B.Cu'")
    if isinstance(path_or_bytes,(str,Path)):
        path=Path(path_or_bytes); data=path.read_bytes(); filename=filename or path.name
    else:
        data=bytes(path_or_bytes); filename=filename or 'upload.kicad_pcb'
    thickness=_num(paste_thickness_mm) if paste_thickness_mm is not None else None
    scaling=_num(aperture_scaling)
    if thickness is not None and thickness<=0: raise ValueError('Paste thickness must be positive')
    if scaling<=0: raise ValueError('Aperture scaling must be positive')
    text=data.decode('utf-8-sig'); board=sexpr(text)
    roots={int(n[1]):n[2] for n in _children(board,'net') if len(n)>=3}
    footprints=[]; pads=[]; fids=[]
    paste_layer='F.Paste' if side=='F.Cu' else 'B.Paste'
    for fp in _children(board,'footprint'):
        lay=_one(fp,'layer')
        if lay is None or len(lay)<2 or lay[1] != side: continue
        ref=next((p[2] for p in _children(fp,'property') if len(p)>2 and p[1]=='Reference'),None)
        if not ref: ref=next((p[2] for p in _children(fp,'fp_text') if len(p)>2 and p[1]=='reference'),None)
        ident=fp[1] if len(fp)>1 else ''
        fx,fy,fa=_xy(fp); cx,cy=fx,-fy
        val=next((p[2] for p in _children(fp,'property') if len(p)>2 and p[1]=='Value'),'')
        fp_paste_override=_paste_override(fp)
        item={'reference':ref or '','value':val,'libraryId':ident,'side':side,'centerMm':[cx,cy], 'rotationDeg':fa}
        footprints.append(item)
        if 'fiducial' in (ident+' '+(ref or '')).lower() or (ref or '').upper().startswith('FID'):
            fids.append({'reference':ref or '', 'boardXYmm':[cx,cy], 'source':'KiCad footprint metadata; camera registration still required'})
        for pad in _children(fp,'pad'):
            if len(pad)<4 or pad[2] not in ('smd','connect','thru_hole'): continue
            layers=_one(pad,'layers',[])
            if not layers or paste_layer not in layers[1:]: continue
            px,py,pa=_xy(pad); dx,dy=_rotate(px,-py,fa); x,y=fx+dx,-(fy-dy)
            # pad rotation is defined relative to footprint; bottom-side mirroring is flagged for preview review.
            ptype=pad[3]
            size=_one(pad,'size')
            if size is None or len(size)<3: continue
            w,h=_num(size[1]),_num(size[2])
            if w<=0 or h<=0: raise ValueError(f'Nonpositive pad size at {ref}.{pad[1]}')
            ratio=_one(pad,'roundrect_rratio'); ratio=_num(ratio[1]) if ratio and len(ratio)>1 else None
            if ratio is not None and not 0<ratio<=0.5: raise ValueError(f'Invalid roundrect ratio at {ref}.{pad[1]}')
            paste_override=fp_paste_override or _paste_override(pad)
            area=None if paste_override else _shape_area(ptype,w,h,ratio)
            net=_one(pad,'net'); netid=int(net[1]) if net and len(net)>1 else 0
            volume=area*thickness*scaling if area is not None and paste_thickness_mm is not None else None
            if volume is not None and not math.isfinite(volume): raise ValueError(f'Non-finite paste volume at {ref}.{pad[1]}')
            dose=_calibrate(volume,flow_calibration)
            pads.append({'id':f"{ref or ident}.{pad[1]}",'reference':ref or '', 'padNumber':pad[1],
              'footprint':ident,'side':side,'centerMm':[x,y],'sizeMm':[w,h], 'rotationDeg':pa,
              'shape':ptype,'areaMm2':area,'pasteMarginOverride':paste_override,'netId':netid,'net':roots.get(netid),
              'pasteVolumeMm3':volume,'doseBDegrees':dose,
              'doseStatus':'calibrated' if dose is not None else ('needs-calibration' if volume is not None else 'needs-volume-input'),
              'geometryStatus':'known' if area is not None else ('paste-override-review-required' if paste_override else 'review-required'),
              'bottomSideTransformReviewRequired':side=='B.Cu'})
    pads.sort(key=lambda p:(p['reference'],p['padNumber']))
    # Candidate same-footprint pad pairs below 0.65 mm pitch, retained as separate deposits.
    groups=[]
    byref={}
    for p in pads: byref.setdefault(p['reference'],[]).append(p)
    for ref,ps in byref.items():
        for i,a in enumerate(ps):
            for b in ps[i+1:]:
                dx=b['centerMm'][0]-a['centerMm'][0]; dy=b['centerMm'][1]-a['centerMm'][1]; d=math.hypot(dx,dy)
                if 0 < d < 0.65:
                    groups.append({'reference':ref,'padIds':[a['id'],b['id']],'pitchMm':d,
                      'reviewRequired':True,'lineBridgeRisk':'possible','automation':'individual-pad-deposits-only'})
    coords=[]
    outline=[]; outline_complete=True
    for tag in ('gr_line','gr_rect','gr_poly','gr_circle','gr_arc'):
        for obj in _children(board,tag):
            layer=_one(obj,'layer')
            if not layer or len(layer)<2 or layer[1]!='Edge.Cuts': continue
            geom={'type':tag}
            for coordtag in ('start','end','center','mid'):
                c=_one(obj,coordtag)
                if c and len(c)>=3:
                    xy=[_num(c[1]),-_num(c[2])]; geom[coordtag+'Mm']=xy; coords.append(xy)
            # A circle's bbox includes its full radius, not just the center and endpoint.
            if tag=='gr_circle' and _one(obj,'center') and _one(obj,'end'):
                c=_one(obj,'center'); e=_one(obj,'end')
                radius=math.hypot(_num(e[1])-_num(c[1]),_num(e[2])-_num(c[2]))
                geom['radiusMm']=radius
                coords.extend([[ _num(c[1])-radius, -_num(c[2])-radius],
                               [ _num(c[1])+radius, -_num(c[2])+radius]])
            if tag=='gr_arc':
                pts3=[_one(obj,name) for name in ('start','mid','end')]
                if all(p is not None and len(p)>=3 for p in pts3):
                    arcpts=[[ _num(p[1]),-_num(p[2])] for p in pts3]
                    arc=_arc_geometry(*arcpts)
                    if arc is None:
                        geom['geometryStatus']='review-required-degenerate-arc'; outline_complete=False
                    else:
                        geom.update(arc); geom['geometryStatus']='exact-circular-arc'
                        coords.extend(arc['boundsExtremaMm'])
                else:
                    geom['geometryStatus']='review-required-missing-arc-points'; outline_complete=False
            pts=_one(obj,'pts')
            if pts:
                geom['pointsMm']=[[ _num(p[1]),-_num(p[2])] for p in _children(pts,'xy') if len(p)>2]
                coords.extend(geom['pointsMm'])
            outline.append(geom)
    bounds=[min(p[0] for p in coords),min(p[1] for p in coords),max(p[0] for p in coords),max(p[1] for p in coords)] if coords else None
    return {'schema':1,'scope':'offline-kicad-paste-job','plannerVersion':'1.0.0',
      'board':{'fileName':filename,'sha256':hashlib.sha256(data).hexdigest(),'side':side,'boundsMm':bounds,
        'boundsStatus':'exact-for-parsed-primitives' if outline_complete else 'review-required-incomplete-outline-geometry','outline':outline},
      'footprints':footprints,'pads':pads,'fiducials':fids,'finePitchGroups':groups,
      'pasteModel':{'thicknessMm':thickness,'apertureScaling':scaling,
        'calibrationId':flow_calibration.get('id') if isinstance(flow_calibration,dict) else None,
        'calibrationStatus':'available' if isinstance(flow_calibration,dict) else 'needs-calibration',
        'recipe':'volume = CAD paste aperture area × configured paste thickness × aperture scaling; B degrees require supplied calibration knots'},
      'recipes':{'registration':{'method':'CAD fiducial anchors + camera detection + reviewed registration; no machine transform fabricated','status':'requires-camera-capture-and-review'},
        'inspection':{'method':'per-pad camera capture and conventional image inspection','status':'requires-camera-calibration-and-review'}},
      'requiresReview':True,'executionAuthorized':False}


def write_job_json(job,path):
    Path(path).write_text(json.dumps(job,indent=2,sort_keys=True)+'\n',encoding='utf-8')


def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('board'); ap.add_argument('-o','--output',required=True)
    ap.add_argument('--side',choices=['F.Cu','B.Cu'],default='F.Cu'); ap.add_argument('--paste-thickness-mm',type=float)
    ap.add_argument('--aperture-scaling',type=float,default=1.0); ap.add_argument('--flow-calibration')
    a=ap.parse_args(); cal=json.loads(Path(a.flow_calibration).read_text()) if a.flow_calibration else None
    write_job_json(plan_board(a.board,side=a.side,paste_thickness_mm=a.paste_thickness_mm,aperture_scaling=a.aperture_scaling,flow_calibration=cal),a.output)


if __name__=='__main__': main()
