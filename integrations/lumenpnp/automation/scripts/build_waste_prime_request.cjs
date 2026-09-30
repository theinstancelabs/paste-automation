#!/usr/bin/env node
// Offline files only: hashes evidence and writes one request. No bridge/serial,
// ledger reservation/write, motion, activation, or dispatcher modification.
'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),P=require('../paste/waste-prime.cjs');
function file(filename,json=true){const full=path.resolve(filename),data=fs.readFileSync(full);return {value:json?JSON.parse(data):null,evidence:{path:full,sha256:crypto.createHash('sha256').update(data).digest('hex')}};}
function requireThat(ok,why){if(!ok)throw Error(why);}
function bound(e){const f=file(e.path);requireThat(f.evidence.sha256===e.sha256,'Bound JSON evidence changed');return f.value;}
function boundBytes(e){requireThat(file(e.path,false).evidence.sha256===e.sha256,'Bound measured/image evidence changed');}
function build(input,{now=Date.now(),id=crypto.randomUUID(),root=path.resolve(__dirname,'../..'),previewOnly=false}={}){
 const barrier=file(input.barrierPath),b=barrier.value;
 requireThat(b.status==='completed-read-only-position-barrier'&&b.controllerPositionVerified===true&&b.uncertainCompletion===false,'Successful fresh barrier required');
 const base={schema:1,id,createdMs:now,jvmStartMs:b.request.jvmStartMs,liveConfigurationSha256:b.liveConfigurationSha256,expectedRaw:b.afterQuerySnapshot.raw,expectedDriver:b.afterQuerySnapshot.driver,expectedNativePoses:b.afterQuerySnapshot.nativePoses};
 P.barrier(b,base,now);
 if(previewOnly)return {request:{...base,scope:'model-only-B-minus20-native-preview'},mode:'offline-model-preview-request'};
 requireThat(input.schema===1&&input.scope==='reviewed-waste-prime-request-input','Explicit offline request input required');
 requireThat(input.reviewedReceiverAndBothHeads===true&&input.noChangesSinceMeasurement===true,'Explicit current receiver/both-head and unchanged-measurement review required');
 requireThat(typeof input.reviewedMs==='number'&&Number.isFinite(input.reviewedMs)&&input.reviewedMs<=now&&now-input.reviewedMs<=300000,'Fresh input review required');
 const profile=file(input.profilePath),configuration=file(input.configurationPath),home=file(input.homePath),accounting=file(input.accountingPath),preview=file(input.nativePreviewPath),image=file(input.corridor.path,false),p=profile.value,c=configuration.value,h=home.value,v=preview.value;
 const fixedLedger=path.join(root,'automation/evidence/paste-waste-prime-session/ledger.json');
 let old=null,ledgerHash=null,observation=null;
 if(input.previousLedgerPath!==null){requireThat(path.resolve(input.previousLedgerPath)===fixedLedger,'Only fixed durable waste-prime ledger permitted');const f=file(fixedLedger);old=f.value;ledgerHash=f.evidence.sha256;observation=file(input.observationPath);}else requireThat(!fs.existsSync(path.dirname(fixedLedger)),'Existing session directory forbids a fresh ledger/reset');
 const q={...base,scope:'single-negative-raw-B-waste-prime',sessionId:p.sessionId,operator:input.operator,axis:'B',deltaDegrees:-20,speedFraction:.05,operatorVerifiedReceiver:true,bothHeadsClear:true,motionAreaClear:true,reviewedNegativeBWastePrime:true,installedNeedleId:input.installedNeedleId,noHomeOrReceiverOrNeedleChangeSinceMeasurement:true,previousLedgerSha256:ledgerHash,observationEvidence:observation?observation.evidence:null,barrierEvidence:barrier.evidence,profileEvidence:profile.evidence,configurationEvidence:configuration.evidence,homeEvidence:home.evidence,initialAccountingEvidence:accounting.evidence,corridorEvidence:{...image.evidence,capturedMs:input.corridor.capturedMs},nativePreviewEvidence:preview.evidence,expectedExpandedCommands:v.formatter&&v.formatter.expandedCommands};
 P.validate(q,now,q.jvmStartMs);P.profile(p,q);P.accounting(accounting.value,p,q);boundBytes(p.measurementEvidence);
 if(p.priorChargedDegrees>0)P.priorDirectionLedger(bound(accounting.value.priorDirectionLedgerEvidence),p);
 requireThat(c.status==='configured-B-prerequisites-in-memory-awaiting-fresh-barrier'&&c.exactTwoFieldChangeVerified===true&&c.noControllerCommands===true&&c.diskUnchanged===true&&c.coordinatesUnchanged===true&&c.configurationSaved===false&&c.liveConfigurationAfterSha256===q.liveConfigurationSha256&&c.request.jvmStartMs===q.jvmStartMs,'Matching successful B configuration required');
 requireThat(h.status==='completed-native-home-enabled-awaiting-image-review'&&h.uncertainCompletion===false&&h.controllerPositionVerified===true&&h.request.jvmStartMs===q.jvmStartMs,'Matching successful current home required');
 P.nativePreview(v,q,now);
 if(old){const o=observation.value,previousReport=bound(o.previousReportEvidence);requireThat(previousReport.completedLedgerSha256===ledgerHash,'Previous terminal report ledger hash mismatch');P.observation(o,previousReport,old.entries[old.entries.length-1],q,now);o.images.forEach(boundBytes);}
 const prospective=P.reserve(old,q,p); // Pure arithmetic only; never persisted.
 return {request:q,mode:'offline-waste-prime-request',prospectiveReservedDegrees:prospective.reservedDegrees,ledgerWritten:false,dispatched:false};
}
function writeRequest(destination,request){const dest=path.resolve(destination),tmp=dest+'.'+crypto.randomUUID()+'.tmp';fs.writeFileSync(tmp,JSON.stringify(request,null,2)+'\n',{flag:'wx'});try{fs.linkSync(tmp,dest);}finally{fs.unlinkSync(tmp);}return dest;}
function main(){const args=process.argv.slice(2),previewOnly=args.includes('--preview-only'),pos=args.filter(x=>x!=='--preview-only');if(pos.length!==2)throw Error('Usage: node build_waste_prime_request.cjs [--preview-only] input.json output-request.json');const result=build(JSON.parse(fs.readFileSync(pos[0],'utf8')),{previewOnly});const dest=writeRequest(pos[1],result.request);console.log(JSON.stringify({mode:result.mode,requestPath:dest,id:result.request.id,prospectiveReservedDegrees:result.prospectiveReservedDegrees,ledgerWritten:false,dispatched:false}));}
if(require.main===module){try{main();}catch(e){console.error(e.message);process.exitCode=1;}}
module.exports={build,writeRequest};
