#!/usr/bin/env python3
"""Author one to three reviewed FTP pairs as a disabled selected-pad route.

Offline only: consumes caller-supplied evidence, invokes the checked-in
selected-pad authorer/preparer, and writes a disabled preview. It has no OpenPnP
bridge or motion dispatcher. Each review flag is explicit; camera reports and
images are hash-bound from the supplied report map.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
AUTHOR_PATH=ROOT/'automation/paste/author-conditioned-ftp-selected-pads.py'
_SPEC=importlib.util.spec_from_file_location('selected_pad_author',AUTHOR_PATH)
_AUTHOR=importlib.util.module_from_spec(_SPEC);_SPEC.loader.exec_module(_AUTHOR)
_PREP=_AUTHOR.P.PREP
CONTROLS=('R1.2','R16.1','R40.1')
ATTESTATION_FLAGS={
 'boardCleaned':'board_cleaned_reviewed',
 'padsAvailable':'pads_available_reviewed',
 'boardUnmovedSinceRegistration':'board_unmoved_reviewed',
 'bothHeadsClearanceReviewed':'both_heads_clearance_reviewed',
 'clearTransitCorridorReviewed':'clear_transit_corridor_reviewed',
 'scrapPrimeAndWipeReviewed':'scrap_prime_and_wipe_reviewed',
 'tipReviewedNoLongStrand':'tip_no_long_strand_reviewed',
}
class InputError(ValueError): pass
def require(ok,msg):
 if not ok: raise InputError(msg)
def finite(x):return type(x) in (int,float) and math.isfinite(x)
def read_json(p):return json.loads(Path(p).read_text())
def evidence(p):
 p=Path(p).resolve(strict=True);return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def parse_refs(raw):
 refs=[x.strip().upper() for x in raw.split(',')]
 require(1<=len(refs)<=3 and len(set(refs))==len(refs) and all(x in {f'R{i}' for i in range(1,41)} for x in refs),'Select one to three distinct resistor references')
 return refs
def selected_pad_ids(refs):return [f'{ref}.{side}' for ref in refs for side in ('1','2')]
def explicit_attestations(args):
 out={key:bool(getattr(args,flag)) for key,flag in ATTESTATION_FLAGS.items()}
 require(all(out.values()),'Every named review flag is required: '+', '.join(k for k,v in out.items() if not v))
 return out
def route_gross(pair_count,conditioning_gross, dose=12,retract=2,idle_relief=40):
 require(type(pair_count)is int and 1<=pair_count<=3,'Pair count must be one to three')
 require((dose,retract,idle_relief)==(12,2,40),'Selected route is fixed at 12-degree dose, R2 and 40-degree final relief')
 selected=pair_count*2*(dose+2*retract)
 return {'conditioningGrossDegrees':conditioning_gross,'selectedPadsGrossDegrees':selected,'idleReliefGrossDegrees':idle_relief,'grossDegrees':conditioning_gross+selected+idle_relief}
def validate_report_map(refs,report_map):
 pads=selected_pad_ids(refs);required=pads+list(CONTROLS)
 require(isinstance(report_map,dict) and all(k in report_map for k in required),'Report map must explicitly include selected pad IDs and all current controls; no historical fallback is allowed')
 return required
def conditioning_prefix(experiment,raw,profile,stationary_evidence,prime_x,prime_y,dummy_x,dummy_y):
 exp={**experiment,'startRaw':raw,'doseDegrees':12,'retractDegrees':2,'conditioningDoseDegrees':20,'conditioningRestoreDegrees':0,'conditioningFinalWipeMm':0,'conditioningDwellMilliseconds':2000,'dwellMilliseconds':2000,'retractDwellMilliseconds':500,'workRawZ':raw['Z'],'clearanceRawZ':53.45,'targetsXY':[{'X':round(prime_x+1.5,2),'Y':prime_y},{'X':dummy_x,'Y':dummy_y}]}
 prefix,poses,accounting=_PREP.stages_for(exp,stationary_evidence,profile.get('estimatedGapMm'),profile.get('gapUncertaintyMm'))
 return exp,prefix,poses,accounting
def validate_camera_report(report,template,now_ms,require_fresh):
 require(report.get('status') in ('completed-camera-survey-awaiting-image-review','completed-contiguous-air-batch-awaiting-observation'),'Camera report must be a completed supported observation')
 require(report.get('controllerPositionVerified') is True and report.get('uncertainCompletion') is False,'Camera report must have verified position and no uncertainty')
 req=report.get('request') or {}
 require(req.get('jvmStartMs')==template.get('jvmStartMs') and req.get('liveConfigurationSha256')==template.get('liveConfigurationSha256'),'Camera report must match template JVM/configuration')
 try: finished_ms=round(datetime.datetime.fromisoformat(report['finishedAt'].replace('Z','+00:00')).timestamp()*1000)
 except (KeyError,TypeError,ValueError):raise InputError('Camera report requires a valid finishedAt')
 if require_fresh: require(0<=now_ms-finished_ms<=300000,'Selected-pad report must be no more than five minutes old')
 return finished_ms
def make_parser():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--output',required=True,help='new output directory; must not already exist')
 for name in ('template','barrier','stationary-image','tip-image','registration','target-base','profile-base','tip-offset','previous-report','ledger','scrap-experiment','surface','reports'):
  p.add_argument('--'+name,required=True,help='explicit source path')
 p.add_argument('--registration-revalidation',help='optional fresh-board-unmoved revalidation evidence JSON')
 p.add_argument('--refs',required=True,help='one to three refs, e.g. R28,R27,R26')
 p.add_argument('--prime-x',required=True,type=float);p.add_argument('--prime-y',required=True,type=float)
 p.add_argument('--dummy-x',required=True,type=float);p.add_argument('--dummy-y',required=True,type=float)
 p.add_argument('--reviewer',required=True);p.add_argument('--review',required=True,help='substantive review basis, at least 60 characters')
 p.add_argument('--reviewed-pad',action='append',default=[],help='explicitly reviewed selected pad; repeat once per selected pad')
 p.add_argument('--surface-reviewed-pad',action='append',default=[],help='explicit same-surface review for a selected pad; repeat once per selected pad')
 p.add_argument('--reviewed-control',action='append',default=[],help='explicitly reviewed aligned control pad; repeat R1.2/R16.1/R40.1')
 for flag in ATTESTATION_FLAGS.values():p.add_argument('--'+flag.replace('_','-'),action='store_true')
 return p
def build_inputs(args,now_ms=None):
 now_ms=int(time.time()*1000) if now_ms is None else now_ms
 refs=parse_refs(args.refs);pads=selected_pad_ids(refs)
 require(len(set(args.reviewed_pad))==len(args.reviewed_pad) and set(args.reviewed_pad)==set(pads),'--reviewed-pad must name each selected pad exactly once')
 require(len(set(args.surface_reviewed_pad))==len(args.surface_reviewed_pad) and set(args.surface_reviewed_pad)==set(pads),'--surface-reviewed-pad must name each selected pad exactly once')
 require(len(set(args.reviewed_control))==len(args.reviewed_control) and set(args.reviewed_control)==set(CONTROLS),'--reviewed-control must name each control pad exactly once')
 attest=explicit_attestations(args)
 reviewer=args.reviewer.strip();review=args.review.strip()
 require(len(reviewer)>=2 and len(review)>=60,'Reviewer and substantive --review text are required')
 raw_paths={k:Path(getattr(args,k.replace('-','_'))).resolve(strict=True) for k in ('template','barrier','stationary_image','tip_image','registration','target_base','profile_base','tip_offset','previous_report','ledger','scrap_experiment','surface','reports')}
 template=read_json(raw_paths['template']);barrier=read_json(raw_paths['barrier']);target_base=read_json(raw_paths['target_base']);ledger=read_json(raw_paths['ledger']);surface_doc=read_json(raw_paths['surface']);experiment=read_json(raw_paths['scrap_experiment']);profile_base=read_json(raw_paths['profile_base'])
 snap=barrier.get('afterQuerySnapshot') or {};raw=snap.get('raw')
 require(barrier.get('status')=='completed-read-only-position-barrier' and barrier.get('controllerPositionVerified') is True and barrier.get('noMotionCommandSubmitted') is True and barrier.get('uncertainCompletion') is False,'Fresh successful read-only barrier required')
 require(isinstance(raw,dict) and set(raw)==set('XYZAB') and all(finite(v) for v in raw.values()),'Barrier must contain finite X/Y/Z/A/B raw pose')
 require(barrier.get('request',{}).get('jvmStartMs')==template.get('jvmStartMs') and barrier.get('liveConfigurationSha256')==template.get('liveConfigurationSha256'),'Barrier/template session mismatch')
 require(abs(raw['X']-args.prime_x)<=.005 and abs(raw['Y']-args.prime_y)<=.005 and abs(raw['Z']-58.45)<=.005 and raw['A']==720,'Barrier must match explicitly supplied prime XY, Z58.45, A720')
 require(ledger.get('status')=='verified' and ledger.get('sessionId')==template.get('sessionId') and ledger.get('lastVerifiedB')==raw['B'],'Current ledger must be verified and match template session and barrier B')
 require(surface_doc.get('boardId')==target_base.get('boardId') and surface_doc.get('provenance')=='commissioning-provisional' and surface_doc.get('precisionCalibrated') is False and surface_doc.get('flowCalibrated') is False and surface_doc.get('jvmStartMs')==template.get('jvmStartMs') and surface_doc.get('liveConfigurationSha256')==template.get('liveConfigurationSha256'),'Shared surface must be provisional and bind same board/session/config')
 require(isinstance(surface_doc.get('reviewedBy'),str) and surface_doc['reviewedBy'].strip(),'Shared surface needs reviewer attribution')
 surf=surface_doc.get('surface') or {};work_z=surf.get('rawZ')
 require(finite(work_z) and 58<=work_z<=58.5 and experiment.get('workRawZ')==raw['Z'],'Surface and experiment work height must bind reviewed start Z')
 require(all(finite(v) for v in (args.prime_x,args.prime_y,args.dummy_x,args.dummy_y)),'Prime/dummy XY must be finite')
 for path,label in ((raw_paths['stationary_image'],'stationary image'),(raw_paths['tip_image'],'tip image')):
  st=path.stat();captured=st.st_mtime_ns//1_000_000;require(0<=now_ms-captured<=300000,label+' must be fresh within five minutes')
 report_map=read_json(raw_paths['reports']);all_ids=validate_report_map(refs,report_map)
 controls_docs={};
 for padid in CONTROLS:
  rp=Path(report_map[padid]).resolve(strict=True);doc=read_json(rp);validate_camera_report(doc,template,now_ms,False)
  top=(doc.get('afterImages') or {}).get('top');require(top and top.get('path'),'Control report lacks top image: '+padid)
  controls_docs[padid]={'path':rp,'image':(rp.parent/top['path']).resolve(strict=True)}
 target= dict(target_base)
 target.pop('registrationRevalidationEvidence',None)
 if args.registration_revalidation:
  target['registrationRevalidationEvidence']=evidence(args.registration_revalidation)
 target['padChecks']=[{'reference':padid.split('.')[0],'padId':padid,'reviewedAligned':True,'reportEvidence':evidence(controls_docs[padid]['path']),'imageEvidence':evidence(controls_docs[padid]['image'])} for padid in CONTROLS]
 output=Path(args.output).resolve();require(not output.exists(),'Refusing to overwrite existing output directory')
 target_path=output/'target-base.json'
 inputs={
  'schema':1,'scope':'reviewed-selected-pads-authoring-inputs','reviewedBy':reviewer,'reviewedMs':now_ms,'reviewBasis':review,
  'profileBasis':'Shared provisional surface review for this group; no precision contact calibration is claimed.',
  'startRaw':raw,'doseDegrees':12,'dwellMilliseconds':2000,'retractDegrees':2,'conditioningDoseDegrees':20,
  'conditioningRestoreDegrees':0,'conditioningFinalWipeMm':0,'xyClearanceRawZ':53.45,
  'conditioningRawZRange':[53.45,max(58.45,work_z)],
  'scrapTargetsXY':[{'X':round(args.prime_x+1.5,2),'Y':args.prime_y},{'X':args.dummy_x,'Y':args.dummy_y}],
  'attestations':attest,'selectedPads':[]}
 registration_doc=read_json(raw_paths['registration']);regids={p.get('padId') for p in registration_doc.get('resistorPadMachineXYTargets',[])}
 require(set(pads)<=regids,'All selected pad identities must exist in supplied current registration')
 for padid in pads:
  rp=Path(report_map[padid]).resolve(strict=True);doc=read_json(rp);finished_ms=validate_camera_report(doc,template,now_ms,True)
  top=(doc.get('afterImages') or {}).get('top');require(top and top.get('path'),'Selected-pad report lacks top image: '+padid)
  image=(rp.parent/top['path']).resolve(strict=True)
  inputs['selectedPads'].append({'padId':padid,'padIdentityReviewed':padid in args.reviewed_pad,
    'padAvailableReviewed':padid in args.reviewed_pad,'surfaceReviewed':padid in args.surface_reviewed_pad,
    'availabilityReportEvidence':evidence(rp),'availabilityImageEvidence':evidence(image),
    'availabilityCapturedMs':finished_ms,'surfaceEvidence':evidence(raw_paths['surface'])})
 source_paths={k:raw_paths[k] for k in ('template','barrier','stationary_image','tip_image','registration','profile_base','tip_offset','previous_report','ledger','scrap_experiment')}
 if args.registration_revalidation:source_paths['registration_revalidation']=Path(args.registration_revalidation).resolve(strict=True)
 names={'stationary_image':'stationaryImage','tip_image':'tipImage','target_base':'targetBase','profile_base':'profileBase','tip_offset':'tipOffset','previous_report':'previousReport','scrap_experiment':'scrapExperiment','registration_revalidation':'registrationRevalidation'}
 inputs['sources']={names.get(k,k):evidence(v) for k,v in source_paths.items()}
 # Recompute conditioner prefix gross with the same checked-in route generator.
 prof=profile_base;prepared_exp,prefix,_,accounting=conditioning_prefix(experiment,raw,prof,evidence(raw_paths['stationary_image']),args.prime_x,args.prime_y,args.dummy_x,args.dummy_y)
 budget=route_gross(len(refs),accounting['grossCommandedDegrees'])
 require(budget['grossDegrees']<=240,'Selected-pair route exceeds existing 240-degree per-batch gross cap')
 output.mkdir(parents=True)
 target_path.write_text(json.dumps(target,indent=2,allow_nan=False)+'\n')
 inputs['sources']['targetBase']=evidence(target_path)
 input_path=output/'reviewed-inputs.json';input_path.write_text(json.dumps(inputs,indent=2,allow_nan=False)+'\n')
 return {'output':output,'input':input_path,'inputs':inputs,'budget':budget,'prefixStages':len(prefix)}
def route_gross(pair_count,conditioning_gross,dose=12,retract=2,idle_relief=40):
 require(type(pair_count)is int and 1<=pair_count<=3,'Select one to three pairs')
 require((dose,retract,idle_relief)==(12,2,40),'Fixed route is 12-degree dose, R2 and 40-degree final relief')
 selected_pads=pair_count*2;selected_gross=selected_pads*(dose+2*retract)
 return {'conditioningGrossDegrees':conditioning_gross,'selectedPadsGrossDegrees':selected_gross,'idleReliefGrossDegrees':idle_relief,'grossDegrees':conditioning_gross+selected_gross+idle_relief}
def main(argv=None):
 p=make_parser();a=p.parse_args(argv);result=build_inputs(a);authored=result['output']/'authored'
 subprocess.run([sys.executable,str(AUTHOR_PATH),'--inputs',str(result['input']),'--output',str(authored)],check=True,cwd=ROOT)
 print(json.dumps({'authoringInput':str(result['input']),'authoredOutput':str(authored),'previewRequest':str(authored/'prepared/native/preview-request.json'),
  'prefixStages':result['prefixStages'],'recipe':{'doseDegrees':12,'retractDegrees':2,'conditioningDoseDegrees':20,'conditioningDwellMilliseconds':2000,'retractDwellMilliseconds':500,'pairs':len([x for x in result['inputs']['selectedPads']])/2},
  'budget':result['budget'],'enabled':False,'motionDispatched':False},indent=2))
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,KeyError,TypeError) as exc:raise SystemExit('error: '+str(exc))
