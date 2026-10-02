'use strict';
const assert=require('assert');
const F=require('./fast-camera-inspection.cjs');
const H='a'.repeat(64);
function pose(x,y,z,r){return {x,y,z,rotation:r};}
function fixture(){
 var raw0={X:100,Y:200,Z:32.25,A:200,B:-4316.05},raw1={X:100.1,Y:200,Z:32.25,A:200,B:-4316.05};
 var poses0={N1:pose(100,180,32.25,200),N2:pose(120,180,30.75,-4316.05),top:pose(100,200,15,0),bottom:pose(40,50,25.2,0)};
 var poses1={N1:pose(100.1,180,32.25,200),N2:pose(120.1,180,30.75,-4316.05),top:pose(100.1,200,15,0),bottom:pose(40,50,25.2,0)};
 var q={schema:1,scope:'camera-only-registered-fast-inspection',enabled:true,id:'12345678-1234-4234-8234-123456789abc',mode:'registered-fiducials',references:['FID1'],targets:[{reference:'FID1',x:100.1,y:200,pads:[]}],speedFraction:1,speedOverPrecision:true,maxSegmentMm:10,maxTotalTravelMm:120,operatorReviewed:true,reviewedBy:'test',completionScope:'Camera frames and XY position reports only; no paste, calibration, or placement acceptance.',jvmStartMs:1,liveConfigurationSha256:H,expectedRaw:raw0,expectedDriver:raw0,expectedNativePoses:poses0,plannedDistanceMm:.1,routeSteps:[{index:0,x:100.1,y:200,z:32.25,a:200,b:-4316.05,captureReferences:['FID1']}]};
 return {schema:1,id:q.id,scope:q.scope,status:'completed-camera-survey-awaiting-image-review',request:q,motionSubmitted:true,controllerPositionVerified:true,nativeMotionCompletionReported:true,uncertainCompletion:false,physicalAcceptanceEstablished:false,calibrationEstablished:false,beforeQuerySnapshot:{raw:raw0,driver:raw0,nativePoses:poses0},afterQuerySnapshot:{raw:raw1,driver:raw1,nativePoses:poses1},beforeReported:raw0,afterReported:raw1,transitions:[{status:'route-step-0-verified'}],frames:[{reference:'FID1',path:'frame.png',width:1920,height:1080,rawAxes:raw1,nativePose:poses1.top}],afterImages:{top:{path:'frame.png',width:1920,height:1080}}};
}
assert.strictEqual(F.verifyCalibrationReport(fixture(),'FID1'),true);
for(const mutate of [r=>r.afterQuerySnapshot.raw.B+=1,r=>r.afterQuerySnapshot.driver.X+=.01,r=>r.afterReported.Y+=.01,r=>r.request.routeSteps[0].b+=1,r=>r.transitions[0].status='route-step-0-submitted',r=>r.frames[0].reference='FID2']){
 const r=fixture();mutate(r);assert.throws(()=>F.verifyCalibrationReport(r,'FID1'));
}
assert.throws(()=>F.verifyCalibrationReport(fixture(),'FID2'));
var reference=fixture();reference.request.mode='registered-references';reference.request.references=['R1'];reference.request.targets=[{reference:'R1',x:100.1,y:200,pads:[{padId:'R1.1',x:99.2,y:200},{padId:'R1.2',x:100.1,y:200}]}];reference.request.routeSteps[0].captureReferences=['R1'];reference.frames[0].reference='R1';assert.strictEqual(F.verifyCalibrationReport(reference,'R1'),true);
var duplicateReference=fixture();duplicateReference.request.mode='registered-references';duplicateReference.request.references=['R1'];duplicateReference.request.targets=[{reference:'R1',x:100.1,y:200,pads:[{padId:'R1.1',x:99.2,y:200},{padId:'R1.1',x:100.1,y:200}]}];duplicateReference.request.routeSteps[0].captureReferences=['R1'];assert.throws(()=>F.verifyCalibrationReport(duplicateReference,'R1'));
console.log('fast-camera-inspection.test.cjs: passed');
