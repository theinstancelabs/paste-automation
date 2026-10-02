'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const C=require('./commissioning-stroke.cjs'),Group=require('./ftp-pad-group.cjs');
function trial(percent=30){return {scope:'contiguous-native-ftp-minimum-travel-eight-pad-preview',mode:'wet',ftpTargetRecord:{scope:'ftp-selected-pads-targets',compensatedSequence:{doseDegrees:6,retractPercent:percent,requestedRetractionDegrees:6*percent/100},minimumTravelPolicy:{plan:{transitions:Array.from({length:7},(_,i)=>({reason:i%2?'component-boundary':'same-component-short-move',xyTravelMm:i%2?3:1,retractBeforeMove:!!(i%2),restoreAfterMove:!!(i%2),skipRequiresNoPriorRetract:!(i%2),preserveClearanceLift:true}))},pads:[]}}};}
function retractRecord(percent,start=-3976.6){const requested=6*percent/100,expected=requested*4.44;let best=null;for(let n=-30;n<=30;n++){const delta=Math.round((requested+n*.01)*100)/100,target=start+delta,count=C.controllerStepCount(target)-C.controllerStepCount(start),error=Math.abs(count-expected);if(!best||error<best.error||error===best.error&&Math.abs(delta-requested)<Math.abs(best.delta-requested))best={delta,count,error};}const stage={axis:'B',startRaw:{B:start},targetRaw:{B:start+best.delta}};return {stage,pad:{pairOrder:2,retractPercent:percent,requestedRetractionDegrees:requested,actualRetractRawDelta:best.delta,actualRetractControllerSteps:best.count,actualQuantizedRetractionDegrees:best.count/4.44}};}
test('minimum-travel policy admits phase-aware 15/20/25/30% of six-degree interpair retracts',()=>{
 for(const percent of [15,20,25,30]){const {stage,pad}=retractRecord(percent);assert.ok(Math.abs(C.validateMinimumTrialRetraction(trial(percent),pad,stage).actualCountDelta-6*percent/100*4.44)<=.500001);}
 const {stage,pad}=retractRecord(30);for(const bad of [{...pad,retractPercent:25},{...pad,requestedRetractionDegrees:1.5},{...pad,actualRetractControllerSteps:7},{...pad,actualRetractRawDelta:1.7}])assert.throws(()=>C.validateMinimumTrialRetraction(trial(),bad,stage));
});
test('pair restore must reverse the conditioner or prior pair retract exactly in raw B and controller counts',()=>{
 const source={axis:'B',startRaw:{B:200},targetRaw:{B:203}},restore={axis:'B',startRaw:{B:203},targetRaw:{B:200}},pad={pairOrder:1};
 assert.equal(C.validateMinimumTrialRestore(pad,restore,source).restoreCountDelta,C.controllerStepCount(200)-C.controllerStepCount(203));
 assert.throws(()=>C.validateMinimumTrialRestore(pad,{...restore,targetRaw:{B:199.99}},source));
});
test('trial scope and four reviewed same-component moves are explicit',()=>{
 const q=trial();assert.equal(Group.isMinimumTravelTrial(q),true);assert.equal(Group.minimumTravelTrialScope(true),q.scope);
 q.ftpTargetRecord.minimumTravelPolicy.plan.transitions[0].xyTravelMm=2;assert.throws(()=>Group.validateMinimumTravelTrial(q));
});
