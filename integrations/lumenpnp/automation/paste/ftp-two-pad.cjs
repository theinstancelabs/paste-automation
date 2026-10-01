'use strict';
// Pure, narrowly scoped FTP demo target policy. readEvidence is supplied by the
// caller and MUST verify file SHA-256 before returning JSON or image bytes.
(function(root){
var fail=function(s){throw Error(s);},hash=/^[a-f0-9]{64}$/;
function number(v,label){if(typeof v!=='number'||!isFinite(v))fail(label+' must be finite');return v;}
function evidence(e){if(!e||typeof e.path!=='string'||e.path.charAt(0)!=='/'||!hash.test(e.sha256))fail('FTP evidence path/hash required');return e;}
function same(a,b){if(a===b)return true;if(!a||!b||typeof a!=='object'||typeof b!=='object'||Array.isArray(a)!==Array.isArray(b))return false;var ak=Object.keys(a).sort(),bk=Object.keys(b).sort();return JSON.stringify(ak)===JSON.stringify(bk)&&ak.every(function(k){return same(a[k],b[k]);});}
function close(a,b,label){if(Math.abs(number(a,label)-Math.round(number(b,label)*100)/100)>1e-9)fail(label+' differs from registered target');}
function scope(preview){return 'contiguous-native-ftp-two-pad'+(preview?'-preview':'');}
function isFtp(q){return q&&(q.scope===scope(false)||q.scope===scope(true));}
function integer(v,lo,hi,label){if(Math.floor(number(v,label))!==v||v<lo||v>hi)fail(label+' outside reviewed integer range');return v;}
function entryTime(q,now){var c=q.ftpTargetRecord&&q.ftpTargetRecord.compensatedSequence;if(!c)return;var elapsed=number(now,'entry time')-number(c.conditioningFinishedMs,'conditioning finish');if(elapsed<0||elapsed>integer(c.maximumElapsedMilliseconds,1,300000,'conditioning elapsed limit'))fail('FTP conditioning entry state expired');}
function compensated(q,t,now){
 var c=t.compensatedSequence;if(c===undefined)return null;if(!c)fail('Explicit compensated FTP object required');
 if(q.mode!=='wet'||c.schema!==1||c.protocol!=='restore-dose-retract-lift-two-pad'||[2,3,4,6,12,20].indexOf(c.doseDegrees)<0||[2,3,4,6].indexOf(c.retractDegrees)<0)fail('Unknown compensated FTP protocol/amount');
 integer(c.dwellMilliseconds,0,2000,'FTP dose dwell');entryTime(q,now);
 ['conditioningReportEvidence','conditioningLedgerEvidence','preparationExperimentEvidence','tipObservationEvidence'].forEach(function(k){evidence(c[k]);});
 if(!same(c.conditioningReportEvidence,q.previousReportEvidence)||c.conditioningLedgerEvidence.sha256!==q.previousLedgerSha256)fail('FTP conditioning must be exact preceding charged report/ledger');
 var covered={},last=-1;
 function at(i,axis){integer(i,0,q.previewStages.length-1,'FTP stage index');var st=q.previewStages[i];if(st.axis!==axis||covered[i])fail('FTP stage axis/duplicate index');covered[i]=true;return st;}
 function b(i,delta,p,dwell){var st=at(i,'B');if(st.targetRaw.B-st.startRaw.B!==delta||(st.dwellMilliseconds||0)!==dwell)fail('FTP compensated amount/dwell differs');['X','Y','Z','A'].forEach(function(k){if(st.startRaw[k]!==p[k]||st.targetRaw[k]!==p[k])fail('FTP compensated pose differs');});var gap=t.surface.estimatedGapMm+t.surface.rawZ-p.Z;if(!same(st.gapEvidence,t.surfaceEvidence)||st.estimatedGapMm!==gap||st.gapUncertaintyMm!==t.surface.gapUncertaintyMm)fail('FTP compensated gap differs');}
 t.pads.forEach(function(p){
  if(p.doseStageIndex!==undefined)fail('Compensated FTP uses explicit doseStageIndices only');
  var ds=p.doseStageIndices,count=c.doseDegrees===12?2:1;
  if(!Array.isArray(ds)||ds.length!==count||p.restoreStageIndex<=last)fail('FTP ordered dose group required');
  b(p.restoreStageIndex,-c.retractDegrees,p.rawPose,0);
  ds.forEach(function(i,n){if(i!==p.restoreStageIndex+1+n)fail('FTP dose stages must immediately follow restore');b(i,c.doseDegrees===12?-6:-c.doseDegrees,p.rawPose,n===count-1?c.dwellMilliseconds:0);});
  if(p.retractStageIndex!==ds[count-1]+1||p.liftStageIndex!==p.retractStageIndex+1)fail('FTP immediate retract and lift required');
  b(p.retractStageIndex,c.retractDegrees,p.rawPose,0);var lift=at(p.liftStageIndex,'Z');if(lift.startRaw.Z!==t.surface.rawZ||lift.targetRaw.Z!==q.xyClearanceRawZ)fail('FTP lift must reach common clearance');last=p.liftStageIndex;
 });
 if(c.finalIdleStageIndex!==last+1||c.finalIdleStageIndex!==q.previewStages.length-1)fail('FTP final idle must immediately follow second lift and end route');
 var final=q.previewStages[c.finalIdleStageIndex];b(c.finalIdleStageIndex,20,{X:final.startRaw.X,Y:final.startRaw.Y,Z:q.xyClearanceRawZ,A:q.expectedRaw.A},2000);
 q.previewStages.forEach(function(st,i){if(st.axis==='B'&&!covered[i])fail('FTP unaccounted B stage');});return covered;
}
function verifyConditioning(q,read){
 var t=q.ftpTargetRecord,c=t.compensatedSequence;if(!c)return;
 var r=read(c.conditioningReportEvidence,true),l=read(c.conditioningLedgerEvidence,true),e=read(c.preparationExperimentEvidence,true),o=read(c.tipObservationEvidence,true),rq=r&&r.request;
 if(!rq||r.status!=='completed-contiguous-batch-awaiting-observation'||r.controllerPositionVerified!==true||r.uncertainCompletion!==false||r.id!==rq.id||rq.scope!=='contiguous-native-scrap-batch'||rq.mode!=='wet'||rq.sessionId!==q.sessionId||rq.syringeId!==q.syringeId||rq.jvmStartMs!==q.jvmStartMs||rq.liveConfigurationSha256!==q.liveConfigurationSha256||r.completedLedgerSha256!==q.previousLedgerSha256)fail('Verified same-session scrap conditioning report required');
 if(!isFinite(Date.parse(r.finishedAt))||Date.parse(r.finishedAt)<c.conditioningFinishedMs||!l||l.status!=='verified'||l.sessionId!==q.sessionId||l.syringeId!==q.syringeId||l.lastVerifiedB!==q.expectedRaw.B||!r.afterQuerySnapshot||r.afterQuerySnapshot.raw.B!==q.expectedRaw.B)fail('FTP conditioning terminal B/ledger/time differs');
 if(!e||e.schema!==1||e.scope!=='reviewed-scrap-retraction-coupon'||e.mode!=='transfer-preparation'||e.retractDegrees!==c.retractDegrees||e.maximumTransferElapsedMilliseconds!==c.maximumElapsedMilliseconds||e.conditioningDoseDegrees!==20)fail('Explicit transfer-preparation experiment required');
 var review=read(evidence(rq.clearanceReviewEvidence),true);if(!same(review.experimentEvidence,c.preparationExperimentEvidence))fail('Conditioning review does not bind preparation experiment');
 var stages=rq.previewStages,done=r.stages;if(!Array.isArray(stages)||stages.length<3||!Array.isArray(done)||done.length!==stages.length)fail('Complete conditioning stage history required');
 stages.forEach(function(s,i){var d=done[i];if(!d||d.index!==i||d.verified!==true||d.axis!==s.axis||!same(d.startRaw,s.startRaw)||!same(d.targetRaw,s.targetRaw))fail('Unverified conditioning stage');});
 var n=stages.length;if(Date.parse(done[n-2].finishedAt)!==c.conditioningFinishedMs)fail('Conditioning clock must start at verified retraction');var dose=stages[n-3],retract=stages[n-2],lift=stages[n-1];
 if(dose.axis!=='B'||dose.targetRaw.B-dose.startRaw.B!==-20||dose.startRaw.Z!==e.workRawZ||(dose.dwellMilliseconds||0)!==(e.conditioningDwellMilliseconds===undefined?(e.dwellMilliseconds===undefined?2000:e.dwellMilliseconds):e.conditioningDwellMilliseconds)||retract.axis!=='B'||retract.targetRaw.B-retract.startRaw.B!==c.retractDegrees||(retract.dwellMilliseconds||0)!==0||lift.axis!=='Z'||lift.targetRaw.Z!==e.clearanceRawZ||!same(dose.targetRaw,retract.startRaw)||!same(retract.targetRaw,lift.startRaw)||!same(lift.targetRaw,rq.finalTargetRaw)||!same(lift.targetRaw,r.afterQuerySnapshot.raw)||lift.targetRaw.B!==q.expectedRaw.B)fail('Conditioning must end with dose, selected retract, lift and no idle relief');
 var tail=l.entries&&l.entries[l.entries.length-1];if(!tail||tail.status!=='verified'||tail.batchId!==r.id||tail.stageIndex!==n-2||tail.targetB!==q.expectedRaw.B||tail.deltaDegrees!==c.retractDegrees)fail('Conditioning is not the current charged ledger tail');
 if(!o||o.noLongStrand!==true||typeof o.reviewedBy!=='string'||!o.reviewedBy.trim()||!same(o.conditioningReportEvidence,c.conditioningReportEvidence)||integer(o.reviewedMs,c.conditioningFinishedMs,t.reviewedMs,'tip observation time')!==o.reviewedMs||integer(o.capturedMs,c.conditioningFinishedMs,o.reviewedMs,'tip capture time')!==o.capturedMs)fail('Fresh authored tip observation required');read(evidence(o.imageEvidence),false);
}
function validate(q,now){
 var t=q.ftpTargetRecord;if(!t||t.schema!==1||t.scope!=='ftp-two-pad-commissioning-targets'||typeof t.boardId!=='string'||!t.boardId.trim())fail('Explicit FTP board identity/target record required');
 evidence(q.ftpTargetEvidence);if(t.quantizationMm!==0.01)fail('FTP targets must explicitly use the 0.01 mm report grid');
 if(t.sessionId!==q.sessionId||t.jvmStartMs!==q.jvmStartMs||t.liveConfigurationSha256!==q.liveConfigurationSha256)fail('FTP session/configuration mismatch');
 if(typeof t.reviewedBy!=='string'||!t.reviewedBy.trim()||Math.floor(number(t.reviewedMs,'FTP review time'))!==t.reviewedMs||t.reviewedMs>now||now-t.reviewedMs>300000)fail('Fresh explicitly authored FTP review required');
 if(t.boardCleaned!==true||t.padsAvailable!==true||t.boardUnmovedSinceRegistration!==true||t.provenance!=='commissioning-provisional'||t.precisionCalibrated!==false||t.flowCalibrated!==false)fail('Explicit cleaned/unmoved/available FTP attestations and provisional status required');
 evidence(t.cadEvidence);evidence(t.registrationEvidence);evidence(t.tipOffsetEvidence);evidence(t.surfaceEvidence);evidence(t.padAvailabilityImage);
 if(!Array.isArray(t.cameraMinusTipXYMm)||t.cameraMinusTipXYMm.length!==2)fail('Explicit parent-chosen provisional tip offset required');t.cameraMinusTipXYMm.forEach(function(x){number(x,'tip offset');});
 var s=t.surface;if(!s||number(s.rawZ,'FTP dispense Z')<=q.xyClearanceRawZ||number(s.estimatedGapMm,'FTP gap')<=0||number(s.gapUncertaintyMm,'FTP uncertainty')<0||s.estimatedGapMm-s.gapUncertaintyMm<0.1)fail('FTP board-specific positive gap required');
 if(!Array.isArray(t.padChecks)||t.padChecks.length!==3||t.padChecks.map(function(c){return c.reference;}).sort().join(',')!=='R1,R16,R40')fail('Three distant FTP pad checks required');
 t.padChecks.forEach(function(c){if(c.reviewedAligned!==true||!new RegExp('^'+c.reference+'\\.[12]$').test(c.padId))fail('Explicit reviewed distant-pad identity required');evidence(c.reportEvidence);evidence(c.imageEvidence);});
 if(!Array.isArray(t.pads)||t.pads.length!==2)fail('Exactly two FTP pads required');
 var ids={},ref=null,indices={};t.pads.forEach(function(p){var m=/^(R(?:[1-9]|[1-3][0-9]|40))\.([12])$/.exec(p.padId);if(!m||ids[p.padId]||ref&&m[1]!==ref)fail('Two unique pads of the same resistor required');ids[p.padId]=true;ref=m[1];
  if(!p.rawPose)fail('FTP pad pose required');['X','Y','Z','A'].forEach(function(k){number(p.rawPose[k],'pad '+k);});
  if(['X','Y','Z'].some(function(k){return Math.abs(p.rawPose[k]-Math.round(p.rawPose[k]*100)/100)>1e-9;}))fail('FTP raw target must be on the 0.01 mm report grid');
  if(p.rawPose.Z!==s.rawZ||p.rawPose.A!==q.expectedRaw.A)fail('FTP target Z/A differs');
  if(q.mode==='wet'&&!t.compensatedSequence){var i=number(p.doseStageIndex,'dose stage');if(Math.floor(i)!==i||i<0||i>=q.previewStages.length||indices[i])fail('Unique FTP dose stage indices required');indices[i]=p;}
  else if(q.mode==='air'&&p.doseStageIndex!==null)fail('Air FTP record must not map a B dose stage');
 });
 if(q.rawBounds.Z.max>s.rawZ)fail('FTP route exceeds reviewed board dispense Z');
 var coverage=compensated(q,t,now);
 var doses=0;q.previewStages.forEach(function(st,i){if(st.wipeReview===true||((st.axis==='X'||st.axis==='Y')&&st.startRaw.Z!==q.xyClearanceRawZ))fail('FTP branch forbids low XY/wipe');
  if(coverage)return;
  if(st.axis==='B'&&st.targetRaw.B>=st.startRaw.B)fail('FTP permits only its two negative B dose stages');
  if(st.axis==='B'&&st.targetRaw.B<st.startRaw.B){var p=indices[i];if(!p)fail('Negative B outside the two FTP dose stages');['X','Y','Z','A'].forEach(function(k){if(st.startRaw[k]!==p.rawPose[k]||st.targetRaw[k]!==p.rawPose[k])fail('FTP dose pose differs from target record');});if(!same(st.gapEvidence,t.surfaceEvidence)||st.estimatedGapMm!==s.estimatedGapMm||st.gapUncertaintyMm!==s.gapUncertaintyMm)fail('FTP dose gap differs from board evidence');doses++;}
 });
 if(q.mode==='wet'&&!coverage&&doses!==2)fail('Exactly one negative B dose per FTP pad required');
 return t;
}
function verifySources(q,readEvidence){
 var t=q.ftpTargetRecord,actual=readEvidence(evidence(q.ftpTargetEvidence),true);if(!same(actual,t))fail('FTP target record bytes/content differ');
 var reg=readEvidence(t.registrationEvidence,true);readEvidence(t.cadEvidence,false);readEvidence(t.padAvailabilityImage,false);
 if(!reg||reg.scope!=='offline-fresh-ftp-two-fiducial-transform-with-third-point-check'||!reg.acceptance||reg.acceptance.passed!==true||!same(reg.board,t.cadEvidence)||!reg.session||reg.session.jvmStartMs!==q.jvmStartMs||reg.session.liveConfigurationSha256!==q.liveConfigurationSha256||!reg.independentFID3Check||number(reg.independentFID3Check.residualMm,'FID3 residual')<0||reg.independentFID3Check.residualMm>0.08)fail('Accepted same-session three-fiducial registration required');
 function observation(report,ev,image){
  if(!report||report.controllerPositionVerified!==true||report.uncertainCompletion!==false||['completed-camera-survey-awaiting-image-review','completed-contiguous-air-batch-awaiting-observation'].indexOf(report.status)<0||!report.request||report.request.jvmStartMs!==q.jvmStartMs||report.request.liveConfigurationSha256!==q.liveConfigurationSha256)fail('FTP camera evidence session/completion mismatch');
  var finished=Date.parse(report.finishedAt);if(!isFinite(finished)||finished>t.reviewedMs||t.reviewedMs-finished>3600000)fail('FTP registration/pad checks must be reviewed within one hour');
  var top=report.afterImages&&report.afterImages.top;if(!top||image.path!==ev.path.slice(0,ev.path.lastIndexOf('/')+1)+top.path)fail('FTP image must belong to its camera report');readEvidence(image,false);
 }
 ['FID1','FID2','FID3'].forEach(function(k){var m=reg.measurements&&reg.measurements[k];if(!m||number(m.imageCenterErrorPx,'fiducial centering')<0||m.imageCenterErrorPx>2)fail('Reviewed three centered fiducials required');observation(readEvidence(evidence(m.report),true),m.report,evidence(m.image));});
 var registered={};if(!Array.isArray(reg.resistorPadMachineXYTargets)||reg.resistorPadMachineXYTargets.length!==80)fail('FTP registration must contain 80 pad targets');reg.resistorPadMachineXYTargets.forEach(function(p){if(registered[p.padId])fail('Duplicate registered pad');registered[p.padId]=p;});
 t.padChecks.forEach(function(c){var report=readEvidence(c.reportEvidence,true);observation(report,c.reportEvidence,c.imageEvidence);var p=registered[c.padId],cam=report.afterQuerySnapshot&&report.afterQuerySnapshot.nativePoses&&report.afterQuerySnapshot.nativePoses.top;if(!p||!cam||Math.sqrt(Math.pow(number(cam.x,'check camera X')-number(p.machineXYMm[0],'registered X'),2)+Math.pow(number(cam.y,'check camera Y')-number(p.machineXYMm[1],'registered Y'),2))>0.1)fail('Distant-pad camera location differs from registration');});
 var off=readEvidence(t.tipOffsetEvidence,true),surf=readEvidence(t.surfaceEvidence,true);
 [off,surf].forEach(function(v){if(!v||v.boardId!==t.boardId||v.provenance!=='commissioning-provisional'||v.precisionCalibrated!==false||v.jvmStartMs!==q.jvmStartMs||v.liveConfigurationSha256!==q.liveConfigurationSha256||typeof v.reviewedBy!=='string'||!v.reviewedBy.trim())fail('Explicit provisional board/tip evidence required');});
 readEvidence(evidence(off.basisEvidence),false);readEvidence(evidence(surf.basisEvidence),false);
 if(!same(off.cameraMinusTipXYMm,t.cameraMinusTipXYMm)||!same(surf.surface,t.surface))fail('Selected tip offset or Z/gap differs from authored evidence');
 t.pads.forEach(function(p){var rp=registered[p.padId];if(!rp)fail('FTP pad missing from registration');close(p.rawPose.X,rp.machineXYMm[0]-t.cameraMinusTipXYMm[0],'registered head X');close(p.rawPose.Y,rp.machineXYMm[1]-t.cameraMinusTipXYMm[1],'registered head Y');});
 verifyConditioning(q,readEvidence);
 return t;
}
var api={entryTime:entryTime,scope:scope,isFtp:isFtp,validate:validate,verifySources:verifySources,same:same};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.PasteFtpTwoPad=api;
})(this);
