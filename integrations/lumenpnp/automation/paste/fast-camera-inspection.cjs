/* Strict no-contact camera route contract shared by planner and Nashorn owner. */
(function(root){
'use strict';
function fail(message){throw Error(message);}
function finite(value,label){if(typeof value!=='number'||!isFinite(value))fail(label+' must be finite');return value;}
function object(value,label){if(!value||typeof value!=='object'||Array.isArray(value))fail(label+' must be an object');return value;}
function hash(value,label){if(typeof value!=='string'||!/^[a-f0-9]{64}$/.test(value))fail(label+' SHA-256 required');}
function axes(value,label){object(value,label);if(Object.keys(value).sort().join(',')!=='A,B,X,Y,Z')fail(label+' must name exactly raw X/Y/Z/A/B');Object.keys(value).forEach(function(k){finite(value[k],label+' '+k);});}
function close(a,b,tol,label){if(Math.abs(finite(a,label)-finite(b,label))>tol)fail(label+' mismatch');}
function validate(q,now,jvm){
 object(q,'Inspection request');
 if(q.schema!==1||q.scope!=='camera-only-registered-fast-inspection'||q.enabled!==true)fail('Enabled fast camera inspection request required');
 if(typeof q.id!=='string'||!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(q.id))fail('Fresh UUID required');
 if(q.createdMs>now||now-q.createdMs>300000||q.jvmStartMs!==jvm)fail('Inspection request is stale or belongs to another OpenPnP JVM');
 if(q.speedFraction!==1||q.speedOverPrecision!==true||q.maxSegmentMm!==10||q.maxTotalTravelMm>120)fail('Reviewed bounded camera-only speed policy required');
 if(q.operatorReviewed!==true||typeof q.reviewedBy!=='string'||!q.reviewedBy.trim()||typeof q.review!=='string'||q.review.trim().length<20)fail('Named review of the camera route required');
 axes(q.expectedRaw,'Expected raw');axes(q.expectedDriver,'Expected driver');
 if(q.expectedRaw.Z!==32.25||q.expectedRaw.A!==200)fail('Verified source must bind current Z/A to 32.25 / 200');
 if(q.expectedDriver.Z!==q.expectedRaw.Z||q.expectedDriver.A!==q.expectedRaw.A||q.expectedDriver.B!==q.expectedRaw.B)fail('Expected driver Z/A/B differ from raw axes');
 object(q.expectedNativePoses,'Expected native poses');['N1','N2','top','bottom'].forEach(function(n){var p=q.expectedNativePoses[n];object(p,n+' pose');['x','y','z','rotation'].forEach(function(k){finite(p[k],n+' '+k);});});
 object(q.sourceReport,'Terminal source report');hash(q.sourceReport.sha256,'Source report');if(typeof q.sourceReport.path!=='string'||q.sourceReport.path.indexOf('/automation/evidence/')<0)fail('Bound terminal report path required');
 object(q.registration,'Registration');hash(q.registration.sha256,'Registration');if(typeof q.registration.path!=='string'||!Array.isArray(q.registration.targets))fail('Hash-bound registration targets required');
 object(q.inspectionJob,'Inspection job');hash(q.inspectionJob.jobSha256,'Inspection job');hash(q.inspectionJob.boardSha256,'Inspection board');if(typeof q.inspectionJob.jobPath!=='string'||typeof q.inspectionJob.boardPath!=='string')fail('Hash-bound inspection job and board required');
 if(q.mode==='registered-references'){
  if(!Array.isArray(q.references)||q.references.length<1||q.references.length>8)fail('Choose one to eight registered component references');
  var seen={};q.references.forEach(function(ref){if(typeof ref!=='string'||!/^R(?:[1-9]|[1-3][0-9]|40)$/.test(ref)||seen[ref])fail('Reference list must contain unique FTP resistors');seen[ref]=true;});
  if(!Array.isArray(q.targets)||q.targets.length!==q.references.length)fail('Every reference must bind one registered target');
  q.targets.forEach(function(t,i){object(t,'Registered target');if(t.reference!==q.references[i])fail('Target order differs from named references');finite(t.x,'target X');finite(t.y,'target Y');if(!Array.isArray(t.pads)||t.pads.length!==2)fail('Target must bind both resistor pad centers');var padX=(finite(t.pads[0].x,'pad1 X')+finite(t.pads[1].x,'pad2 X'))/2,padY=(finite(t.pads[0].y,'pad1 Y')+finite(t.pads[1].y,'pad2 Y'))/2;close(t.x,padX,.0001,'registered midpoint X');close(t.y,padY,.0001,'registered midpoint Y');});
 }else if(q.mode==='reviewed-scrap-camera'){
  if(q.operatorReviewed!==true||typeof q.review!=='string'||q.review.length<20||!Array.isArray(q.references)||q.references.length!==0||!Array.isArray(q.targets)||q.targets.length!==1||q.targets[0].reference!=='scrap')fail('Explicitly reviewed scrap camera target required');
  close(q.targets[0].x,310,.0001,'reviewed scrap X');close(q.targets[0].y,232.27,.0001,'reviewed scrap Y');
 }else fail('Only registered references or the reviewed scrap camera target are allowed');
 var route= q.routeSteps;if(!Array.isArray(route)||route.length>32)fail('At most 32 bounded XY route steps allowed');
 var cursor={x:q.expectedRaw.X,y:q.expectedRaw.Y},total=0,captures=[];
 route.forEach(function(s,i){object(s,'Route step');if(s.index!==i||!Array.isArray(s.captureReferences))fail('Ordered route step required');var x=finite(s.x,'route X'),y=finite(s.y,'route Y'),dist=Math.sqrt((x-cursor.x)*(x-cursor.x)+(y-cursor.y)*(y-cursor.y));if(dist<.0001||dist>10.0001)fail('Each native camera step must move 0–10 mm in XY only');if(s.z!==q.expectedRaw.Z||s.a!==q.expectedRaw.A||s.b!==q.expectedRaw.B)fail('Route may not change Z, A or B');total+=dist;cursor={x:x,y:y};s.captureReferences.forEach(function(ref){captures.push(ref);});});
 if(total>120.0001||total>q.maxTotalTravelMm+.0001)fail('Camera route exceeds reviewed travel ceiling');
 if(q.mode==='registered-references'){if(captures.join(',')!==q.references.join(','))fail('Route captures must match selected references in order');route.forEach(function(step){step.captureReferences.forEach(function(ref){var t=q.targets.filter(function(x){return x.reference===ref;})[0];if(!t||Math.abs(step.x-t.x)>.0001||Math.abs(step.y-t.y)>.0001)fail('Reference capture waypoint must equal hash-bound registered target');});});}
 if(q.mode==='reviewed-scrap-camera'&&(route.length!==0||total!==0))fail('Reviewed current-position scrap capture must not move');
 q.plannedDistanceMm=total;return q;
}


function verifySourceReport(source,q){
 object(source,'Source report');var statuses=['completed-contiguous-air-batch-awaiting-observation','completed-contiguous-batch-awaiting-observation','completed-camera-survey-awaiting-image-review'];
 if(statuses.indexOf(source.status)<0||source.motionSubmitted!==true||source.controllerPositionVerified!==true||source.uncertainCompletion!==false||source.transportUncertain===true||source.id!==q.sourceReport.id)fail('Certain terminal source report required');
 var req=source.request||{};if(req.id!==source.id||req.jvmStartMs!==q.jvmStartMs||req.liveConfigurationSha256!==q.liveConfigurationSha256)fail('Source must bind same JVM and live configuration');
 var snap=source.afterQuerySnapshot||{};axes(snap.raw,'Source raw');axes(snap.driver,'Source driver');Object.keys(q.expectedRaw).forEach(function(k){close(snap.raw[k],q.expectedRaw[k],0,'source raw '+k);close(snap.driver[k],q.expectedDriver[k],0,'source driver '+k);});
 object(snap.nativePoses,'Source native poses');['N1','N2','top','bottom'].forEach(function(n){object(snap.nativePoses[n],n+' source pose');['x','y','z','rotation'].forEach(function(k){close(snap.nativePoses[n][k],q.expectedNativePoses[n][k],0,n+' source '+k);});});return true;
}
function verifyStep(q,before,step,model,reported){
 object(before,'Before step');object(model,'After model');object(reported,'After M114');
 var dx=finite(step.x,'step X')-finite(before.raw.X,'before X'),dy=finite(step.y,'step Y')-finite(before.raw.Y,'before Y');
 close(model.raw.X,step.x,.02,'model X');close(model.raw.Y,step.y,.02,'model Y');close(model.raw.Z,q.expectedRaw.Z,.02,'model Z');close(model.raw.A,q.expectedRaw.A,.3,'model A');close(model.raw.B,q.expectedRaw.B,.3,'model B');
 close(reported.X,step.x,.02,'M114 X');close(reported.Y,step.y,.02,'M114 Y');close(reported.Z,q.expectedRaw.Z,.02,'M114 Z');close(reported.A,q.expectedRaw.A,.3,'M114 A');close(reported.B,q.expectedRaw.B,.3,'M114 B');
 Object.keys(q.expectedNativePoses).forEach(function(n){var a=before.nativePoses[n],b=model.nativePoses[n];object(a,'before '+n);object(b,'after '+n);if(n==='bottom'){close(b.x,a.x,.0001,n+' fixed X');close(b.y,a.y,.0001,n+' fixed Y');}else{close(b.x,a.x+dx,.02,n+' expected X');close(b.y,a.y+dy,.02,n+' expected Y');}close(b.z,a.z,.0001,n+' unchanged Z');close(b.rotation,a.rotation,.0001,n+' unchanged rotation');});return true;
}
function installationPolicy(policy,installationLock,action){
 object(policy,'Camera inspection policy');object(installationLock,'Installation lock');
 if(policy.schema!==1||policy.scope!=='camera-only-inspection-under-paste-installation-lock'||policy.enabled!==true||policy.action!==action||action!=='paste-fast-camera-inspection')fail('Dedicated camera inspection policy rejects action');
 if(installationLock.schema!==1||typeof installationLock.locked!=='boolean')fail('Main installation lock missing or malformed');
 if(policy.requiresInstallationLockPreserved!==true||policy.noPasteActuation!==true||policy.topCameraXYOnly!==true||policy.n2Quarantined!==true)fail('Camera inspection may not relax paste installation restrictions');
 return true;
}
var api={validate:validate,verifyStep:verifyStep,verifySourceReport:verifySourceReport,installationPolicy:installationPolicy};if(typeof module!=='undefined')module.exports=api;else root.PasteFastCameraInspection=api;
})(this);
