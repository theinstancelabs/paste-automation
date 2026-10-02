/* Strict no-contact camera route contract shared by planner and Nashorn owner. */
(function(root){
'use strict';
function fail(message){throw Error(message);}
function finite(value,label){if(typeof value!=='number'||!isFinite(value))fail(label+' must be finite');return value;}
function object(value,label){if(!value||typeof value!=='object'||Array.isArray(value))fail(label+' must be an object');return value;}
function hash(value,label){if(typeof value!=='string'||!/^[a-f0-9]{64}$/.test(value))fail(label+' SHA-256 required');}
function same(a,b){return JSON.stringify(a)===JSON.stringify(b);}
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
 if(q.mode==='registered-fiducials'){
  if(['base','xplus','yplus'].indexOf(q.fiducialSample)<0)fail('FID sample must be base, xplus or yplus');
  if(!Array.isArray(q.references)||q.references.length<1||q.references.length>3)fail('Choose one to three registered fiducials');
  if(q.fiducialSample!=='base'&&q.references.length!==1)fail('An offset sample must select exactly one registered fiducial');
  var seenF={};q.references.forEach(function(ref){if(['FID1','FID2','FID3'].indexOf(ref)<0||seenF[ref])fail('Only unique FID1/FID2/FID3 targets are allowed');seenF[ref]=true;});
  if(!Array.isArray(q.targets)||q.targets.length!==q.references.length)fail('Every fiducial must bind one measured target');
  var sources=q.registration.fiducials||{},offsets={base:[0,0],xplus:[1,0],yplus:[0,1]};if(Array.isArray(sources)){var map={};sources.forEach(function(x){map[x.reference]=x.measuredTopCameraXYMm;});sources=map;}
  var center=q.fiducialCenteringReport;if(center){object(center,'Native FID centering evidence');hash(center.sha256,'FID centering report');hash(center.image&&center.image.sha256,'FID centering image');if(typeof center.path!=='string'||typeof center.id!=='string'||typeof center.finishedAt!=='string'||center.reference!==q.references[0]||!Array.isArray(center.detectedMachineXYMm)||center.detectedMachineXYMm.length!==2||q.references.length!==1)fail('One hash-bound native FID centering report required');var centerMs=Date.parse(center.finishedAt);if(!isFinite(centerMs)||centerMs>now||now-centerMs>1800000)fail('FID centering report must be no more than 30 minutes old');var registered=sources[center.reference];if(!Array.isArray(registered)||Math.sqrt(Math.pow(center.detectedMachineXYMm[0]-registered[0],2)+Math.pow(center.detectedMachineXYMm[1]-registered[1],2))>.2)fail('Detected FID center differs from accepted registration by more than 0.2 mm');}
  q.targets.forEach(function(t,i){var xy=center?center.detectedMachineXYMm:sources[q.references[i]],o=offsets[q.fiducialSample];object(t,'Measured fiducial target');if(!Array.isArray(xy)||xy.length!==2||t.reference!==q.references[i]||!Array.isArray(t.pads)||t.pads.length!==0||t.sample!==q.fiducialSample||!Array.isArray(t.offsetXYMm)||t.offsetXYMm.length!==2)fail('Fiducial target must bind its native registration measurement and named sample');close(t.offsetXYMm[0],o[0],0,'fiducial sample offset X');close(t.offsetXYMm[1],o[1],0,'fiducial sample offset Y');close(t.x,xy[0]+o[0],.000001,'fiducial X');close(t.y,xy[1]+o[1],.000001,'fiducial Y');finite(t.x,'target X');finite(t.y,'target Y');});
 }else if(q.mode==='registered-references'){
  if(q.fiducialSample!==null&&q.fiducialSample!==undefined)fail('FID sample may only be used with registered fiducials');
  if(['midpoint','pad1','pad2'].indexOf(q.targetMode)<0)fail('Registered target mode must be midpoint, pad1 or pad2');
  if(!Array.isArray(q.references)||q.references.length<1||q.references.length>8)fail('Choose one to eight registered component references');
  var seen={};q.references.forEach(function(ref){if(typeof ref!=='string'||!/^R(?:[1-9]|[1-3][0-9]|40)$/.test(ref)||seen[ref])fail('Reference list must contain unique FTP resistors');seen[ref]=true;});
  if(!Array.isArray(q.targets)||q.targets.length!==q.references.length)fail('Every reference must bind one registered target');
  q.targets.forEach(function(t,i){object(t,'Registered target');if(t.reference!==q.references[i])fail('Target order differs from named references');finite(t.x,'target X');finite(t.y,'target Y');if(!Array.isArray(t.pads)||t.pads.length!==2)fail('Target must bind both resistor pad centers');var pad1X=finite(t.pads[0].x,'pad1 X'),pad1Y=finite(t.pads[0].y,'pad1 Y'),pad2X=finite(t.pads[1].x,'pad2 X'),pad2Y=finite(t.pads[1].y,'pad2 Y'),padX=(pad1X+pad2X)/2,padY=(pad1Y+pad2Y)/2,expectedX=q.targetMode==='pad1'?pad1X:q.targetMode==='pad2'?pad2X:padX,expectedY=q.targetMode==='pad1'?pad1Y:q.targetMode==='pad2'?pad2Y:padY;close(t.x,expectedX,.0001,'registered target X');close(t.y,expectedY,.0001,'registered target Y');});
 }else if(q.mode==='reviewed-scrap-camera'){
  if(q.operatorReviewed!==true||typeof q.review!=='string'||q.review.length<20||!Array.isArray(q.references)||q.references.length!==0||!Array.isArray(q.targets)||q.targets.length!==1||q.targets[0].reference!=='scrap')fail('Explicitly reviewed scrap camera target required');
  close(q.targets[0].x,310,.0001,'reviewed scrap X');close(q.targets[0].y,232.27,.0001,'reviewed scrap Y');
 }else fail('Only registered references or the reviewed scrap camera target are allowed');
 var route= q.routeSteps;if(!Array.isArray(route)||route.length<1||route.length>32)fail('One to 32 bounded XY route steps required');
 var cursor={x:q.expectedRaw.X,y:q.expectedRaw.Y},total=0,captures=[];
 route.forEach(function(s,i){object(s,'Route step');if(s.index!==i||!Array.isArray(s.captureReferences))fail('Ordered route step required');var x=finite(s.x,'route X'),y=finite(s.y,'route Y');if(Math.abs(x-Math.round(x*100)/100)>.000001||Math.abs(y-Math.round(y*100)/100)>.000001)fail('Route waypoints must use firmware 0.01 mm reporting grid');var dist=Math.sqrt((x-cursor.x)*(x-cursor.x)+(y-cursor.y)*(y-cursor.y));if(dist<.0001||dist>10.0001)fail('Each native camera step must move 0–10 mm in XY only');if(s.z!==q.expectedRaw.Z||s.a!==q.expectedRaw.A||s.b!==q.expectedRaw.B)fail('Route may not change Z, A or B');total+=dist;cursor={x:x,y:y};s.captureReferences.forEach(function(ref){captures.push(ref);});});
 if(total>120.0001||Math.abs(total-q.plannedDistanceMm)>1e-5)fail('Camera route distance exceeds/reports incorrectly against its bound');
 if(total>120.0001||total>q.maxTotalTravelMm+.0001)fail('Camera route exceeds reviewed travel ceiling');
 if(q.mode==='registered-references'||q.mode==='registered-fiducials'){if(captures.join(',')!==q.references.join(','))fail('Route captures must match selected references in order');route.forEach(function(step){step.captureReferences.forEach(function(ref){var t=q.targets.filter(function(x){return x.reference===ref;})[0];if(!t||Math.abs(step.x-t.x)>.0051||Math.abs(step.y-t.y)>.0051)fail('Reference capture waypoint must equal hash-bound registered target');});});}
 if(q.mode==='reviewed-scrap-camera'){if(route.length){var last=route[route.length-1];if(Math.abs(last.x-310)>.0051||Math.abs(last.y-232.27)>.0051||captures.join(',')!=='scrap')fail('Reviewed scrap route must terminate at the fixed camera target and capture there');for(var j=0;j<route.length-1;j++)if(route[j].captureReferences.length)fail('Scrap frame is permitted only at the fixed route endpoint');}else{if(total!==0||Math.abs(q.expectedRaw.X-310)>.0051||Math.abs(q.expectedRaw.Y-232.27)>.0051||captures.length)fail('Stationary scrap capture requires current camera at the fixed target');}}
 q.plannedDistanceMm=total;return q;
}


function verifySourceReport(source,q){
 object(source,'Source report');var statuses=['completed-contiguous-air-batch-awaiting-observation','completed-contiguous-batch-awaiting-observation','completed-camera-survey-awaiting-image-review'];
 if(statuses.indexOf(source.status)<0||(source.status!=='completed-camera-survey-awaiting-image-review'&&source.motionSubmitted!==true)||(source.motionSubmitted!==true&&source.motionSubmitted!==false)||source.controllerPositionVerified!==true||source.uncertainCompletion!==false||source.transportUncertain===true||source.id!==q.sourceReport.id)fail('Certain terminal source report required');
 var req=source.request||{};if(req.id!==source.id||req.jvmStartMs!==q.jvmStartMs||req.liveConfigurationSha256!==q.liveConfigurationSha256)fail('Source must bind same JVM and live configuration');
 var snap=source.afterQuerySnapshot||{};axes(snap.raw,'Source raw');axes(snap.driver,'Source driver');Object.keys(q.expectedRaw).forEach(function(k){close(snap.raw[k],q.expectedRaw[k],0,'source raw '+k);close(snap.driver[k],q.expectedDriver[k],0,'source driver '+k);});
 object(snap.nativePoses,'Source native poses');['N1','N2','top','bottom'].forEach(function(n){object(snap.nativePoses[n],n+' source pose');['x','y','z','rotation'].forEach(function(k){close(snap.nativePoses[n][k],q.expectedNativePoses[n][k],0,n+' source '+k);});});return true;
}
function verifyCalibrationReport(source,expectedReference){
 object(source,'Fast calibration report');var q=source.request||{};
 if(source.scope!=='camera-only-registered-fast-inspection'||source.status!=='completed-camera-survey-awaiting-image-review'||source.id!==q.id||source.motionSubmitted!==true||source.controllerPositionVerified!==true||source.nativeMotionCompletionReported!==true||source.uncertainCompletion!==false||source.error||source.physicalAcceptanceEstablished!==false||source.calibrationEstablished!==false)fail('Completed fast-camera calibration report required');
 if(q.schema!==1||q.scope!=='camera-only-registered-fast-inspection'||q.enabled!==true||q.mode!=='registered-fiducials'||q.speedFraction!==1||q.speedOverPrecision!==true||q.maxSegmentMm!==10||q.maxTotalTravelMm>120||q.operatorReviewed!==true||!q.reviewedBy||!q.completionScope||q.completionScope.indexOf('Camera frames and XY position reports only')!==0)fail('Fast-camera request policy/mode differs');
 if(expectedReference!==undefined&&(!Array.isArray(q.references)||q.references.length!==1||q.references[0]!==expectedReference))fail('Fast-camera route must bind only the expected reference');
 axes(q.expectedRaw,'Fast-camera requested raw');axes(q.expectedDriver,'Fast-camera requested driver');if(!same(q.expectedRaw,q.expectedDriver))fail('Fast-camera request raw/driver must match');
 var route=q.routeSteps;if(!Array.isArray(route)||route.length<1||route.length>32||!Array.isArray(q.targets)||q.targets.length!==q.references.length)fail('Fast-camera route/target list is invalid');var cursor={X:q.expectedRaw.X,Y:q.expectedRaw.Y},routeDistance=0,captured=[];
 route.forEach(function(s,i){object(s,'Fast-camera route step');if(s.index!==i||!Array.isArray(s.captureReferences))fail('Fast-camera route index/captures differ');var x=finite(s.x,'route X'),y=finite(s.y,'route Y');if(Math.abs(x-Math.round(x*100)/100)>.000001||Math.abs(y-Math.round(y*100)/100)>.000001||s.z!==q.expectedRaw.Z||s.a!==q.expectedRaw.A||s.b!==q.expectedRaw.B)fail('Fast-camera route changed Z/A/B or report-grid XY');var d=Math.sqrt(Math.pow(x-cursor.X,2)+Math.pow(y-cursor.Y,2));if(d<.0001||d>10.0001)fail('Fast-camera route step exceeds 10 mm XY bound');routeDistance+=d;cursor={X:x,Y:y};s.captureReferences.forEach(function(ref){captured.push(ref);});});
 if(routeDistance>120.0001||routeDistance>q.maxTotalTravelMm+.0001||Math.abs(routeDistance-q.plannedDistanceMm)>1e-5||!same(captured,q.references))fail('Fast-camera route total/capture list differs from reviewed request');
 q.references.forEach(function(ref,i){var target=q.targets[i];if(!target||target.reference!==ref||!Array.isArray(target.pads)||target.pads.length!==0)fail('Fast-camera target identity differs');close(target.x,cursor.X,.0051,'Fast-camera target terminal X');close(target.y,cursor.Y,.0051,'Fast-camera target terminal Y');});
 var before=source.beforeQuerySnapshot,after=source.afterQuerySnapshot;object(before,'Fast-camera before query');object(after,'Fast-camera after query');axes(before.raw,'Fast-camera before raw');axes(before.driver,'Fast-camera before driver');axes(after.raw,'Fast-camera after raw');axes(after.driver,'Fast-camera after driver');
 if(!same(before.raw,before.driver)||!same(after.raw,after.driver)||!same(q.expectedRaw,before.raw)||!same(q.expectedDriver,before.driver)||!same(source.beforeReported,before.raw)||!same(source.afterReported,after.raw))fail('Fast-camera raw/driver/M114 endpoint identity differs');
 var last=q.routeSteps.length?q.routeSteps[q.routeSteps.length-1]:null,terminal={X:last?last.x:q.expectedRaw.X,Y:last?last.y:q.expectedRaw.Y,Z:q.expectedRaw.Z,A:q.expectedRaw.A,B:q.expectedRaw.B};if(!same(after.raw,terminal))fail('Fast-camera terminal raw pose differs from bounded route');
 if(['Z','A','B'].some(function(k){return before.raw[k]!==after.raw[k];}))fail('Fast-camera route changed Z/A/B');
 var startPoses=q.expectedNativePoses,endPoses=after.nativePoses;object(startPoses,'Fast-camera initial native poses');object(endPoses,'Fast-camera terminal native poses');var dx=terminal.X-before.raw.X,dy=terminal.Y-before.raw.Y;
 ['N1','N2','top','bottom'].forEach(function(n){var a=startPoses[n],b=endPoses[n];object(a,n+' expected pose');object(b,n+' terminal pose');['x','y','z','rotation'].forEach(function(k){finite(a[k],n+' initial '+k);finite(b[k],n+' terminal '+k);});close(b.x,n==='bottom'?a.x:a.x+dx,.02,n+' terminal X');close(b.y,n==='bottom'?a.y:a.y+dy,.02,n+' terminal Y');close(b.z,a.z,.0001,n+' unchanged Z');close(b.rotation,a.rotation,.0001,n+' unchanged rotation');});
 var statuses=(source.transitions||[]).map(function(x){return x&&x.status;});q.routeSteps.forEach(function(s,i){if(statuses.filter(function(v){return v==='route-step-'+i+'-verified';}).length!==1)fail('Fast-camera route step lacks exactly one verified completion transition');});
 var frames=source.frames,imgs=source.afterImages&&source.afterImages.top;if(!Array.isArray(frames)||frames.length!==q.references.length||!imgs)fail('Fast-camera captured frame list differs from its request');
 frames.forEach(function(f){if(q.references.indexOf(f.reference)<0||!f.path||f.path!==imgs.path||!same(f.rawAxes,after.raw)||!same(f.nativePose,endPoses.top)||f.width!==imgs.width||f.height!==imgs.height)fail('Fast-camera frame/report terminal pose identity differs');});
 var captured=[];q.routeSteps.forEach(function(s){(s.captureReferences||[]).forEach(function(r){captured.push(r);});});if(!same(captured,q.references)||!same(frames.map(function(f){return f.reference;}),q.references))fail('Fast-camera reference capture order differs');return true;
}
function verifyStep(q,before,step,model,reported){
 object(before,'Before step');object(model,'After model');object(reported,'After M114');axes(model.raw,'After model raw');axes(model.driver,'After model driver');
 var dx=finite(step.x,'step X')-finite(before.raw.X,'before X'),dy=finite(step.y,'step Y')-finite(before.raw.Y,'before Y');
 close(model.raw.X,step.x,.02,'model X');close(model.raw.Y,step.y,.02,'model Y');close(model.raw.Z,q.expectedRaw.Z,.02,'model Z');close(model.raw.A,q.expectedRaw.A,.3,'model A');close(model.raw.B,q.expectedRaw.B,.3,'model B');Object.keys(model.raw).forEach(function(k){close(model.driver[k],model.raw[k],.0001,'model driver '+k);});
 close(reported.X,step.x,.02,'M114 X');close(reported.Y,step.y,.02,'M114 Y');close(reported.Z,q.expectedRaw.Z,.02,'M114 Z');close(reported.A,q.expectedRaw.A,.3,'M114 A');close(reported.B,q.expectedRaw.B,.3,'M114 B');
 Object.keys(q.expectedNativePoses).forEach(function(n){var a=before.nativePoses[n],b=model.nativePoses[n];object(a,'before '+n);object(b,'after '+n);if(n==='bottom'){close(b.x,a.x,.0001,n+' fixed X');close(b.y,a.y,.0001,n+' fixed Y');}else{close(b.x,a.x+dx,.02,n+' expected X');close(b.y,a.y+dy,.02,n+' expected Y');}close(b.z,a.z,.0001,n+' unchanged Z');close(b.rotation,a.rotation,.0001,n+' unchanged rotation');});return true;
}

function executeRoute(q,adapter){
 object(adapter,'Route adapter');if(typeof adapter.snapshot!=='function'||typeof adapter.move!=='function'||typeof adapter.query!=='function')fail('Route adapter needs snapshot, move and query');
 var cursor={X:q.expectedRaw.X,Y:q.expectedRaw.Y},result=[];
 for(var i=0;i<q.routeSteps.length;i++){
  var step=q.routeSteps[i],before=adapter.snapshot();object(before,'Before step '+i);
  Object.keys(q.expectedRaw).forEach(function(k){var want=(k==='X'?cursor.X:k==='Y'?cursor.Y:q.expectedRaw[k]);close(before.raw[k],want,0,'route cursor '+k);close(before.driver[k],before.raw[k],0,'route driver '+k);});
  if(adapter.beforeMove)adapter.beforeMove(step,i,before);
  adapter.move(step,i);var model=adapter.snapshot(),reported=adapter.query();verifyStep(q,before,step,model,reported);
  cursor={X:step.x,Y:step.y};result.push({step:step,index:i,model:model,reported:reported});
  if(adapter.afterStep)adapter.afterStep(step,i,model,reported);
 }
 return result;
}
function installationPolicy(policy,installationLock,action){
 object(policy,'Camera inspection policy');object(installationLock,'Installation lock');
 if(policy.schema!==1||policy.scope!=='camera-only-inspection-under-paste-installation-lock'||policy.enabled!==true||policy.action!==action||action!=='paste-fast-camera-inspection')fail('Dedicated camera inspection policy rejects action');
 if(installationLock.schema!==1||typeof installationLock.locked!=='boolean')fail('Main installation lock missing or malformed');
 if(policy.requiresInstallationLockPreserved!==true||policy.noPasteActuation!==true||policy.topCameraXYOnly!==true||policy.n2Quarantined!==true)fail('Camera inspection may not relax paste installation restrictions');
 return true;
}
var api={validate:validate,verifyStep:verifyStep,verifySourceReport:verifySourceReport,verifyCalibrationReport:verifyCalibrationReport,executeRoute:executeRoute,installationPolicy:installationPolicy};if(typeof module!=='undefined')module.exports=api;else root.PasteFastCameraInspection=api;
})(this);
