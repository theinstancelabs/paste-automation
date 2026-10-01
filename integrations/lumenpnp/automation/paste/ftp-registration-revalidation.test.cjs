'use strict';
const assert=require('assert');
const api=require('./ftp-registration-revalidation.cjs');
const H='a'.repeat(64),J='b'.repeat(64);
function ev(path,sha=H){return {path,sha256:sha};}
function clone(x){return JSON.parse(JSON.stringify(x));}
function fixture(){
 const reg={transformFromThreeFiducials:{matrix:[[1,0],[0,1]],translationMm:[0,0]},session:{fixedRawZAB:[32.25,720,-2706],topCameraZRotation:[0,0]},measurements:{}};
 const v={schema:1,scope:'ftp-registration-revalidation',originalRegistrationEvidence:ev('/reg.json'),reviewedBy:'reviewer',reviewedMs:10000,boardUnmovedSinceRegistration:true,measurements:{}};
 const files={'/revalidation.json':v,'/reg.json':reg};
 for(const [i,k] of ['FID1','FID2','FID3'].entries()){
  const design=[i+1,i+2],oldPath='/original/'+k+'/report.json',rp='/fresh/'+k+'/report.json',ip='/fresh/'+k+'/top-after-raw.png';
  reg.measurements[k]={report:ev(oldPath),designXYMm:design};
  files[oldPath]={id:'original-'+k};
  const start={X:design[0]+1,Y:design[1],Z:32.25,A:720,B:-2706};
  const end={X:design[0],Y:design[1],Z:32.25,A:720,B:-2706};
  const count={B:-12015};
  const pose={X:design[0],Y:design[1],Z:32.25,A:720,B:-2706};
  const stage={index:0,axis:'X',startRaw:clone(start),targetRaw:clone(end),verified:true,nativeMotionCompletionReported:true};
  const snap={raw:pose,nativePoses:{top:{x:design[0],y:design[1],z:0,rotation:0}}};
  const report={id:'new-'+k,status:'completed-contiguous-air-batch-awaiting-observation',finishedAt:new Date(9500).toISOString(),request:{id:'new-'+k,scope:'contiguous-native-scrap-batch',mode:'air',jvmStartMs:123,liveConfigurationSha256:'live-config',expectedRaw:clone(start),expectedDriver:clone(start),rawBounds:{B:{min:-2706,max:-2706}},previewStages:[{axis:'X',startRaw:clone(start),targetRaw:clone(end)}],finalTargetRaw:clone(end)},controllerPositionVerified:true,uncertainCompletion:false,afterImages:{top:{path:'top-after-raw.png'}},beforeQuerySnapshot:{raw:clone(start)},before:{saved:{raw:clone(start)},reported:clone(start),counts:clone(count)},stages:[stage],stage0:{saved:{raw:clone(end)},reported:clone(end),counts:clone(count)},afterQuerySnapshot:{raw:clone(pose),nativePoses:clone(snap.nativePoses)},expectedAfterRaw:clone(end),after:{saved:{raw:clone(end)},reported:clone(end),counts:clone(count)}};
  files[rp]=report;
  v.measurements[k]={report:ev(rp),image:ev(ip,J),fiducialIdentityReviewed:true,centeredInTopImageReviewed:true,observedCenterPixel:[127.5,127.5],imageSizePixels:[256,256]};
 }
 const q={jvmStartMs:123,liveConfigurationSha256:'live-config',ftpTargetRecord:{registrationEvidence:ev('/reg.json'),registrationRevalidationEvidence:ev('/revalidation.json'),reviewedMs:11000}};
 return {q,reg,files};
}
function run(change){const f=fixture();if(change)change(f);return api.verify(f.q,f.reg,(e,parse)=>parse?f.files[e.path]:null);}
assert.strictEqual(run(),true,'accept valid three-report air route');
assert.throws(()=>run(f=>{f.files['/fresh/FID1/report.json'].request.mode='wet';}),/air-batch scope/);
assert.throws(()=>run(f=>{f.files['/fresh/FID1/report.json'].stages[0].axis='B';}),/mismatched plan/);
assert.throws(()=>run(f=>{f.files['/fresh/FID1/report.json'].request.previewStages[0].targetRaw.X+=0.1;}),/mismatched plan/);
assert.throws(()=>run(f=>{f.files['/fresh/FID1/report.json'].stage0.counts.B+=1;}),/B drift/);
assert.throws(()=>run(f=>{f.files['/fresh/FID1/report.json'].request.finalTargetRaw.B+=1;}),/final target/);
assert.strictEqual(run(f=>{for(const k of ['FID1','FID2','FID3'])f.files['/fresh/'+k+'/report.json'].status='completed-camera-survey-awaiting-image-review';}),true,'preserve original camera-survey reports');
console.log('ftp-registration-revalidation synthetic compatibility: 7 checks passed');
