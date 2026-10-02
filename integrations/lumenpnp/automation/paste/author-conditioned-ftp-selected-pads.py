#!/usr/bin/env python3
"""Author one-to-eight individually reviewed FTP pads and prepare a disabled route."""
import argparse,copy,datetime,hashlib,importlib.util,json,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('selected_preparer',HERE/'prepare-conditioned-ftp-selected-pads.py');P=importlib.util.module_from_spec(spec);spec.loader.exec_module(P)
SOURCES=('template','barrier','stationaryImage','tipImage','registration','registrationRevalidation','targetBase','profileBase','tipOffset','previousReport','ledger','scrapExperiment','applicationRestartEvidence','manualHomeLedgerAnchorEvidence')
ATTEST=('boardCleaned','padsAvailable','boardUnmovedSinceRegistration','bothHeadsClearanceReviewed','clearTransitCorridorReviewed','scrapPrimeAndWipeReviewed','tipReviewedNoLongStrand')
def fail(s):raise ValueError(s)
def load_hash(e,json_mode=True):
 P.PREP.WIPE.checked_evidence(e,'authoring source');path=Path(e['path']).resolve(strict=True);data=path.read_bytes()
 if hashlib.sha256(data).hexdigest()!=e['sha256']:fail('Source hash changed: '+str(path))
 return json.loads(data) if json_mode else data
def derive(q,load,now):
 if q.get('schema')!=1 or q.get('scope')!='reviewed-selected-pads-authoring-inputs':fail('Explicit selected-pad authoring scope required')
 stamp=q.get('reviewedMs')
 if type(stamp)is not int or not 0<=now-stamp<=300000 or not isinstance(q.get('reviewedBy'),str) or not q['reviewedBy'].strip():fail('Fresh explicit integer reviewer/time required')
 for key in ('reviewBasis','profileBasis'):
  if not isinstance(q.get(key),str) or len(q[key].strip())<12:fail('Explicit '+key+' required')
 attest=q.get('attestations') or {}
 if any(attest.get(k)is not True for k in ATTEST):fail('Explicit route/cleaning attestations required')
 src=q.get('sources') or {};docs={k:load(src.get(k),k not in ('stationaryImage','tipImage')) for k in SOURCES if k not in ('registrationRevalidation','applicationRestartEvidence','manualHomeLedgerAnchorEvidence') or k in src}
 raw=(docs['barrier'].get('afterQuerySnapshot') or {}).get('raw')
 if not isinstance(raw,dict) or set(raw)!=set('XYZAB') or q.get('startRaw')!=raw:fail('Explicit startRaw must exactly equal source barrier')
 if docs['barrier'].get('status')!='completed-read-only-position-barrier' or docs['barrier'].get('controllerPositionVerified') is not True or docs['barrier'].get('noMotionCommandSubmitted') is not True or docs['barrier'].get('uncertainCompletion') is not False:fail('Successful read-only barrier required')
 session={k:docs['template'][k] for k in ('sessionId','jvmStartMs','liveConfigurationSha256')};reg={p['padId']:p for p in docs['registration'].get('resistorPadMachineXYTargets',[])}
 offset=docs['tipOffset'].get('cameraMinusTipXYMm')
 if not isinstance(offset,list) or len(offset)!=2 or not all(P.COMP.finite(v) for v in offset):fail('Bound camera-minus-tip offset required')
 reviews=q.get('selectedPads');
 if not isinstance(reviews,list) or not 1<=len(reviews)<=8:fail('Select one to eight explicitly reviewed pads')
 dose=q.get('doseDegrees');dwell=q.get('dwellMilliseconds',200);retract=q.get('retractDegrees',2)
 conditioning=q.get('conditioningDoseDegrees',20);restore=q.get('conditioningRestoreDegrees',0);final_wipe=q.get('conditioningFinalWipeMm',0)
 if type(dose)is not int or dose not in (2,3,4,6,12,20):fail('Selected-pad dose must be an allowed integer degree amount')
 if type(dwell)is not int or dwell not in (200,1000,2000):fail('Selected-pad dwell must be 200, 1000 or 2000 ms')
 if type(retract)is not int or retract not in (2,3,4,6):fail('Selected-pad retract must be an allowed integer degree amount')
 if type(conditioning)is not int or conditioning not in (6,12,20):fail('Selected-pad conditioner must be 6, 12 or 20 degrees')
 if type(restore)is not int or restore not in (0,3) or restore and (conditioning!=12 or retract!=3 or final_wipe):fail('Conditioner restore3 requires conditioner12/R3 and no final wipe')
 if type(final_wipe) not in (int,float) or final_wipe not in (0,1.5):fail('Conditioner final wipe must be 0 or +X1.5 mm')
 if final_wipe and (conditioning!=6 or retract!=3 or attest.get('conditioningFinalWipeReviewed') is not True):fail('Conditioner final wipe requires conditioner6/R3 and explicit review')
 target=copy.deepcopy(docs['targetBase'])
 if 'registrationRevalidation' not in src:target.pop('registrationRevalidationEvidence',None)
 for k in ('pairReferences','inlineConditioning','compensatedSequence','padAvailabilityImage','padAvailabilityReport','cleanupSequence'):target.pop(k,None)
 surface_first=None;surface_ev_first=None;pads=[];seen=set()
 for item in reviews:
  padid=item.get('padId')
  if not isinstance(padid,str) or padid in seen or padid not in reg or item.get('padIdentityReviewed') is not True or item.get('padAvailableReviewed') is not True or item.get('surfaceReviewed') is not True:fail('Each selected pad must be unique, registered, and individually reviewed')
  seen.add(padid)
  report=load(item.get('availabilityReportEvidence'),True);image=load(item.get('availabilityImageEvidence'),False);surface_doc=load(item.get('surfaceEvidence'),True);surface=surface_doc.get('surface')
  load(surface_doc.get('basisEvidence'),False)
  captured=item.get('availabilityCapturedMs')
  try:report_ms=round(datetime.datetime.fromisoformat(report['finishedAt'].replace('Z','+00:00')).timestamp()*1000)
  except (KeyError,ValueError,TypeError):fail('Pad report requires an exact finish time')
  if type(captured)is not int or captured!=report_ms or captured>stamp or not 0<=now-captured<=300000:fail('Pad availability report must be fresh and precede review')
  req=report.get('request') or {}
  if report.get('status') not in ('completed-camera-survey-awaiting-image-review','completed-contiguous-air-batch-awaiting-observation') or report.get('controllerPositionVerified') is not True or report.get('uncertainCompletion') is not False or req.get('jvmStartMs')!=session['jvmStartMs'] or req.get('liveConfigurationSha256')!=session['liveConfigurationSha256']:fail('Pad availability must bind verified same-session camera observation')
  top=(report.get('afterImages') or {}).get('top');report_path=Path(item['availabilityReportEvidence']['path']).resolve(strict=True);image_path=Path(item['availabilityImageEvidence']['path']).resolve(strict=True)
  if not top or image_path!=report_path.parent.joinpath(top.get('path','')).resolve():fail('Pad availability image must be report top image')
  if not isinstance(surface,dict) or surface_doc.get('boardId')!=target.get('boardId') or surface_doc.get('provenance')!='commissioning-provisional' or surface_doc.get('precisionCalibrated') is not False or surface_doc.get('flowCalibrated') is not False or surface_doc.get('jvmStartMs')!=session['jvmStartMs'] or surface_doc.get('liveConfigurationSha256')!=session['liveConfigurationSha256'] or not isinstance(surface_doc.get('reviewedBy'),str) or not surface_doc['reviewedBy'].strip():fail('Per-pad same-board provisional surface evidence required')
  P.PREP.WIPE.checked_evidence(surface_doc.get('basisEvidence'),'per-pad surface basis')
  for k in ('rawZ','estimatedGapMm','gapUncertaintyMm'):
   if not P.COMP.finite(surface.get(k)):fail('Per-pad surface '+k+' must be finite')
  if surface['estimatedGapMm']<=0 or surface['gapUncertaintyMm']<0 or surface['estimatedGapMm']-surface['gapUncertaintyMm']<.1:fail('Per-pad surface lower gap bound must be at least0.1mm')
  xy=reg[padid]['machineXYMm'];pose={'X':P.COMP.q01(xy[0]-offset[0]),'Y':P.COMP.q01(xy[1]-offset[1]),'Z':surface['rawZ'],'A':raw['A']}
  pad={'padId':padid,'rawPose':pose,'padIdentityReviewed':True,'padAvailableReviewed':True,'availabilityReportEvidence':copy.deepcopy(item['availabilityReportEvidence']),'availabilityImageEvidence':copy.deepcopy(item['availabilityImageEvidence']),'availabilityCapturedMs':captured,'surface':copy.deepcopy(surface),'surfaceEvidence':copy.deepcopy(item['surfaceEvidence'])}
  pads.append(pad)
  if surface_first is None:surface_first=copy.deepcopy(surface);surface_ev_first=copy.deepcopy(item['surfaceEvidence'])
 target.update(schema=1,scope='ftp-selected-pads-targets',reviewedBy=q['reviewedBy'],reviewedMs=stamp,**session)
 target.update(boardCleaned=attest['boardCleaned'],padsAvailable=attest['padsAvailable'],boardUnmovedSinceRegistration=attest['boardUnmovedSinceRegistration'],registrationEvidence=copy.deepcopy(src['registration']),surfaceEvidence=surface_ev_first,surface=surface_first,tipOffsetEvidence=copy.deepcopy(src['tipOffset']),cameraMinusTipXYMm=copy.deepcopy(offset),provenance='commissioning-provisional',precisionCalibrated=False,flowCalibrated=False,quantizationMm=.01,pads=pads)
 if 'registrationRevalidation' in src:target['registrationRevalidationEvidence']=copy.deepcopy(src['registrationRevalidation'])
 target['padAvailabilityImage']=copy.deepcopy(pads[0]['availabilityImageEvidence']);target['padAvailabilityReport']=copy.deepcopy(pads[0]['availabilityReportEvidence']);target['compensatedSequence']={'schema':1,'protocol':'restore-dose-retract-lift-selected-pads','doseDegrees':dose,'retractDegrees':retract,'dwellMilliseconds':dwell,'retractDwellMilliseconds':500,'idleReliefDegrees':40}
 exp=copy.deepcopy(docs['scrapExperiment']);exp.update(startRaw=copy.deepcopy(raw),doseDegrees=dose,retractDegrees=retract,conditioningDoseDegrees=conditioning,conditioningRestoreDegrees=restore,conditioningFinalWipeMm=final_wipe,targetsXY=copy.deepcopy(q.get('scrapTargetsXY')))
 if exp.get('mode')!='transfer-preparation' or exp.get('workRawZ')!=raw['Z'] or not isinstance(exp.get('targetsXY'),list) or len(exp['targetsXY'])!=2:fail('Explicit transfer-preparation experiment with two reviewed scrap targets required')
 if final_wipe:exp['conditioningFinalWipeReviewed']=True
 else:exp.pop('conditioningFinalWipeReviewed',None)
 review={'mode':'wet','reviewedBy':q['reviewedBy'],'reviewedMs':stamp,'imageEvidence':copy.deepcopy(src['stationaryImage']),'cleanTipImage':copy.deepcopy(src['tipImage']),'rawZRange':q.get('conditioningRawZRange'),'basis':q['reviewBasis'],'attestations':copy.deepcopy(attest)}
 profile=copy.deepcopy(docs['profileBase']);profile.update(rawPose={k:raw[k] for k in 'XYZA'},basis=q['profileBasis'])
 return exp,review,profile,target

def build(inputs,output):
 ip=Path(inputs).resolve(strict=True);ib=ip.read_bytes();q=json.loads(ib);now=int(time.time()*1000);snap={ip:ib}
 def load(e,json_mode=True):
  val=load_hash(e,json_mode);p=Path(e['path']).resolve(strict=True);snap[p]=p.read_bytes()
  if hashlib.sha256(snap[p]).hexdigest()!=e['sha256']:fail('Source changed while binding bytes: '+str(p))
  if not json_mode and e in [q.get('sources',{}).get(k) for k in ('stationaryImage','tipImage')]:
   captured=p.stat().st_mtime_ns//1000000
   if not 0<=now-captured<=300000 or captured>q.get('reviewedMs',0):fail('Current setup image must precede fresh authored review')
  return val
 exp,review,profile,target=derive(q,load,now);out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
 def write(n,v):p=out/n;p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n');return p
 ep=write('experiment.json',exp);review['experimentEvidence']=ev(ep);review['authoringInputEvidence']=ev(ip);rp=write('clearance-review.json',review);profile['measurementEvidence']=ev(rp);pp=write('profile.json',profile);tp=write('targets.json',target)
 src=q['sources'];cmd=[sys.executable,str(HERE/'prepare-conditioned-ftp-selected-pads.py')]
 for k,p in [('template',src['template']['path']),('barrier',src['barrier']['path']),('target-record',tp),('experiment',ep),('profile',pp),('clearance-review',rp),('image',src['stationaryImage']['path']),('previous-report',src['previousReport']['path']),('ledger',src['ledger']['path']),('output',out/'prepared'),('xy-clearance-raw-z',q['xyClearanceRawZ'])]:cmd.extend(['--'+k,str(p)])
 if 'applicationRestartEvidence' in src:cmd.extend(['--application-restart-evidence',src['applicationRestartEvidence']['path']])
 if 'manualHomeLedgerAnchorEvidence' in src:cmd.extend(['--manual-home-ledger-anchor-evidence',src['manualHomeLedgerAnchorEvidence']['path']])
 try:result=subprocess.run(cmd,check=True,text=True,capture_output=True)
 except subprocess.CalledProcessError as exc:fail('Selected-pad disabled preparer rejected inputs: '+(exc.stderr or exc.stdout or str(exc)).strip())
 for p,b in snap.items():
  if p.read_bytes()!=b:fail('Source changed during selected-pad preparation: '+str(p))
 print(json.dumps({'output':str(out),'previewRequest':str(out/'prepared/native/preview-request.json'),'enabled':False,'motionDispatched':False,'preparerResult':json.loads(result.stdout)},indent=2))

def ev(path):return P.ev(path)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inputs',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 try:build(a.inputs,a.output)
 except Exception as exc:p.error(str(exc))
if __name__=='__main__':main()
