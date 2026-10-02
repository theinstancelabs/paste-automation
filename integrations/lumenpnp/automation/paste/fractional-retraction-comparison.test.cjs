'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const C=require('./commissioning-stroke.cjs');
const percents=[15,20,25,30];
function record(){return {schema:1,protocol:'four-group-fractional-retraction-comparison',doseDegrees:6,stepsPerDegree:4.44,groups:percents.map((p,i)=>({group:i+1,retractPercent:p,padIds:Array.from({length:8},(_,n)=>'G'+(i+1)+'P'+(n+1))}))};}
function padFor(r,i,stage){const d=stage.targetRaw.B-stage.startRaw.B,n=C.controllerStepCount(stage.targetRaw.B)-C.controllerStepCount(stage.startRaw.B);return {padId:r.groups[i].padIds[0],group:i+1,retractPercent:percents[i],actualRetractRawDelta:d,actualRetractControllerSteps:n,actualQuantizedRetractionDegrees:n/4.44};}
test('four absolute retraction amounts quantize to audited B step counts',()=>{
 const expected=[4,5,7,8],r=record();assert.equal(C.validateFractionalRetractionComparison(r),r);
 percents.forEach((p,i)=>{const spec=C.retractionCountsForPercent(p,6,4.44);assert.equal(spec.requestedDegrees,[.9,1.2,1.5,1.8][i]);assert.equal(spec.roundedSteps,expected[i]);
  const stage={axis:'B',startRaw:{B:100},targetRaw:{B:100+spec.requestedDegrees}};
  const pad=padFor(r,i,stage),checked=C.validateFractionalRetractionComparison(r,pad,stage,4.44);
  assert.equal(checked.roundedSteps,expected[i]);assert.equal(checked.actualCountDelta,expected[i]);
 });
});
test('comparison policy rejects altered group order, percentage, dose, scale, and duplicate pads',()=>{
 for(const edit of [r=>r.groups[0].retractPercent=20,r=>r.groups[2].group=2,r=>r.doseDegrees=4,r=>r.stepsPerDegree=4.4,r=>r.groups[3].padIds[0]=r.groups[0].padIds[0]]){const r=record();edit(r);assert.throws(()=>C.validateFractionalRetractionComparison(r));}
});
test('per-pad validation binds group identity and checks absolute-count delta, rejecting stale or malformed stage',()=>{
 const r=record(),i=2;
 const stage={axis:'B',startRaw:{B:100},targetRaw:{B:101.5}};
 const pad=padFor(r,i,stage);assert.equal(C.validateFractionalRetractionComparison(r,pad,stage).actualCountDelta,7);
 for(const bad of [
  {pad:{...pad,group:2},stage},
  {pad:{...pad,padId:'foreign'},stage},
  {pad,stage:{...stage,axis:'Z'}},
  {pad,stage:{...stage,targetRaw:{B:101.3}}},
  {pad,stage:{...stage,targetRaw:{B:101.7}}},
 ])assert.throws(()=>C.validateFractionalRetractionComparison(r,bad.pad,bad.stage));
});
test('fractional step delta is evaluated at the absolute B count phase',()=>{
 const feasible={axis:'B',startRaw:{B:-240},targetRaw:{B:-238.86}};
 const r=record(),pad=padFor(r,1,feasible);
 const accepted=C.validateFractionalRetractionComparison(r,pad,feasible);
 assert.equal(accepted.actualCountDelta,5);
 assert.ok(accepted.countLatticeError<=0.5);
 const sixCounts={axis:'B',startRaw:{B:-240},targetRaw:{B:-238.8}};
 assert.throws(()=>C.validateFractionalRetractionComparison(r,pad,sixCounts),/bound actual amount/);
});
test('ledger B verification for fractional retracts requires the exact audited controller count',()=>{
 const q={id:'12345678-1234-1234-1234-123456789abc',previewStages:[{axis:'B'}]},start=100,target=100.9;
 const entry={batchId:q.id,stageIndex:0,startB:start,targetB:target,batchScope:'contiguous-native-ftp-retraction-comparison',retractionComparisonGroup:1,retractionPercent:15,controllerStepDelta:4,status:'reserved'};
 const ledger={status:'reserved',activeBatchId:q.id,lastVerifiedB:start,entries:[entry]};
 const good=C.markBatchStep(ledger,q,0,target+0.01);assert.equal(good.lastVerifiedB,target);assert.equal(good.entries[0].status,'verified');
 assert.throws(()=>C.markBatchStep(ledger,q,0,target+0.2),/count verification/);
});
