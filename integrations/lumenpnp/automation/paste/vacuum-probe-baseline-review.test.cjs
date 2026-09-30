'use strict';
// Independent offline regression scenarios: no transport or machine callbacks.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const native=require('./vacuum-probe-native.cjs');
const contract={offBaselineTolerance:1,baselineTolerance:1,expectedEmptyMean:232.25,expectedEmptyTolerance:1.5,minimumPumpResponseDelta:10};
const validOn=[233,233,232,232,232,232,232,232];
test('fresh baseline accepts observed empty band with explicit pump response',()=>{
 const result=native.validateFreshBaselines([255,255,255],validOn,contract);
 assert.equal(result.onMean,232.25);assert.equal(result.pumpResponseDelta,22.75);
});
test('stable pump failure, blockage and inadequate pump contrast never pass',()=>{
 for(const [off,on] of [[[255,255,255],Array(8).fill(255)],[[255,255,255],Array(8).fill(210)],[[240,240,240],validOn]])
  assert.throws(()=>native.validateFreshBaselines(off,on,contract));
});
test('no missing, unstable or malformed sample can authorize descent',()=>{
 for(const [off,on] of [[[255,255],validOn],[[255,255,255],validOn.slice(1)],[[255,250,255],validOn],[[255,255,255],[230,233,232,232,232,232,232,232]],[[255,NaN,255],validOn],[[255,255,255],[Infinity,...validOn.slice(1)]]])
  assert.throws(()=>native.validateFreshBaselines(off,on,contract));
});
test('empty-mean band boundaries are enforced independently of stable spread',()=>{
 assert.doesNotThrow(()=>native.validateFreshBaselines([255,255,255],Array(8).fill(231),contract));
 assert.throws(()=>native.validateFreshBaselines([255,255,255],Array(8).fill(230),contract));
 assert.throws(()=>native.validateFreshBaselines([255,255,255],Array(8).fill(234),contract));
});
test('baseline evidence cannot be accepted with missing or nonfinite thresholds',()=>{
 for(const c of [{},{...contract,expectedEmptyTolerance:NaN},{...contract,minimumPumpResponseDelta:Infinity}])
  assert.throws(()=>native.validateFreshBaselines([255,255,255],validOn,c));
});
