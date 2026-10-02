#!/usr/bin/env python3
"""Measure 2D deposit image change on CAD-projected bare-pad ROIs.

Uses the existing measure_paste_repeat registration/threshold implementation,
with one ±70 px ROI per CAD pad. This estimates visible 2D change only; it is
not a volume or process acceptance measurement.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('measure_paste_repeat',HERE/'measure_paste_repeat.py')
MEASURE=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MEASURE)


def _read(path):
    p=Path(path).resolve(strict=True); return json.loads(p.read_text(encoding='utf-8')),p


def _pearson(a,b):
    if len(a)<2:return None
    ma=sum(a)/len(a);mb=sum(b)/len(b)
    va=sum((x-ma)**2 for x in a);vb=sum((y-mb)**2 for y in b)
    if not va or not vb:return None
    return sum((x-ma)*(y-mb) for x,y in zip(a,b))/math.sqrt(va*vb)


def _photometric_delta(before,after,roi,translation_px,mm_per_pixel):
    bp=before.load();ap=after.load();w,h=before.size;dx,dy=translation_px
    x0,y0,x1,y1=roi;bare=[];changed=[];covered=[]
    for y in range(y0,y1):
        for x in range(x0,x1):
            if not (0<=x<w and 0<=y<h and 0<=x+dx<w and 0<=y+dy<h): continue
            b=bp[x,y];a=ap[x+dx,y+dy];delta=b[1]-a[1]
            if min(b)>210:
                bare.append((x,y))
                if delta>35: changed.append((x,y))
                if delta>70: covered.append((x,y))
    bc=[sum(x+.5 for x,y in bare)/len(bare),sum(y+.5 for x,y in bare)/len(bare)] if bare else None
    pc=[sum(x+.5 for x,y in changed)/len(changed),sum(y+.5 for x,y in changed)/len(changed)] if changed else None
    shift=[pc[0]-bc[0],pc[1]-bc[1]] if pc and bc else None
    shift_mm=[shift[0]*mm_per_pixel[0],shift[1]*mm_per_pixel[1]] if shift else None
    area=len(changed)*mm_per_pixel[0]*mm_per_pixel[1]
    return {'bareCopperPixels':bare,'changedPixels':changed,'coveredPixels':covered,
      'bareCopperCentroidPx':bc,'changedCentroidPx':pc,'centroidShiftPx':shift,'centroidShiftMm':shift_mm,
      'changedAreaMm2':area,'equivalentDiameterMm':2*math.sqrt(area/math.pi)}


def measure_batch(before_map_path,after_map_path,baseline_scan_path,batch_report_path,output_dir,*,roi_half_px=70,mm_per_pixel=(0.01068376,0.01072961)):
    before_map,bmp=_read(before_map_path); after_map,amp=_read(after_map_path)
    baseline,bsp=_read(baseline_scan_path); batch,brp=_read(batch_report_path)
    if batch.get('status')!='completed-contiguous-batch-awaiting-observation' or batch.get('uncertainCompletion') is not False:
        raise ValueError('exact completed wet batch report required')
    if batch.get('request',{}).get('mode')!='wet': raise ValueError('dose-order binding requires a wet batch')
    if baseline.get('scope')!='offline-registered-bare-copper-availability-scan' or not baseline.get('measurements'):
        raise ValueError('before-image bare-copper projection report required')
    if roi_half_px<45: raise ValueError('ROI half-width must include the complete 0.8x0.95mm pad and deposit')
    base_by_id={m['padId']:m for m in baseline['measurements']}
    target_record=batch['request'].get('ftpTargetRecord',{});targets=target_record.get('pads',[])
    if not targets: raise ValueError('batch must bind reviewed pad targets')
    target_by_id={p['padId']:p for p in targets}
    if not set(target_by_id).issubset(base_by_id): raise ValueError('wet batch contains pads absent from the before projection')
    board_ref=target_record.get('cadEvidence',{})
    if board_ref.get('sha256')!=baseline.get('boardSha256'): raise ValueError('before projection and wet batch CAD hashes differ')
    maprefs={}
    # Reports map a selected pad to its real camera view. The sibling pad uses
    # the same image because both CAD pads lie in the same captured frame.
    for ref in before_map:
        if ref in ('scrap5','tipcheck') or ref not in after_map: continue
        owner=ref.rsplit('.',1)[0]
        for pid in target_by_id:
            if pid.rsplit('.',1)[0]==owner: maprefs[pid]=ref
    if set(maprefs)!=set(target_by_id): raise ValueError('before/after camera maps do not cover all selected batch pads')
    out=Path(output_dir).resolve();out.mkdir(parents=True,exist_ok=False);maskdir=out/'masks';maskdir.mkdir()
    by_view={}
    for pid in target_by_id: by_view.setdefault(base_by_id[pid]['imagePath'],[]).append(pid)
    measured={};view_records=[]
    for before_img,pad_ids in sorted(by_view.items()):
        pad_ids.sort(); first=pad_ids[0]; view_key=maprefs[first]
        before_report_path=Path(base_by_id[first]['cameraReportPath']).resolve(strict=True)
        after_report_path=Path(after_map[view_key]).resolve(strict=True)
        before_report,_=_read(before_report_path);after_report,_=_read(after_report_path)
        bpose=before_report['afterQuerySnapshot']['nativePoses']['top'];apose=after_report['afterQuerySnapshot']['nativePoses']['top']
        if math.hypot(float(bpose['x'])-float(apose['x']),float(bpose['y'])-float(apose['y']))>0.02:
            raise ValueError(f'{view_key}: before/after camera centers differ by more than 0.02mm')
        after_image_ref=after_report.get('afterImages',{}).get('top',{})
        after_img=(after_report_path.parent/after_image_ref['path']).resolve(strict=True)
        rois=[]
        for pid in pad_ids:
            c=base_by_id[pid]['expectedCenterPx'];rois.append({'id':pid,'roiPx':[math.floor(c[0]-roi_half_px),math.floor(c[1]-roi_half_px),math.ceil(c[0]+roi_half_px),math.ceil(c[1]+roi_half_px)]})
        # Call existing conventional before/after registration and ROI measure.
        per_view=MEASURE.measure(before_img,after_img,rois,mm_per_pixel)
        dx,dy=per_view['registration']['translationPx'];before=Image.open(before_img).convert('RGB');after=Image.open(after_img).convert('RGB')
        if before.size!=after.size: raise ValueError('before/after camera image dimensions differ')
        w,h=before.size;bp=before.load();ap=after.load();mask_image=Image.new('L',(w,h),0);md=ImageDraw.Draw(mask_image)
        for p,record in zip(rois,per_view['pads']):
            pid=p['id']
            change=_photometric_delta(before,after,p['roiPx'],(dx,dy),mm_per_pixel)
            bare=change['bareCopperPixels'];changed_on_bare=change['changedPixels'];covered=change['coveredPixels']
            bare_center=change['bareCopperCentroidPx'];paste_center=change['changedCentroidPx']
            shift_px=change['centroidShiftPx'];shift_mm=change['centroidShiftMm'];area_mm2=change['changedAreaMm2']
            mask=Image.new('L',(w,h),0);draw=ImageDraw.Draw(mask)
            for x,y in changed_on_bare:draw.point((x,y),fill=255)
            mask_path=maskdir/(pid.replace('/','_')+'-change.png');mask.save(mask_path)
            target=target_by_id[pid];di=target.get('doseStageIndices',[])
            if len(di)!=1: raise ValueError(f'{pid}: expected one dose stage for order binding')
            stage_index=di[0];stage=batch['request']['previewStages'][stage_index]
            measured[pid]={'padId':pid,'doseStageIndex':stage_index,'doseOrderRank':None,
              'doseDeltaDegrees':stage['targetRaw']['B']-stage['startRaw']['B'],
              'rawPose':target.get('rawPose'),'workRawZ':target.get('rawPose',{}).get('Z'),
              'estimatedGapMm':target.get('surface',{}).get('estimatedGapMm'),
              'gapUncertaintyMm':target.get('surface',{}).get('gapUncertaintyMm'),
              'roiPx':p['roiPx'],'beforeImage':str(Path(before_img).resolve()),'afterImage':str(after_img),
              'beforeCopperCentroidPx':bare_center,'changedPasteCentroidPx':paste_center,
              'pasteCentroidShiftFromBareCopperPx':shift_px,'pasteCentroidShiftFromBareCopperMm':shift_mm,
              'bareCopperPixels':len(bare),'changedPixelsOnBareCopper':len(changed_on_bare),
              'coveredBareCopperPixelsDeltaGt70':len(covered),'coveredBrightPadFraction':len(covered)/len(bare) if bare else None,
              'changedAreaMm2OnBareCopper':area_mm2,
              'equivalentChangedDiameterMmOnBareCopper':2*math.sqrt(area_mm2/math.pi),
              'existingMeasurePasteRepeat':record,'changeMaskPath':str(mask_path.resolve()),
              'status':'2d-photometric-change-review-only','volumeMeasured':False}
        view_records.append({'viewKey':view_key,'beforeImage':str(Path(before_img).resolve()),'afterImage':str(after_img),
          'padIds':pad_ids,'translationPx':[dx,dy],'referenceStripGreenMae':per_view['registration']['referenceStripGreenMeanAbsoluteError']})
    order=sorted(measured,key=lambda pid:measured[pid]['doseStageIndex'])
    for rank,pid in enumerate(order,1):measured[pid]['doseOrderRank']=rank
    rows=[measured[pid] for pid in order]
    sizes=[r['equivalentChangedDiameterMmOnBareCopper'] for r in rows]
    shifts=[math.hypot(*(r['pasteCentroidShiftFromBareCopperMm'] or [0,0])) for r in rows]
    indices=[r['doseOrderRank'] for r in rows]
    bands=[]
    for start in range(0,len(rows),9):
        chunk=rows[start:start+9];diam=[r['equivalentChangedDiameterMmOnBareCopper'] for r in chunk]
        bands.append({'doseOrderRanks':[chunk[0]['doseOrderRank'],chunk[-1]['doseOrderRank']],
          'meanChangedEquivalentDiameterMm':sum(diam)/len(diam),'medianChangedEquivalentDiameterMm':sorted(diam)[len(diam)//2],
          'padIds':[r['padId'] for r in chunk]})
    comparison=target_record.get('retractionComparison',{}); group_summaries=[]
    for group in comparison.get('groups',[]):
        group_rows=[measured[pid] for pid in group.get('padIds',[]) if pid in measured]
        if len(group_rows)!=len(group.get('padIds',[])) or not group_rows: raise ValueError('comparison group pad list does not match measured batch pads')
        diameters=sorted(r['equivalentChangedDiameterMmOnBareCopper'] for r in group_rows)
        areas=sorted(r['changedAreaMm2OnBareCopper'] for r in group_rows)
        shifts=sorted(math.hypot(*(r['pasteCentroidShiftFromBareCopperMm'] or [0,0])) for r in group_rows)
        median=lambda values:(values[(len(values)-1)//2]+values[len(values)//2])/2
        group_summaries.append({'group':group.get('group'),'retractPercent':group.get('retractPercent'),
          'padCount':len(group_rows),'doseOrderRanks':[min(r['doseOrderRank'] for r in group_rows),max(r['doseOrderRank'] for r in group_rows)],
          'medianChangedEquivalentDiameterMm':median(diameters),'minChangedEquivalentDiameterMm':diameters[0],
          'maxChangedEquivalentDiameterMm':diameters[-1],'medianChangedAreaMm2':median(areas),
          'medianCentroidShiftMagnitudeMm':median(shifts),'padIds':[r['padId'] for r in group_rows]})
    request=batch['request']; ev=lambda p:{'path':str(Path(p).resolve()),'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()}
    result={'schema':1,'scope':'offline-ftp-batch-paste-change-selected-pad-roi-analysis',
      'batchEvidence':ev(brp),'beforeCameraMapEvidence':ev(bmp),'afterCameraMapEvidence':ev(amp),'beforeProjectionEvidence':ev(bsp),
      'doseOrderSource':'ftpTargetRecord.pads[].doseStageIndices, ordered by exact previewStages index',
      'padCount':len(rows),'viewCount':len(view_records),'roiHalfWidthPx':roi_half_px,
      'mmPerPixel':list(mm_per_pixel),'wetBatchWorkZRawValues':sorted(set(r['workRawZ'] for r in rows)),
      'estimatedGapMmValues':sorted(set(r['estimatedGapMm'] for r in rows)),
      'gapUncertaintyMmValues':sorted(set(r['gapUncertaintyMm'] for r in rows)),
      'doseOrderTrend':{'pearsonRankVsChangedEquivalentDiameter':_pearson(indices,sizes),
        'pearsonRankVsCentroidShiftMagnitude':_pearson(indices,shifts),
        'ninePadBands':bands,'retractionComparisonGroups':group_summaries,
        'interpretation':'descriptive only; order correlation is not a causal or flow calibration'},
      'perPad':rows,'views':view_records,'status':'low-confidence-2d-review-only',
      'volumeMeasured':False,'autoAuthorize':False,
      'limitations':['Green-channel change thresholded within fixed CAD-centered ±70 px ROIs after only top-strip translation alignment.',
        'Equivalent diameter is a 2D area descriptor, not a paste volume or nozzle dose.',
        'Bare-copper centroid is the before-image bright-pixel centroid; deposit centroid shift is relative to that measured centroid.',
        'Lighting, glare, flux/residue, outline changes and cross-pad spill can affect pixel change.',
        'RawZ/workplane comparison is descriptive; a height error is only a hypothesis and is not inferred causally.']}
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--before-map',required=True);p.add_argument('--after-map',required=True)
    p.add_argument('--before-projection',required=True);p.add_argument('--batch-report',required=True);p.add_argument('--output-dir',required=True)
    p.add_argument('--roi-half-px',type=int,default=70);a=p.parse_args()
    result=measure_batch(a.before_map,a.after_map,a.before_projection,a.batch_report,a.output_dir,roi_half_px=a.roi_half_px)
    print(json.dumps({'output':str(Path(a.output_dir).resolve()),'padCount':result['padCount'],'viewCount':result['viewCount'],'status':result['status']}))

if __name__=='__main__':main()
