'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),P=require('./commissioning-stroke.cjs');
const H='a'.repeat(64),uuid='12345678-1234-1234-1234-123456789abc';
function q(delta=20){return {schema:1,scope:'single-signed-raw-B-commissioning-stroke',enabled:false,id:uuid,sessionId:uuid,jvmStartMs:10,createdMs:1000,imageCapturedMs:800,reviewedImageMs:900,axis:'B',deltaDegrees:delta,speedFraction:.05,liveConfigurationSha256:H,evidence:[{path:'/x',sha256:H},{path:'/y',sha256:H},{path:'/z',sha256:H},{path:'/i',sha256:H}],expectedRaw:{X:1,Y:2,Z:31.5,A:720,B:-240},expectedDriver:{X:1,Y:2,Z:31.5,A:720,B:-240},expectedNativePoses:{},syringeId:'s1',primeLedgerSha256:H,carryoverSha256:H,previousLedgerSha256:null,clearanceReview:true,receivingProfile:{measured:true,flowCalibrated:false,sha256:H,measuredGapMm:.4,gapUncertaintyMm:.2,rawPose:{X:1,Y:2,Z:31.5,A:720}}};}
const carry={schema:1,sessionId:uuid,syringeId:'s1',primeLedgerSha256:H,priorGrossDegrees:10940,manualDisplacementUnknown:true,verifiedPrimeDegrees:960,startB:-240,maximumAbsoluteDegrees:120};
test('permits only bounded signed commissioning strokes and requires gap evidence for doses',()=>{for(const d of [2,4,6,20,-2,-4,-6,-20])P.validate(q(d),1000,10);for(const d of [0,1,3,5,7,19.9,21,-1,-3,-5,-7,-19.9,-21,-100])assert.throws(()=>P.validate(q(d),1000,10));const noGap=q(-2);noGap.receivingProfile.measuredGapMm=.29;assert.throws(()=>P.validate(noGap,1000,10),/gap/);const relief=q(20);relief.clearanceReview=false;assert.throws(()=>P.validate(relief,1000,10),/clear/);});
test('signed B target moves both ways while gross ledger charges absolute strokes and never refunds',()=>{let first=q(20),l=P.reserve(null,first,carry);assert.equal(l.entries[0].targetB,-220);assert.equal(l.totalAbsoluteDegrees,20);l=P.finish(l,first,true);const next=q(-2);next.id='22345678-1234-1234-1234-123456789abc';next.expectedRaw.B=-220;next.previousLedgerSha256=H;next.previousReportEvidence={path:'/report',sha256:H};const l2=P.reserve(l,next,carry);assert.equal(l2.entries[1].targetB,-222);assert.equal(l2.totalAbsoluteDegrees,22);assert.equal(P.finish(l2,next,true).lastVerifiedB,-222);});
test('ledger ceiling, replay, unverified old charge, and carryover mismatch fail closed',()=>{const l={schema:1,scope:'signed-B-commissioning-strokes',sessionId:uuid,syringeId:'s1',primeLedgerSha256:H,carryoverSha256:H,startB:-240,lastVerifiedB:-120,totalAbsoluteDegrees:120,status:'verified',entries:[]};for(let i=0;i<6;i++)l.entries.push({requestId:String(i).padStart(8,'0')+'-1234-1234-1234-123456789abc',startB:-240+i*20,targetB:-220+i*20,deltaDegrees:20,absoluteDegrees:20,status:'verified'});const next=q(-2);next.id='22345678-1234-1234-1234-123456789abc';next.expectedRaw.B=-120;next.expectedDriver.B=-120;next.previousLedgerSha256=H;next.previousReportEvidence={path:'/report',sha256:H};assert.throws(()=>P.reserve(l,next,carry),/exhausted/);assert.throws(()=>P.reserve(null,q(20),{...carry,priorGrossDegrees:0}));const bad=P.reserve(null,q(20),carry);bad.status='reserved';const replay={...q(-2),expectedRaw:{...q(-2).expectedRaw,B:-220},previousLedgerSha256:H,previousReportEvidence:{path:'/report',sha256:H}};assert.throws(()=>P.reserve(bad,replay,carry));});
function amendmentFixture(){
 const anchor={schema:1,scope:'signed-B-commissioning-strokes',sessionId:uuid,syringeId:'s1',primeLedgerSha256:H,carryoverSha256:H,startB:-240,lastVerifiedB:-284,totalAbsoluteDegrees:120,status:'verified',entries:[]},ds=[-20,-20,-20,-20,-2,20,6,6,6];let b=-240;
 ds.forEach((d,i)=>{const start=b;b+=d;anchor.entries.push({requestId:`5234567${i}-1234-1234-1234-123456789abc`,startB:start,targetB:b,deltaDegrees:d,absoluteDegrees:Math.abs(d),status:'verified'});});
 const anchorSha='b'.repeat(64),reportSha='c'.repeat(64),report={id:anchor.entries.at(-1).requestId,status:'completed-commissioning-stroke-awaiting-observation',uncertainCompletion:false,completedLedgerSha256:anchorSha,finishedAt:'1970-01-01T00:00:00.000Z',request:{id:anchor.entries.at(-1).requestId,sessionId:uuid,jvmStartMs:10,liveConfigurationSha256:H}};
 const record={schema:1,sessionId:uuid,syringeId:'s1',originalCarryoverSha256:H,anchorLedgerSha256:anchorSha,anchorGrossDegrees:120,anchorB:-284,newMaximumAbsoluteDegrees:240,reviewedAt:'1970-01-01T00:00:00.500Z',reviewedBy:'commissioning reviewer',reason:'Continue bounded commissioning after observed response.',anchorLedgerEvidence:{path:'/anchor-ledger.json',sha256:anchorSha},anchorReportEvidence:{path:'/anchor-report.json',sha256:reportSha}};
 const envelope={...record,path:'/budget-amendment.json',sha256:'d'.repeat(64)},context={record,anchorLedger:anchor,anchorReport:report,anchorLedgerSha256:anchorSha,anchorReportSha256:reportSha};
 return {anchor,anchorSha,report,record,envelope,context};
}
test('reviewed stroke amendment preserves the 120-degree anchor and permits only forward gross up to 240',()=>{
 const f=amendmentFixture(),next=q(6);next.id='62345678-1234-1234-1234-123456789abc';next.expectedRaw.B=-284;next.expectedDriver.B=-284;next.previousLedgerSha256='e'.repeat(64);next.previousReportEvidence={path:'/prior-report',sha256:'f'.repeat(64)};next.budgetAmendmentEvidence=f.envelope;next.createdMs=1000;next.reviewedImageMs=900;next.imageCapturedMs=800;
 const expanded=P.reserve(f.anchor,next,carry,f.context);assert.equal(expanded.totalAbsoluteDegrees,126);assert.equal(expanded.carryoverSha256,H);assert.equal(expanded.entries.length,f.anchor.entries.length+1);const complete=P.finish(expanded,next,true);assert.equal(complete.lastVerifiedB,-278);assert.equal(complete.totalAbsoluteDegrees,126);assert.equal(complete.carryoverSha256,H);
 const replay={...next,expectedRaw:{...next.expectedRaw,B:-278},expectedDriver:{...next.expectedDriver,B:-278},previousLedgerSha256:'9'.repeat(64)};assert.throws(()=>P.reserve(complete,replay,carry,f.context),/replay/);
 const atLimit=JSON.parse(JSON.stringify(f.anchor));let b=atLimit.lastVerifiedB;for(let i=0;i<6;i++){const d=20,start=b;b+=d;atLimit.entries.push({requestId:`7234567${i}-1234-1234-1234-123456789abc`,startB:start,targetB:b,deltaDegrees:d,absoluteDegrees:d,status:'verified'});}atLimit.lastVerifiedB=b;atLimit.totalAbsoluteDegrees=240;const over={...next,id:'82345678-1234-1234-1234-123456789abc',deltaDegrees:2,expectedRaw:{...next.expectedRaw,B:b},expectedDriver:{...next.expectedDriver,B:b},previousLedgerSha256:'8'.repeat(64)};assert.throws(()=>P.reserve(atLimit,over,carry,f.context),/budget exhausted/);
});
test('amendment rejects a changed anchor prefix, digest, carryover refund, and missing runtime evidence',()=>{
 const f=amendmentFixture(),next=q(6);next.id='92345678-1234-1234-1234-123456789abc';next.expectedRaw.B=-284;next.expectedDriver.B=-284;next.previousLedgerSha256='e'.repeat(64);next.previousReportEvidence={path:'/prior-report',sha256:'f'.repeat(64)};next.budgetAmendmentEvidence=f.envelope;
 const changed=JSON.parse(JSON.stringify(f.anchor));changed.entries[0].targetB+=1;assert.throws(()=>P.reserve(f.anchor,next,carry,{...f.context,anchorLedger:changed}),/prefix/);
 const badDigest={...f.context,record:{...f.record,anchorLedgerSha256:'a'.repeat(64)}};assert.throws(()=>P.reserve(f.anchor,next,carry,badDigest),/amendment/);
 assert.throws(()=>P.reserve(f.anchor,next,{...carry,maximumAbsoluteDegrees:240},f.context),/carryover/);
 assert.throws(()=>P.reserve(f.anchor,next,carry,null),/not loaded/);
 const highPrecision='1970-01-01T00:00:00.500123Z',precisionRecord={...f.record,reviewedAt:highPrecision},precisionEnvelope={...f.envelope,reviewedAt:highPrecision};assert.throws(()=>P.reserve(f.anchor,{...next,budgetAmendmentEvidence:precisionEnvelope},carry,{...f.context,record:precisionRecord}),/UTC ISO milliseconds/);
 const over={...f.record,newMaximumAbsoluteDegrees:241},overEnvelope={...f.envelope,newMaximumAbsoluteDegrees:241};assert.throws(()=>P.reserve(f.anchor,{...next,budgetAmendmentEvidence:overEnvelope},carry,{...f.context,record:over}),/amendment/);
});
test('verified cycle terminal report resumes a forward stroke only from the exact digest-bound ledger tail',()=>{const ledger={status:'verified',entries:[{requestId:uuid+':dose',cycleId:uuid,status:'verified'},{requestId:uuid+':retract',cycleId:uuid,status:'verified'}]},report={id:uuid,status:'completed-dose-cycle-awaiting-observation',uncertainCompletion:false,completedLedgerSha256:H,finishedAt:'2026-09-30T20:00:00.000Z',request:{id:uuid}};assert.equal(P.validatePreviousReport(report,ledger,H,Date.parse('2026-09-30T20:01:00.000Z')),true);assert.throws(()=>P.validatePreviousReport({...report,completedLedgerSha256:'b'.repeat(64)},ledger,H,Date.parse('2026-09-30T20:01:00.000Z')),/hash-bind/);assert.throws(()=>P.validatePreviousReport(report,{status:'verified',entries:[{requestId:'other',status:'verified'}]},H,Date.parse('2026-09-30T20:01:00.000Z')),/latest verified/);assert.throws(()=>P.validatePreviousReport(report,ledger,H,Date.parse('2026-09-30T19:59:00.000Z')),/fresh image/);});
function cycle(){const raw={X:1,Y:2,Z:58,A:720,B:-220},dose={...raw,B:-240},retract={...dose,B:-238},lift={...retract,Z:53};return {schema:1,scope:'single-native-B-dose-retract-Z-lift-cycle',enabled:false,id:'32345678-1234-1234-1234-123456789abc',sessionId:uuid,jvmStartMs:10,createdMs:1000,imageCapturedMs:800,reviewedImageMs:900,axis:'B',doseDegrees:20,retractDegrees:2,dwellMilliseconds:200,liftDeltaMm:-5,liftClearanceReview:true,dispenseSpeedFraction:.05,retractSpeedFraction:.05,liftSpeedFraction:1.0,liveConfigurationSha256:H,expectedRaw:raw,expectedDriver:{...raw},expectedNativePoses:{},liftTargetRaw:lift,syringeId:'s1',primeLedgerSha256:H,carryoverSha256:H,previousLedgerSha256:H,receivingProfile:{measured:true,flowCalibrated:false,sha256:H,measuredGapMm:.65,gapUncertaintyMm:.3,rawPose:{X:1,Y:2,Z:58,A:720}},evidence:Array.from({length:7},(_,i)=>({path:'/cycle-'+i,sha256:H})),previewStages:[{axis:'B',speedFraction:.05,startRaw:raw,targetRaw:dose,path:'/preview/dose',sha256:H},{axis:'B',speedFraction:.05,startRaw:dose,targetRaw:retract,path:'/preview/retract',sha256:H},{axis:'Z',speedFraction:1,startRaw:retract,targetRaw:lift,path:'/preview/lift',sha256:H}]};}
test('cycle binds negative lift, bounded parameters, and three intermediate preview targets',()=>{const q=cycle();P.validateCycle(q,1000,10);for(const patch of [{liftDeltaMm:5},{dwellMilliseconds:1001},{doseDegrees:3},{retractDegrees:1},{liftSpeedFraction:.05}])assert.throws(()=>P.validateCycle({...q,...patch},1000,10));const bad=cycle();bad.previewStages[1].targetRaw.B=-239;assert.throws(()=>P.validateCycle(bad,1000,10),/target chain/);});
test('cycle reserves dose and retract gross together, verifies intermediate B, then lifts without changing ledger B',()=>{let l=null;for(const [i,d] of [[0,20],[1,-2],[2,2]]){let s=q(d);s.id=`4234567${i}-1234-1234-1234-123456789abc`;if(l){s.expectedRaw.B=l.lastVerifiedB;s.expectedDriver.B=l.lastVerifiedB;s.previousLedgerSha256=H;s.previousReportEvidence={path:'/report',sha256:H};}l=P.reserve(l,s,carry);l=P.finish(l,s,true);}assert.equal(l.totalAbsoluteDegrees,24);const c=cycle();c.expectedRaw.B=l.lastVerifiedB;c.expectedDriver.B=l.lastVerifiedB;c.previewStages=cycle().previewStages;c.previewStages[0].startRaw.B=-220;c.previewStages[0].targetRaw.B=-240;c.previewStages[1].startRaw.B=-240;c.previewStages[1].targetRaw.B=-238;c.previewStages[2].startRaw.B=-238;c.previewStages[2].targetRaw.B=-238;c.liftTargetRaw.B=-238;c.previousLedgerSha256=H;const pending=P.reserveCycle(l,c,carry);assert.equal(pending.totalAbsoluteDegrees,46);assert.equal(pending.entries.at(-2).targetB,-240);assert.equal(pending.entries.at(-1).targetB,-238);assert.throws(()=>P.markCycleStep(pending,c,2,-238));const forged={...l,totalAbsoluteDegrees:0};assert.throws(()=>P.reserveCycle(forged,c,carry),/sum\/chain/);const afterDose=P.markCycleStep(pending,c,0,-240);assert.equal(afterDose.lastVerifiedB,-240);const afterRetract=P.markCycleStep(afterDose,c,1,-238);const complete=P.finishCycle(afterRetract,c,true);assert.equal(complete.status,'verified');assert.equal(complete.lastVerifiedB,-238);assert.equal(complete.totalAbsoluteDegrees,46);});
test('failed cycle faults pending substeps and retains the absolute reserve',()=>{const c=cycle();c.expectedRaw.B=-240;c.expectedDriver.B=-240;c.previousLedgerSha256=null;c.liftTargetRaw.B=-258;c.previewStages[0].startRaw.B=-240;c.previewStages[0].targetRaw.B=-260;c.previewStages[1].startRaw.B=-260;c.previewStages[1].targetRaw.B=-258;c.previewStages[2].startRaw.B=-258;c.previewStages[2].targetRaw.B=-258;const l=P.reserveCycle(null,c,carry),failed=P.finishCycle(l,c,false);assert.equal(failed.status,'faulted');assert.equal(failed.totalAbsoluteDegrees,22);assert.throws(()=>P.reserveCycle(failed,cycle(),carry));});

test('reviewed 240, 2400 and evidence-bound 3600 ceilings stay bounded with immutable anchor and individual20 cap',()=>{
 for(const ceiling of [240,2400,3600]){
  const f=amendmentFixture();f.record.newMaximumAbsoluteDegrees=ceiling;f.envelope.newMaximumAbsoluteDegrees=ceiling;
  if(ceiling===3600){f.record.travelReviewEvidence={path:'/travel-review.json',sha256:'9'.repeat(64)};f.envelope.travelReviewEvidence=f.record.travelReviewEvidence;}
  const ledger=JSON.parse(JSON.stringify(f.anchor));let i=0;
  while(ledger.totalAbsoluteDegrees<ceiling-20){const start=ledger.lastVerifiedB;ledger.entries.push({requestId:`${String(i++).padStart(8,'0')}-1234-1234-1234-123456789abc`,startB:start,targetB:start+20,deltaDegrees:20,absoluteDegrees:20,status:'verified'});ledger.lastVerifiedB+=20;ledger.totalAbsoluteDegrees+=20;}
  const next={...q(20),id:'a2345678-1234-1234-1234-123456789abc',expectedRaw:{...q().expectedRaw,B:ledger.lastVerifiedB},expectedDriver:{...q().expectedDriver,B:ledger.lastVerifiedB},previousLedgerSha256:H,previousReportEvidence:{path:'/prior-report',sha256:H},budgetAmendmentEvidence:f.envelope};
  if(ceiling===3600)next.evidence.push(f.record.travelReviewEvidence);
  assert.throws(()=>P.reserve(ledger,{...next,deltaDegrees:40},carry,f.context),/bounded reviewed signed B/);
  const reserved=P.reserve(ledger,next,carry,f.context);assert.equal(reserved.totalAbsoluteDegrees,ceiling);assert.deepEqual(reserved.entries.slice(0,f.anchor.entries.length),f.anchor.entries);assert.equal(carry.maximumAbsoluteDegrees,120);
  const done=P.finish(reserved,next,true),over={...next,id:'b2345678-1234-1234-1234-123456789abc',deltaDegrees:2,expectedRaw:{...next.expectedRaw,B:done.lastVerifiedB},expectedDriver:{...next.expectedDriver,B:done.lastVerifiedB}};
  assert.throws(()=>P.reserve(done,over,carry,f.context),/budget exhausted/);
 }
});

function amendedCycle(b,envelope,id='d2345678-1234-1234-1234-123456789abc'){
 const c=cycle(),raw={...c.expectedRaw,B:b},dose={...raw,B:b-4},retract={...raw,B:b-2},lift={...retract,Z:raw.Z-5};
 return {...c,id,doseDegrees:4,retractDegrees:2,expectedRaw:raw,expectedDriver:{...raw},liftTargetRaw:lift,budgetAmendmentEvidence:envelope,previewStages:[{...c.previewStages[0],startRaw:raw,targetRaw:dose},{...c.previewStages[1],startRaw:dose,targetRaw:retract},{...c.previewStages[2],startRaw:retract,targetRaw:lift}]};
}
function extendAnchor(anchor,gross){
 const l=JSON.parse(JSON.stringify(anchor));let i=0;
 while(l.totalAbsoluteDegrees<gross){const d=[20,6,4,2].find(n=>n<=gross-l.totalAbsoluteDegrees),start=l.lastVerifiedB;l.entries.push({requestId:`extra-${i++}`,startB:start,targetB:start-d,deltaDegrees:-d,absoluteDegrees:d,status:'verified'});l.lastVerifiedB-=d;l.totalAbsoluteDegrees+=d;}
 return l;
}
test('cycle amendment reserves both phases through reviewed 240 or 2400 ceiling without refund/replay',()=>{
 for(const ceiling of [240,2400]){
  const f=amendmentFixture();f.record.newMaximumAbsoluteDegrees=ceiling;f.envelope.newMaximumAbsoluteDegrees=ceiling;
  const l=extendAnchor(f.anchor,ceiling-6),c=amendedCycle(l.lastVerifiedB,f.envelope),reserved=P.reserveCycle(l,c,carry,f.context);
  assert.equal(reserved.totalAbsoluteDegrees,ceiling);assert.deepEqual(reserved.entries.slice(0,f.anchor.entries.length),f.anchor.entries);assert.deepEqual(reserved.entries.slice(-2).map(e=>e.absoluteDegrees),[4,2]);assert.equal(carry.maximumAbsoluteDegrees,120);
  const faulted=P.finishCycle(reserved,c,false);assert.equal(faulted.totalAbsoluteDegrees,ceiling);assert.throws(()=>P.reserveCycle(faulted,c,carry,f.context),/identity\/status/);
  const dose=P.markCycleStep(reserved,c,0,c.expectedRaw.B-4),retract=P.markCycleStep(dose,c,1,c.expectedRaw.B-2),done=P.finishCycle(retract,c,true);
  assert.throws(()=>P.reserveCycle(done,amendedCycle(done.lastVerifiedB,f.envelope,c.id),carry,f.context),/replay/);
  assert.throws(()=>P.reserveCycle(done,amendedCycle(done.lastVerifiedB,f.envelope,'e2345678-1234-1234-1234-123456789abc'),carry,f.context),/ceiling/);
  const onlyDoseFits=extendAnchor(f.anchor,ceiling-4);assert.throws(()=>P.reserveCycle(onlyDoseFits,amendedCycle(onlyDoseFits.lastVerifiedB,f.envelope),carry,f.context),/ceiling/);
 }
});
test('cycle at gross 464 needs loaded 2400 amendment and retains anchor/time/parameter gates',()=>{
 const f=amendmentFixture(),l=extendAnchor(f.anchor,464);f.record.newMaximumAbsoluteDegrees=2400;f.envelope.newMaximumAbsoluteDegrees=2400;
 const c=amendedCycle(l.lastVerifiedB,f.envelope);assert.equal(P.reserveCycle(l,c,carry,f.context).totalAbsoluteDegrees,470);
 assert.throws(()=>P.reserveCycle(l,c,carry),/not loaded/);assert.throws(()=>P.reserveCycle(l,{...c,budgetAmendmentEvidence:null},carry),/sum\/chain/);
 const changed=JSON.parse(JSON.stringify(l));changed.entries[0].targetB++;assert.throws(()=>P.reserveCycle(changed,c,carry,f.context),/prefix/);
 const stale={...f.record,reviewedAt:'1969-12-30T00:00:00.000Z'};assert.throws(()=>P.reserveCycle(l,{...c,budgetAmendmentEvidence:{...f.envelope,reviewedAt:stale.reviewedAt}},carry,{...f.context,record:stale}),/stale/);
 assert.throws(()=>P.reserveCycle(l,{...c,doseDegrees:40},carry,f.context),/bounds/);
 const small={...f.record,newMaximumAbsoluteDegrees:240};assert.throws(()=>P.reserveCycle(l,{...c,budgetAmendmentEvidence:{...f.envelope,newMaximumAbsoluteDegrees:240}},carry,{...f.context,record:small}),/ceiling/);
});

test('3600 requires exact loaded travel evidence and preserves charges, anchors and original carryover',()=>{
 const f=amendmentFixture(),travel={path:'/travel-review.json',sha256:'9'.repeat(64)};
 f.record.newMaximumAbsoluteDegrees=3600;f.envelope.newMaximumAbsoluteDegrees=3600;
 const next={...q(20),expectedRaw:{...q().expectedRaw,B:-284},expectedDriver:{...q().expectedDriver,B:-284},previousLedgerSha256:H,previousReportEvidence:{path:'/previous',sha256:H},budgetAmendmentEvidence:f.envelope};
 assert.throws(()=>P.reserve(f.anchor,next,carry,f.context),/travel review/);
 f.record.travelReviewEvidence=travel;f.envelope.travelReviewEvidence={...travel};
 assert.throws(()=>P.reserve(f.anchor,next,carry,f.context),/travel review/);
 next.evidence.push({...travel});f.envelope.travelReviewEvidence.sha256='8'.repeat(64);
 assert.throws(()=>P.reserve(f.anchor,next,carry,f.context),/travel review/);
 f.envelope.travelReviewEvidence={...travel,path:'/different-review.json'};
 assert.throws(()=>P.reserve(f.anchor,next,carry,f.context),/travel review/);
 f.envelope.travelReviewEvidence={...travel};const reserved=P.reserve(f.anchor,next,carry,f.context);
 assert.equal(reserved.totalAbsoluteDegrees,140);assert.deepEqual(reserved.entries.slice(0,f.anchor.entries.length),f.anchor.entries);
 const failed=P.finish(reserved,next,false);assert.equal(failed.totalAbsoluteDegrees,140);assert.equal(failed.entries.at(-1).status,'faulted');assert.throws(()=>P.reserve(failed,next,carry,f.context));
 const refund=JSON.parse(JSON.stringify(f.anchor));refund.totalAbsoluteDegrees=100;assert.throws(()=>P.reserve(refund,next,carry,f.context));
 assert.throws(()=>P.reserve(f.anchor,next,{...carry,maximumAbsoluteDegrees:3600},f.context),/carryover/);
});
