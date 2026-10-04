#!/usr/bin/env python3
"""Read-only paired operator image occlusion probe for this blue-lit camera.

The metric is the fraction of baseline bright metal pixels newly dark in the
after image. It is useful for obvious transfer changes, not paste volume,
outside-pad spread, bridge clearance, or an automatic accept/reject decision.
Two central bright components are image candidates, not board pad IDs.
"""
import argparse
import hashlib
from PIL import Image
from pathlib import Path
import json

def components(points):
    unseen=set(points);out=[]
    while unseen:
        seed=unseen.pop();q=[seed];cc=[seed]
        while q:
            x,y=q.pop()
            for p in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if p in unseen:unseen.remove(p);q.append(p);cc.append(p)
        out.append(cc)
    return out

def inspect(before_path,after_path,red_delta=70):
    a=Image.open(before_path).convert('RGB');b=Image.open(after_path).convert('RGB');assert a.size==b.size==(1920,1080)
    aa=a.load();bb=b.load();cx,cy=960,540
    roi=(cx-190,cy-220,cx+190,cy+220)
    bright={(x,y) for y in range(roi[1],roi[3]) for x in range(roi[0],roi[2]) if aa[x,y][0]>150 and aa[x,y][1]>180 and aa[x,y][2]>180}
    cc=[c for c in components(bright) if len(c)>1200]
    cc.sort(key=lambda c:(sum((x-cx)**2+(y-cy)**2 for x,y in c)/len(c)))
    if len(cc)<2:raise ValueError('Fewer than two central bright baseline pads')
    pads=cc[:2]
    # The middle silkscreen above the pads is unchanged; use it for pixel shift.
    # Red channel is maximally separated between white metal and blue board.
    best=(float('inf'),0,0)
    for dy in range(-8,9):
        for dx in range(-8,9):
            sad=0
            for y in range(315,450,5):
                for x in range(790,1110,5):
                    sad+=abs(aa[x,y][0]-bb[x+dx,y+dy][0])
            if sad<best[0]:best=(sad,dx,dy)
    _,dx,dy=best
    out=[]
    for c in pads:
        dark=sum(1 for x,y in c if aa[x,y][0]-bb[x+dx,y+dy][0]>red_delta and bb[x+dx,y+dy][0]<150)
        out.append({'center':[round(sum(x for x,y in c)/len(c),1),round(sum(y for x,y in c)/len(c),1)],'bbox':[min(x for x,y in c),min(y for x,y in c),max(x for x,y in c),max(y for x,y in c)],'baselineBrightAreaPx':len(c),'newDarkAreaPx':dark,'newDarkFraction':round(dark/len(c),3)})
    return {'alignmentDxDy':[dx,dy],'pads':out}

def report_images(path):
    report=json.loads(path.read_text())
    if report.get('status')!='completed-awaiting-image-review':
        raise ValueError('Terminal successful image report required: '+str(path))
    images={r['reference']:Path(r['image']) for r in report['records']}
    if len(images)!=len(report['records']):
        raise ValueError('Duplicate reference in image report: '+str(path))
    return report,images


def compare(baseline,after,refs=None,red_delta=70):
    before_report,before=report_images(baseline)
    after_report,after_images=report_images(after)
    selected=refs or sorted(before.keys()&after_images.keys())
    if not selected or len(selected)!=len(set(selected)):
        raise ValueError('Explicit nonempty unique reference selection required')
    results=[]
    for ref in selected:
        if ref not in before or ref not in after_images:
            raise ValueError('Missing paired image for '+ref)
        a,b=before[ref],after_images[ref]
        metrics=inspect(a,b,red_delta)
        results.append({'reference':ref,'baselineImage':str(a),'baselineSha256':hashlib.sha256(a.read_bytes()).hexdigest(),
                        'afterImage':str(b),'afterSha256':hashlib.sha256(b.read_bytes()).hexdigest(),**metrics})
    return {'schema':1,'metric':'new-dark-fraction-of-baseline-bright-pad-candidates',
            'interpretation':'image occlusion only; no volume, spread, bridge, or automatic pass/fail inference',
            'baselineReport':str(baseline),'baselineReportId':before_report['id'],
            'afterReport':str(after),'afterReportId':after_report['id'],
            'redDeltaThreshold':red_delta,'results':results}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline',type=Path,required=True)
    ap.add_argument('--after',type=Path,required=True)
    ap.add_argument('--refs',nargs='+')
    ap.add_argument('--red-delta',type=int,default=70,choices=(50,70,90))
    ap.add_argument('--output',type=Path)
    args=ap.parse_args()
    result=compare(args.baseline,args.after,args.refs,args.red_delta)
    data=json.dumps(result,indent=2)+'\n'
    if args.output:
        if args.output.exists():raise FileExistsError('Refuse to overwrite '+str(args.output))
        args.output.write_text(data)
    else:print(data,end='')


if __name__=='__main__':
    main()
