#!/usr/bin/env python3
"""LAN snapshots of OpenPnP/webcam plus a visible conversation and reply panel.

Run with uv run --with python-xlib --with pillow python automation/scripts/live_viewer.py
--bind LAN_IP. Token lives outside tracked files. No keyboard/mouse or filesystem endpoints.
"""
import argparse
import hashlib
import hmac
import html
import importlib.util
import io
import json
import math
import mimetypes
import os
from pathlib import Path
import secrets
import re
import subprocess
import threading
import time
import uuid
import zipfile
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlsplit
from html.parser import HTMLParser
from PIL import Image
from Xlib import X, display
from chat_mirror import ChatMirror
from message_outbox import MessageOutbox

REPOSITORY = Path(__file__).resolve().parents[2]
_PLANNER_SPEC = importlib.util.spec_from_file_location(
    'lumenpnp_paste_job_planner', REPOSITORY / 'automation/paste/job_planner.py')
paste_job_planner = importlib.util.module_from_spec(_PLANNER_SPEC)
_PLANNER_SPEC.loader.exec_module(paste_job_planner)
_GENERIC_ADAPTER_SPEC = importlib.util.spec_from_file_location(
    'lumenpnp_generic_paste_adapter', REPOSITORY / 'automation/paste/generic_paste_adapter.py')
generic_paste_adapter = importlib.util.module_from_spec(_GENERIC_ADAPTER_SPEC)
_GENERIC_ADAPTER_SPEC.loader.exec_module(generic_paste_adapter)
INSPECTION_DIR = (REPOSITORY / 'automation/evidence/2026-09-23/placement-review-1790317888491').resolve()
EVIDENCE_ROOT = (REPOSITORY / 'automation/evidence').resolve()
_ASSET_MAP_LOCK = threading.Lock()
_ASSET_MAP_SIGNATURE = None
_ASSET_MAP = {}
PASTE_STATUS_PATH = REPOSITORY / 'automation/paste/run-status.json'
PASTE_EVIDENCE_ROOT = REPOSITORY / 'automation/evidence'
R33_RESULT_DIR = (PASTE_EVIDENCE_ROOT / 'manual-home-r33-resume').resolve()
PASTE_STATUSES = {'pending', 'running', 'blocked', 'completed'}
MAX_BOARD_UPLOAD = 32 * 1024 * 1024


def render_paste_job_svg(job):
    """Render a review preview from planner geometry, without implying registration."""
    board = job.get('board') or {}
    bounds = board.get('boundsMm')
    if not isinstance(bounds, list) or len(bounds) != 4:
        bounds = [0.0, 0.0, 10.0, 10.0]
    min_x, min_y, max_x, max_y = map(float, bounds)
    span_x, span_y = max(max_x-min_x, 1e-6), max(max_y-min_y, 1e-6)
    size, margin = 900, 40
    scale = min((size-2*margin)/span_x, (size-2*margin)/span_y)
    width, height = span_x*scale+2*margin, span_y*scale+2*margin
    def xy(point):
        return margin+(float(point[0])-min_x)*scale, margin+(max_y-float(point[1]))*scale
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.1f} {height:.1f}" role="img" aria-label="Offline paste job preview">',
         '<rect width="100%" height="100%" fill="#101720"/>']
    out.append(f'<text x="{margin}" y="22" fill="#e6edf3" font-size="14">{html.escape(str(board.get("fileName") or "KiCad board"))} · {html.escape(str(board.get("side") or "F.Cu"))} · CAD preview (not registered) · {html.escape(str(board.get("boundsStatus") or "bounds review required"))}</text>')
    outline_warnings=[]
    for geom in board.get('outline') or []:
        if str(geom.get('geometryStatus','')).startswith('review-required'):
            outline_warnings.append(str(geom.get('geometryStatus')))
            continue
        if geom.get('type')=='gr_arc' and geom.get('geometryStatus')=='exact-circular-arc':
            cx,cy=xy(geom['centerMm']);radius=float(geom['radiusMm'])*scale
            start=math.radians(float(geom['startAngleDeg']));end=math.radians(float(geom['startAngleDeg'])+float(geom['sweepAngleDeg']))
            x1,y1=cx+radius*math.cos(start),cy-radius*math.sin(start)
            x2,y2=cx+radius*math.cos(end),cy-radius*math.sin(end)
            sweep=float(geom['sweepAngleDeg']);large=1 if abs(sweep)>180 else 0
            sweep_flag=0 if sweep>0 else 1
            out.append(f'<path d="M {x1:.2f} {y1:.2f} A {radius:.2f} {radius:.2f} 0 {large} {sweep_flag} {x2:.2f} {y2:.2f}" fill="none" stroke="#536b81" stroke-width="1"/>')
            continue
        if geom.get('type') == 'gr_circle' and geom.get('centerMm') and geom.get('radiusMm') is not None:
            cx,cy=xy(geom['centerMm']);out.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{float(geom["radiusMm"])*scale:.2f}" fill="none" stroke="#536b81" stroke-width="1"/>')
        points=geom.get('pointsMm')
        if isinstance(points,list) and len(points)>1:
            encoded=' '.join(f'{x:.2f},{y:.2f}' for x,y in (xy(p) for p in points))
            tag='polygon' if geom.get('type')=='gr_poly' else 'polyline'
            out.append(f'<{tag} points="{encoded}" fill="none" stroke="#536b81" stroke-width="1"/>')
        elif geom.get('type')=='gr_rect' and geom.get('startMm') and geom.get('endMm'):
            x1,y1=xy(geom['startMm']);x2,y2=xy(geom['endMm'])
            out.append(f'<rect x="{min(x1,x2):.2f}" y="{min(y1,y2):.2f}" width="{abs(x2-x1):.2f}" height="{abs(y2-y1):.2f}" fill="none" stroke="#536b81" stroke-width="1"/>')
        elif geom.get('startMm') and geom.get('endMm'):
            x1,y1=xy(geom['startMm']);x2,y2=xy(geom['endMm']);out.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="#536b81" stroke-width="1"/>')
    if outline_warnings:
        out.append(f'<text x="{margin}" y="40" fill="#ff9b9b" font-size="12">Outline review required: {html.escape(", ".join(outline_warnings))}</text>')
    for group in job.get('finePitchGroups') or []:
        proposal=group.get('proposedLine') or {};points=proposal.get('polylineMm')
        if group.get('kind')=='fine-pitch-row' and isinstance(points,list) and len(points)>1:
            encoded=' '.join(f'{x:.2f},{y:.2f}' for x,y in (xy(p) for p in points))
            gid=html.escape(str(group.get('id') or 'unidentified row'))
            out.append(f'<polyline points="{encoded}" fill="none" stroke="#ff9b4a" stroke-width="3" stroke-dasharray="8 6" opacity=".9"><title>Unvalidated line candidate · {gid} · individual pad deposits remain the default</title></polyline>')
    for fp in job.get('footprints') or []:
        if fp.get('centerMm'):
            x,y=xy(fp['centerMm']);out.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.2" fill="#7c8da0"/><title>{html.escape(str(fp.get("reference") or fp.get("libraryId") or "footprint"))}</title>')
    for pad in job.get('pads') or []:
        x,y=xy(pad.get('centerMm',[0,0]));sz=pad.get('sizeMm',[.3,.3]);w=max(2.0,float(sz[0])*scale);h=max(2.0,float(sz[1])*scale)
        cls='needs-calibration' if pad.get('doseStatus')!='calibrated' else 'calibrated'
        color='#53d4a3' if cls=='calibrated' else '#e6ae4a'
        out.append(f'<rect x="{x-w/2:.2f}" y="{y-h/2:.2f}" width="{w:.2f}" height="{h:.2f}" transform="rotate({-float(pad.get("rotationDeg",0)):.2f} {x:.2f} {y:.2f})" fill="{color}" fill-opacity=".82" stroke="#101720" stroke-width=".5"><title>{html.escape(str(pad.get("id") or "pad"))} · {html.escape(str(pad.get("doseStatus") or "needs-review"))}</title></rect>')
    for fid in job.get('fiducials') or []:
        if fid.get('boardXYmm'):
            x,y=xy(fid['boardXYmm']);out.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="6" fill="none" stroke="#6db6ff" stroke-width="2"/><text x="{x+8:.2f}" y="{y-6:.2f}" fill="#6db6ff" font-size="10">{html.escape(str(fid.get("reference") or "FID"))}</text>')
    out.append('</svg>')
    return ''.join(out).encode('utf-8')


def render_openpnp_draft(job, part_mappings=None):
    """Create a portable OpenPnP-format board/job draft with every placement disabled."""
    board=job.get('board') or {};bounds=board.get('boundsMm')
    if not isinstance(bounds,list) or len(bounds)!=4 or any(not math.isfinite(float(v)) for v in bounds):
        raise ValueError('OpenPnP draft requires finite parsed board bounds')
    min_x,min_y,max_x,max_y=map(float,bounds);width=max_x-min_x;height=max_y-min_y
    if width<=0 or height<=0: raise ValueError('OpenPnP draft requires nondegenerate board bounds')
    placements=[];seen=set()
    for fp in job.get('footprints') or []:
        ref=str(fp.get('reference') or '')
        if not ref: continue
        if not re.fullmatch(r'[A-Za-z0-9_.+-]{1,80}',ref): raise ValueError('Footprint reference is not a safe OpenPnP placement ID')
        if ref in seen: raise ValueError('Duplicate footprint reference; resolve CAD identities before job export')
        seen.add(ref)
        pos=fp.get('centerMm')
        if not isinstance(pos,list) or len(pos)!=2: raise ValueError('Footprint lacks finite board-local coordinates')
        x,y=map(float,pos);rotation=float(fp.get('rotationDeg',0))
        if not all(math.isfinite(v) for v in (x,y,rotation)): raise ValueError('Footprint placement contains non-finite geometry')
        fid=any(str(f.get('reference') or '')==ref for f in job.get('fiducials') or [])
        kind='Fiducial' if fid else 'Placement'
        attrs={'version':'1.4','side':'Bottom' if board.get('side')=='B.Cu' else 'Top',
          'id':ref,'type':kind,'enabled':'false','rank':'0'}
        if (part_mappings or {}).get(ref):attrs['part-id']=(part_mappings or {})[ref]
        element=ET.Element('placement',attrs)
        ET.SubElement(element,'location',{'units':'Millimeters','x':f'{x-min_x:.6f}','y':f'{y-min_y:.6f}','z':'0.0','rotation':f'{rotation:.6f}'})
        ET.SubElement(element,'error-handling').text='Default';placements.append(element)
    root=ET.Element('openpnp-board',{'version':'1.1','name':'pnp-draft.board.xml'})
    ET.SubElement(root,'dimensions',{'units':'Millimeters','x':f'{width:.6f}','y':f'{height:.6f}','z':'0.0','rotation':'0.0'})
    listing=ET.SubElement(root,'placements');[listing.append(item) for item in placements]
    ET.SubElement(root,'fiducials');ET.SubElement(root,'solder-paste-pads')
    board_xml=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    job_root=ET.Element('openpnp-job',{'version':'2.0'})
    panel=ET.SubElement(job_root,'root-panel',{'version':'2.0'})
    ET.SubElement(panel,'dimensions',{'units':'Millimeters','x':'0.0','y':'0.0','z':'0.0','rotation':'0.0'})
    ET.SubElement(panel,'placements');children=ET.SubElement(panel,'children')
    loc=ET.SubElement(children,'object',{'class':'org.openpnp.model.BoardLocation','side':'Bottom' if board.get('side')=='B.Cu' else 'Top',
      'id':'Brd1','file-name':'pnp-draft.board.xml','check-fiducials':'true','locally-enabled':'false'})
    ET.SubElement(loc,'location',{'units':'Millimeters','x':'0.0','y':'0.0','z':'0.0','rotation':'0.0'})
    ET.SubElement(panel,'pseudo-placement-ids')
    placed=ET.SubElement(job_root,'placed-status-map',{'class':'java.util.HashMap'})
    for item in placements:
        entry=ET.SubElement(placed,'entry');ET.SubElement(entry,'string').text='Brd1⇒'+item.get('id');ET.SubElement(entry,'boolean').text='false'
    ET.SubElement(job_root,'enabled-state-map',{'class':'java.util.HashMap'})
    ET.SubElement(job_root,'check-fiducials-state-map',{'class':'java.util.HashMap'})
    ET.SubElement(job_root,'error-handling-state-map',{'class':'java.util.HashMap'})
    ET.SubElement(job_root,'error-handling').text='Alert'
    job_xml=ET.tostring(job_root,encoding='utf-8',xml_declaration=True)
    return {'boardXml':board_xml,'jobXml':job_xml,'placementCount':len(placements),
      'unmappedCount':len(placements),'allPlacementsDisabled':True,'boardLocallyEnabled':False,
      'mappingStatus':'parts-packages-feed assignments missing; all placements disabled',
      'executionAuthorized':False}


def render_generic_target_svg(prepared):
    """Plot review-authorized target coordinates in machine XY, without dispatch."""
    targets=prepared.get('individualDotTargets') or []
    if not targets:return b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 120"><text x="20" y="60">No generic target preview: preparation requirements are incomplete.</text></svg>'
    xs=[float(t['machineXYMm'][0]) for t in targets];ys=[float(t['machineXYMm'][1]) for t in targets]
    minx,maxx=min(xs),max(xs);miny,maxy=min(ys),max(ys);sx=max(maxx-minx,1e-6);sy=max(maxy-miny,1e-6);scale=min(700/sx,700/sy)
    out=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 800" role="img" aria-label="Offline registered paste targets">',
         '<rect width="800" height="800" fill="#101720"/>','<text x="20" y="26" fill="#e6edf3">Reviewed target XY · offline preview only · no machine dispatch</text>']
    for target in targets:
        x=50+(float(target['machineXYMm'][0])-minx)*scale;y=750-(float(target['machineXYMm'][1])-miny)*scale
        label=html.escape(str(target.get('padId','pad')))
        out.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="#e6ae4a"><title>{label} · {target.get("doseDegrees")} degrees · {target.get("rawZMm")} mm raw Z</title></circle><text x="{x+5:.2f}" y="{y-5:.2f}" fill="#c7d5e2" font-size="8">{label}</text>')
    out.append('</svg>');return ''.join(out).encode()


def openpnp_catalog_snapshot(config_dir=None, backups_dir=None):
    """Read configured part/package IDs and latest pure model feeder snapshot."""
    config_dir=Path(config_dir or (Path.home()/'.openpnp2'))
    parts_root=ET.parse(config_dir/'parts.xml').getroot()
    packages_root=ET.parse(config_dir/'packages.xml').getroot()
    packages={str(item.get('id')) for item in packages_root.findall('package') if item.get('id')}
    parts=[]
    for item in parts_root.findall('part'):
        part_id=item.get('id');package_id=item.get('package-id')
        if part_id and package_id and package_id in packages:parts.append({'id':part_id,'packageId':package_id})
    snapshot=None
    backups_dir=Path(backups_dir or (REPOSITORY/'.local-machine-backups'))
    candidates=sorted(backups_dir.glob('paste-live-model-state-*/report.json'),key=lambda p:p.parent.name,reverse=True)
    for candidate in candidates:
        try:
            report=json.loads(candidate.read_text(encoding='utf-8'))
            if report.get('scope')=='pure-model-state-no-controller-access' and isinstance(report.get('feeders'),list):
                snapshot={'time':report.get('time'),'jvmStartMs':report.get('jvmStartMs'),
                  'configurationSha256':report.get('liveConfigurationSha256'),
                  'feeders':[{'id':f.get('id'),'name':f.get('name'),'className':f.get('className'),
                    'enabled':f.get('enabled'),'partId':f.get('partId'),'configuredLocation':f.get('configuredLocation')}
                    for f in report['feeders'] if isinstance(f,dict)]}
                break
        except (OSError,ValueError,TypeError):continue
    return {'parts':sorted(parts,key=lambda item:(item['packageId'],item['id'])),
      'packages':sorted(packages),'feederSnapshot':snapshot,
      'catalogScope':'saved OpenPnP parts/packages configuration; feeder data is configured-model snapshot only',
      'physicalFeederReadiness':'unknown'}


def save_openpnp_mapping(job_dir, mappings, config_dir=None, backups_dir=None):
    """Bind manually chosen known part IDs to references; keep every placement disabled."""
    if not isinstance(mappings,dict) or len(mappings)>10000:raise ValueError('Expected a bounded placement-to-part mapping object.')
    job_dir=Path(job_dir).resolve(strict=True)
    job=json.loads((job_dir/'job.json').read_text(encoding='utf-8'))
    refs={str(fp.get('reference')) for fp in job.get('footprints') or [] if fp.get('reference')}
    catalog=openpnp_catalog_snapshot(config_dir,backups_dir)
    part_ids={part['id'] for part in catalog['parts']}
    cleaned={}
    for ref,part_id in mappings.items():
        if ref not in refs or not isinstance(part_id,str) or part_id not in part_ids:
            raise ValueError('Mapping must use an uploaded footprint reference and a configured catalog part ID.')
        cleaned[ref]=part_id
    draft=render_openpnp_draft(job,cleaned)
    for filename,content in (('pnp-draft.board.xml',draft['boardXml']),('pnp-draft.job.xml',draft['jobXml'])):
        tmp=job_dir/(filename+'.tmp');tmp.write_bytes(content);os.chmod(tmp,0o600);tmp.replace(job_dir/filename)
    saved={'schema':1,'scope':'manual-configured-part-mapping-review-only','mappings':cleaned,
      'catalogPartCount':len(catalog['parts']),'feederSnapshotTime':(catalog.get('feederSnapshot') or {}).get('time'),
      'physicalFeederReadiness':'unknown','allPlacementsDisabled':True,'executionAuthorized':False}
    dest=job_dir/'mapping.json';tmp=job_dir/'mapping.json.tmp';tmp.write_text(json.dumps(saved,indent=2,sort_keys=True)+'\n');os.chmod(tmp,0o600);tmp.replace(dest)
    return saved


def parse_paste_job_multipart(content_type, body):
    """Read only the expected board/options fields from one bounded multipart body."""
    from email.parser import BytesParser
    from email.policy import default
    message=BytesParser(policy=default).parsebytes(
        b'MIME-Version: 1.0\r\nContent-Type: '+content_type.encode('ascii','strict')+b'\r\n\r\n'+body)
    if not message.is_multipart(): raise ValueError('Expected multipart form data.')
    fields={}
    for part in message.iter_parts():
        if part.get_content_disposition()!='form-data': raise ValueError('Malformed multipart form part.')
        name=part.get_param('name',header='content-disposition')
        if not name or name not in ('board','side','pasteThicknessMm','apertureScaling','flowCalibration'):
            raise ValueError('Unexpected upload field.')
        if name in fields: raise ValueError('Duplicate upload field: '+name)
        payload=part.get_payload(decode=True) or b''
        if name!='board' and len(payload)>64*1024: raise ValueError('Planner options must be at most 64 KiB each.')
        if name=='board' and part.get_content_type().lower() not in ('application/octet-stream','application/vnd.kicad.pcb','text/plain','application/x-kicad-pcb'):
            raise ValueError('Board file MIME type is not a supported KiCad board type.')
        if name=='flowCalibration' and part.get_content_type().lower() not in ('application/json','application/octet-stream','text/plain'):
            raise ValueError('Flow calibration must be uploaded as JSON.')
        fields[name]=(part.get_filename(),payload)
    filename,board=fields.get('board',(None,b''))
    if not filename or not filename.lower().endswith('.kicad_pcb') or not board:
        raise ValueError('Choose a non-empty .kicad_pcb board file.')
    if len(board)>MAX_BOARD_UPLOAD: raise ValueError('Board upload exceeds 32 MiB.')
    def field(name, default=None):
        item=fields.get(name)
        return item[1].decode('utf-8').strip() if item else default
    thickness=field('pasteThicknessMm')
    scaling=field('apertureScaling','1')
    calibration=field('flowCalibration')
    try:
        options={'filename':Path(filename).name,'side':field('side','F.Cu'),
                 'paste_thickness_mm':float(thickness) if thickness else None,
                 'aperture_scaling':float(scaling),
                 'flow_calibration':json.loads(calibration) if calibration else None}
    except (ValueError,TypeError,json.JSONDecodeError) as exc:
        raise ValueError('Thickness, aperture scaling, or flow calibration is invalid.') from exc
    return board,options


def build_saved_paste_job(board_bytes, options, jobs_dir):
    """Plan a board and atomically save only deterministic derived artifacts."""
    job=paste_job_planner.plan_board(board_bytes,**options)
    encoded=json.dumps(job,indent=2,sort_keys=True,allow_nan=False).encode('utf-8')+b'\n'
    job_id=hashlib.sha256(encoded).hexdigest()
    preview=render_paste_job_svg(job)
    openpnp=render_openpnp_draft(job)
    generic_preview=generic_paste_adapter.prepare_generic_job(job,job_id,{})
    root=Path(jobs_dir);root.mkdir(mode=0o700,parents=True,exist_ok=True)
    directory=root/job_id;directory.mkdir(mode=0o700,exist_ok=True)
    pads=job.get('pads') or [];model=job.get('pasteModel') or {}
    counts={status:sum(1 for pad in pads if pad.get('doseStatus')==status) for status in ('calibrated','candidate-unverified-flow-model','needs-calibration','needs-volume-input')}
    groups=job.get('finePitchGroups') or []
    readiness={'schema':1,'scope':'offline-kicad-paste-job-readiness','jobId':job_id,
      'executionAuthorized':False,'stages':[
        {'id':'cad-plan','status':'complete','detail':'Board parsed; saved plan and CAD preview are bound to the uploaded board SHA-256.'},
        {'id':'geometry-review','status':'required','artifacts':['reviewed-pad-map.json'],'detail':'Review pad identities, mask apertures, fine-pitch bridge risk, bottom-side transform, and fiducials.'},
        {'id':'flow-calibration','status':'required',
         'artifacts':['measured-flow-calibration.json','paste-thickness-review.json','flow-model-review.json'],
         'detail':f"Candidate model provides estimates for {counts['calibrated']+counts['candidate-unverified-flow-model']} pads; uploaded knots count as unverified absent a measured-evidence binding. {counts['needs-calibration']} pads lack model estimates; {counts['needs-volume-input']} need thickness/volume inputs."},
        {'id':'board-registration','status':'required','artifacts':['same-session-fiducial-registration-report.json','camera-tip-offset-review.json'],'detail':'Acquire and review fiducials through the existing OpenPnP owner; CAD coordinates are not machine coordinates.'},
        {'id':'machine-session','status':'required','artifacts':['same-session-position-barrier.json','measured-profile.json','both-head-clearance-review.json'],'detail':'Verify installation, N2 exclusion, axis semantics, live configuration, and supervised clearances.'},
        {'id':'native-openpnp-job','status':'blocked','artifacts':['registered-native-job.json','detached-native-preview.json'],'detail':'The offline plan is not an OpenPnP job and cannot be dispatched.'}
      ]}
    readiness_bytes=json.dumps(readiness,indent=2,sort_keys=True,allow_nan=False).encode('utf-8')+b'\n'
    for name,data in (('job.json',encoded),('preview.svg',preview),
                      ('pnp-draft.board.xml',openpnp['boardXml']),('pnp-draft.job.xml',openpnp['jobXml']),
                      ('generic-preview.json',(json.dumps(generic_preview,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()),
                      ('generic-target-preview.svg',render_generic_target_svg(generic_preview))):
        destination=directory/name;temporary=directory/(name+'.tmp')
        temporary.write_bytes(data);os.chmod(temporary,0o600);temporary.replace(destination)
    destination=directory/'readiness.json';temporary=directory/'readiness.json.tmp';temporary.write_bytes(readiness_bytes);os.chmod(temporary,0o600);temporary.replace(destination)
    gates=[
      'Home / calibrate: this viewer has no registered machine action. Use the existing OpenPnP owner only after the active session, N2 quarantine, both-head clearance, axis semantics, and supervised homing envelope are verified.',
      'Start paste: this saved CAD plan is not a registered native OpenPnP job. Board registration, current tip/profile measurements, same-session position barrier, clearance review, and native preview are still required.',
      'PnP handoff: placement registration and a reviewed OpenPnP placement job are not created by this paste planner.',
      'Review every pad geometry and fiducial; inspect fine-pitch groups individually. Software planning does not establish physical alignment or paste quality.'
    ]
    return {'jobId':job_id,'fileName':job['board']['fileName'],'side':job['board']['side'],
      'padCount':len(pads),'footprintCount':len(job.get('footprints') or []),'placementReferences':[str(fp.get('reference')) for fp in job.get('footprints') or [] if fp.get('reference')],'fiducialCount':len(job.get('fiducials') or []),
      'finePitchCount':len(groups),'finePitchGroups':[{'id':g.get('id'),'reference':g.get('reference'),'kind':g.get('kind'),
        'padIds':g.get('padIds'),'pitchMm':g.get('pitchMm'),'gapMm':g.get('gapMm'),'lineBridgeRisk':g.get('lineBridgeRisk'),
        'depositStrategy':g.get('depositStrategy'),'lineWidthMm':(g.get('proposedLine') or {}).get('nominalWidthMm'),
        'theoreticalVolumeBasedWidthMm':(g.get('proposedLine') or {}).get('theoreticalVolumeBasedWidthMm'),
        'targetVolumeMm3':(g.get('proposedLine') or {}).get('targetVolumeMm3'),'componentPads':g.get('componentPads',[]),
        'requiredRecipe':g.get('continuousLineProcessRecipeRequired',False)} for g in groups],
      'boundsMm':job['board'].get('boundsMm'),
      'calibrationStatus':model.get('calibrationStatus','needs-calibration'),
      'calibrationModelSupplied':model.get('calibrationStatus')!='needs-calibration',
      'estimatedDosePadCount':counts['calibrated']+counts['candidate-unverified-flow-model'],
      'unverifiedModelDoseCount':counts['candidate-unverified-flow-model'],
      'needsCalibrationPadCount':counts['needs-calibration'],'needsVolumePadCount':counts['needs-volume-input'],
      'componentRecipes':[{'padId':p.get('id'),'footprint':p.get('reference'),'kind':(p.get('depositProposal') or {}).get('kind'),
        'targetVolumeMm3':p.get('pasteVolumeMm3'),'doseBDegrees':p.get('doseBDegrees'),'doseStatus':p.get('doseStatus'),
        'theoreticalVolumeBasedLengthMm':(p.get('depositProposal') or {}).get('theoreticalVolumeBasedLengthMm'),
        'theoryStatus':(p.get('depositProposal') or {}).get('theoryStatus')} for p in pads],
      'executionAuthorized':False,'executionGates':gates,
      'jobUrl':'/paste-jobs/'+job_id,'previewUrl':'/paste-jobs/'+job_id+'/preview.svg',
      'readinessUrl':'/paste-jobs/'+job_id+'/readiness.json','reviewBundleUrl':'/paste-jobs/'+job_id+'/review-bundle.zip',
      'openpnpDraftUrl':'/paste-jobs/'+job_id+'/openpnp-draft.zip',
      'genericPrepareUrl':'/paste-jobs/'+job_id+'/generic-prepare',
      'genericPreviewUrl':'/paste-jobs/'+job_id+'/generic-preview.json',
      'openpnpDraft':{k:v for k,v in openpnp.items() if k not in ('boardXml','jobXml')}}


def r33_repeat_result():
    """Display-safe summary from the fixed, reviewed R33 observation and CV files."""
    report=json.loads((R33_RESULT_DIR/'repeat-observation.json').read_text(encoding='utf-8'))
    if report.get('scope')!='R33-recipe-four-pad-repeat-observation':
        raise ValueError('Unexpected observation scope.')
    measurements=[]
    for name in ('R19-cv-measurements.json','R18-cv-measurements.json'):
        data=json.loads((R33_RESULT_DIR/name).read_text(encoding='utf-8'))
        if data.get('scope')!='conventional-before-after-paste-coverage':
            raise ValueError('Unexpected CV measurement scope.')
        measurements.extend(data.get('pads') or [])
    values=[p for p in measurements if isinstance(p,dict)]
    coverage=[float(p['brightPadCoverageFraction'])*100 for p in values]
    diameter=[float(p['equivalentChangedDiameterMm']) for p in values]
    return {
      'status':str(report.get('status')),
      'executionSeconds':float(report['executionSeconds']),
      'padCount':len(report.get('pads') or []),
      'padIds':[str(v) for v in report.get('pads') or []],
      'boardProgress':{'touched':int(report['boardProgress']['resistorPadsTouched']),
                       'total':int(report['boardProgress']['resistorPadsTotal']),
                       'priorMixedQualityDepositsRemain':bool(report['boardProgress']['priorMixedQualityDepositsRemain'])},
      'physicalAcceptanceEstablished':bool(report.get('physicalAcceptanceEstablished')),
      'coveragePercentRange':[round(min(coverage),1),round(max(coverage),1)] if coverage else None,
      'equivalentChangedDiameterMmRange':[round(min(diameter),2),round(max(diameter),2)] if diameter else None,
      'measurementMeaning':'Conventional image-change area expressed as equivalent 2D diameter; this is not paste volume.',
      'imageUrls':{'R19.1':'/paste-results/latest/image/R19.1','R18.1':'/paste-results/latest/image/R18.1'}
    }


def known_r33_service_status(jobs_dir):
    """Bind and observe the fixed, already-consumed R33 native request; never dispatch it."""
    from importlib.util import module_from_spec, spec_from_file_location
    path=REPOSITORY/'automation/paste/job_service.py'
    spec=spec_from_file_location('lumen_paste_job_service',path)
    module=module_from_spec(spec);spec.loader.exec_module(module)
    service=module.PasteJobService(jobs_dir=jobs_dir,root=REPOSITORY)
    board_path=REPOSITORY/'pnp/pcb/ftp/ftp.kicad_pcb'
    prepared=R33_RESULT_DIR/'r33-repeat/authored/prepared/native'
    plan=service.plan_upload(board_path.read_bytes(),{'filename':board_path.name,'side':'F.Cu'})
    descriptor=service.commissioning_descriptor(plan['jobId'],prepared)
    state=descriptor['status']
    report=state.get('report') or {}
    preview=state.get('preview') or {}
    return {'jobId':descriptor['jobId'],'preparedId':descriptor['preparedId'],
      'action':descriptor['action'],'stage':state.get('stage'),
      'boardSha256':state.get('boardSha256'), 'executionAuthorized':False,
      'reportStatus':report.get('status'),'controllerPositionVerified':report.get('controllerPositionVerified'),
      'uncertainCompletion':report.get('uncertainCompletion'),
      'nativePreviewPassed':preview.get('passed'),'photos':[{'view':p.get('view'),'name':p.get('name')} for p in state.get('photos',[])],
      'detail':'Read-only descriptor for the existing R33 commissioning request. It will only be observed; this status route does not start, preview, or replay machine work.'}


def _trusted_active_report(path):
    """Load only a canonical report in the approved batch evidence directory."""
    if not isinstance(path, str):
        return None
    match = re.fullmatch(
        re.escape(str(REPOSITORY)) +
        r'/automation/evidence/paste-contiguous-batch-([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/report\.json',
        path)
    if not match:
        return None
    try:
        root = PASTE_EVIDENCE_ROOT.resolve(strict=True)
        candidate = Path(path)
        resolved = candidate.resolve(strict=True)
        if (resolved != candidate or resolved.parent.parent != root
                or resolved.parent.name != 'paste-contiguous-batch-' + match.group(1)
                or resolved.name != 'report.json' or not resolved.is_file()):
            return None
        report = json.loads(resolved.read_text(encoding='utf-8'))
        if not isinstance(report, dict) or report.get('id') != match.group(1):
            return None
        return report, resolved.stat().st_mtime
    except (OSError, RuntimeError, ValueError, TypeError):
        return None


def _active_report_progress(report):
    """Return display-safe state for a live motion report, or None for previews."""
    if report.get('motionSubmitted') is not True:
        return None
    request = report.get('request')
    stages = report.get('stages')
    if not isinstance(request, dict) or not isinstance(stages, list):
        return None
    planned = request.get('previewStages')
    total = len(planned) if isinstance(planned, list) else 0
    verified = sum(1 for stage in stages
                   if isinstance(stage, dict) and stage.get('verified') is True)
    current_pad = None
    target = next((stage for stage in reversed(stages)
                   if isinstance(stage, dict) and isinstance(stage.get('targetRaw'), dict)), None)
    ftp = request.get('ftpTargetRecord')
    pads = ftp.get('pads') if isinstance(ftp, dict) else None
    if target and isinstance(pads, list):
        xy = target['targetRaw']
        try:
            x, y = float(xy['X']), float(xy['Y'])
            matches = [p.get('padId') for p in pads if isinstance(p, dict)
                       and isinstance(p.get('rawPose'), dict)
                       and abs(float(p['rawPose']['X']) - x) <= 0.005
                       and abs(float(p['rawPose']['Y']) - y) <= 0.005
                       and isinstance(p.get('padId'), str)]
            if len(matches) == 1:
                current_pad = matches[0]
        except (KeyError, TypeError, ValueError):
            current_pad = None
    report_status = report.get('status')
    if (report_status in ('completed-contiguous-air-batch-awaiting-observation',
                          'completed-contiguous-batch-awaiting-observation')
            and total > 0 and verified == total):
        status = 'completed'
        message = (f'Dispensing script: verified stages {verified}/{total}; '
                   'awaiting image inspection after completion')
    elif (report.get('transportUncertain') is True
          or (isinstance(report_status, str) and
              (report_status.startswith('failed') or report_status.startswith('blocked')))):
        status = 'blocked'
        message = f'Dispensing script: verified stages {verified}/{total}; report requires review'
    else:
        status = 'running'
        message = f'Dispensing script: verified stages {verified}/{total}'
        if current_pad:
            message += f'; current pad {current_pad}'
    return {'status': status, 'currentPad': current_pad, 'message': message}


CURRENT_NATIVE_BATCH_ID = '7cdffa63-b208-4204-8671-2dc341115b12'
CURRENT_NATIVE_BATCH_DIR = (PASTE_EVIDENCE_ROOT /
    ('paste-contiguous-batch-' + CURRENT_NATIVE_BATCH_ID)).resolve()
CURRENT_NATIVE_PREPARED_DIR = (REPOSITORY /
    'automation/evidence/manual-home-r33-resume/whole-remainder2/authored/prepared/native').resolve()
CURRENT_NATIVE_GALLERY = (PASTE_EVIDENCE_ROOT /
    'manual-home-r33-resume/after-whole-pad-gallery.jpg').resolve()


def current_native_batch_status():
    """Read the fixed 35-pad request and its saved report; never dispatch work."""
    report_path = CURRENT_NATIVE_BATCH_DIR / 'report.json'
    if report_path.resolve(strict=True) != report_path or not report_path.is_file():
        raise ValueError('Native report path is not canonical.')
    report = json.loads(report_path.read_text(encoding='utf-8'))
    request = report.get('request') if isinstance(report, dict) else None
    if (not isinstance(request, dict) or request.get('id') != CURRENT_NATIVE_BATCH_ID
            or request.get('scope') != 'contiguous-native-ftp-selected-pads-up-to-40'
            or request.get('enabled') is not False
            or not isinstance(report, dict) or report.get('id') != CURRENT_NATIVE_BATCH_ID
            or report.get('motionSubmitted') is not True):
        raise ValueError('Fixed native batch evidence did not match.')
    stages = report.get('stages')
    planned = request.get('previewStages')
    ftp = request.get('ftpTargetRecord')
    pads = ftp.get('pads') if isinstance(ftp, dict) else None
    if not isinstance(stages, list) or not isinstance(planned, list) or not isinstance(pads, list):
        raise ValueError('Native batch evidence is incomplete.')
    done = {s.get('index') for s in stages if isinstance(s, dict)
            and s.get('verified') is True and s.get('nativeMotionCompletionReported') is True}
    verified_count = len(done)
    completed_pads = sum(1 for p in pads if isinstance(p, dict)
                         and isinstance(p.get('liftStageIndex'), int) and p['liftStageIndex'] in done)
    unfinished = next((p for p in pads if isinstance(p, dict)
                       and isinstance(p.get('liftStageIndex'), int) and p['liftStageIndex'] not in done), None)
    status = str(report.get('status') or 'unknown')
    if status.startswith('completed') and verified_count == len(planned):
        state = 'completed'
    elif status.startswith(('failed', 'blocked', 'cancelled', 'stopped')) or report.get('transportUncertain') is True:
        state = 'blocked'
    else:
        state = 'running'
    result = {'id': CURRENT_NATIVE_BATCH_ID, 'status': state, 'reportStatus': status,
      'verifiedStages': verified_count, 'totalStages': len(planned),
      'completedPads': completed_pads, 'totalPads': len(pads),
      'currentPad': unfinished.get('padId') if unfinished else None,
      'controllerPositionVerified': report.get('controllerPositionVerified'),
      'updatedAt': (stages[-1].get('finishedAt') or stages[-1].get('startedAt')) if stages else report.get('startedAt'),
      'executionAuthorized': False,
      'detail': 'Read-only status from the fixed native request and saved execution report.'}
    images = report.get('afterImages')
    result['imageUrls'] = {view: f'/paste-results/current-native/image/{view}'
                           for view in ('top', 'bottom')
                           if isinstance(images, dict) and isinstance(images.get(view), dict)
                           and isinstance(images[view].get('path'), str)}
    return result


def paste_status():
    """Read the coordinator's public progress fields; never trigger any work."""
    try:
        value = json.loads(PASTE_STATUS_PATH.read_text(encoding='utf-8'))
        if not isinstance(value, dict):
            raise ValueError('status must be an object')
        status = value.get('status')
        if status not in PASTE_STATUSES:
            raise ValueError('invalid status')
        result = {
            'phase': str(value.get('phase') or ''),
            'currentPad': value.get('currentPad'),
            'completedPads': value.get('completedPads', 0),
            'totalPads': value.get('totalPads', 0),
            'message': str(value.get('message') or ''),
            'updatedAt': str(value.get('updatedAt') or ''),
            'status': status,
        }
        active = _trusted_active_report(value.get('activeReport'))
        if active:
            report, report_mtime = active
            progress = _active_report_progress(report)
            if progress:
                result.update(progress)
                from datetime import datetime, timezone
                result['updatedAt'] = datetime.fromtimestamp(report_mtime, timezone.utc).isoformat()
        return result
    except FileNotFoundError:
        return {'phase': 'waiting', 'currentPad': None, 'completedPads': 0,
                'totalPads': 0, 'message': 'Paste run has not started.',
                'updatedAt': '', 'status': 'pending'}


class _InspectionRefs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        self.urls.extend(value for key, value in attrs if key.lower() in ('href', 'src') and value)


def inspection_asset_map():
    """Cache references from the generated page, admitting only files within evidence trees."""
    global _ASSET_MAP_SIGNATURE, _ASSET_MAP
    report_path = INSPECTION_DIR / 'index.html'
    stat = report_path.stat()
    signature = (stat.st_mtime_ns, stat.st_size)
    with _ASSET_MAP_LOCK:
        if signature == _ASSET_MAP_SIGNATURE:
            return _ASSET_MAP
        report = report_path.read_text(encoding='utf-8')
        refs = _InspectionRefs()
        refs.feed(report)
        allowed = {}
        for reference in refs.urls:
            parts = urlsplit(html.unescape(reference))
            path = unquote(parts.path)
            if parts.scheme or parts.netloc or not path or path.startswith('/') or '\\' in path or '\x00' in path:
                continue
            try:
                source = (INSPECTION_DIR / path).resolve(strict=True)
            except (OSError, RuntimeError):
                continue
            if source.is_file() and (source.is_relative_to(INSPECTION_DIR) or source.is_relative_to(EVIDENCE_ROOT)):
                allowed[path] = source
        _ASSET_MAP_SIGNATURE, _ASSET_MAP = signature, allowed
        return _ASSET_MAP


def resolve_inspection_asset(name):
    """Resolve only a local reference present in the generated page."""
    if not isinstance(name, str) or not name or len(name) > 2048 or '\x00' in name or '\\' in name:
        return None
    name = unquote(name)
    if name.startswith('/') or name not in inspection_asset_map():
        return None
    return inspection_asset_map()[name]


def inspection_html():
    """Serve the fixed report with local references routed through its authenticated asset endpoint."""
    source = (INSPECTION_DIR / 'index.html').read_text(encoding='utf-8')
    pattern = re.compile(r'(?P<prefix>\b(?:href|src)\s*=\s*)(?P<quote>["\'])(?P<url>[^"\']*)(?P=quote)', re.I)

    def replace(match):
        url = html.unescape(match.group('url'))
        parts = urlsplit(url)
        path = unquote(parts.path)
        if parts.scheme or parts.netloc or not path:
            return match.group(0)
        if resolve_inspection_asset(path) is None:
            return match.group(0)
        routed = '/inspection/asset?file=' + quote(path, safe='')
        return f'{match.group("prefix")}{match.group("quote")}{routed}{match.group("quote")}'

    return pattern.sub(replace, source).encode('utf-8')


def validate_public_origin(value):
    """Accept only a bare HTTP(S) origin; it is compared literally to Origin."""
    if value is None:
        return None
    try:
        parsed = urlsplit(value)
        # Accessing .port validates that the port is numeric and in range.
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f'invalid public origin: {exc}') from exc
    if (parsed.scheme not in ('http', 'https') or not parsed.netloc or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.path or parsed.query or parsed.fragment
            or any(character.isspace() for character in value)
            or parsed.netloc.endswith(':') or port == 0):
        raise argparse.ArgumentTypeError('public origin must be only an http:// or https:// origin (no path, query, fragment, or user info)')
    return value


def expected_request_origin(public_origin, host_header):
    """Use the configured external origin, or preserve direct-LAN behavior."""
    return public_origin or ('http://' + host_header)

PAGE = '''<!doctype html><meta name="viewport" content="width=device-width"><title>LumenPnP live view</title>
<style>body{background:#101720;color:#e6edf3;font:16px system-ui;margin:20px}header{display:flex;justify-content:space-between}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(450px,1fr));gap:16px}article{background:#1d2733;padding:12px;border-radius:10px}img{width:100%;cursor:zoom-in}small{color:#9bb1c8}h2{font-size:18px}#status{color:#9bb1c8}#paste-progress{margin:12px 0;max-width:900px}#paste-progress p{margin:6px 0}@media(max-width:500px){main{display:block}}</style>
<header><h1>LumenPnP live view</h1><p>Private viewer · 1 frame/sec</p><p><a id="inspection-report" href="/inspection">Placement inspection report</a></p></header>
<article id="unlock-panel" hidden><h2>Unlock private dashboard</h2><p>Open the private viewer link with its token, or paste the access token below. Your token is saved in this browser session only.</p><form id="unlock-form"><label for="unlock-token">Access token</label><input id="unlock-token" type="password" autocomplete="current-password" required><button type="submit">Unlock dashboard</button></form><p id="unlock-error" role="status"></p></article>
<div id="private-dashboard" hidden>
<nav id="dashboard-nav"><a href="#current-native-batch">Current run</a> · <a href="#live-cameras">Live cameras</a> · <a href="#paste-planner">KiCad upload</a> · <a href="#previous-runs">Previous runs</a></nav>
<div id="private-dashboard" hidden>
<style>[hidden]{display:none!important}#dashboard-nav{position:sticky;top:0;z-index:5;background:#101720;padding:10px}#unlock-panel{max-width:620px;margin:10vh auto}#unlock-form{display:flex;gap:10px;align-items:end;flex-wrap:wrap}#unlock-form label{display:flex;flex-direction:column;gap:6px}#unlock-token{background:#101720;color:#e6edf3;border:1px solid #49647d;padding:8px}#layout{display:grid;grid-template-columns:minmax(420px,1fr) minmax(360px,500px);gap:20px}main{display:block}main article{margin-bottom:16px}#chat{background:#1d2733;border-radius:10px;padding:16px;position:sticky;top:12px;height:calc(100vh - 165px);display:flex;flex-direction:column}#messages{overflow:auto;flex:1;min-height:200px}.message{padding:12px;margin:12px 0;background:#101720;border-radius:8px;border-left:3px solid #79b8ff}.message.user{border-color:#8be0b2}.message.progress{opacity:.85}.message p{white-space:pre-wrap;overflow-wrap:anywhere;margin:8px 0 0;line-height:1.5}.message small{font-size:12px}button{background:#324b66;color:white;border:0;padding:8px;border-radius:5px;cursor:pointer}button:disabled{opacity:.55;cursor:not-allowed}textarea{box-sizing:border-box;width:100%;min-height:84px;resize:vertical;background:#101720;color:#e6edf3;border:1px solid #49647d;border-radius:5px;padding:8px;font:inherit}#chat h2{margin:0 0 8px}#chat-status{padding:8px 0}.chat-controls{display:flex;gap:10px;align-items:center;font-size:13px}.composer{border-top:1px solid #49647d;margin-top:10px;padding-top:10px}.composer-row{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-top:6px}.composer-row small{flex:1}@media(max-width:900px){#layout{display:block}#chat{position:static;height:70vh}}</style>
<p id="status">Connecting…</p><article id="paste-progress" aria-live="polite"><h2>Paste run</h2><strong id="paste-state">Loading…</strong><p id="paste-phase"></p><p id="paste-count"></p><p id="paste-message"></p><small id="paste-updated"></small></article>
<article id="current-native-batch" aria-live="polite"><h2>Current 35-pad native batch</h2><strong id="current-native-state">Loading saved report…</strong><p id="current-native-recipe">Recipe 6 · R3 · 2.0 s dwell · 0.5 s pause · Z 58.2 · XYZ 100% · B 5% · current limit 400</p><p id="current-native-count"></p><p id="current-native-detail"></p><p><strong>Image review: quality pending and variable; this gallery does not establish acceptance.</strong></p><img id="whole-board-gallery" alt="Whole-board post-run gallery; quality review pending" ><div id="current-native-photos"></div><small id="current-native-updated"></small></article>
<section id="live-cameras"><h2>Live cameras</h2><div id="layout"><main></main><aside id="chat"><h2>Our conversation</h2><small>Live mirror · replies are sent to this Codex task</small><div class="chat-controls"><label><input id="progress" type="checkbox" checked>Progress updates</label><button id="latest">Jump to latest</button></div><small id="chat-status">Loading conversation…</small><div id="messages" aria-label="Conversation"></div><form id="composer" class="composer"><label for="reply">Reply to Codex</label><textarea id="reply" maxlength="4000" placeholder="Send a message to this task" required></textarea><div class="composer-row"><small id="send-status">Messages are delivered to the Codex task queue.</small><button id="send" type="submit">Send</button></div></form></aside></div></section>
<details id="previous-runs"><summary>Previous run details</summary>
<style>#paste-result{display:grid;grid-template-columns:minmax(280px,1fr) minmax(280px,1fr);gap:12px}#paste-result img{width:100%;border-radius:6px}#paste-result .summary{grid-column:1/-1}</style><article id="paste-result"><div class="summary"><h2>Latest R33 repeat observation</h2><p id="paste-result-summary">Loading reviewed result…</p><p id="paste-result-cv"></p><p id="paste-result-limits"></p></div><div><strong>R19.1 after image</strong><img id="result-r19" alt="R19.1 camera observation after paste"></div><div><strong>R18.1 after image</strong><img id="result-r18" alt="R18.1 camera observation after paste"></div></article>
<article id="known-job-status"><h2>Existing R33 native job status</h2><p id="known-job-status-text">Loading read-only job descriptor…</p><small id="known-job-status-detail"></small></article>
</details>
<style>#paste-planner{margin:12px 0;background:#1d2733;padding:16px;border-radius:10px}#paste-planner form{display:flex;gap:12px;flex-wrap:wrap;align-items:end}#paste-planner label{display:flex;flex-direction:column;gap:4px}#paste-planner input,#paste-planner select{background:#101720;color:#e6edf3;border:1px solid #49647d;border-radius:5px;padding:8px}#paste-job-result{display:grid;grid-template-columns:minmax(280px,1fr) minmax(320px,2fr);gap:16px;margin-top:12px}#paste-job-preview{width:100%;background:#101720;border-radius:6px}#paste-job-gates{border-left:3px solid #e6ae4a;padding-left:12px;color:#f0d28c}#paste-controls button{margin:4px}#paste-job-error{color:#ff9b9b;white-space:pre-wrap}#paste-component-table{width:100%;border-collapse:collapse;font-size:13px;margin:12px 0}#paste-component-table th,#paste-component-table td{border:1px solid #49647d;padding:5px;text-align:left}#paste-component-table-wrap{max-height:350px;overflow:auto}@media(max-width:700px){#paste-job-result{display:block}}</style>
<article id="paste-planner"><h2>KiCad paste job planner</h2><p>Upload a board for a saved CAD job and pad preview. This does not connect to OpenPnP or authorize dispensing.</p><form id="paste-job-form" enctype="multipart/form-data"><label>Board file (.kicad_pcb)<input name="board" type="file" accept=".kicad_pcb" required></label><label>Side<select name="side"><option>F.Cu</option><option>B.Cu</option></select></label><label>Paste thickness (mm)<input name="pasteThicknessMm" type="number" min="0.001" max="2" step="0.001" placeholder="Required for volume estimates"></label><label>Aperture scaling<input name="apertureScaling" type="number" min="0.1" max="3" step="0.01" value="1"></label><label>Flow calibration JSON<input name="flowCalibration" type="file" accept="application/json,.json"></label><button id="paste-job-submit" type="submit">Plan and save preview</button></form><p id="paste-job-error" role="status"></p><section id="paste-job-result" hidden><div><strong id="paste-job-title"></strong><p id="paste-job-summary"></p><p id="paste-job-calibration"></p><p id="paste-job-fiducials"></p><p id="paste-job-finepitch"></p><p><a id="paste-job-json" target="_blank" rel="noopener">Saved deterministic job JSON</a> · <a id="paste-job-readiness" target="_blank" rel="noopener">Readiness checklist</a> · <a id="paste-job-bundle">Download review bundle</a> · <a id="paste-job-openpnp">Download disabled OpenPnP draft</a></p><p id="paste-job-openpnp-status"></p><section id="paste-part-mapping"><h3>Optional configured part mapping</h3><p>Select known catalog parts for review. This does not map or verify feeders; configured feeder snapshot is informational only. Every generated placement remains disabled.</p><div id="paste-part-mapping-table"></div><button id="paste-part-mapping-save" type="button" disabled>Save disabled mapped draft</button><p id="paste-part-mapping-status" role="status"></p></section><p>Orange dashed lines are geometry candidates only. Individual pad deposits remain the default until a matching validated line-process recipe is supplied.</p><div id="paste-component-table-wrap"><table id="paste-component-table"><thead><tr><th>Component / pad</th><th>Proposal</th><th>Target volume (mm³)</th><th>Candidate dose (degrees)</th><th>Status</th></tr></thead><tbody></tbody></table></div><div id="paste-controls"><h3>Machine controls</h3><button type="button" disabled title="Requires a registered supervised OpenPnP owner action">Home / calibrate — unavailable</button><button type="button" disabled title="Requires an actual registered and validated paste job">Start paste — blocked</button><button type="button" disabled title="Requires an actual registered and validated placement job">Hand off to PnP — blocked</button><div id="paste-job-gates"></div></div></div><img id="paste-job-preview" alt="CAD pad and fiducial preview"></section></article>
<article id="generic-preparation"><h2>Generic dot-only preparation review</h2><p>This second pass binds fiducial registration, per-pad availability/surface, measured flow calibration, and both-head bounds to the saved CAD job. Upload the authored review JSON to see exact missing fields. It never submits a machine job.</p><form id="generic-review-form"><label>Reviewed generic-paste-human-review JSON <input id="generic-review-file" type="file" accept="application/json,.json" required></label><button id="generic-review-submit" type="submit" disabled>Validate and prepare offline dot preview</button></form><p id="generic-review-status" role="status">Upload and save a KiCad plan to start this review.</p><ul id="generic-review-missing"></ul><p><a id="generic-target-preview-link" hidden target="_blank" rel="noopener">Open registered target preview SVG</a></p><img id="generic-target-preview-image" hidden alt="Registered machine XY dot targets; review preview only"></article>
</div><script>
const token=location.hash.slice(1)||sessionStorage.getItem('viewerToken');
if(token)sessionStorage.setItem('viewerToken',token);history.replaceState(null,'',location.pathname);
const authHeaders=()=>({Authorization:'Bearer '+token});let csrfToken=null;
document.querySelector('#unlock-form').onsubmit=async event=>{event.preventDefault();const proposed=document.querySelector('#unlock-token').value.trim(),error=document.querySelector('#unlock-error');try{const r=await fetch('/paste-status',{headers:{Authorization:'Bearer '+proposed},cache:'no-store'});if(!r.ok)throw Error('That token was not accepted.');sessionStorage.setItem('viewerToken',proposed);location.reload();}catch(e){error.textContent=e.message;}};

async function loadCurrentNativeBatch(){try{const r=await fetch('/paste-results/current-native',{headers:authHeaders(),cache:'no-store'});if(!r.ok)throw Error('Saved batch report unavailable.');const d=await r.json();document.querySelector('#current-native-state').textContent=`${d.status.toUpperCase()} · ${d.reportStatus}`;document.querySelector('#current-native-count').textContent=`Stages verified ${d.verifiedStages}/${d.totalStages} · pads completed ${d.completedPads}/${d.totalPads}`;document.querySelector('#current-native-detail').textContent=`${d.currentPad?'Current pad '+d.currentPad+' · ':''}Controller position verified: ${d.controllerPositionVerified===true?'yes':d.controllerPositionVerified===false?'no':'not reported'}. ${d.detail}`;document.querySelector('#current-native-updated').textContent=d.updatedAt?'Last saved stage update '+new Date(d.updatedAt).toLocaleString():'';const gallery=document.querySelector('#whole-board-gallery');if(!gallery.dataset.loaded){const gr=await fetch('/paste-results/current-native/gallery',{headers:authHeaders(),cache:'no-store'});if(gr.ok){gallery.src=URL.createObjectURL(await gr.blob());gallery.dataset.loaded='true';}}const photos=document.querySelector('#current-native-photos');photos.replaceChildren();for(const [view,url] of Object.entries(d.imageUrls||{})){const label=document.createElement('strong');label.textContent=view+' after image';const image=document.createElement('img');image.alt=view+' camera image after batch';image.src=url+'?v='+encodeURIComponent(d.updatedAt||'');photos.append(label,image);}}catch(e){document.querySelector('#current-native-state').textContent='UNAVAILABLE';document.querySelector('#current-native-detail').textContent=e.message;}setTimeout(loadCurrentNativeBatch,2000);}
async function pasteTick(){const el=id=>document.querySelector('#paste-'+id);try{const r=await fetch('/paste-status',{headers:authHeaders(),cache:'no-store'});if(!r.ok)throw Error('Progress unavailable.');const s=await r.json();el('state').textContent=s.status.toUpperCase();el('phase').textContent=s.phase?'Phase: '+s.phase:'';el('count').textContent=`Pads: ${s.completedPads}/${s.totalPads}`+(s.currentPad?' · current: '+s.currentPad:'');el('message').textContent=s.message||'';const time=Date.parse(s.updatedAt);if(!Number.isFinite(time)){el('updated').textContent='No update timestamp';}else{const age=Math.max(0,Math.floor((Date.now()-time)/1000));const ago=age<60?age+'s':Math.floor(age/60)+'m';el('updated').textContent=(age>60?'STALE · ':'Updated ')+ago+' ago · '+new Date(time).toLocaleString();}}catch(e){el('state').textContent='UNAVAILABLE';el('message').textContent=e.message;}setTimeout(pasteTick,2000);}
async function loadR33Result(){try{const r=await fetch('/paste-results/latest',{headers:authHeaders(),cache:'no-store'});if(!r.ok)throw Error('Reviewed result unavailable.');const d=await r.json();document.querySelector('#paste-result-summary').textContent=`${d.status} · ${d.padCount} separated deposits on ${d.padIds.join(', ')} · ${d.executionSeconds.toFixed(2)} s.`;document.querySelector('#paste-result-cv').textContent=`Conventional image analysis: ${d.coveragePercentRange[0]}–${d.coveragePercentRange[1]}% bright bare-pad coverage; equivalent changed-area diameter ${d.equivalentChangedDiameterMmRange[0]}–${d.equivalentChangedDiameterMmRange[1]} mm.`;document.querySelector('#paste-result-limits').textContent=`Board progress ${d.boardProgress.touched}/${d.boardProgress.total} resistor pads touched. Physical acceptance: ${d.physicalAcceptanceEstablished?'established':'not established'}; prior mixed-quality deposits remain: ${d.boardProgress.priorMixedQualityDepositsRemain?'yes':'no'}. ${d.measurementMeaning}`;for(const [id,alias] of [['result-r19','R19.1'],['result-r18','R18.1']]){const ir=await fetch(d.imageUrls[alias],{headers:authHeaders(),cache:'no-store'});if(!ir.ok)throw Error('Observation image unavailable.');document.getElementById(id).src=URL.createObjectURL(await ir.blob());}}catch(e){document.querySelector('#paste-result-summary').textContent=e.message;}}
async function loadKnownJobStatus(){const text=document.querySelector('#known-job-status-text'),detail=document.querySelector('#known-job-status-detail');try{const r=await fetch('/paste-jobs/known-r33/status',{headers:authHeaders(),cache:'no-store'});const d=await r.json();if(!r.ok)throw Error(d.error||'Existing job status unavailable.');text.textContent=`${d.stage.toUpperCase()} · ${d.action} only · report: ${d.reportStatus||'no report'} · controller position verified: ${d.controllerPositionVerified?'yes':'no'} · uncertain completion: ${d.uncertainCompletion===null?'not reported':d.uncertainCompletion?'yes':'no'}`;detail.textContent=`Board-bound job ${d.jobId.slice(0,12)} · model preview passed: ${d.nativePreviewPassed?'yes':'no'} · executionAuthorized=${d.executionAuthorized}. ${d.detail}`;}catch(e){text.textContent=e.message;}}
document.querySelector('#paste-job-form').onsubmit=async event=>{event.preventDefault();const form=event.currentTarget,button=document.querySelector('#paste-job-submit'),error=document.querySelector('#paste-job-error');button.disabled=true;error.textContent='Planning board geometry…';try{const r=await fetch('/paste-jobs/plan',{method:'POST',headers:{...authHeaders(),'X-Viewer-CSRF':await csrf()},body:new FormData(form)});const body=await r.json();if(!r.ok)throw Error(body.error||'Job planning failed.');document.querySelector('#paste-job-result').hidden=false;document.querySelector('#paste-job-title').textContent=body.fileName+' · '+body.side;document.querySelector('#paste-job-summary').textContent=`${body.padCount} paste pads · ${body.footprintCount} footprints · ${body.boundsMm?body.boundsMm.map(x=>Number(x).toFixed(2)).join(' × ')+' mm board bounds':'no Edge.Cuts bounds'} · saved job ${body.jobId.slice(0,12)}`;document.querySelector('#paste-job-calibration').textContent=`Flow model: ${body.calibrationStatus}; ${body.estimatedDosePadCount} candidate dose estimates (unverified), ${body.needsCalibrationPadCount} need a model, ${body.needsVolumePadCount} need thickness/volume input.`;document.querySelector('#paste-job-fiducials').textContent=`CAD fiducials: ${body.fiducialCount}. Camera registration still requires capture and review.`;document.querySelector('#paste-job-finepitch').textContent=`Fine-pitch groups: ${body.finePitchCount} complete rows or close pairs flagged for individual review. Dashed line candidates are never automatically applied.`;document.querySelector('#paste-job-json').href=body.jobUrl;document.querySelector('#paste-job-readiness').href=body.readinessUrl;document.querySelector('#paste-job-bundle').href=body.reviewBundleUrl;document.querySelector('#paste-job-openpnp').href=body.openpnpDraftUrl;preparePartMapping(body);document.querySelector('#paste-job-openpnp-status').textContent=`OpenPnP-format draft: ${body.openpnpDraft.placementCount} placements, all disabled; ${body.openpnpDraft.mappingStatus}. This is review-only and executionAuthorized=false.`;document.querySelector('#paste-job-preview').src=body.previewUrl;const table=document.querySelector('#paste-component-table tbody');table.replaceChildren();for(const c of body.componentRecipes||[]){const tr=document.createElement('tr');for(const value of [c.footprint+' · '+c.padId,c.kind||'dot',c.targetVolumeMm3==null?'unknown':Number(c.targetVolumeMm3).toFixed(5),c.doseBDegrees==null?'—':Number(c.doseBDegrees).toFixed(2),c.doseStatus+' · '+c.theoryStatus]){const td=document.createElement('td');td.textContent=value;tr.append(td);}table.append(tr);}const gates=document.querySelector('#paste-job-gates');gates.replaceChildren();const rr=await fetch(body.readinessUrl,{headers:authHeaders(),cache:'no-store'});if(!rr.ok)throw Error('Saved job readiness checklist could not be loaded.');const readiness=await rr.json();for(const stage of readiness.stages){const p=document.createElement('p');p.textContent=`${stage.status.toUpperCase()} · ${stage.id}: ${stage.detail}`;gates.append(p);}error.textContent='Saved offline only · executionAuthorized=false';}catch(e){error.textContent=e.message;}finally{button.disabled=false;}};
document.querySelector('#inspection-report').onclick=async event=>{event.preventDefault();const link=event.currentTarget;try{const r=await fetch('/inspection/session',{method:'POST',headers:authHeaders(),cache:'no-store'});if(!r.ok)throw Error('Private viewer authorization is required.');location.href='/inspection';}catch(error){link.textContent='Placement inspection report unavailable.';}};
const names={openpnp:'OpenPnP · top and bottom cameras',webcam:'Machine USB camera'};
const main=document.querySelector('main');let urls={};
let chatRevision=-1,chatMessages=[];
const messages=document.querySelector('#messages');
function renderChat(force=false){const bottom=messages.scrollHeight-messages.scrollTop-messages.clientHeight<90;const old=messages.scrollTop;messages.replaceChildren();for(const m of chatMessages){if(!document.querySelector('#progress').checked&&m.phase==='commentary')continue;const a=document.createElement('div');a.className='message '+m.role+(m.phase==='commentary'?' progress':'');const label=document.createElement('small');label.textContent=(m.role==='user'?'You':m.phase==='commentary'?'Codex · progress':'Codex')+' · '+new Date(m.timestamp).toLocaleString();const p=document.createElement('p');p.textContent=m.text;a.append(label,p);messages.append(a);}if(bottom||force)messages.scrollTop=messages.scrollHeight;else messages.scrollTop=old;}
document.querySelector('#progress').onchange=()=>renderChat();document.querySelector('#latest').onclick=()=>{messages.scrollTop=messages.scrollHeight;};
async function chatTick(){try{const r=await fetch('/chat',{headers:{Authorization:'Bearer '+token},cache:'no-store'});if(!r.ok)throw Error('Open the complete private viewer link to read chat.');const c=await r.json();if(c.revision!==chatRevision){const first=chatRevision<0;chatRevision=c.revision;chatMessages=c.messages;renderChat(first);}document.querySelector('#chat-status').textContent=c.error||'Connected · '+c.messages.length+' messages';}catch(e){document.querySelector('#chat-status').textContent=e.message;}setTimeout(chatTick,2000);}
async function csrf(){if(csrfToken)return csrfToken;const r=await fetch('/csrf',{headers:authHeaders(),cache:'no-store'});if(!r.ok)throw Error('Private viewer authorization is required.');csrfToken=(await r.json()).token;return csrfToken;}
let activePasteJobId=null;
async function preparePartMapping(job){activePasteJobId=job.jobId;const holder=document.querySelector('#paste-part-mapping-table'),status=document.querySelector('#paste-part-mapping-status'),button=document.querySelector('#paste-part-mapping-save');holder.replaceChildren();button.disabled=true;try{const response=await fetch('/paste-jobs/catalog',{headers:authHeaders(),cache:'no-store'}),catalog=await response.json();if(!response.ok)throw Error(catalog.error||'Configured catalog unavailable.');const table=document.createElement('table'),body=document.createElement('tbody');for(const ref of job.placementReferences||[]){const row=document.createElement('tr'),label=document.createElement('td'),cell=document.createElement('td'),select=document.createElement('select');label.textContent=ref;const blank=document.createElement('option');blank.value='';blank.textContent='Unmapped';select.append(blank);for(const part of catalog.parts||[]){const option=document.createElement('option');option.value=part.id;option.textContent=part.id+' · '+part.packageId;select.append(option);}cell.append(select);row.append(label,cell);body.append(row);}table.append(body);holder.append(table);const snapshot=catalog.feederSnapshot;status.textContent=snapshot?`Configured model snapshot ${snapshot.time||'time unknown'} · ${(snapshot.feeders||[]).length} feeder identities. Physical feeder presence/index/stock readiness remains unknown.`:'No pure model feeder snapshot with feeder identities is available. Physical feeder readiness is unknown.';button.disabled=false;}catch(e){status.textContent=e.message;}}
document.querySelector('#paste-part-mapping-save').onclick=async()=>{const status=document.querySelector('#paste-part-mapping-status'),button=document.querySelector('#paste-part-mapping-save');button.disabled=true;try{const mappings={};for(const row of document.querySelectorAll('#paste-part-mapping-table tr')){const ref=row.cells[0].textContent,part=row.querySelector('select').value;if(part)mappings[ref]=part;}const response=await fetch(`/paste-jobs/${activePasteJobId}/openpnp-mapping`,{method:'POST',headers:{...authHeaders(),'X-Viewer-CSRF':await csrf(),'Content-Type':'application/json'},body:JSON.stringify({mappings})}),result=await response.json();if(!response.ok)throw Error(result.error||'Mapping could not be saved.');status.textContent=`Saved ${Object.keys(result.mappings).length} configured part mappings. All placements remain disabled; feeder readiness unknown; executionAuthorized=false.`;}catch(e){status.textContent=e.message;}finally{button.disabled=false;}};
function messageKey(text){try{const prior=JSON.parse(sessionStorage.getItem('viewerPendingReply')||'null');if(prior?.text===text&&prior?.key)return prior.key;const key=self.crypto?.randomUUID?.()||('message-'+Date.now()+'-'+Math.random().toString(36).slice(2));sessionStorage.setItem('viewerPendingReply',JSON.stringify({text,key}));return key;}catch{return self.crypto?.randomUUID?.()||('message-'+Date.now()+'-'+Math.random().toString(36).slice(2));}}
document.querySelector('#composer').onsubmit=async event=>{event.preventDefault();const reply=document.querySelector('#reply'),send=document.querySelector('#send'),status=document.querySelector('#send-status');const text=reply.value;send.disabled=true;status.textContent='Sending to Codex…';try{const r=await fetch('/messages',{method:'POST',headers:{...authHeaders(),'Content-Type':'application/json','X-Viewer-CSRF':await csrf(),'Idempotency-Key':messageKey(text)},body:JSON.stringify({message:text})});const body=await r.json();if(!r.ok)throw Error(body.error||'Message could not be sent.');if(body.status==='delivered'){reply.value='';sessionStorage.removeItem('viewerPendingReply');status.textContent='Delivered to the Codex task queue.';}else if(body.status==='unknown'){status.textContent='Delivery outcome is unknown. Check Codex before sending again.';}else{status.textContent=body.error||'Delivery failed. Keep this text and retry only after checking Codex.';}}catch(error){status.textContent=error.message;}finally{send.disabled=false;}};
for(const [id,name] of Object.entries(names)){let a=document.createElement('article');a.innerHTML=`<h2>${name}</h2><small id="s-${id}"></small><img id="${id}" alt="Waiting for ${name}">`;main.append(a);a.querySelector('img').onclick=()=>a.requestFullscreen();}
async function tick(){
 try{const r=await fetch('/status',{headers:{Authorization:'Bearer '+token},cache:'no-store'});if(!r.ok)throw Error('Access denied. Open the complete private link.');const s=await r.json();
 document.querySelector('#status').textContent='Latest capture: '+new Date(s.time*1000).toLocaleTimeString()+' · '+(Date.now()/1000-s.time<5?'live':'STALE');
 await Promise.all(Object.keys(names).map(async id=>{document.querySelector('#s-'+id).textContent=s.errors[id]||'';if(s.errors[id])return;let r=await fetch('/frame/'+id,{headers:{Authorization:'Bearer '+token},cache:'no-store'});if(!r.ok)return;let u=URL.createObjectURL(await r.blob());document.getElementById(id).src=u;if(urls[id])URL.revokeObjectURL(urls[id]);urls[id]=u;}));
 }catch(e){document.querySelector('#status').textContent=e.message;}setTimeout(tick,1000);
}async function verifyPrivateAccess(){const unlock=document.querySelector('#unlock-panel'),privateView=document.querySelector('#private-dashboard');if(!token){unlock.hidden=false;return;}try{const r=await fetch('/paste-status',{headers:authHeaders(),cache:'no-store'});if(!r.ok)throw Error('Access token expired or invalid.');privateView.hidden=false;unlock.hidden=true;loadCurrentNativeBatch();pasteTick();loadR33Result();loadKnownJobStatus();tick();chatTick();}catch(e){sessionStorage.removeItem('viewerToken');unlock.hidden=false;document.querySelector('#unlock-error').textContent=e.message;}}verifyPrivateAccess();async function showGenericRequirements(jobHash){const section=document.querySelector('#generic-preparation'),status=document.querySelector('#generic-review-status'),list=document.querySelector('#generic-review-missing'),button=document.querySelector('#generic-review-submit');section.dataset.jobHash=jobHash;list.replaceChildren();document.querySelector('#generic-target-preview-link').hidden=true;document.querySelector('#generic-target-preview-image').hidden=true;button.disabled=false;try{const r=await fetch(`/paste-jobs/${jobHash}/generic-preview.json`,{headers:authHeaders(),cache:'no-store'}),data=await r.json();if(!r.ok)throw Error(data.error||'Review checklist unavailable.');status.textContent=`Generic preparation ${data.reviewStatus}. No execution authorized.`;for(const item of data.missingRequirements||[]){const li=document.createElement('li');li.textContent=item;list.append(li);}}catch(e){status.textContent=e.message;button.disabled=true;}}
const genericJobLink=document.querySelector('#paste-job-json');new MutationObserver(()=>{const m=genericJobLink.href.match(new RegExp('/paste-jobs/([a-f0-9]{64})$'));if(m)showGenericRequirements(m[1]);}).observe(genericJobLink,{attributes:true,attributeFilter:['href']});
document.querySelector('#generic-review-form').onsubmit=async event=>{event.preventDefault();const status=document.querySelector('#generic-review-status'),list=document.querySelector('#generic-review-missing'),button=document.querySelector('#generic-review-submit'),file=document.querySelector('#generic-review-file').files[0],jobHash=document.querySelector('#generic-preparation').dataset.jobHash;button.disabled=true;try{if(!jobHash||!file)throw Error('Plan a board and choose the authored review JSON first.');const review=JSON.parse(await file.text());const r=await fetch(`/paste-jobs/${jobHash}/generic-prepare`,{method:'POST',headers:{...authHeaders(),'X-Viewer-CSRF':await csrf(),'Content-Type':'application/json'},body:JSON.stringify(review)}),data=await r.json();if(!r.ok)throw Error(data.error||'Preparation review rejected.');status.textContent=`${data.reviewStatus} · ${data.individualDotTargets.length} individual dot targets · executionAuthorized=${data.executionAuthorized} · ${data.dispatcherStatus}`;list.replaceChildren();for(const item of [...(data.missingRequirements||[]),...(data.validationErrors||[])]){const li=document.createElement('li');li.textContent=item;list.append(li);}if(data.previewAuthorized){const link=document.querySelector('#generic-target-preview-link'),image=document.querySelector('#generic-target-preview-image');link.href=data.targetPreviewUrl;link.hidden=false;image.src=data.targetPreviewUrl;image.hidden=false;}}catch(e){status.textContent=e.message;}finally{button.disabled=false;}};
</script>'''.encode('utf-8')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--bind',required=True)
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--public-origin',type=validate_public_origin,
                        help='Exact external http(s) origin for HTTPS tunnel deployments; no path, query, or user info')
    parser.add_argument('--thread',help='Codex task UUID to receive web replies (overrides local config)')
    parser.add_argument('--state',help='Private viewer state directory (default: repository .local-viewer)')
    args=parser.parse_args()
    state=Path(args.state) if args.state else Path(__file__).resolve().parents[2]/'.local-viewer'
    state.mkdir(mode=0o700,exist_ok=True)
    paste_jobs_dir=state/'paste-jobs'
    token_file=state/'token'
    if not token_file.exists():
        token_file.write_text(secrets.token_urlsafe(32))
    os.chmod(token_file,0o600)
    token=token_file.read_text().strip()
    chat_config=state/'chat-source.json'
    mirror=ChatMirror(json.loads(chat_config.read_text())['path'] if chat_config.exists() else None)
    outbox=MessageOutbox(state/'messages.json')
    csrf_token=hmac.new(token.encode(),b'live-viewer-csrf',hashlib.sha256).hexdigest()
    cache={'frames':{},'errors':{},'time':0}
    lock=threading.Lock()
    def capture():
        d=display.Display()
        root=d.screen().root
        def windows(w):
            for c in w.query_tree().children:
                yield c
                yield from windows(c)
        while True:
            frames,errors={},{}
            targets={}
            try:
                for w in windows(root):
                    if w.get_attributes().map_state!=X.IsViewable:continue
                    title=w.get_wm_name() or ''
                    cls=' '.join(w.get_wm_class() or ()).lower()
                    if title.startswith('OpenPnP -') and 'openpnp' in cls:targets['openpnp']=w
                    elif title=='gst-launch-1.0' and 'gstreamer' in cls:targets['webcam']=w
                for key in ('openpnp','webcam'):
                    try:
                        if key not in targets:raise RuntimeError('Window unavailable or minimized')
                        w=targets[key];g=w.get_geometry()
                        raw=w.get_image(0,0,g.width,g.height,X.ZPixmap,0xffffffff)
                        im=Image.frombytes('RGB',(g.width,g.height),raw.data,'raw','BGRX')
                        im.thumbnail((1920,1080));buf=io.BytesIO();im.save(buf,'JPEG',quality=80)
                        frames[key]=buf.getvalue()
                    except Exception as e:errors[key]=str(e)
            except Exception as e:errors['desktop']=str(e)
            with lock:cache.update(frames=frames,errors=errors,time=time.time())
            time.sleep(1)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def authorized(self):
            return hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token)
        def inspection_authorized(self):
            expected='inspectionAuth='+token
            cookie=self.headers.get('Cookie','')
            return self.authorized() or any(hmac.compare_digest(v.strip(),expected) for v in cookie.split(';'))
        def paste_jobs_authorized(self):
            expected='pasteJobAuth='+token
            cookie=self.headers.get('Cookie','')
            return self.authorized() or any(hmac.compare_digest(v.strip(),expected) for v in cookie.split(';'))
        def reply(self,status,body,kind='application/json',extra_headers=None):
            if isinstance(body,dict):body=json.dumps(body).encode()
            self.send_response(status)
            self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer')
            self.send_header('X-Content-Type-Options','nosniff')
            for header,value in (extra_headers or {}).items():self.send_header(header,value)
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self' blob:; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
            self.end_headers()
            try:self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError):pass
        def target_thread(self):
            configured=args.thread
            if not configured and chat_config.exists():
                try:configured=json.loads(chat_config.read_text()).get('thread')
                except (OSError,ValueError,TypeError):configured=None
            try:return str(uuid.UUID(configured))
            except (ValueError,TypeError,AttributeError):return None
        def dispatch(self,record):
            claimed=outbox.claim(record['id'])
            if not claimed:return outbox.get(record['id'])
            target=self.target_thread()
            if not target:
                return outbox.complete(record['id'],'failed','No Codex task is configured for replies.')
            try:
                result=subprocess.run(['codex','queue','--thread',target,'--message',claimed['message']],
                                      stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                                      stderr=subprocess.PIPE,text=True,timeout=20,check=False)
            except subprocess.TimeoutExpired:
                return outbox.complete(record['id'],'unknown','Codex delivery timed out; it may still have been queued.')
            except OSError:
                return outbox.complete(record['id'],'failed','Codex task delivery could not start.')
            if result.returncode:
                return outbox.complete(record['id'],'failed','Codex rejected delivery. Check that the configured task is open.')
            return outbox.complete(record['id'],'delivered')
        def expected_origin(self):
            # A tunnel's public Origin differs from the loopback Host. Never
            # infer trust from X-Forwarded-* headers supplied by the client.
            return expected_request_origin(args.public_origin, self.headers.get('Host',''))
        def do_GET(self):
            path=urlsplit(self.path).path
            if path=='/':
                self.reply(200,PAGE,'text/html; charset=utf-8')
                return
            if path == '/inspection' or path.startswith('/inspection/'):
                if not self.inspection_authorized():
                    self.reply(403,{'error':'Access denied.'});return
                if path == '/inspection':
                    try: body=inspection_html()
                    except OSError: self.reply(404,{'error':'Inspection report unavailable.'});return
                    self.reply(200,body,'text/html; charset=utf-8');return
                if path == '/inspection/asset':
                    name=parse_qs(urlsplit(self.path).query,keep_blank_values=True).get('file',[''])[0]
                    target=resolve_inspection_asset(name)
                    if target is None:
                        self.reply(404,{'error':'Inspection asset not found.'});return
                    try: body=target.read_bytes()
                    except OSError:
                        self.reply(404,{'error':'Inspection asset not found.'});return
                    kind={'.md':'text/plain; charset=utf-8','.json':'application/json; charset=utf-8'}.get(target.suffix.lower())
                    self.reply(200,body,kind or mimetypes.guess_type(target.name)[0] or 'application/octet-stream');return
                self.reply(404,{'error':'Not found.'});return
            paste_job_path=path.startswith('/paste-jobs/')
            if not self.authorized() and not (paste_job_path and self.paste_jobs_authorized()):
                self.reply(403,{'error':'Access denied.'});return
            if path=='/csrf':
                self.reply(200,{'token':csrf_token});return
            if path=='/paste-status':
                self.reply(200,paste_status());return
            if path=='/paste-results/latest':
                try:self.reply(200,r33_repeat_result())
                except (OSError,ValueError,TypeError,KeyError) as error:
                    self.reply(503,{'error':'Reviewed repeat observation is unavailable.'})
                return
            if path=='/paste-results/current-native':
                try:self.reply(200,current_native_batch_status())
                except (OSError,ValueError,TypeError,KeyError) as error:
                    self.reply(503,{'error':'Current native batch report is unavailable.'})
                return
            if path=='/paste-jobs/known-r33/status':
                try:self.reply(200,known_r33_service_status(paste_jobs_dir.parent/'service-paste-jobs'))
                except (OSError,ValueError,TypeError,KeyError) as error:
                    self.reply(503,{'error':'Existing R33 job status is unavailable; no machine action was attempted.'})
                return
            if path=='/paste-jobs/catalog':
                try:self.reply(200,openpnp_catalog_snapshot())
                except (OSError,ValueError,TypeError) as error:self.reply(503,{'error':'Saved OpenPnP catalog/snapshot unavailable.'})
                return
            result_image=re.fullmatch(r'/paste-results/latest/image/(R19\.1|R18\.1)',path)
            if result_image:
                alias=result_image.group(1)
                filename={'R19.1':'after-R19.1.png','R18.1':'after-R18.1.png'}[alias]
                try:
                    target=(R33_RESULT_DIR/filename).resolve(strict=True)
                    if target.parent!=R33_RESULT_DIR or not target.is_file():raise OSError('unavailable')
                    self.reply(200,target.read_bytes(),'image/png')
                except OSError:self.reply(404,{'error':'Observation image unavailable.'})
                return
            native_image=re.fullmatch(r'/paste-results/current-native/image/(top|bottom)',path)
            if native_image:
                try:
                    report=json.loads((CURRENT_NATIVE_BATCH_DIR/'report.json').read_text(encoding='utf-8'))
                    entry=(report.get('afterImages') or {}).get(native_image.group(1))
                    if not isinstance(entry,dict) or not isinstance(entry.get('path'),str):raise OSError('unavailable')
                    candidate=Path(entry['path'])
                    if not candidate.is_absolute():candidate=CURRENT_NATIVE_BATCH_DIR/candidate
                    target=candidate.resolve(strict=True)
                    if target.parent!=CURRENT_NATIVE_BATCH_DIR or not target.is_file():raise OSError('unavailable')
                    self.reply(200,target.read_bytes(),'image/png')
                except (OSError,ValueError,TypeError,AttributeError):
                    self.reply(404,{'error':'Batch observation image unavailable.'})
                return
            if path=='/paste-results/current-native/gallery':
                try:
                    target=CURRENT_NATIVE_GALLERY.resolve(strict=True)
                    if target!=CURRENT_NATIVE_GALLERY or target.name!='after-whole-pad-gallery.jpg' or not target.is_file():
                        raise OSError('unavailable')
                    self.reply(200,target.read_bytes(),'image/jpeg')
                except OSError:
                    self.reply(404,{'error':'Whole-board gallery unavailable.'})
                return
            job_match=re.fullmatch(r'/paste-jobs/([a-f0-9]{64})(/(?:preview\.svg|readiness\.json|generic-preview\.json|generic-target-preview\.svg|review-bundle\.zip|openpnp-draft\.zip))?',path)
            if job_match:
                job_dir=paste_jobs_dir/job_match.group(1)
                suffix=job_match.group(2) or ''
                if suffix=='/openpnp-draft.zip':
                    try:
                        bundle=io.BytesIO()
                        with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED) as archive:
                            for name in ('pnp-draft.board.xml','pnp-draft.job.xml'):
                                archive.write(job_dir/name,arcname=name)
                            archive.writestr('README.txt',(
                                'OpenPnP-format disabled placement draft\n\n'
                                'Every placement and the board location are disabled. Part/package/feeder mappings,\n'
                                'board registration, machine offsets, and execution authorization are absent.\n'
                                'Keep both XML files together; the job references pnp-draft.board.xml by relative name.\n'
                                'This artifact is for review and manual mapping only, not a runnable job.\n'))
                        self.reply(200,bundle.getvalue(),'application/zip',{'Content-Disposition':f'attachment; filename="openpnp-disabled-draft-{job_match.group(1)[:12]}.zip"'})
                    except OSError:self.reply(404,{'error':'Saved OpenPnP draft not found.'})
                    return
                if suffix=='/review-bundle.zip':
                    try:
                        bundle=io.BytesIO()
                        with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED) as archive:
                            for name in ('job.json','preview.svg','readiness.json','generic-preview.json','generic-target-preview.svg','pnp-draft.board.xml','pnp-draft.job.xml'):
                                archive.write(job_dir/name,arcname=name)
                            archive.writestr('README.txt',(
                                'Offline KiCad paste-planning review bundle\n'
                                f'Job ID: {job_match.group(1)}\n\n'
                                'This bundle contains CAD-derived geometry and a disabled OpenPnP-format draft.\n'
                                'All placements and the board location are disabled; mappings and registration are absent.\n'
                                'has no board-to-machine registration, and is not authorized for motion or dispensing.\n'
                                'Use the readiness.json artifact checklist and the existing OpenPnP owner for any\n'
                                'separate, reviewed native job creation.\n'))
                        self.reply(200,bundle.getvalue(),'application/zip',{'Content-Disposition':f'attachment; filename="paste-review-{job_match.group(1)[:12]}.zip"'})
                    except OSError:self.reply(404,{'error':'Saved paste job not found.'})
                    return
                target=job_dir/({'/preview.svg':'preview.svg','/readiness.json':'readiness.json','/generic-preview.json':'generic-preview.json','/generic-target-preview.svg':'generic-target-preview.svg'}.get(suffix,'job.json'))
                try: body=target.read_bytes()
                except OSError:self.reply(404,{'error':'Saved paste job not found.'});return
                kind='image/svg+xml; charset=utf-8' if suffix in ('/preview.svg','/generic-target-preview.svg') else 'application/json; charset=utf-8'
                self.reply(200,body,kind);return
            if path=='/chat':
                self.reply(200,mirror.snapshot());return
            with lock:
                if path=='/status':body,kind=json.dumps({'time':cache['time'],'errors':cache['errors']}).encode(),'application/json'
                elif path.startswith('/frame/') and path[7:] in cache['frames']:
                    body,kind=cache['frames'][path[7:]],'image/jpeg'
                else:self.reply(404,{'error':'Not found.'});return
            self.reply(200,body,kind)
        def do_POST(self):
            path=urlsplit(self.path).path
            expected_origin=self.expected_origin()
            if path == '/inspection/session':
                if (not self.authorized() or self.headers.get('Origin') != expected_origin
                        or self.headers.get('Content-Length','0') not in ('0','')):
                    self.reply(403,{'error':'Access denied.'});return
                self.send_response(204)
                secure='; Secure' if args.public_origin and urlsplit(args.public_origin).scheme == 'https' else ''
                self.send_header('Set-Cookie',f'inspectionAuth={token}; Path=/inspection; HttpOnly; SameSite=Strict; Max-Age=3600{secure}')
                self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Content-Length','0')
                self.end_headers()
                return
            if (not self.authorized() or not hmac.compare_digest(self.headers.get('X-Viewer-CSRF',''),csrf_token)
                    or self.headers.get('Origin') != expected_origin):
                self.reply(403,{'error':'Access denied.'});return
            mapping_match=re.fullmatch(r'/paste-jobs/([a-f0-9]{64})/openpnp-mapping',path)
            if mapping_match:
                try:
                    length=int(self.headers.get('Content-Length','-1'))
                    if length<1 or length>1_000_000:raise ValueError('Mapping request exceeds limit.')
                    if self.headers.get('Content-Type','').split(';',1)[0].strip()!='application/json':raise ValueError('Expected JSON mapping.')
                    payload=json.loads(self.rfile.read(length))
                    if not isinstance(payload,dict) or not isinstance(payload.get('mappings'),dict):raise ValueError('Expected a mappings object.')
                    job_dir=(paste_jobs_dir/mapping_match.group(1)).resolve(strict=True)
                    if job_dir.parent!=paste_jobs_dir.resolve():raise ValueError('Invalid saved job.')
                    saved=save_openpnp_mapping(job_dir,payload['mappings'])
                    self.reply(200,saved)
                except (OSError,ValueError,TypeError,json.JSONDecodeError) as error:self.reply(400,{'error':str(error)})
                return
            generic_match=re.fullmatch(r'/paste-jobs/([a-f0-9]{64})/generic-prepare',path)
            if generic_match:
                try:
                    length=int(self.headers.get('Content-Length','-1'))
                    if length<1 or length>2_000_000:raise ValueError('Review input exceeds limit.')
                    if self.headers.get('Content-Type','').split(';',1)[0].strip()!='application/json':raise ValueError('Expected JSON review input.')
                    review=json.loads(self.rfile.read(length))
                    if not isinstance(review,dict):raise ValueError('Expected a review object.')
                    job_dir=(paste_jobs_dir/generic_match.group(1)).resolve(strict=True)
                    if job_dir.parent!=paste_jobs_dir.resolve():raise ValueError('Invalid saved job.')
                    job=json.loads((job_dir/'job.json').read_text(encoding='utf-8'))
                    prepared=generic_paste_adapter.prepare_generic_job(job,generic_match.group(1),review)
                    prepared['targetPreviewUrl']='/paste-jobs/'+generic_match.group(1)+'/generic-target-preview.svg'
                    raw=(json.dumps(prepared,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
                    tmp=job_dir/'generic-preview.json.tmp';tmp.write_bytes(raw);os.chmod(tmp,0o600);tmp.replace(job_dir/'generic-preview.json')
                    svg_tmp=job_dir/'generic-target-preview.svg.tmp';svg_tmp.write_bytes(render_generic_target_svg(prepared));os.chmod(svg_tmp,0o600);svg_tmp.replace(job_dir/'generic-target-preview.svg')
                    self.reply(200,prepared)
                except (OSError,ValueError,TypeError,json.JSONDecodeError) as error:self.reply(400,{'error':str(error)})
                return
            if path=='/paste-jobs/plan':
                try:
                    length=int(self.headers.get('Content-Length','-1'))
                    if length<1 or length>MAX_BOARD_UPLOAD+512_000:raise ValueError('Upload exceeds the 32 MiB request limit.')
                    content_type=self.headers.get('Content-Type','')
                    if not content_type.lower().startswith('multipart/form-data;'):raise ValueError('Expected multipart board upload.')
                    board,options=parse_paste_job_multipart(content_type,self.rfile.read(length))
                    result=build_saved_paste_job(board,options,paste_jobs_dir)
                    secure='; Secure' if args.public_origin and urlsplit(args.public_origin).scheme=='https' else ''
                    self.reply(201,result,extra_headers={'Set-Cookie':f'pasteJobAuth={token}; Path=/paste-jobs; HttpOnly; SameSite=Strict; Max-Age=3600{secure}'})
                except (OSError,ValueError,TypeError,UnicodeError,json.JSONDecodeError) as error:
                    self.reply(400,{'error':str(error)})
                return
            if path!='/messages':
                self.reply(404,{'error':'Not found.'});return
            try:
                length=int(self.headers.get('Content-Length','-1'))
                if length < 1 or length > 20_000:raise ValueError('Invalid request size.')
                if self.headers.get('Content-Type','').split(';',1)[0].strip() != 'application/json':
                    raise ValueError('Expected JSON.')
                payload=json.loads(self.rfile.read(length))
                if not isinstance(payload,dict):raise ValueError('Expected a JSON object.')
                record,created=outbox.submit(payload.get('message'),self.headers.get('Idempotency-Key'))
                if created:record=self.dispatch(record)
                self.reply(201 if created else 200,record)
            except (ValueError,TypeError,json.JSONDecodeError) as error:
                self.reply(400,{'error':str(error)})
    threading.Thread(target=capture,daemon=True).start()
    print(f'Viewer on {args.bind}:{args.port}',flush=True)
    ThreadingHTTPServer((args.bind,args.port),Handler).serve_forever()

if __name__=='__main__':main()
