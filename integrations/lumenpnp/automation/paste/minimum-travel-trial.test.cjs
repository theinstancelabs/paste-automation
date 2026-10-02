'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const C=require('./commissioning-stroke.cjs'),Group=require('./ftp-pad-group.cjs');
function trial(){return {scope:'contiguous-native-ftp-minimum-travel-eight-pad-preview',mode:'wet',ftpTargetRecord:{scope:'ftp-selected-pads-targets',compensatedSequence:{doseDegrees:6,retractPercent:30,requestedRetractionDegrees:1.8},minimumTravelPolicy:{plan:{transitions:Array.from({length:7},(_,i)=>({reason:i%2?'component-boundary':'same-component-short-move',xyTravelMm:i%2?3:1,retractBeforeMove:!!(i%2),restoreAfterMove:!!(i%2),skipRequiresNoPriorRetract:!(i%2),preserveClearanceLift:true}))},pads:[]}}};}
function retractRecord(start=-3976.6,delta=1.8){const stage={axis:'B',startRaw:{B:start},targetRaw:{B:start+delta}},steps=C.controllerStepCount(stage.targetRaw.B)-C.controllerStepCount(stage.startRaw.B);return {stage,pad:{pairOrder:2,retractPercent:30,requestedRetractionDegrees:1.8,actualRetractRawDelta:delta,actualRetractControllerSteps:steps,actualQuantizedRetractionDegrees:steps/4.44}};}
test('minimum-travel policy admits only phase-aware 30% of 6 degree interpair retracts',()=>{
 const {stage,pad}=retractRecord();assert.equal(C.validateMinimumTrialRetraction(trial(),pad,stage).actualCountDelta,8);
 for(const bad of [{...pad,retractPercent:25},{...pad,requestedRetractionDegrees:1.5},{...pad,actualRetractControllerSteps:7},{...pad,actualRetractRawDelta:1.7}])assert.throws(()=>C.validateMinimumTrialRetraction(trial(),bad,stage));
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
