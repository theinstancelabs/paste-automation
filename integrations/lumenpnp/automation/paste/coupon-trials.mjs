#!/usr/bin/env node
/** Offline trial planning/observation records only. No machine connection or G-code. */
import {createHash} from 'node:crypto';
import {readFile, writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import guard from './safety.cjs';

const fail = message => {throw Error(message);};
const text = (v,k) => {if(typeof v!=='string'||!v.trim()||v.length>2000) fail(`${k} required`);};
const finite = (v,k) => {if(typeof v!=='number'||!Number.isFinite(v))fail(`${k} must be finite`);return v;};
const positive = (v,k) => {if(finite(v,k)<=0)fail(`${k} must be positive`);return v;};
const nonnegative = (v,k) => {if(finite(v,k)<0)fail(`${k} must be nonnegative`);return v;};
const clone = v => JSON.parse(JSON.stringify(v));
export const canonical = v => JSON.stringify(v,(_,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.keys(x).sort().map(k=>[k,x[k]])):x);
export const sha256 = v => createHash('sha256').update(v).digest('hex');
function reference(r,label){if(!r||typeof r.path!=='string'||!r.path.startsWith('/')||!/^[a-f0-9]{64}$/.test(r.sha256))fail(`${label} needs absolute path and SHA256`);}
function rect(r,label){if(!r)fail(`${label} required`);for(const a of ['x','y']){finite(r[a+'Min'],label);finite(r[a+'Max'],label);if(r[a+'Min']>=r[a+'Max'])fail(`${label} extents invalid`);}}
function contains(a,b){return b.xMin>=a.xMin&&b.xMax<=a.xMax&&b.yMin>=a.yMin&&b.yMax<=a.yMax;}
function gap(a,b){return Math.hypot(Math.max(a.xMin-b.xMax,b.xMin-a.xMax,0),Math.max(a.yMin-b.yMax,b.yMin-a.yMax,0));}
function checked(request,profile,profileReference){
 guard.profile(profile);reference(profileReference,'measured profile');
 if(!request||request.schema!==1||request.coordinateFrame!=='openpnp-N2-mm')fail('Registered native N2 request required');
 const s=request.substrate,p=request.process,l=request.limits;
 if(!s||s.kind!=='scrap'||s.support!=='unplatformed')fail('Separate unplatformed scrap substrate required');
 for(const k of ['id','registrationRecord','surfaceRecord','tipAndMaterialRecord','clearanceRecord'])text(s[k],`substrate ${k}`);
 rect(s.bounds,'scrap');rect(request.demoBounds,'demo exclusion');
 positive(request.minDemoGapMm,'minimum demo gap');positive(request.minPadGapMm,'minimum pad gap');positive(request.tipEdgeMarginMm,'tip edge margin');
 // The supplied +Y description never creates registration. Measured extents
 // must establish separation in this explicit native coordinate frame.
 if(s.bounds.yMin-request.demoBounds.yMax<request.minDemoGapMm)fail('Registered scrap must be separated on +Y side of demo');
 if(!contains({xMin:profile.xMin,xMax:profile.xMax,yMin:profile.yMin,yMax:profile.yMax},s.bounds))fail('Scrap outside measured native bounds');
 if(!Array.isArray(request.pads)||request.pads.length!==6)fail('Exactly six registered distinct unused pads required (3 compare + 3 repeat); empty template is not runnable');
 const ids=new Set();let width,height;
 for(const pad of request.pads){
  text(pad.id,'pad id');if(ids.has(pad.id))fail('Duplicate pad id');ids.add(pad.id);
  if(pad.unused!==true)fail('Every reserved pad must be explicitly unused');rect(pad.extents,'pad');
  if(!contains(s.bounds,pad.extents))fail('Pad outside scrap bounds');
  const w=pad.extents.xMax-pad.extents.xMin,h=pad.extents.yMax-pad.extents.yMin;
  if(width===undefined){width=w;height=h;}else if(Math.abs(w-width)>0.001||Math.abs(h-height)>0.001)fail('Dose comparison requires matching pad extents; separate different pad sizes');
  finite(pad.x,'pad x');finite(pad.y,'pad y');finite(pad.surfaceZ,'scrap surface Z');
  if(pad.x-pad.extents.xMin<request.tipEdgeMarginMm||pad.extents.xMax-pad.x<request.tipEdgeMarginMm||pad.y-pad.extents.yMin<request.tipEdgeMarginMm||pad.extents.yMax-pad.y<request.tipEdgeMarginMm)fail('Target lacks measured pad edge margin');
  if(pad.surfaceZ<profile.zMin||pad.surfaceZ>profile.zMax)fail('Scrap surface outside Z bounds');
  if((profile.clearanceDirection==='increasing'?profile.safeZ-pad.surfaceZ:pad.surfaceZ-profile.safeZ)<=0)fail('No measured clearance above scrap surface');
 }
 for(let i=0;i<request.pads.length;i++)for(let j=0;j<i;j++)if(gap(request.pads[i].extents,request.pads[j].extents)<request.minPadGapMm)fail('Pads overlap or lack required edge-to-edge spacing');
 if(!p||!l)fail('Measured process and limit records required');
 for(const k of ['doseLimitRecord','remainingStrokeRecord','currentRateLimitRecord'])text(l[k],k);
 for(const k of ['maxDoseDegrees','maxTotalGrossDegrees'])positive(l[k],k);
 for(const k of ['maxRetractionDegrees','maxDwellMilliseconds'])nonnegative(l[k],k);
 for(const k of ['maxMotorCurrentMa','maxDispenseDegreesPerMinute','maxRetractionDegreesPerMinute'])positive(l[k],k);
 positive(p.observedCurrentMa,'observed motor current');
 positive(p.dispenseDegreesPerMinute,'dispense angular rate');
 positive(p.retractionDegreesPerMinute,'retraction angular rate');
 text(p.currentSettingsRecord,'current/settings evidence');
 if(p.observedCurrentMa>l.maxMotorCurrentMa||p.dispenseDegreesPerMinute>l.maxDispenseDegreesPerMinute||p.retractionDegreesPerMinute>l.maxRetractionDegreesPerMinute)fail('Current or angular rate exceeds reviewed limit');
 if(!Array.isArray(p.dosesDegrees)||p.dosesDegrees.length!==3)fail('Exactly three explicit measured/conservative comparison doses required');
 p.dosesDegrees.forEach((dose,i)=>{positive(dose,'dose');if(dose>l.maxDoseDegrees||(i&&dose<=p.dosesDegrees[i-1]))fail('Doses must increase strictly within measured limit');});
 nonnegative(p.retractionDegrees,'retraction');nonnegative(p.dwellMilliseconds,'dwell');nonnegative(p.standoffMm,'standoff');
 if(p.retractionDegrees>p.dosesDegrees[0]||p.retractionDegrees>l.maxRetractionDegrees||p.dwellMilliseconds>l.maxDwellMilliseconds)fail('Retraction/dwell exceeds reviewed bounds');
 if(![-1,1].includes(p.verifiedDispenseSign))fail('Measured dispense direction required');text(p.directionRecord,'direction evidence');
 for(const pad of request.pads){const z=pad.surfaceZ+(profile.clearanceDirection==='increasing'?1:-1)*p.standoffMm;
  if(z<profile.zMin||z>profile.zMax||(profile.clearanceDirection==='increasing'?profile.safeZ-z:z-profile.safeZ)<=0)fail('Standoff approach outside measured Z/clearance');}
 if(p.dosesDegrees.reduce((a,b)=>a+b,0)>l.maxTotalGrossDegrees)fail('Comparison exceeds remaining gross stroke budget');
}
function seal(body){return {...body,sha256:sha256(canonical(body))};}
function verify(plan){const {sha256:hash,...body}=plan;if(hash!==sha256(canonical(body)))fail('Plan digest mismatch');if(plan.schema!==1||plan.kind!=='offline-coupon-trials'||plan.executionEnabled!==false)fail('Unknown/non-offline plan');checked(plan.request,plan.profile,plan.profileReference);return plan;}
function trials(request,pads,doses,stage){return pads.map((pad,i)=>({id:`${stage}-${i+1}`,padId:pad.id,x:pad.x,y:pad.y,surfaceZ:pad.surfaceZ,doseDegrees:doses[i],retractionDegrees:request.process.retractionDegrees,dwellMilliseconds:request.process.dwellMilliseconds,standoffMm:request.process.standoffMm,verifiedDispenseSign:request.process.verifiedDispenseSign,motorCurrentMa:request.process.observedCurrentMa,dispenseDegreesPerMinute:request.process.dispenseDegreesPerMinute,retractionDegreesPerMinute:request.process.retractionDegreesPerMinute,currentSettingsRecord:request.process.currentSettingsRecord}));}
export function planComparison(request,profile,profileReference){
 checked(request,profile,profileReference);
 return seal({schema:1,kind:'offline-coupon-trials',stage:'screening-comparison',executionEnabled:false,physicalAcceptanceEstablished:false,demoAuthorized:false,request:clone(request),profile:clone(profile),profileReference:clone(profileReference),trials:trials(request,request.pads.slice(0,3),request.process.dosesDegrees,'compare'),reservedRepeatPadIds:request.pads.slice(3).map(p=>p.id),grossDegrees:request.process.dosesDegrees.reduce((a,b)=>a+b,0)});
}
export function recordObservation(plan,observation){
 verify(plan);if(!observation)fail('Observation required');
 const t=plan.trials.find(t=>t.id===observation.trialId);if(!t||observation.padId!==t.padId||observation.planSha256!==plan.sha256)fail('Observation must bind exact plan/trial/pad');
 for(const k of ['operator','observedAt','notes'])text(observation[k],k);
 if(!/^\d{4}-\d\d-\d\dT.*Z$/.test(observation.observedAt)||!Number.isFinite(Date.parse(observation.observedAt)))fail('UTC observation timestamp required');
 if(!['deposited','no-deposit','uncertain','not-run'].includes(observation.outcome))fail('Explicit actual outcome required');
 if(!['too-small','too-large','acceptable-by-operator','defective','unassessed'].includes(observation.assessment))fail('Explicit operator assessment required');
 if(typeof observation.settingsMatchedPlan!=='boolean')fail('Explicit settings-matched-plan observation required');
 const actualSettings={motorCurrentMa:observation.appliedMotorCurrentMa,dispenseDegreesPerMinute:observation.appliedDispenseDegreesPerMinute,retractionDegreesPerMinute:observation.appliedRetractionDegreesPerMinute};
 const settingsKnown=Object.values(actualSettings).every(v=>typeof v==='number'&&Number.isFinite(v));
 const settingsMatch=settingsKnown&&actualSettings.motorCurrentMa===t.motorCurrentMa&&actualSettings.dispenseDegreesPerMinute===t.dispenseDegreesPerMinute&&actualSettings.retractionDegreesPerMinute===t.retractionDegreesPerMinute;
 if(['deposited','no-deposit'].includes(observation.outcome)&&!settingsKnown)fail('Actual motor current and angular rates required for an attempted trial');
 if(settingsKnown)for(const [k,v] of Object.entries(actualSettings))positive(v,k);
 else if(Object.values(actualSettings).some(v=>v!==null))fail('Actual current/rate values must all be finite or all null');
 if(observation.settingsMatchedPlan===true&&!settingsMatch)fail('Settings-matched claim conflicts with actual current/rates');
 if(['deposited','no-deposit'].includes(observation.outcome))nonnegative(observation.appliedDoseDegrees,'actual applied dose');
 else if(observation.appliedDoseDegrees!==null)nonnegative(observation.appliedDoseDegrees,'actual applied dose');
 if(observation.assessment==='acceptable-by-operator'&&observation.outcome!=='deposited')fail('Only an observed deposit can receive operator acceptable assessment');
 if(!Array.isArray(observation.evidence)||(!observation.evidence.length&&observation.outcome!=='not-run'))fail('Physical observation evidence required');
 observation.evidence.forEach(r=>reference(r,'observation evidence'));
 if(!Array.isArray(observation.settingsEvidence)||(!observation.settingsEvidence.length&&['deposited','no-deposit'].includes(observation.outcome)))fail('Evidence of actual motor current/angular-rate settings required for attempted trials');
 observation.settingsEvidence.forEach(r=>reference(r,'settings evidence'));
 if(!Array.isArray(observation.measurements))fail('Actual measurements array required; empty is valid');
 const names=new Set();for(const m of observation.measurements){text(m.name,'measurement name');if(names.has(m.name))fail('Duplicate measurement');names.add(m.name);nonnegative(m.value,'measured value');if(!['mm','mm2','ms','count'].includes(m.unit))fail('Measurement unit required');text(m.method,'measurement method');}
 return seal({schema:1,kind:'coupon-observation',planSha256:plan.sha256,observation:clone(observation),physicalAcceptanceEstablished:false,demoAuthorized:false,interpretation:'Operator observation recorded; software does not establish deposit quality or physical acceptance.'});
}
export function planRepeats(comparison,records,selection){
 verify(comparison);if(comparison.stage!=='screening-comparison')fail('Original screening comparison plan required');
 if(!Array.isArray(records)||records.length!==3)fail('All three comparison observations required');
 const seen=new Set();for(const r of records){const checkedRecord=recordObservation(comparison,r.observation);if(canonical(checkedRecord)!==canonical(r))fail('Observation record modified');const id=r.observation.trialId;if(seen.has(id))fail('Duplicate trial observation');seen.add(id);const trial=comparison.trials.find(t=>t.id===id),o=r.observation;if(o.settingsMatchedPlan!==true||o.appliedDoseDegrees!==trial.doseDegrees||o.appliedMotorCurrentMa!==trial.motorCurrentMa||o.appliedDispenseDegreesPerMinute!==trial.dispenseDegreesPerMinute||o.appliedRetractionDegreesPerMinute!==trial.retractionDegreesPerMinute)fail('Actual comparison dose/current/rates differ; review before new trial plan');if(!['deposited','no-deposit'].includes(o.outcome))fail('Uncertain/unrun comparison requires recovery and review, not repeat planning');}
 if(!selection||selection.comparisonSha256!==comparison.sha256||selection.fixtureUnchanged!==true||selection.registrationCurrent!==true)fail('Fresh unchanged-fixture/registration selection attestation required');
 for(const k of ['operator','reason','evidenceRecord','reviewedAt'])text(selection[k],`selection ${k}`);
 if(!/^\d{4}-\d\d-\d\dT.*Z$/.test(selection.reviewedAt)||!Number.isFinite(Date.parse(selection.reviewedAt))||records.some(r=>Date.parse(r.observation.observedAt)>Date.parse(selection.reviewedAt)))fail('Selection review must be timestamped after its observations');
 const selected=comparison.trials.find(t=>t.id===selection.selectedTrialId);if(!selected)fail('Select one reviewed comparison dose');
 const chosen=records.find(r=>r.observation.trialId===selected.id);if(chosen.observation.outcome!=='deposited'||chosen.observation.assessment!=='acceptable-by-operator')fail('Selected dose needs explicit acceptable operator deposit assessment');
 const total=comparison.grossDegrees+3*selected.doseDegrees;if(total>comparison.request.limits.maxTotalGrossDegrees)fail('Comparison plus repeats exceeds gross stroke budget');
 return seal({schema:1,kind:'offline-coupon-trials',stage:'repeat-validation',executionEnabled:false,physicalAcceptanceEstablished:false,demoAuthorized:false,request:clone(comparison.request),profile:clone(comparison.profile),profileReference:clone(comparison.profileReference),comparisonSha256:comparison.sha256,comparisonRecordSha256:records.map(r=>r.sha256).sort(),selection:clone(selection),trials:trials(comparison.request,comparison.request.pads.slice(3),Array(3).fill(selected.doseDegrees),'repeat'),grossDegrees:3*selected.doseDegrees,cumulativeGrossDegrees:total});
}
async function json(path){return JSON.parse(await readFile(path,'utf8'));}
async function verifyFileReference(r){reference(r,'file reference');if(sha256(await readFile(r.path))!==r.sha256)fail(`Referenced file changed: ${r.path}`);}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 try{
  const [mode,...args]=process.argv.slice(2);let result,output;
  if(mode==='compare'&&args.length===3){const [reqPath,profilePath,out]=args,raw=await readFile(profilePath);result=planComparison(await json(reqPath),JSON.parse(raw),{path:resolve(profilePath),sha256:sha256(raw)});output=out;}
  else if(mode==='record'&&args.length===3){const [planPath,obsPath,out]=args,plan=await json(planPath),obs=await json(obsPath);await verifyFileReference(plan.profileReference);for(const r of [...(obs.evidence||[]),...(obs.settingsEvidence||[])])await verifyFileReference(r);result=recordObservation(plan,obs);output=out;}
  else if(mode==='repeat'&&args.length===4){const [planPath,recordsPath,selectionPath,out]=args,plan=await json(planPath),records=await json(recordsPath);await verifyFileReference(plan.profileReference);for(const r of records)for(const e of [...r.observation.evidence,...(r.observation.settingsEvidence||[])])await verifyFileReference(e);result=planRepeats(plan,records,await json(selectionPath));output=out;}
  else fail('Usage: coupon-trials.mjs compare request.json measured-profile.json output.json | record plan.json observation.json output.json | repeat comparison.json records-array.json selection.json output.json');
  await writeFile(output,JSON.stringify(result,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify({output,sha256:result.sha256,executionEnabled:false,demoAuthorized:false}));
 }catch(e){console.error(e.message);process.exitCode=1;}
}
