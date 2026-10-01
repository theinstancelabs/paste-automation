#!/usr/bin/env python3
"""Prepare disabled contiguous-batch requests offline. Never connects to or dispatches to OpenPnP."""
import argparse, copy, hashlib, json, math, os, subprocess, sys, time, uuid, datetime
from pathlib import Path
ROOT=Path('/home/lumen/lumenpnp'); POLICY=ROOT/'automation/paste/commissioning-stroke.cjs'
def err(s): raise ValueError(s)
def read(p):
 p=Path(p).resolve(strict=True); b=p.read_bytes(); return json.loads(b),p,b

def evidence(p):
 p=Path(p).resolve(strict=True); b=p.read_bytes()
 if not b: err(f'Empty evidence: {p}')
 return {'path':str(p),'sha256':hashlib.sha256(b).hexdigest()}
def same(a,b):
 if isinstance(a,bool) or isinstance(b,bool): return type(a) is bool and type(b) is bool and a is b
 if isinstance(a,(int,float)) and isinstance(b,(int,float)):
  return math.isfinite(a) and math.isfinite(b) and a==b
 if type(a) is not type(b): return False
 if isinstance(a,dict): return a.keys()==b.keys() and all(same(a[k],b[k]) for k in a)
 if isinstance(a,list): return len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
 return a==b
def node_previous(report,ledger,ledger_sha,captured_ms):
 js="const P=require(process.argv[1]),v=JSON.parse(require('fs').readFileSync(0,'utf8'));P.validatePreviousReport(v.report,v.ledger,v.sha,v.capturedMs);"
 data={'report':report,'ledger':ledger,'sha':ledger_sha,'capturedMs':captured_ms}
 try: subprocess.run(['node','-e',js,str(POLICY)],input=json.dumps(data),text=True,check=True,capture_output=True)
 except subprocess.CalledProcessError as e: err('Installed previous-report validator rejected evidence: '+(e.stderr or e.stdout).strip())
def node_validate(q,preview,now=None):
 js="const P=require(process.argv[1]);const q=JSON.parse(require('fs').readFileSync(0,'utf8'));P.validateBatch(q,Date.now(),q.jvmStartMs,"+("true" if preview else "false")+");"
 js+="const F=require(require('path').join(require('path').dirname(process.argv[1]),'ftp-two-pad.cjs'));if(F.isFtp(q))F.verifySources(q,(e,json)=>{const b=require('fs').readFileSync(e.path);if(require('crypto').createHash('sha256').update(b).digest('hex')!==e.sha256)throw Error('FTP source hash changed');return json?JSON.parse(b):null;});"
 try: subprocess.run(['node','-e',js,str(POLICY)],input=json.dumps(q),text=True,check=True,capture_output=True)
 except subprocess.CalledProcessError as e: err('Installed Node validateBatch rejected request: '+(e.stderr or e.stdout).strip())
def required_dict(o,k):
 v=o.get(k)
 if not isinstance(v,dict): err(f'{k} must be a JSON object')
 return v
def sha_evidence(e,label):
 if not isinstance(e,dict) or not isinstance(e.get('path'),str) or not isinstance(e.get('sha256'),str): err(f'{label} must contain path and sha256')
 got=evidence(e['path'])
 if got['sha256']!=e['sha256']: err(f'{label} SHA-256 mismatch')
 return got

def prepare(args):
 base,bp,_=read(args.template); barrier,bp2,_=read(args.barrier); recipe,rp,_=read(args.recipe)
 image=Path(args.image).resolve(strict=True); ib=image.read_bytes(); st=image.stat(); now=int(time.time()*1000); captured=st.st_mtime_ns//1_000_000
 if not (ib.startswith(b'\x89PNG\r\n\x1a\n') or ib.startswith(b'\xff\xd8\xff')): err('Reviewed image must be PNG/JPEG')
 if captured>now or now-captured>300000: err('Reviewed image must be no more than five minutes old')
 if barrier.get('status')!='completed-read-only-position-barrier' or barrier.get('controllerPositionVerified') is not True or barrier.get('noMotionCommandSubmitted') is not True or barrier.get('uncertainCompletion') is not False: err('Fresh successful no-motion barrier required')
 try: bdone=int(datetime.datetime.fromisoformat(barrier['finishedAt'].replace('Z','+00:00')).timestamp()*1000)
 except Exception: err('Barrier lacks a valid finishedAt timestamp')
 if bdone>now or now-bdone>300000: err('Barrier must be no more than five minutes old')
 reqb=required_dict(barrier,'request'); snap=required_dict(barrier,'afterQuerySnapshot')
 if reqb.get('jvmStartMs')!=base.get('jvmStartMs') or barrier.get('liveConfigurationSha256')!=base.get('liveConfigurationSha256'): err('Barrier JVM/configuration differs from immutable template session')
 raw=snap.get('raw'); driver=snap.get('driver'); poses=snap.get('nativePoses')
 if not all(isinstance(x,dict) for x in (raw,driver,poses)) or set(raw)!={'X','Y','Z','A','B'} or set(driver)!=set(raw) or set(poses)!={'N1','N2','top','bottom'}: err('Barrier lacks complete five-axis and four-pose snapshot')
 mode=recipe.get('mode')
 if mode not in ('air','wet'): err('Recipe mode must be air or wet')
 clear=sha_evidence(recipe.get('clearanceReviewEvidence'),'clearanceReviewEvidence'); profile_ev=sha_evidence(recipe.get('profileEvidence'),'profileEvidence'); prev=sha_evidence(recipe.get('previousReportEvidence'),'previousReportEvidence')
 review,_,_=read(clear['path']); profile,_,_=read(profile_ev['path']); report,_,_=read(prev['path']); ledger,lp,lb=read(recipe.get('previousLedgerPath'))
 if review.get('mode')!=mode or not isinstance(review.get('reviewedBy'),str) or not review.get('reviewedBy').strip(): err('Clearance review must name reviewer and matching mode')
 if review.get('imageEvidence',{}).get('path')!=str(image) or review.get('imageEvidence',{}).get('sha256')!=hashlib.sha256(ib).hexdigest(): err('Clearance review does not bind supplied image')
 bounds=required_dict(recipe,'rawBounds'); heads=required_dict(recipe,'headClearanceBounds'); zrange=review.get('rawZRange')
 if not isinstance(zrange,list) or len(zrange)!=2 or zrange!=[bounds.get('Z',{}).get('min'),bounds.get('Z',{}).get('max')]: err('Reviewed clearance Z range must exactly match raw Z bounds')
 if not isinstance(review.get('reviewedMs'),(int,float)) or review['reviewedMs']<captured or review['reviewedMs']>now or now-review['reviewedMs']>300000: err('Clearance review timestamp must follow image capture and be current')
 if profile.get('provenance')!='commissioning-provisional' or profile.get('precisionCalibrated') is not False or profile.get('flowCalibrated') is not False: err('Profile must remain explicitly provisional and uncalibrated')
 if profile.get('sessionId')!=base.get('sessionId') or profile.get('jvmStartMs')!=base.get('jvmStartMs') or profile.get('liveConfigurationSha256')!=base.get('liveConfigurationSha256'): err('Profile session/configuration identity mismatch')
 pr=required_dict(profile,'rawPose')
 for k in ('X','Y','Z','A'):
  if not isinstance(pr.get(k),(int,float)) or not math.isclose(pr[k],raw[k],abs_tol=1e-4): err(f'Profile does not match barrier {k}')
 for k in ('X','Y','Z','B'):
  b=required_dict(bounds,k)
  if not isinstance(b.get('min'),(int,float)) or not isinstance(b.get('max'),(int,float)) or b['min']>b['max'] or not b['min']<=raw[k]<=b['max']: err(f'Initial {k} outside reviewed raw bounds')
 if ledger.get('status')!='verified' or ledger.get('sessionId')!=base.get('sessionId') or ledger.get('syringeId')!=base.get('syringeId') or ledger.get('primeLedgerSha256')!=base.get('primeLedgerSha256') or ledger.get('carryoverSha256')!=base.get('carryoverSha256'): err('Current ledger does not match immutable template identities')
 if report.get('status') not in ('completed-pre-dose-batch-reconciliation-no-motion','completed-commissioning-stroke-awaiting-observation','completed-dose-cycle-awaiting-observation','completed-contiguous-batch-awaiting-observation') or report.get('uncertainCompletion') is not False or report.get('completedLedgerSha256')!=hashlib.sha256(lb).hexdigest() or report.get('id')!=report.get('request',{}).get('id'): err('Previous report is not a successful report for exact current ledger')
 node_previous(report,ledger,hashlib.sha256(lb).hexdigest(),captured)
 if not ledger.get('entries') or ledger['entries'][-1].get('status')!='verified' or report['id'] not in (ledger['entries'][-1].get('requestId'),ledger['entries'][-1].get('cycleId'),ledger['entries'][-1].get('batchId')): err('Previous report is not current verified ledger tail')
 stages=recipe.get('stages')
 if not isinstance(stages,list) or not 1<=len(stages)<=40: err('Recipe needs 1..40 reviewed stages')
 start=copy.deepcopy(raw); built=[]
 for i,src in enumerate(stages):
  if not isinstance(src,dict) or src.get('axis') not in ('X','Y','Z','B') or not isinstance(src.get('target'),(int,float)): err(f'Invalid recipe stage {i}')
  # The shared batch policy admits reviewed +/-3-degree stages; formatter and counts remain native.
  axis=src['axis']; target=copy.deepcopy(start); target[axis]=src['target']; stg={'axis':axis,'speedFraction':.05 if axis=='B' else 1,'startRaw':start,'targetRaw':target}
  for key in ('gapEvidence','estimatedGapMm','gapUncertaintyMm','wipeReview','wipeReviewEvidence','dwellMilliseconds'):
   if key in src: stg[key]=src[key]
  if 'gapEvidence' in stg: stg['gapEvidence']=sha_evidence(stg['gapEvidence'],f'stage {i} gapEvidence')
  if 'wipeReviewEvidence' in stg: stg['wipeReviewEvidence']=sha_evidence(stg['wipeReviewEvidence'],f'stage {i} wipeReviewEvidence')
  built.append(stg); start=target
 imgsha=hashlib.sha256(ib).hexdigest(); ident=str(uuid.uuid4()); out=Path(args.output).resolve()
 out.mkdir(parents=True,exist_ok=False)
 stop=str(out/'cooperative-stop.requested')
 receiving={'provenance':profile['provenance'],'precisionCalibrated':False,'flowCalibrated':False,'sha256':profile_ev['sha256'],'estimatedGapMm':profile['estimatedGapMm'],'gapUncertaintyMm':profile['gapUncertaintyMm'],'basis':profile['basis'],'rawPose':pr}
 q={'schema':1,'scope':'contiguous-native-scrap-batch-preview','enabled':False,'mode':mode,'stopPath':stop,'id':ident,'sessionId':base['sessionId'],'jvmStartMs':base['jvmStartMs'],'createdMs':now,'imageCapturedMs':captured,'reviewedImageMs':int(review['reviewedMs']),'liveConfigurationSha256':barrier['liveConfigurationSha256'],'expectedRaw':raw,'expectedDriver':driver,'expectedNativePoses':poses,'rawBounds':bounds,'headClearanceBounds':heads,'bothHeadsClearanceReview':True,'clearanceReviewEvidence':clear,'xyClearanceRawZ':recipe['xyClearanceRawZ'],'receivingProfile':receiving,'previewStages':built,'finalTargetRaw':start,
    'evidence':[],'previousReportEvidence':prev,'nativePreviewEvidence':None,'profileEvidence':profile_ev,'barrierEvidence':evidence(bp2),'reviewedImageEvidence':{'path':str(image),'sha256':imgsha},'previousLedgerSha256':hashlib.sha256(lb).hexdigest(),'syringeId':base['syringeId'],'primeLedgerSha256':base['primeLedgerSha256'],'carryoverSha256':base['carryoverSha256'],'budgetAmendmentEvidence':base.get('budgetAmendmentEvidence'),
    'primeLedgerEvidence':sha_evidence(base.get('primeLedgerEvidence'),'template primeLedgerEvidence'),'priorLedgerEvidence':sha_evidence(base.get('priorLedgerEvidence'),'template priorLedgerEvidence'),'carryoverEvidence':sha_evidence(base.get('carryoverEvidence'),'template carryoverEvidence')}
 if recipe.get('targetSurface') in ('cleaned-ftp-demo','scrap-conditioned-ftp-demo'):
  target_ev=sha_evidence(recipe.get('ftpTargetEvidence'),'ftpTargetEvidence'); target,_,_=read(target_ev['path'])
  q.update(scope='contiguous-native-ftp-conditioned-two-pad-preview' if recipe['targetSurface']=='scrap-conditioned-ftp-demo' else 'contiguous-native-ftp-two-pad-preview',ftpTargetEvidence=target_ev,ftpTargetRecord=target)
 elif recipe.get('targetSurface') not in (None,'scrap') or 'ftpTargetEvidence' in recipe: err('Explicit supported target surface required')
 q['evidence']=[q[k] for k in ('barrierEvidence','reviewedImageEvidence','profileEvidence','previousReportEvidence','primeLedgerEvidence','priorLedgerEvidence','carryoverEvidence')]+[{'path':str(lp),'sha256':q['previousLedgerSha256']},clear]
 amendment=q.get('budgetAmendmentEvidence')
 if amendment and amendment.get('newMaximumAbsoluteDegrees') in (3600,8400):
  ceiling=amendment['newMaximumAbsoluteDegrees']
  amend_ev=sha_evidence(amendment,f'{ceiling}-degree amendment'); record,_,_=read(amend_ev['path'])
  travel=sha_evidence(record.get('travelReviewEvidence'),'travelReviewEvidence')
  if record.get('newMaximumAbsoluteDegrees')!=ceiling or not same(amendment.get('travelReviewEvidence'),travel): err(f'{ceiling}-degree amendment travel review must match request envelope')
  q['evidence'].append(travel)
 node_validate(q,True)
 (out/'preview-request.json').write_text(json.dumps(q,indent=2)+'\n')
 print(out/'preview-request.json')

def finalize(args):
 q,qp,_=read(args.request); pr,pp,pbytes=read(args.preview)
 if q.get('scope') not in ('contiguous-native-scrap-batch-preview','contiguous-native-ftp-two-pad-preview','contiguous-native-ftp-conditioned-two-pad-preview') or q.get('enabled') is not False: err('Disabled preview request required')
 if pr.get('status')!='completed-model-only-contiguous-batch-preview' or pr.get('noControllerAccess') is not True or pr.get('noMotion') is not True or pr.get('id')!=q.get('id') or pr.get('jvmStartMs')!=q.get('jvmStartMs') or pr.get('liveConfigurationSha256')!=q.get('liveConfigurationSha256'): err('Matching no-controller/no-motion native preview required')
 if not same(pr.get('request'),q) or not isinstance(pr.get('stages'),list) or len(pr['stages'])!=len(q.get('previewStages',[])): err('Preview report request/stage count mismatch')
 q=copy.deepcopy(q); stages=[]
 for i,(s,p) in enumerate(zip(q['previewStages'],pr['stages'])):
  for k in ('axis','speedFraction','startRaw','targetRaw'):
   if not same(s.get(k),p.get(k)): err(f'Preview stage {i} {k} mismatch')
  if (s.get('dwellMilliseconds',0)!=p.get('dwellMilliseconds',0)): err(f'Preview stage {i} dwell mismatch')
  fe=p.get('formatterEvidence')
  if not isinstance(fe,dict): err(f'Preview stage {i} lacks formatter evidence')
  ev=sha_evidence(fe,f'preview stage {i} formatterEvidence')
  if p.get('path')!=ev['path'] or p.get('sha256')!=ev['sha256'] or not isinstance(p.get('expandedCommands'),list) or not p['expandedCommands']: err(f'Preview stage {i} formatter trace mismatch')
  s.update({'expandedCommands':p['expandedCommands'],'path':ev['path'],'sha256':ev['sha256']}); stages.append(s)
 q['previewStages']=stages; q['scope']=q['scope'][:-len('-preview')]; q['nativePreviewEvidence']=evidence(pp)
 q['evidence']=[e for e in q['evidence'] if e.get('path')!=q['nativePreviewEvidence']['path']]+[q['nativePreviewEvidence']]+[{'path':s['path'],'sha256':s['sha256']} for s in stages]
 node_validate(q,False)
 out=pp.parent/'runtime-request.json'
 with out.open('x') as f: f.write(json.dumps(q,indent=2)+'\n')
 print(out)

def main():
 p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
 a=sub.add_parser('prepare'); a.add_argument('--template',required=True); a.add_argument('--barrier',required=True); a.add_argument('--image',required=True); a.add_argument('--recipe',required=True); a.add_argument('--output',required=True); a.set_defaults(fn=prepare)
 b=sub.add_parser('finalize'); b.add_argument('--request',required=True); b.add_argument('--preview',required=True); b.set_defaults(fn=finalize)
 args=p.parse_args()
 try: args.fn(args)
 except Exception as e: p.error(str(e))
if __name__=='__main__': main()
